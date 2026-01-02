import os
import json
import time
import uuid
import base64
import threading
import requests
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, session
import google.generativeai as genai

app = Flask(__name__)

# --- Gemini API Configuration ---
GEMINI_API_KEY = "AIzaSyB_mMNJpXvWf2haPw5Gz6KTNlQmIaRQhEs"
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-2.5-flash')
app.secret_key = 'nano-banana-pro-secret-key-2024'  # Session için secret key
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Global State ---
STATE = {
    "accounts": [],       # {email, password} listesi
    "current_account_index": 0,
    "current_token": None,
    "active_quota": "Bilinmiyor", 
    "tasks": {},          # task_id -> {status, log, image_url, params, created_at, api_task_id}
    "favorites": [],      # [{"image_url": "...", "prompt": "...", "params": {...}}]
    "prompts": []         # [{"title": "...", "text": "..."}]
}

ACCOUNTS_FILE = 'accounts.txt'
accounts_lock = threading.Lock()

# --- API Constants ---
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.ewogICJyb2xlIjogImFub24iLAogICJpc3MiOiAic3VwYWJhc2UiLAogICJpYXQiOiAxNzM0OTY5NjAwLAogICJleHAiOiAxODkyNzM2MDAwCn0.4NnK23LGYvKPGuKI5rwQn2KbLMzzdE4jXpHwbGCqPqY"
URL_AUTH = "https://sp.deevid.ai/auth/v1/token?grant_type=password"
URL_UPLOAD = "https://api.deevid.ai/file-upload/image"
URL_SUBMIT = "https://api.deevid.ai/text-to-image/task/submit"
URL_ASSETS = "https://api.deevid.ai/my-assets?limit=50&assetType=All&filter=CREATION"
URL_QUOTA = "https://api.deevid.ai/subscription/plan"

# --- Account File Management ---

def load_accounts_from_file():
    """Disk'teki accounts.txt'den hesapları yükler."""
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    accs = []
    try:
        with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if ':' in line:
                    parts = line.split(':')
                    accs.append({'email': parts[0], 'password': parts[1]})
    except Exception as e:
        print(f"Dosya okuma hatası: {e}")
    return accs

def save_accounts_to_file(accounts_list):
    """Verilen listeyi accounts.txt'ye yazar (Overwrite)."""
    with accounts_lock:
        try:
            with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
                for acc in accounts_list:
                    f.write(f"{acc['email']}:{acc['password']}\n")
        except Exception as e:
            print(f"Dosya yazma hatası: {e}")

def append_accounts_to_file(new_accounts):
    """Mevcut hesaplara yenilerini ekler ve dosyayı günceller."""
    current_accs = STATE['accounts']
    existing_emails = {a['email'] for a in current_accs}
    
    added_count = 0
    for acc in new_accounts:
        if acc['email'] not in existing_emails:
            current_accs.append(acc)
            added_count += 1
    
    if added_count > 0:
        save_accounts_to_file(current_accs)
        STATE['accounts'] = current_accs
    
    return added_count

def remove_current_account_permanently():
    """Şu anki aktif hesabı listeden ve dosyadan siler."""
    if not STATE['accounts']:
        return
    
    idx = STATE['current_account_index'] % len(STATE['accounts'])
    removed_email = STATE['accounts'][idx]['email']
    
    print(f"!!! Hesap Siliniyor: {removed_email}")
    
    # Listeden çıkar
    STATE['accounts'].pop(idx)
    
    # Dosyayı güncelle
    save_accounts_to_file(STATE['accounts'])
    
    if STATE['accounts']:
        STATE['current_account_index'] = STATE['current_account_index'] % len(STATE['accounts'])
    else:
        STATE['current_account_index'] = 0
        
    STATE['current_token'] = None
    STATE['active_quota'] = "Hesap Silindi"

STATE['accounts'] = load_accounts_from_file()

# --- Helper Functions ---

def get_current_account():
    if not STATE['accounts']:
        return None
    idx = STATE['current_account_index'] % len(STATE['accounts'])
    return STATE['accounts'][idx]

def rotate_account(delete_current=False):
    if not STATE['accounts']:
        return False
    
    if delete_current:
        remove_current_account_permanently()
        if not STATE['accounts']:
            return False
        STATE['current_token'] = None
        STATE['active_quota'] = "Hesaplanıyor..."
        return True
    else:
        prev_email = get_current_account()['email']
        STATE['current_account_index'] = (STATE['current_account_index'] + 1) % len(STATE['accounts'])
        STATE['current_token'] = None
        STATE['active_quota'] = "Hesaplanıyor..."
        new_email = get_current_account()['email']
        print(f"!!! Hesap Değiştiriliyor (Silinmedi): {prev_email} -> {new_email}")
        return True

def login_and_get_token():
    if STATE['current_token']:
        return STATE['current_token']

    account = get_current_account()
    if not account:
        raise Exception("Yüklü hesap kalmadı!")

    headers = {"apikey": API_KEY}
    payload = {
        "email": account['email'],
        "password": account['password'],
        "gotrue_meta_security": {}
    }

    try:
        response = requests.post(URL_AUTH, json=payload, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Login failed: {response.text}")
        
        data = response.json()
        token = data.get('access_token')
        STATE['current_token'] = token
        
        refresh_quota(token)
        return token
    except Exception as e:
        print(f"Login hatası ({account['email']}): {e}")
        if rotate_account(delete_current=False): 
            return login_and_get_token()
        else:
            raise Exception("Tüm hesaplar denendi, giriş yapılamadı.")

def refresh_quota(token):
    headers = {"authorization": "Bearer " + token}
    try:
        resp = requests.get(URL_QUOTA, headers=headers)
        data = resp.json()['data']['data']['message_quota']
        quota_total = data['quota_count']
        quota_used = data['subscription_quota_used']
        remaining = quota_total - quota_used
        STATE['active_quota'] = remaining
        return remaining
    except Exception as e:
        print(f"Kota çekme hatası: {e}")
        return 0

def process_task_thread(task_id, file_paths, form_data):
    if task_id not in STATE['tasks']: return

    log_msg = lambda m: STATE['tasks'][task_id]['logs'].append(m) if task_id in STATE['tasks'] else None
    
    if task_id in STATE['tasks']:
        STATE['tasks'][task_id]['status'] = 'running'
    
    mode = "Text-to-Image" if not file_paths else "Image-to-Image"
    log_msg(f"Mod: {mode} başlatılıyor...")

    try:
        token = login_and_get_token()
        user_image_ids = []

        # Upload Logic (Multiple Files)
        if file_paths:
            log_msg(f"{len(file_paths)} görsel yükleniyor...")
            upload_headers = {"Authorization": "Bearer " + token}
            
            for f_path in file_paths:
                if task_id not in STATE['tasks']: return
                try:
                    with open(f_path, "rb") as f:
                        files = {"file": (os.path.basename(f_path), f, "image/png")}
                        upload_data = {"width": "1024", "height": "1536"}
                        resp_upload = requests.post(URL_UPLOAD, headers=upload_headers, files=files, data=upload_data)
                    
                    if resp_upload.status_code in [200, 201]:
                        uid = resp_upload.json()['data']['data']['id']
                        user_image_ids.append(uid)
                    else:
                        log_msg(f"Upload hatası ({os.path.basename(f_path)}): {resp_upload.status_code}")
                except Exception as ex:
                    log_msg(f"Dosya okuma hatası: {str(ex)}")

            if not user_image_ids:
                log_msg("Hiçbir görsel yüklenemedi.")
                if task_id in STATE['tasks']: STATE['tasks'][task_id]['status'] = 'failed'
                return
            
            log_msg(f"{len(user_image_ids)} görsel yüklendi.")

        target_api_task_id = None

        # Submit Loop
        while True:
            if task_id not in STATE['tasks']: return 
            
            acc = get_current_account()
            if not acc:
                log_msg("Hesap kalmadı!")
                if task_id in STATE['tasks']: STATE['tasks'][task_id]['status'] = 'failed'
                return

            log_msg(f"Görev gönderiliyor... ({acc['email']})")
            submit_headers = {"Authorization": "Bearer " + token}
            
            # Model sabitleme
            MODEL_TYPE = "MODEL_FOUR"
            
            payload = {
                "prompt": form_data.get('prompt', 'odada oturuyor olsun.'),
                "imageSize": form_data.get('image_size'),
                "count": 1,
                "resolution": form_data.get('resolution'),
                "modelType": MODEL_TYPE,
                "modelVersion": form_data.get('model_version')
            }
            
            # Eğer resim varsa ID'leri ekle
            if user_image_ids:
                payload["userImageIds"] = user_image_ids

            resp_submit = requests.post(URL_SUBMIT, headers=submit_headers, json=payload)
            resp_json = resp_submit.json()

            current_q = refresh_quota(token)
            
            error_code = 0
            if 'error' in resp_json and resp_json['error']:
                 error_code = resp_json['error'].get('code', 0)

            if error_code != 0:
                log_msg(f"HATA! Code: {error_code}. Kota: {current_q}")
                
                safe_quota = current_q if isinstance(current_q, int) else 0
                should_switch_and_delete = False

                if safe_quota <= 0:
                    should_switch_and_delete = True
                    log_msg("Kota 0, hesap siliniyor ve geçiliyor...")
                else:
                    log_msg(f"Kota ({safe_quota}) var ama hata. Onay bekleniyor...")
                    if task_id in STATE['tasks']:
                        STATE['tasks'][task_id]['status'] = 'waiting_confirmation'
                    
                    wait_start = time.time()
                    user_response = None
                    while time.time() - wait_start < 300:
                        if task_id not in STATE['tasks']: return 
                        
                        status_now = STATE['tasks'][task_id]['status']
                        if status_now == 'resume_approved':
                            user_response = 'yes'
                            break
                        elif status_now == 'resume_rejected':
                            user_response = 'no'
                            break
                        time.sleep(1)
                    
                    if user_response == 'yes':
                        should_switch_and_delete = True
                        if task_id in STATE['tasks']: STATE['tasks'][task_id]['status'] = 'running'
                    else:
                        log_msg("İptal edildi.")
                        if task_id in STATE['tasks']: STATE['tasks'][task_id]['status'] = 'failed'
                        return

                if should_switch_and_delete:
                    if rotate_account(delete_current=True):
                        token = login_and_get_token()
                        continue
                    else:
                        log_msg("Başka hesap kalmadı.")
                        if task_id in STATE['tasks']: STATE['tasks'][task_id]['status'] = 'failed'
                        return
            else:
                try:
                    target_api_task_id = resp_json['data']['data']['taskId']
                    log_msg(f"ID: {target_api_task_id}")
                except:
                    log_msg("ID parse hatası.")
                break

        # Polling
        attempt = 0
        while attempt < 600:
            if task_id not in STATE['tasks']: return
            attempt += 1
            time.sleep(2)
            try:
                poll_resp = requests.get(URL_ASSETS, headers={"authorization": "Bearer " + token}).json()
                groups = poll_resp.get("data", {}).get("data", {}).get("groups", [])
                
                found_match = False
                for group in groups:
                    for item in group.get("items", []):
                        creation = item.get("detail", {}).get("creation", {})
                        if target_api_task_id and creation.get("taskId") == target_api_task_id:
                            found_match = True
                            task_state = creation.get("taskState")
                            if task_state == 'FAIL':
                                log_msg("API: Başarısız.")
                                STATE['tasks'][task_id]['status'] = 'failed'
                                refresh_quota(token)
                                return
                            image_urls = creation.get("noWaterMarkImageUrl", [])
                            if image_urls:
                                STATE['tasks'][task_id]['image_url'] = image_urls[0]
                                STATE['tasks'][task_id]['status'] = 'completed'
                                log_msg("Tamamlandı!")
                                refresh_quota(token)
                                return
                if not found_match: pass
            except Exception as e: pass
            
        log_msg("Zaman aşımı.")
        STATE['tasks'][task_id]['status'] = 'failed'
        refresh_quota(token)

    except Exception as e:
        log_msg(f"Kritik Hata: {str(e)}")
        if task_id in STATE['tasks']: STATE['tasks'][task_id]['status'] = 'failed'

# --- Routes ---

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    
    if username == 'admin' and password == '123':
        session['logged_in'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Kullanıcı adı veya şifre yanlış!'})

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/check_session')
def check_session():
    return jsonify({'logged_in': session.get('logged_in', False)})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_accounts', methods=['POST'])
def upload_accounts():
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya yok'}), 400
    file = request.files['file']
    new_accounts = []
    try:
        content = file.read().decode('utf-8').splitlines()
        for line in content:
            parts = line.strip().split(':')
            if len(parts) >= 2:
                new_accounts.append({'email': parts[0], 'password': parts[1]})
        
        added = append_accounts_to_file(new_accounts)
        if not STATE['current_token'] and STATE['accounts']:
            STATE['current_account_index'] = 0
            STATE['active_quota'] = "Giriş Bekleniyor"

        return jsonify({'count': len(STATE['accounts']), 'added': added, 'message': f'{added} yeni hesap eklendi.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/create_task', methods=['POST'])
def create_task():
    if not STATE['accounts']:
        return jsonify({'error': 'Önce hesapları yükleyin!'}), 400
    form_data = request.form.to_dict()
    
    # Çoklu dosya desteği
    files = request.files.getlist('files[]')
    file_paths = []
    
    # Dosya var mı diye kontrol et (varsa Image2Image, yoksa Text2Image)
    if files and files[0].filename != '':
        for file in files:
            safe_name = f"{uuid.uuid4()}_{file.filename}"
            path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
            file.save(path)
            file_paths.append(path)
    
    task_id = str(uuid.uuid4())
    
    STATE['tasks'][task_id] = {
        'id': task_id,
        'status': 'pending',
        'logs': [],
        'image_url': None,
        'params': form_data,
        'created_at': time.time(),
        'mode': 'Image-to-Image' if file_paths else 'Text-to-Image'
    }
    
    thread = threading.Thread(target=process_task_thread, args=(task_id, file_paths, form_data))
    thread.daemon = True
    thread.start()
    
    return jsonify({'task_id': task_id, 'message': 'İşlem başlatıldı'})

@app.route('/status')
def get_status():
    sorted_tasks = sorted(STATE['tasks'].values(), key=lambda x: x['created_at'], reverse=True)
    current_acc = "Yok"
    if STATE['accounts']:
        idx = STATE['current_account_index'] % len(STATE['accounts'])
        current_acc = STATE['accounts'][idx]['email']
    return jsonify({
        'tasks': sorted_tasks,
        'active_account': current_acc,
        'active_quota': STATE['active_quota'],
        'account_count': len(STATE['accounts'])
    })

@app.route('/confirm_switch', methods=['POST'])
def confirm_switch():
    data = request.json
    task_id = data.get('task_id')
    action = data.get('action') 
    if task_id in STATE['tasks']:
        STATE['tasks'][task_id]['status'] = 'resume_approved' if action == 'approve' else 'resume_rejected'
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Task not found'}), 404

@app.route('/delete_task', methods=['POST'])
def delete_task():
    data = request.json
    task_id = data.get('task_id')
    if task_id in STATE['tasks']:
        del STATE['tasks'][task_id]
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Task not found'}), 404

@app.route('/delete_all_tasks', methods=['POST'])
def delete_all_tasks():
    STATE['tasks'] = {}
    return jsonify({'status': 'ok'})

@app.route('/add_favorite', methods=['POST'])
def add_favorite():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    favorite = {
        'image_url': data.get('image_url'),
        'prompt': data.get('prompt'),
        'params': data.get('params', {})
    }
    STATE['favorites'].append(favorite)
    return jsonify({'success': True})

@app.route('/remove_favorite', methods=['POST'])
def remove_favorite():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    image_url = data.get('image_url')
    STATE['favorites'] = [f for f in STATE['favorites'] if f['image_url'] != image_url]
    return jsonify({'success': True})

@app.route('/get_favorites')
def get_favorites():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify({'favorites': STATE['favorites']})

@app.route('/add_prompt', methods=['POST'])
def add_prompt():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    prompt = {
        'title': data.get('title'),
        'text': data.get('text')
    }
    STATE['prompts'].insert(0, prompt)  # En son eklenen en üstte olsun
    return jsonify({'success': True})

@app.route('/delete_prompt', methods=['POST'])
def delete_prompt():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    index = data.get('index')
    if 0 <= index < len(STATE['prompts']):
        STATE['prompts'].pop(index)
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid index'}), 400

@app.route('/get_prompts')
def get_prompts():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify({'prompts': STATE['prompts']})

@app.route('/edit_prompt', methods=['POST'])
def edit_prompt():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    index = data.get('index')
    title = data.get('title')
    text = data.get('text')
    
    if 0 <= index < len(STATE['prompts']):
        STATE['prompts'][index] = {'title': title, 'text': text}
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid index'}), 400

@app.route('/delete_all_favorites', methods=['POST'])
def delete_all_favorites():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    STATE['favorites'] = []
    return jsonify({'success': True})

@app.route('/delete_all_prompts', methods=['POST'])
def delete_all_prompts():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    STATE['prompts'] = []
    return jsonify({'success': True})

# Resmi proxy üzerinden sunma (Download force'u bypass etmek için)
@app.route('/proxy_image')
def proxy_image():
    url = request.args.get('url')
    if not url: return "No URL", 400
    try:
        req = requests.get(url, stream=True)
        return Response(stream_with_context(req.iter_content(chunk_size=1024)), content_type=req.headers['content-type'])
    except:
        return "Error fetching image", 500

# --- Gemini Chat Endpoint ---
@app.route('/gemini_chat', methods=['POST'])
def gemini_chat():
    """Gemini 2.5 Flash ile sohbet - streaming yanıt"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        message = data.get('message', '')
        media_data = data.get('media', None)  # Base64 encoded media
        media_type = data.get('media_type', None)  # 'image' or 'video'
        chat_history = data.get('history', [])
        
        print(f"[Gemini] Message: {message[:50]}..." if len(message) > 50 else f"[Gemini] Message: {message}")
        print(f"[Gemini] Media: {media_type if media_type else 'None'}")
        
        # Build content parts
        content_parts = []
        
        # Add media if provided
        if media_data and media_type:
            try:
                # Remove data URL prefix if present
                if ',' in media_data:
                    media_data = media_data.split(',')[1]
                
                media_bytes = base64.b64decode(media_data)
                
                # Determine MIME type
                if media_type == 'image':
                    mime_type = 'image/jpeg'
                elif media_type == 'video':
                    mime_type = 'video/mp4'
                else:
                    mime_type = 'application/octet-stream'
                
                content_parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(media_bytes).decode('utf-8')
                    }
                })
                print(f"[Gemini] Media added: {mime_type}")
            except Exception as e:
                print(f"[Gemini] Media processing error: {e}")
        
        # Add text message
        if message:
            content_parts.append(message)
        
        if not content_parts:
            return jsonify({'error': 'No message or media provided'}), 400
        
        # Convert chat history to Gemini format
        gemini_history = []
        for msg in chat_history:
            role = "user" if msg.get('role') == 'user' else "model"
            gemini_history.append({
                "role": role,
                "parts": [msg.get('content', '')]
            })
        
        # Create chat or generate response
        def generate():
            try:
                print("[Gemini] Starting generation...")
                if gemini_history:
                    chat = gemini_model.start_chat(history=gemini_history)
                    response = chat.send_message(content_parts, stream=True)
                else:
                    response = gemini_model.generate_content(content_parts, stream=True)
                
                print("[Gemini] Got response, streaming chunks...")
                chunk_count = 0
                for chunk in response:
                    chunk_count += 1
                    try:
                        # Try to get text from chunk
                        text = None
                        if hasattr(chunk, 'text') and chunk.text:
                            text = chunk.text
                        elif hasattr(chunk, 'parts') and chunk.parts:
                            for part in chunk.parts:
                                if hasattr(part, 'text') and part.text:
                                    text = part.text
                                    break
                        
                        if text:
                            print(f"[Gemini] Chunk {chunk_count}: {text[:30]}...")
                            yield f"data: {json.dumps({'text': text})}\n\n"
                    except Exception as chunk_error:
                        print(f"[Gemini] Chunk error: {chunk_error}")
                        continue
                
                print(f"[Gemini] Done, total chunks: {chunk_count}")
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                print(f"[Gemini] Generation error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return Response(
            stream_with_context(generate()), 
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
    
    except Exception as e:
        print(f"[Gemini] Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
