import os
import json
import time
import uuid
import threading
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Global State ---
STATE = {
    "accounts": [],       # {email, password} listesi
    "current_account_index": 0,
    "current_token": None,
    "active_quota": "Bilinmiyor", 
    "tasks": {}           # task_id -> {status, log, image_url, params, created_at, api_task_id}
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
    
    # Index yönetimi: Eleman silinince sağdakiler sola kayar, 
    # yani index aynı kalsa bile aslında bir sonraki elemanı gösterir.
    # Ancak liste bittiyse başa dönmeliyiz.
    if STATE['accounts']:
        STATE['current_account_index'] = STATE['current_account_index'] % len(STATE['accounts'])
    else:
        STATE['current_account_index'] = 0
        
    STATE['current_token'] = None
    STATE['active_quota'] = "Hesap Silindi"

# Uygulama başlarken yükle
STATE['accounts'] = load_accounts_from_file()

# --- Helper Functions ---

def get_current_account():
    if not STATE['accounts']:
        return None
    idx = STATE['current_account_index'] % len(STATE['accounts'])
    return STATE['accounts'][idx]

def rotate_account(delete_current=False):
    """
    Bir sonraki hesaba geçer. 
    Eğer delete_current=True ise mevcut hesabı siler (otomatikman sıradaki gelir).
    """
    if not STATE['accounts']:
        return False
    
    if delete_current:
        remove_current_account_permanently()
        if not STATE['accounts']:
            return False
        # Silme işlemi zaten index'i bir sonrakine (kaydığı için) ayarladı.
        # Ekstra artırmaya gerek yok, sadece token sıfırla.
        STATE['current_token'] = None
        STATE['active_quota'] = "Hesaplanıyor..."
        return True
    else:
        # Sadece geçiş yap (Silmeden) - Normalde bu istenmedi ama yedek olarak kalsın
        prev_email = get_current_account()['email']
        STATE['current_account_index'] = (STATE['current_account_index'] + 1) % len(STATE['accounts'])
        STATE['current_token'] = None
        STATE['active_quota'] = "Hesaplanıyor..."
        new_email = get_current_account()['email']
        print(f"!!! Hesap Değiştiriliyor (Silinmedi): {prev_email} -> {new_email}")
        return True

def login_and_get_token():
    """Mevcut token varsa döndürür, yoksa login olup alır."""
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
        # Login olamıyorsa bu hesabı da geçelim/silelim mi? 
        # Güvenlik için şimdilik sadece rotate ediyoruz (silme opsiyonel olabilir).
        # Kullanıcı isteği: "Geç ve devam et dediysem sil". Login hatası ayrı bir durum ama
        # genelde login olamayan hesap da işe yaramaz. Şimdilik sadece geçiyoruz.
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

def process_task_thread(task_id, file_path, form_data):
    # Task silindiyse çalışmayı durdur
    if task_id not in STATE['tasks']: return

    log_msg = lambda m: STATE['tasks'][task_id]['logs'].append(m) if task_id in STATE['tasks'] else None
    
    if task_id in STATE['tasks']:
        STATE['tasks'][task_id]['status'] = 'running'
    log_msg("İşlem başlatılıyor...")

    try:
        token = login_and_get_token()
        
        # Upload
        if task_id not in STATE['tasks']: return
        log_msg("Görsel yükleniyor...")
        upload_headers = {"Authorization": "Bearer " + token}
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "image/png")}
            upload_data = {"width": "1024", "height": "1536"}
            resp_upload = requests.post(URL_UPLOAD, headers=upload_headers, files=files, data=upload_data)
        
        if resp_upload.status_code not in [200, 201]:
            log_msg(f"Upload hatası: {resp_upload.status_code}")
            if task_id in STATE['tasks']: STATE['tasks'][task_id]['status'] = 'failed'
            return

        try:
            user_image_id = resp_upload.json()['data']['data']['id']
        except:
            log_msg("Görsel ID alınamadı.")
            if task_id in STATE['tasks']: STATE['tasks'][task_id]['status'] = 'failed'
            return
        
        target_api_task_id = None

        # Submit Loop
        while True:
            if task_id not in STATE['tasks']: return # Check cancellation
            
            acc = get_current_account()
            if not acc:
                log_msg("Hesap kalmadı!")
                if task_id in STATE['tasks']: STATE['tasks'][task_id]['status'] = 'failed'
                return

            log_msg(f"Görev gönderiliyor... ({acc['email']})")
            submit_headers = {"Authorization": "Bearer " + token}
            payload = {
                "prompt": form_data.get('prompt', 'odada oturuyor olsun.'),
                "imageSize": form_data.get('image_size'),
                "count": 1,
                "resolution": form_data.get('resolution'),
                "userImageIds": [user_image_id],
                "modelType": form_data.get('model_type'),
                "modelVersion": form_data.get('model_version')
            }

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
                        if task_id not in STATE['tasks']: return # Deleted while waiting
                        
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
                    # BURADA HESABI SİLİYORUZ (DELETE CURRENT)
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
        
        # İlk yüklemede state'i güncelle
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
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Görsel seçilmedi!'}), 400
    task_id = str(uuid.uuid4())
    filename = f"{task_id}_{file.filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    STATE['tasks'][task_id] = {
        'id': task_id,
        'status': 'pending',
        'logs': [],
        'image_url': None,
        'params': form_data,
        'created_at': time.time()
    }
    thread = threading.Thread(target=process_task_thread, args=(task_id, filepath, form_data))
    thread.daemon = True
    thread.start()
    return jsonify({'task_id': task_id, 'message': 'İşlem başlatıldı'})

@app.route('/status')
def get_status():
    # Sort tasks by creation time desc
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
        if action == 'approve':
            STATE['tasks'][task_id]['status'] = 'resume_approved'
            return jsonify({'status': 'ok'})
        else:
            STATE['tasks'][task_id]['status'] = 'resume_rejected'
            return jsonify({'status': 'ok'})
    return jsonify({'error': 'Task not found'}), 404

@app.route('/delete_task', methods=['POST'])
def delete_task():
    data = request.json
    task_id = data.get('task_id')
    if task_id in STATE['tasks']:
        del STATE['tasks'][task_id]
        return jsonify({'status': 'ok', 'message': 'Görev silindi'})
    return jsonify({'error': 'Task not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
