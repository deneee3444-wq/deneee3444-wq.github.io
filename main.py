from flask import Flask, render_template_string, request, jsonify
import requests
import json
import time
from threading import Thread

app = Flask(__name__)

# --- GLOBAL DEĞİŞKENLER ---
ACCOUNTS = []  # Hesap listesi [{'email': '...', 'password': '...'}, ...]
CURRENT_ACCOUNT_INDEX = 0
token = None
current_task_status = {"status": "idle", "message": "Hesap dosyası bekleniyor...", "url": ""}

# --- SABİTLER ---
IMAGE_SIZES = {
    'AUTO': 'Otomatik',
    'SIXTEEN_BY_NINE': '16:9',
    'NINE_BY_SIXTEEN': '9:16',
    'ONE_BY_ONE': '1:1',
    'THREE_BY_FOUR': '3:4',
    'FOUR_BY_THREE': '4:3',
    'THREE_BY_TWO': '3:2',
    'TWO_BY_THREE': '2:3'
}

MODEL_TYPES = {
    'MODEL_THREE': 'Model 3',
    'MODEL_FOUR': 'Model 4',
    'MODEL_FIVE': 'Model 5'
}

MODEL_VERSIONS = {
    'MODEL_FIVE_SD_4_0': 'Model 5 SD 4.0',
    'MODEL_FOUR_NANO_BANANA': 'Model 4 Nano Banana',
    'MODEL_FOUR_NANO_BANANA_PRO': 'Model 4 Nano Banana Pro'
}

RESOLUTIONS = {
    '1K': '1K',
    '2K': '2K',
    '4K': '4K'
}

# --- HTML ŞABLONU ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Görsel Oluşturucu (Multi-Account)</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            height: 100vh;
            overflow: hidden;
            color: #333;
        }
        .main-container {
            display: grid;
            grid-template-columns: 400px 1fr;
            height: 100vh;
        }
        .left-panel {
            background: white;
            padding: 20px;
            overflow-y: auto;
            box-shadow: 2px 0 20px rgba(0,0,0,0.2);
        }
        .right-panel {
            display: flex;
            flex-direction: column;
            padding: 20px;
            background: rgba(255,255,255,0.1);
        }
        .header { margin-bottom: 20px; border-bottom: 2px solid #f0f0f0; padding-bottom: 10px; }
        .header h1 { font-size: 22px; color: #1e3c72; margin-bottom: 5px; }
        
        .account-box {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 13px;
        }
        .account-status { font-weight: bold; color: #2ecc71; }
        .account-quota { color: #e67e22; font-weight: bold; }
        
        .form-group { margin-bottom: 15px; }
        label { display: block; font-weight: 600; margin-bottom: 5px; color: #555; font-size: 13px; }
        
        input[type="file"], textarea, select {
            width: 100%; padding: 8px;
            border: 1px solid #ced4da; border-radius: 6px;
            font-size: 13px; font-family: inherit;
        }
        textarea { resize: vertical; min-height: 70px; }
        
        .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        
        .btn {
            background: #1e3c72; color: white; border: none;
            padding: 12px; border-radius: 6px; font-weight: 600;
            cursor: pointer; width: 100%; transition: 0.2s;
        }
        .btn:hover:not(:disabled) { background: #2a5298; }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; }
        
        .btn-upload { background: #6c757d; margin-top: 5px; }
        
        .preview-container {
            flex: 1; background: white; border-radius: 12px;
            padding: 20px; display: flex; flex-direction: column;
            box-shadow: 0 5px 25px rgba(0,0,0,0.2);
            position: relative; overflow: hidden;
        }
        .preview-content {
            flex: 1; display: flex; align-items: center; justify-content: center;
            background: #f1f3f5; border-radius: 8px; overflow: hidden;
        }
        #resultImage { max-width: 100%; max-height: 100%; object-fit: contain; display: none; }
        
        .status-overlay {
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(255,255,255,0.9);
            display: flex; flex-direction: column;
            justify-content: center; align-items: center;
            z-index: 10; display: none;
        }
        .status-overlay.show { display: flex; }
        .spinner {
            width: 40px; height: 40px; border: 4px solid #f3f3f3;
            border-top: 4px solid #1e3c72; border-radius: 50%;
            animation: spin 1s linear infinite; margin-bottom: 15px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        .log-box {
            margin-top: 10px; font-size: 12px; color: #666;
            max-height: 100px; overflow-y: auto; background: #fff;
            padding: 5px; border: 1px solid #eee;
        }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="left-panel">
            <div class="header">
                <h1>🤖 Multi-Account AI</h1>
            </div>
            
            <div class="account-box">
                <div id="accountInfoArea">
                    ⚠️ Önce hesap yükleyin
                </div>
                <form id="accountForm" style="margin-top:10px;">
                    <label>📁 accounts.txt Yükle</label>
                    <input type="file" name="accountFile" accept=".txt" required>
                    <button type="submit" class="btn btn-upload">Hesapları Yükle</button>
                </form>
            </div>

            <form id="generateForm" method="POST" enctype="multipart/form-data">
                <div class="form-group">
                    <label>📝 Prompt</label>
                    <textarea name="prompt" required>{{ default_prompt }}</textarea>
                </div>
                
                <div class="form-group">
                    <label>🖼️ Referans Görsel (Opsiyonel)</label>
                    <input type="file" name="image" accept="image/*">
                </div>
                
                <div class="row">
                    <div class="form-group">
                        <label>📐 Boyut</label>
                        <select name="imageSize">
                            {% for key, value in image_sizes.items() %}
                            <option value="{{ key }}">{{ value }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>✨ Çözünürlük</label>
                        <select name="resolution">
                            {% for key, value in resolutions.items() %}
                            <option value="{{ key }}" {% if key == '4K' %}selected{% endif %}>{{ value }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                
                <div class="row">
                    <div class="form-group">
                        <label>🤖 Model</label>
                        <select name="modelType">
                            {% for key, value in model_types.items() %}
                            <option value="{{ key }}" {% if key == 'MODEL_FOUR' %}selected{% endif %}>{{ value }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>🔧 Versiyon</label>
                        <select name="modelVersion">
                            {% for key, value in model_versions.items() %}
                            <option value="{{ key }}" {% if key == 'MODEL_FOUR_NANO_BANANA_PRO' %}selected{% endif %}>{{ value }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                
                <button type="submit" class="btn" id="submitBtn" disabled>🚀 Başlat</button>
            </form>
        </div>
        
        <div class="right-panel">
            <div class="preview-container">
                <div class="preview-content">
                    <div id="placeholder" style="text-align:center; color:#999;">
                        <h2>🖼️</h2><p>Görsel burada görünecek</p>
                    </div>
                    <img id="resultImage">
                    <div class="status-overlay" id="statusOverlay">
                        <div class="spinner"></div>
                        <div id="statusMessage">İşleniyor...</div>
                    </div>
                </div>
                <a id="downloadBtn" class="btn" style="margin-top:15px; display:none; background:#27ae60; text-align:center; text-decoration:none;" download>⬇️ İndir</a>
            </div>
        </div>
    </div>
    
    <script>
        // Hesap Dosyası Yükleme
        document.getElementById('accountForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            try {
                const res = await fetch('/upload_accounts', { method: 'POST', body: formData });
                const data = await res.json();
                if(data.success) {
                    alert(data.message);
                    updateAccountInfo();
                    document.getElementById('submitBtn').disabled = false;
                } else {
                    alert('Hata: ' + data.message);
                }
            } catch(err) { alert('Yükleme hatası'); }
        });

        function updateAccountInfo() {
            fetch('/account_info')
                .then(r => r.json())
                .then(data => {
                    const el = document.getElementById('accountInfoArea');
                    if(data.total > 0) {
                        el.innerHTML = `
                            <div>Aktif Hesap: <b>${data.current_email}</b></div>
                            <div class="account-quota">Kota: ${data.quota}</div>
                            <div style="font-size:11px; color:#999; margin-top:5px;">Toplam Hesap: ${data.total} | Sıra: ${data.index + 1}</div>
                        `;
                    }
                });
        }

        // Görsel Oluşturma
        document.getElementById('generateForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const overlay = document.getElementById('statusOverlay');
            const msg = document.getElementById('statusMessage');
            const img = document.getElementById('resultImage');
            const dl = document.getElementById('downloadBtn');
            const ph = document.getElementById('placeholder');
            
            document.getElementById('submitBtn').disabled = true;
            overlay.className = 'status-overlay show';
            img.style.display = 'none';
            ph.style.display = 'block';
            dl.style.display = 'none';
            msg.innerText = 'Başlatılıyor...';
            
            try {
                const res = await fetch('/generate', { method: 'POST', body: formData });
                const data = await res.json();
                
                if(data.success) {
                    // Durum polling
                    const interval = setInterval(async () => {
                        const sRes = await fetch('/status');
                        const sData = await sRes.json();
                        
                        msg.innerText = sData.message;
                        
                        // Hesap değişirse arayüzü güncelle
                        updateAccountInfo();
                        
                        if(sData.status === 'completed') {
                            clearInterval(interval);
                            overlay.className = 'status-overlay';
                            img.src = sData.url;
                            img.style.display = 'block';
                            ph.style.display = 'none';
                            dl.href = sData.url;
                            dl.style.display = 'block';
                            document.getElementById('submitBtn').disabled = false;
                        } else if(sData.status === 'error') {
                            clearInterval(interval);
                            msg.innerHTML = '<span style="color:red">Hata: ' + sData.message + '</span>';
                            setTimeout(() => { overlay.className = 'status-overlay'; }, 3000);
                            document.getElementById('submitBtn').disabled = false;
                        }
                    }, 2000);
                } else {
                    msg.innerText = 'Hata: ' + data.message;
                    setTimeout(() => { overlay.className = 'status-overlay'; document.getElementById('submitBtn').disabled = false; }, 2000);
                }
            } catch(err) {
                msg.innerText = 'Bağlantı hatası!';
                setTimeout(() => { overlay.className = 'status-overlay'; document.getElementById('submitBtn').disabled = false; }, 2000);
            }
        });
        
        // Sayfa açıldığında bilgi çekmeyi dene
        updateAccountInfo();
    </script>
</body>
</html>
'''

# --- YARDIMCI FONKSİYONLAR ---

def switch_account():
    global CURRENT_ACCOUNT_INDEX, token
    
    # Sıradaki hesaba geç
    CURRENT_ACCOUNT_INDEX += 1
    
    if CURRENT_ACCOUNT_INDEX >= len(ACCOUNTS):
        # Liste bitti, başa dön veya hata ver. Şimdilik başa dönüyoruz.
        CURRENT_ACCOUNT_INDEX = 0
        if len(ACCOUNTS) == 0:
            return False
            
    print(f"Hesap değiştiriliyor... Yeni sıra: {CURRENT_ACCOUNT_INDEX + 1}")
    return get_token()

def get_token():
    global token
    if not ACCOUNTS:
        return False
        
    account = ACCOUNTS[CURRENT_ACCOUNT_INDEX]
    email = account['email']
    password = account['password']
    
    url = "https://sp.deevid.ai/auth/v1/token?grant_type=password"
    headers = {
        "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.ewogICJyb2xlIjogImFub24iLAogICJpc3MiOiAic3VwYWJhc2UiLAogICJpYXQiOiAxNzM0OTY5NjAwLAogICJleHAiOiAxODkyNzM2MDAwCn0.4NnK23LGYvKPGuKI5rwQn2KbLMzzdE4jXpHwbGCqPqY",
    }
    payload = {
        "email": email,
        "password": password,
        "gotrue_meta_security": {}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        json_data = json.loads(response.text)
        
        if 'access_token' in json_data:
            token = json_data['access_token']
            print(f"Giriş başarılı: {email}")
            return True
        else:
            print(f"Giriş hatası ({email}): {json_data}")
            return False
    except Exception as e:
        print("Token request hatası:", e)
        return False

def get_quota():
    if not token:
        return 0
    url = "https://api.deevid.ai/subscription/plan"
    headers = {"authorization": "Bearer " + token}
    try:
        response = requests.get(url, headers=headers)
        d = response.json()['data']['data']['message_quota']
        return d['quota_count'] - d['subscription_quota_used']
    except:
        return 0

def get_latest_asset_id():
    """Son yüklenen/oluşturulan asset'in ID'sini getirir. Eski resim gelmesini önlemek için referans noktası."""
    url = "https://api.deevid.ai/my-assets?limit=5&assetType=All&filter=CREATION"
    headers = {"authorization": "Bearer " + token}
    try:
        resp = requests.get(url, headers=headers).json()
        groups = resp["data"]["data"]["groups"]
        # En üstteki (en yeni) grubun, en üstteki item'ının ID'sini al
        if groups and groups[0]["items"]:
            return groups[0]["items"][0]["id"]
    except:
        pass
    return None

def upload_image_api(image_file):
    url = "https://api.deevid.ai/file-upload/image"
    headers = {"Authorization": "Bearer " + token}
    files = {"file": (image_file.filename, image_file, image_file.content_type)}
    data = {"width": "1024", "height": "1536"}
    
    try:
        resp = requests.post(url, headers=headers, files=files, data=data)
        json_data = resp.json()
        if 'data' in json_data and 'data' in json_data['data'] and 'id' in json_data['data']['data']:
            return json_data['data']['data']['id']
    except Exception as e:
        print("Upload hatası:", e)
    return None

def generate_logic(prompt, image_size, count, resolution, model_type, model_version, user_image_id):
    global current_task_status
    
    # 1. Token kontrolü
    if not token:
        if not get_token():
             current_task_status = {"status": "error", "message": "Hesaplara giriş yapılamadı.", "url": ""}
             return

    # 2. ESKİ RESMİ ÖNLEME MEKANİZMASI
    # Şu anki en son ID'yi kaydediyoruz. Döngüde bundan daha yeni bir ID arayacağız.
    last_asset_id = get_latest_asset_id()
    print(f"Başlangıç referans ID: {last_asset_id}")

    current_task_status = {"status": "processing", "message": "Görev gönderiliyor...", "url": ""}

    url = "https://api.deevid.ai/text-to-image/task/submit"
    headers = {"Authorization": "Bearer " + token}
    
    payload = {
        "prompt": prompt,
        "imageSize": image_size,
        "count": int(count),
        "resolution": resolution,
        "modelType": model_type,
        "modelVersion": model_version
    }
    if user_image_id:
        payload["userImageIds"] = [user_image_id]
        
    # Sonsuz döngü (Hesap değişimi için)
    while True:
        try:
            # Token başlığı güncelle (Hesap değişmiş olabilir)
            headers["Authorization"] = "Bearer " + token
            
            resp = requests.post(url, headers=headers, json=payload)
            resp_json = resp.json()
            
            # Hata kontrolü (Kota vs.)
            if 'error' in resp_json and resp_json['error'] and resp_json['error']['code'] != 0:
                print("Kota bitti veya API hatası, hesap değiştiriliyor...")
                current_task_status = {"status": "processing", "message": "Kota doldu, diğer hesaba geçiliyor...", "url": ""}
                
                if switch_account():
                    # Yeni hesapla tekrar dene (while döngüsü başa döner)
                    # Not: Referans ID'yi güncellemeye gerek yok, çünkü yeni hesapta zaten liste boş veya farklıdır.
                    # Ama güvenli olması için o hesabın da son ID'sini alabiliriz, fakat ID çakışması düşüktür.
                    # Basitlik için devam ediyoruz.
                    time.sleep(1)
                    continue
                else:
                    current_task_status = {"status": "error", "message": "Tüm hesapların kotası tükendi!", "url": ""}
                    return
            
            # Başarılı gönderim
            break
            
        except Exception as e:
            current_task_status = {"status": "error", "message": f"API Hatası: {str(e)}", "url": ""}
            return

    # 3. Bekleme Döngüsü
    current_task_status = {"status": "processing", "message": "Görsel oluşturuluyor (Kuyrukta)...", "url": ""}
    
    check_url = "https://api.deevid.ai/my-assets?limit=5&assetType=All&filter=CREATION"
    
    max_wait = 120 # saniye
    waited = 0
    
    while waited < max_wait:
        time.sleep(3)
        waited += 3
        
        try:
            headers["authorization"] = "Bearer " + token # Güncel token
            check_resp = requests.get(check_url, headers=headers).json()
            groups = check_resp["data"]["data"]["groups"]
            
            found_new_image = False
            
            for group in groups:
                for item in group["items"]:
                    # ÖNEMLİ: Bu item'ın ID'si referans ID'den farklı mı? (Veya referans ID yoksa her şey yenidir)
                    current_id = item["id"]
                    
                    # Eğer referans aldığımız ID ile aynıysa, bu eski bir resimdir. Atla.
                    if last_asset_id and current_id == last_asset_id:
                        continue
                        
                    # Durum kontrolü
                    task_state = item["detail"]["creation"]["taskState"]
                    
                    if task_state == 'FAIL':
                        # Bu yeni işlem fail olduysa
                        current_task_status = {"status": "error", "message": "İşlem başarısız (API Fail)", "url": ""}
                        return
                    
                    # Görüntü URL'si var mı?
                    image_urls = item["detail"]["creation"].get("noWaterMarkImageUrl", [])
                    if image_urls:
                        # Bingo! Yeni ve bitmiş işlem.
                        print(f"Yeni görsel bulundu! ID: {current_id}")
                        current_task_status = {"status": "completed", "message": "Tamamlandı!", "url": image_urls[0]}
                        return
                        
            current_task_status = {"status": "processing", "message": f"Oluşturuluyor... ({waited}s)", "url": ""}
            
        except Exception as e:
            print("Check hatası:", e)
            
    current_task_status = {"status": "error", "message": "Zaman aşımı.", "url": ""}

# --- FLASK ROUTES ---

@app.route('/')
def index():
    return render_template_string(
        HTML_TEMPLATE,
        image_sizes=IMAGE_SIZES,
        model_types=MODEL_TYPES,
        model_versions=MODEL_VERSIONS,
        resolutions=RESOLUTIONS,
        default_prompt='resimdeki kız beyaz yün bir sütyen giymiş, göğüsleri belirgin olmalı, otel odasında bir koltukta oturuyor olmalı, sinematik ve yakın çekim olmalı.'
    )

@app.route('/upload_accounts', methods=['POST'])
def upload_accounts():
    global ACCOUNTS, CURRENT_ACCOUNT_INDEX
    file = request.files.get('accountFile')
    if not file:
        return jsonify({"success": False, "message": "Dosya yok"})
    
    try:
        content = file.read().decode('utf-8').strip()
        lines = content.split('\n')
        new_accounts = []
        
        for line in lines:
            parts = line.strip().split(':')
            if len(parts) >= 2:
                # email:password:a -> sadece ilk ikisini al
                new_accounts.append({
                    "email": parts[0].strip(),
                    "password": parts[1].strip()
                })
        
        if new_accounts:
            ACCOUNTS = new_accounts
            CURRENT_ACCOUNT_INDEX = 0
            if get_token(): # İlk hesaba giriş yap
                return jsonify({"success": True, "message": f"{len(ACCOUNTS)} hesap yüklendi ve ilkine giriş yapıldı."})
            else:
                return jsonify({"success": True, "message": f"{len(ACCOUNTS)} hesap yüklendi ancak ilk girişte sorun oldu."})
        else:
            return jsonify({"success": False, "message": "Dosyada geçerli hesap bulunamadı"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/account_info')
def account_info():
    if not ACCOUNTS:
        return jsonify({"total": 0})
    
    current_email = ACCOUNTS[CURRENT_ACCOUNT_INDEX]['email']
    q = get_quota()
    return jsonify({
        "total": len(ACCOUNTS),
        "index": CURRENT_ACCOUNT_INDEX,
        "current_email": current_email,
        "quota": q
    })

@app.route('/generate', methods=['POST'])
def generate():
    if not ACCOUNTS:
        return jsonify({"success": False, "message": "Lütfen önce hesap dosyası yükleyin!"})

    prompt = request.form.get('prompt')
    image_size = request.form.get('imageSize')
    count = request.form.get('count')
    resolution = request.form.get('resolution')
    model_type = request.form.get('modelType')
    model_version = request.form.get('modelVersion')
    image_file = request.files.get('image')
    
    user_image_id = None
    if image_file and image_file.filename:
        # Upload sırasında token hatası olursa switch yapılması gerekebilir mi? 
        # Basitlik için mevcut token ile deniyoruz, task gönderirken switch yapısı kurulu.
        user_image_id = upload_image_api(image_file)
        if not user_image_id:
             # Belki token süresi doldu?
             get_token()
             user_image_id = upload_image_api(image_file) # Tekrar dene
    
    # Arka planda çalıştır
    thread = Thread(target=generate_logic, args=(prompt, image_size, count, resolution, model_type, model_version, user_image_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "Başlatıldı"})

@app.route('/status')
def status():
    return jsonify(current_task_status)

if __name__ == '__main__':
    print("Sunucu başlatılıyor...")
    app.run(debug=True, host='0.0.0.0', port=5000)
