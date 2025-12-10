from flask import Flask, render_template_string, request, jsonify
import requests
import json
import time
from threading import Thread

app = Flask(__name__)

# Global değişkenler
token = None
user_email = ""
user_password = ""
current_task_status = {"status": "idle", "message": "", "url": ""}

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

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Görsel Oluşturucu</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            overflow: hidden;
            color: #333;
        }
        
        /* Login Modal Stilleri */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(5px);
            z-index: 9999;
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .login-box {
            background: white;
            padding: 40px;
            border-radius: 15px;
            width: 400px;
            box-shadow: 0 15px 30px rgba(0,0,0,0.3);
            text-align: center;
        }

        .login-box h2 {
            color: #667eea;
            margin-bottom: 25px;
            font-size: 24px;
        }

        .login-input {
            width: 100%;
            padding: 12px;
            margin-bottom: 15px;
            border: 2px solid #e1e8ed;
            border-radius: 8px;
            font-size: 14px;
            transition: 0.3s;
        }

        .login-input:focus {
            border-color: #667eea;
            outline: none;
        }

        .login-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px;
            width: 100%;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.3s;
        }

        .login-btn:hover {
            opacity: 0.9;
            transform: translateY(-2px);
        }
        
        /* Ana Arayüz Stilleri */
        .main-container {
            display: grid;
            grid-template-columns: 450px 1fr;
            height: 100vh;
            gap: 0;
            filter: blur(0px); /* Login açıkken blur olabilir */
            transition: filter 0.3s;
        }
        
        .left-panel {
            background: white;
            padding: 25px;
            overflow-y: auto;
            box-shadow: 2px 0 20px rgba(0,0,0,0.1);
        }
        
        .right-panel {
            display: flex;
            flex-direction: column;
            padding: 25px;
            overflow: hidden;
        }
        
        .header {
            margin-bottom: 20px;
        }
        
        .header h1 {
            font-size: 24px;
            color: #667eea;
            margin-bottom: 15px;
        }
        
        .quota-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .quota-text {
            font-size: 16px;
            font-weight: 600;
        }
        
        .refresh-btn {
            background: rgba(255,255,255,0.3);
            border: none;
            color: white;
            padding: 8px 15px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.3s;
        }
        
        .refresh-btn:hover {
            background: rgba(255,255,255,0.4);
        }
        
        .form-group {
            margin-bottom: 18px;
        }
        
        label {
            display: block;
            font-weight: 600;
            margin-bottom: 6px;
            color: #555;
            font-size: 13px;
        }
        
        input[type="file"],
        textarea,
        select {
            width: 100%;
            padding: 10px;
            border: 2px solid #e1e8ed;
            border-radius: 8px;
            font-size: 13px;
            transition: all 0.3s;
            font-family: inherit;
        }
        
        textarea {
            resize: vertical;
            min-height: 80px;
        }
        
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        
        input[type="file"] {
            padding: 8px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 14px;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            width: 100%;
            margin-top: 10px;
        }
        
        .btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 15px rgba(102, 126, 234, 0.3);
        }
        
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .preview-container {
            flex: 1;
            background: rgba(255,255,255,0.95);
            border-radius: 15px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .preview-header {
            color: #667eea;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
        }
        
        .preview-content {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f8f9fa;
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }
        
        .placeholder {
            text-align: center;
            color: #999;
        }
        
        .placeholder-icon {
            font-size: 64px;
            margin-bottom: 10px;
        }
        
        #resultImage {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            border-radius: 8px;
        }
        
        .status-overlay {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(255,255,255,0.95);
            padding: 25px 35px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            text-align: center;
            display: none;
        }
        
        .status-overlay.show {
            display: block;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .download-btn {
            background: #2ecc71;
            margin-top: 15px;
        }
        
        .download-btn:hover {
            background: #27ae60;
            box-shadow: 0 8px 15px rgba(46, 204, 113, 0.3);
        }
        
        .error-text {
            color: #e74c3c;
            font-weight: 600;
        }
        
        .success-text {
            color: #2ecc71;
            font-weight: 600;
        }
        
        /* Scrollbar styling */
        .left-panel::-webkit-scrollbar {
            width: 8px;
        }
        
        .left-panel::-webkit-scrollbar-track {
            background: #f1f1f1;
        }
        
        .left-panel::-webkit-scrollbar-thumb {
            background: #667eea;
            border-radius: 4px;
        }
        
        @media (max-width: 1024px) {
            .main-container {
                grid-template-columns: 1fr;
                grid-template-rows: auto 1fr;
            }
            
            .left-panel {
                height: auto;
                max-height: 50vh;
            }
        }
    </style>
</head>
<body>
    <div class="modal-overlay" id="loginModal">
        <div class="login-box">
            <h2>🔐 Giriş Yap</h2>
            <form id="loginForm">
                <input type="email" name="email" class="login-input" placeholder="E-posta Adresi" required>
                <input type="password" name="password" class="login-input" placeholder="Şifre" required>
                <button type="submit" class="login-btn" id="loginBtn">Giriş Yap</button>
                <p id="loginError" style="color: #e74c3c; margin-top: 10px; font-size: 13px; display: none;"></p>
            </form>
        </div>
    </div>

    <div class="main-container" id="mainContainer">
        <div class="left-panel">
            <div class="header">
                <h1>🎨 AI Görsel Oluşturucu</h1>
                <div class="quota-box">
                    <span class="quota-text" id="quotaInfo">Giriş yapılıyor...</span>
                    <button class="refresh-btn" onclick="refreshQuota()">🔄 Yenile</button>
                </div>
            </div>
            
            <form id="generateForm" method="POST" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="prompt">📝 Prompt</label>
                    <textarea name="prompt" id="prompt" required>{{ default_prompt }}</textarea>
                </div>
                
                <div class="form-group">
                    <label for="image">🖼️ Referans Görsel (Opsiyonel)</label>
                    <input type="file" name="image" id="image" accept="image/*">
                </div>
                
                <div class="row">
                    <div class="form-group">
                        <label for="imageSize">📐 Boyut</label>
                        <select name="imageSize" id="imageSize">
                            {% for key, value in image_sizes.items() %}
                            <option value="{{ key }}">{{ value }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="resolution">✨ Çözünürlük</label>
                        <select name="resolution" id="resolution">
                            {% for key, value in resolutions.items() %}
                            <option value="{{ key }}" {% if key == '4K' %}selected{% endif %}>{{ value }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                
                <div class="row">
                    <div class="form-group">
                        <label for="modelType">🤖 Model</label>
                        <select name="modelType" id="modelType">
                            {% for key, value in model_types.items() %}
                            <option value="{{ key }}" {% if key == 'MODEL_FOUR' %}selected{% endif %}>{{ value }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="modelVersion">🔧 Versiyon</label>
                        <select name="modelVersion" id="modelVersion">
                            {% for key, value in model_versions.items() %}
                            <option value="{{ key }}" {% if key == 'MODEL_FOUR_NANO_BANANA_PRO' %}selected{% endif %}>{{ value }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="count">🔢 Görsel Sayısı</label>
                    <select name="count" id="count">
                        <option value="1" selected>1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="4">4</option>
                    </select>
                </div>
                
                <button type="submit" class="btn" id="submitBtn">🚀 Görsel Oluştur</button>
            </form>
        </div>
        
        <div class="right-panel">
            <div class="preview-container">
                <div class="preview-header">Önizleme</div>
                <div class="preview-content" id="previewContent">
                    <div class="placeholder">
                        <div class="placeholder-icon">🖼️</div>
                        <div>Oluşturulan görsel burada görünecek</div>
                    </div>
                    <img id="resultImage" style="display:none;">
                    <div class="status-overlay" id="statusOverlay">
                        <div class="spinner"></div>
                        <div id="statusMessage">İşlem devam ediyor...</div>
                    </div>
                </div>
                <a id="downloadBtn" class="btn download-btn" style="display:none;" download>⬇️ Görseli İndir</a>
            </div>
        </div>
    </div>
    
    <script>
        // Login İşlemi
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('loginBtn');
            const errorMsg = document.getElementById('loginError');
            const formData = new FormData(e.target);
            
            btn.disabled = true;
            btn.textContent = 'Giriş Yapılıyor...';
            errorMsg.style.display = 'none';
            
            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                
                if (data.success) {
                    // Modal'ı kapat
                    document.getElementById('loginModal').style.display = 'none';
                    // Kotayı güncelle
                    document.getElementById('quotaInfo').textContent = 'Kalan Kota: ' + data.quota;
                } else {
                    errorMsg.textContent = data.message;
                    errorMsg.style.display = 'block';
                    btn.disabled = false;
                    btn.textContent = 'Giriş Yap';
                }
            } catch (err) {
                errorMsg.textContent = 'Bağlantı hatası!';
                errorMsg.style.display = 'block';
                btn.disabled = false;
                btn.textContent = 'Giriş Yap';
            }
        });

        // Kota yenileme
        function refreshQuota() {
            fetch('/quota')
                .then(r => r.json())
                .then(data => {
                    if (data.quota !== undefined) {
                        document.getElementById('quotaInfo').textContent = 'Kalan Kota: ' + data.quota;
                    }
                });
        }
        
        // Form submit
        document.getElementById('generateForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const submitBtn = document.getElementById('submitBtn');
            const statusOverlay = document.getElementById('statusOverlay');
            const statusMessage = document.getElementById('statusMessage');
            const resultImage = document.getElementById('resultImage');
            const downloadBtn = document.getElementById('downloadBtn');
            
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ İşleniyor...';
            
            statusOverlay.className = 'status-overlay show';
            statusMessage.innerHTML = 'Görsel yükleniyor ve işleme alınıyor...';
            resultImage.style.display = 'none';
            downloadBtn.style.display = 'none';
            
            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    statusMessage.innerHTML = 'Görsel oluşturuluyor, bekleyin...';
                    
                    // Durum kontrolü
                    const checkStatus = setInterval(async () => {
                        const statusResp = await fetch('/status');
                        const statusData = await statusResp.json();
                        
                        if (statusData.status === 'completed') {
                            clearInterval(checkStatus);
                            statusOverlay.className = 'status-overlay';
                            resultImage.src = statusData.url;
                            resultImage.style.display = 'block';
                            downloadBtn.href = statusData.url;
                            downloadBtn.style.display = 'block';
                            submitBtn.disabled = false;
                            submitBtn.textContent = '🚀 Görsel Oluştur';
                            refreshQuota();
                        } else if (statusData.status === 'error') {
                            clearInterval(checkStatus);
                            statusOverlay.className = 'status-overlay show';
                            statusMessage.innerHTML = '<div class="error-text">✗ ' + statusData.message + '</div>';
                            submitBtn.disabled = false;
                            submitBtn.textContent = '🚀 Görsel Oluştur';
                            setTimeout(() => {
                                statusOverlay.className = 'status-overlay';
                            }, 3000);
                        } else {
                            statusMessage.innerHTML = statusData.message;
                        }
                    }, 2000);
                } else {
                    statusOverlay.className = 'status-overlay show';
                    statusMessage.innerHTML = '<div class="error-text">✗ ' + data.message + '</div>';
                    submitBtn.disabled = false;
                    submitBtn.textContent = '🚀 Görsel Oluştur';
                    setTimeout(() => {
                        statusOverlay.className = 'status-overlay';
                    }, 3000);
                }
            } catch (error) {
                statusOverlay.className = 'status-overlay show';
                statusMessage.innerHTML = '<div class="error-text">✗ Bir hata oluştu: ' + error.message + '</div>';
                submitBtn.disabled = false;
                submitBtn.textContent = '🚀 Görsel Oluştur';
                setTimeout(() => {
                    statusOverlay.className = 'status-overlay';
                }, 3000);
            }
        });
    </script>
</body>
</html>
'''

def get_token():
    global token
    # Eğer email veya şifre yoksa token almaya çalışma
    if not user_email or not user_password:
        return False
        
    url = "https://sp.deevid.ai/auth/v1/token?grant_type=password"
    headers = {
        "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.ewogICJyb2xlIjogImFub24iLAogICJpc3MiOiAic3VwYWJhc2UiLAogICJpYXQiOiAxNzM0OTY5NjAwLAogICJleHAiOiAxODkyNzM2MDAwCn0.4NnK23LGYvKPGuKI5rwQn2KbLMzzdE4jXpHwbGCqPqY",
    }
    payload = {
        "email": user_email,
        "password": user_password,
        "gotrue_meta_security": {}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        json_data = json.loads(response.text)
        
        if 'access_token' in json_data:
            token = json_data['access_token']
            return True
        else:
            print("Token hatası:", json_data)
            return False
            
    except Exception as e:
        print("Token bağlantı hatası:", e)
        return False

def get_quota():
    if not token:
        return 0
        
    url = "https://api.deevid.ai/subscription/plan"
    headers = {"authorization": "Bearer " + token}
    try:
        response = requests.get(url, headers=headers)
        quota = response.json()['data']['data']['message_quota']['quota_count'] - response.json()['data']['data']['message_quota']['subscription_quota_used']
        return quota
    except Exception as e:
        print("Kota hatası:", e)
        return 0

def upload_image(image_file):
    # Bu fonksiyon güncellendi (200 kontrolü kaldırıldı, JSON kontrolü eklendi)
    url = "https://api.deevid.ai/file-upload/image"
    headers = {"Authorization": "Bearer " + token}
    
    # Dosya içeriğini doğrudan requests'e veriyoruz
    files = {"file": (image_file.filename, image_file, image_file.content_type)}
    data = {"width": "1024", "height": "1536"}
    
    try:
        resp = requests.post(url, headers=headers, files=files, data=data)
        
        # Status code kontrolü yerine JSON içeriği kontrolü
        try:
            json_data = resp.json()
            if 'data' in json_data and 'data' in json_data['data'] and 'id' in json_data['data']['data']:
                return json_data['data']['data']['id']
            else:
                print("Beklenmedik API yanıtı:", json_data)
        except:
            print("JSON parse hatası, Raw:", resp.text)
            
    except Exception as e:
        print("Görsel yükleme hatası:", e)
    return None

def generate_image_task(prompt, image_size, count, resolution, model_type, model_version, user_image_id=None):
    global current_task_status
    
    if not token:
        current_task_status = {"status": "error", "message": "Oturum süresi dolmuş, sayfayı yenileyip giriş yapın.", "url": ""}
        return False
    
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
    
    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp_json = resp.json()
        
        if 'error' in resp_json and resp_json['error'] and resp_json['error']['code'] != 0:
            current_task_status = {"status": "error", "message": f"API Hatası veya Yetersiz Kota.", "url": ""}
            return False
            
    except Exception as e:
        current_task_status = {"status": "error", "message": f"İstek hatası: {str(e)}", "url": ""}
        return False
    
    current_task_status = {"status": "processing", "message": "Görsel oluşturuluyor...", "url": ""}
    
    # Görseli bekle
    url = "https://api.deevid.ai/my-assets?limit=20&assetType=All&filter=CREATION"
    headers = {"authorization": "Bearer " + token}
    
    max_attempts = 900  # 3 dakika
    attempt = 0
    
    while attempt < max_attempts:
        time.sleep(2)
        attempt += 1
        
        try:
            resp = requests.get(url, headers=headers).json()
            groups = resp["data"]["data"]["groups"]
        except:
            current_task_status = {"status": "error", "message": "API iletişim hatası", "url": ""}
            return False
        
        for group in groups:
            for item in group["items"]:
                if item["detail"]["creation"]["taskState"] == 'FAIL':
                    current_task_status = {"status": "error", "message": "Görsel oluşturma başarısız oldu", "url": ""}
                    return False
                
                creation = item["detail"]["creation"]
                image_urls = creation.get("noWaterMarkImageUrl", [])
                
                if image_urls:
                    current_task_status = {"status": "completed", "message": "Görsel hazır!", "url": image_urls[0]}
                    return True
        
        current_task_status = {"status": "processing", "message": f"Oluşturuluyor... ({attempt * 2}s)", "url": ""}
    
    current_task_status = {"status": "error", "message": "Zaman aşımı (3 dakika)", "url": ""}
    return False

@app.route('/')
def index():
    return render_template_string(
        HTML_TEMPLATE,
        image_sizes=IMAGE_SIZES,
        model_types=MODEL_TYPES,
        model_versions=MODEL_VERSIONS,
        resolutions=RESOLUTIONS,
        default_prompt=''
    )

@app.route('/login', methods=['POST'])
def login():
    global user_email, user_password
    
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        return jsonify({"success": False, "message": "E-posta ve şifre gerekli"})
    
    # Global değişkenleri güncelle
    user_email = email
    user_password = password
    
    # Token almayı dene
    if get_token():
        return jsonify({"success": True, "quota": get_quota()})
    else:
        # Hatalıysa globalleri sıfırla
        user_email = ""
        user_password = ""
        return jsonify({"success": False, "message": "Giriş başarısız. Bilgileri kontrol edin."})

@app.route('/quota')
def quota():
    return jsonify({"quota": get_quota()})

@app.route('/generate', methods=['POST'])
def generate():
    if not token:
         return jsonify({"success": False, "message": "Önce giriş yapmalısınız."})

    prompt = request.form.get('prompt')
    image_size = request.form.get('imageSize')
    count = request.form.get('count')
    resolution = request.form.get('resolution')
    model_type = request.form.get('modelType')
    model_version = request.form.get('modelVersion')
    image_file = request.files.get('image')
    
    user_image_id = None
    if image_file and image_file.filename:
        print("Görsel yükleniyor...")
        user_image_id = upload_image(image_file)
        if not user_image_id:
            return jsonify({"success": False, "message": "Görsel yüklenemedi, API hatası"})
        print(f"Görsel yüklendi: {user_image_id}")
    
    # Arka planda çalıştır
    thread = Thread(target=generate_image_task, args=(prompt, image_size, count, resolution, model_type, model_version, user_image_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "İşlem başlatıldı"})

@app.route('/status')
def status():
    return jsonify(current_task_status)

if __name__ == '__main__':
    print("Sunucu başlatılıyor... (Tarayıcıda http://localhost:5000 adresine gidin)")
    app.run(debug=True, host='0.0.0.0', port=5000)
