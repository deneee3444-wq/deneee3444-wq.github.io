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

# --- API Constants ---
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.ewogICJyb2xlIjogImFub24iLAogICJpc3MiOiAic3VwYWJhc2UiLAogICJpYXQiOiAxNzM0OTY5NjAwLAogICJleHAiOiAxODkyNzM2MDAwCn0.4NnK23LGYvKPGuKI5rwQn2KbLMzzdE4jXpHwbGCqPqY"
URL_AUTH = "https://sp.deevid.ai/auth/v1/token?grant_type=password"
URL_UPLOAD = "https://api.deevid.ai/file-upload/image"
URL_SUBMIT = "https://api.deevid.ai/text-to-image/task/submit"
URL_ASSETS = "https://api.deevid.ai/my-assets?limit=50&assetType=All&filter=CREATION" # Limit artırıldı ki geriye düşmesin
URL_QUOTA = "https://api.deevid.ai/subscription/plan"

# --- Helper Functions ---

def get_current_account():
    if not STATE['accounts']:
        return None
    idx = STATE['current_account_index'] % len(STATE['accounts'])
    return STATE['accounts'][idx]

def rotate_account():
    """Bir sonraki hesaba geçer ve tokeni sıfırlar."""
    if not STATE['accounts']:
        return False
    
    prev_email = get_current_account()['email']
    STATE['current_account_index'] = (STATE['current_account_index'] + 1) % len(STATE['accounts'])
    STATE['current_token'] = None
    STATE['active_quota'] = "Hesaplanıyor..."
    
    new_email = get_current_account()['email']
    print(f"!!! Hesap Değiştiriliyor: {prev_email} -> {new_email}")
    return True

def login_and_get_token():
    """Mevcut token varsa döndürür, yoksa login olup alır."""
    if STATE['current_token']:
        return STATE['current_token']

    account = get_current_account()
    if not account:
        raise Exception("Yüklü hesap bulunamadı!")

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
        
        # Login olunca kotayı da güncelle
        refresh_quota(token)
        
        return token
    except Exception as e:
        print(f"Login hatası ({account['email']}): {e}")
        if rotate_account():
            return login_and_get_token()
        else:
            raise Exception("Tüm hesaplar denendi, giriş yapılamadı.")

def refresh_quota(token):
    """Kotayı çeker ve global state'e yazar."""
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
        STATE['active_quota'] = "Hata"
        return 0

def process_task_thread(task_id, file_path, form_data):
    log_msg = lambda m: STATE['tasks'][task_id]['logs'].append(m)
    STATE['tasks'][task_id]['status'] = 'running'
    log_msg("İşlem başlatılıyor...")

    try:
        # 1. Login
        token = login_and_get_token()
        
        # 2. Upload
        log_msg("Görsel yükleniyor...")
        upload_headers = {"Authorization": "Bearer " + token}
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "image/png")}
            upload_data = {"width": "1024", "height": "1536"}
            resp_upload = requests.post(URL_UPLOAD, headers=upload_headers, files=files, data=upload_data)
        
        if resp_upload.status_code not in [200, 201]:
            log_msg(f"Upload hatası: {resp_upload.status_code}")
            STATE['tasks'][task_id]['status'] = 'failed'
            return

        try:
            user_image_id = resp_upload.json()['data']['data']['id']
        except:
            log_msg("Görsel ID alınamadı.")
            STATE['tasks'][task_id]['status'] = 'failed'
            return
        
        target_api_task_id = None

        # 3. Submit Loop (Kota hatasında retry için)
        while True:
            log_msg(f"Görev gönderiliyor... (Hesap: {get_current_account()['email']})")
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

            # Hata / Kota Kontrolü
            error_code = 0
            if 'error' in resp_json and resp_json['error']:
                 error_code = resp_json['error'].get('code', 0)

            if error_code != 0:
                log_msg(f"HATA/KOTA SORUNU! Code: {error_code}. Hesap değiştiriliyor...")
                if rotate_account():
                    token = login_and_get_token() # Yeni token ve hesap
                    # Resmi tekrar upload etmiyoruz, image ID global değilse fail olabilir ama 
                    # genelde hesaplar arası erişim yoksa userImageId patlar. 
                    # Bu durumda en doğrusu tekrar upload etmektir ama şimdilik retry yapıyoruz.
                    continue 
                else:
                    STATE['tasks'][task_id]['status'] = 'failed'
                    return
            else:
                # BAŞARILI SUBMIT - Task ID'yi yakala!
                try:
                    target_api_task_id = resp_json['data']['data']['taskId']
                    log_msg(f"Talep iletildi. Task ID: {target_api_task_id}")
                except:
                    log_msg("Response ID parse edilemedi, manuel takip yapılacak.")
                
                break

        # 4. Polling (ID'ye göre Tam Eşleşme)
        attempt = 0
        while attempt < 60: # 2 dakika bekle
            attempt += 1
            time.sleep(2)
            
            try:
                # Listeyi çek
                poll_resp = requests.get(URL_ASSETS, headers={"authorization": "Bearer " + token}).json()
                groups = poll_resp.get("data", {}).get("data", {}).get("groups", [])
                
                found_match = False
                
                # Tüm grupları ve itemleri gez
                for group in groups:
                    for item in group.get("items", []):
                        creation = item.get("detail", {}).get("creation", {})
                        item_task_id = creation.get("taskId")
                        
                        # EĞER ID BİZİMKİYLE AYNIYSA
                        if target_api_task_id and item_task_id == target_api_task_id:
                            found_match = True
                            task_state = creation.get("taskState")
                            
                            if task_state == 'FAIL':
                                log_msg("API: İşlem başarısız.")
                                STATE['tasks'][task_id]['status'] = 'failed'
                                return
                            
                            image_urls = creation.get("noWaterMarkImageUrl", [])
                            if image_urls:
                                final_url = image_urls[0]
                                STATE['tasks'][task_id]['image_url'] = final_url
                                STATE['tasks'][task_id]['status'] = 'completed'
                                log_msg("İşlem Tamamlandı!")
                                refresh_quota(token)
                                return
                            else:
                                # Hala işleniyor
                                pass
                
                if not found_match:
                    # Listede henüz görünmüyor olabilir
                    pass

            except Exception as e:
                pass
            
        log_msg("Zaman aşımı. Resim oluşmadı.")
        STATE['tasks'][task_id]['status'] = 'failed'

    except Exception as e:
        log_msg(f"Kritik Hata: {str(e)}")
        STATE['tasks'][task_id]['status'] = 'failed'

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_accounts', methods=['POST'])
def upload_accounts():
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya yok'}), 400
    file = request.files['file']
    accounts = []
    try:
        content = file.read().decode('utf-8').splitlines()
        for line in content:
            parts = line.strip().split(':')
            if len(parts) >= 2:
                accounts.append({'email': parts[0], 'password': parts[1]})
        STATE['accounts'] = accounts
        STATE['current_account_index'] = 0
        STATE['current_token'] = None
        STATE['active_quota'] = "Giriş Bekleniyor"
        return jsonify({'count': len(accounts), 'message': 'Hesaplar yüklendi'})
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
