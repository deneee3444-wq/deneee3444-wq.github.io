from flask import Flask, render_template_string, request, Response
import base64
from curl_cffi import requests
import json
from pathlib import Path
import time
import uuid

app = Flask(__name__)

# Cookie string - Kendi cookie'lerinizi buraya koyun
COOKIE_STRING = """stblid=64c0788f-2da3-41e3-8045-ac4d0d1fa72c; x-anon-token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiNWFiNjZiYjMtZTEzYS00NzhhLWI3M2EtM2YyZTE0NGVmYzhjIiwidGVhbV9pZCI6bnVsbCwiZXhwIjoxNzkxODc4NzU3LCJpc19hbm9uX3VzZXIiOnRydWV9.Fo9Nm91QnvVrqaYI6F1DhdJIeCPtNqF8ykIQlYuhNdc; _ga=GA1.1.919478197.1764574701; i18nextLng=tr; x-anonuserid=0f0b189d-06dc-4b2f-a7ec-82b67091852f; x-challenge=Y%2BuhYOoyuXrGd%2B5SzSHx0MQjID%2B%2FsdBmKdae5U0j41I%2BkR9UU2I8aDezKSTrkcN8kwMdn1YmsO3LO%2FcwFjjn6flBbnPjxcP8vMgxEknJzrIoZ7LKHzSLLpSDjXDOqdIiDP8TSgYChpW4KsySOBPJrcrbp8bOiybxmfDyS9XvB8B%2FIpeSNxw%3D; x-signature=Po%2FWDHkbDcpDIa%2Fr1xCoFnWEmopx2P3cyFWywHrxxYkRdkgY2aVe9DCDquuwH7mJC6XHqqtURULZM0iWgK1jjg%3D%3D; sso=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzZXNzaW9uX2lkIjoiMTBmZDA1NWUtNzk3NC00YjAwLWFiMDUtNDBhN2JiMWI4MWQ0In0.hzyt96l2tXF-qJPIE_VIl77zaS_xvQyVsNHiRi8hEcQ; sso-rw=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzZXNzaW9uX2lkIjoiMTBmZDA1NWUtNzk3NC00YjAwLWFiMDUtNDBhN2JiMWI4MWQ0In0.hzyt96l2tXF-qJPIE_VIl77zaS_xvQyVsNHiRi8hEcQ; x-userid=c00677ff-6c73-4f75-a54c-8c2a65d6ec9b; mp_ea93da913ddb66b6372b89d97b1029ac_mixpanel=%7B%22distinct_id%22%3A%22c00677ff-6c73-4f75-a54c-8c2a65d6ec9b%22%2C%22%24device_id%22%3A%22221a43d4-d560-4913-9aa6-82bf51db419f%22%2C%22%24search_engine%22%3A%22google%22%2C%22%24initial_referrer%22%3A%22https%3A%2F%2Fwww.google.com%2F%22%2C%22%24initial_referring_domain%22%3A%22www.google.com%22%2C%22__mps%22%3A%7B%7D%2C%22__mpso%22%3A%7B%7D%2C%22__mpus%22%3A%7B%7D%2C%22__mpa%22%3A%7B%7D%2C%22__mpu%22%3A%7B%7D%2C%22__mpr%22%3A%5B%5D%2C%22__mpap%22%3A%5B%5D%2C%22%24user_id%22%3A%22c00677ff-6c73-4f75-a54c-8c2a65d6ec9b%22%7D; cf_clearance=x25yPl9rjzgd9IHr9QSdY8lAe5VWTso5xuDKlMncLxk-1764865756-1.2.1.1-pU3V68i_J6FstW5LCty0OuqbV8rGqkK2niVDy0WHnkdAw86lYiTHEGKpOFLdXq5E1NXWfuPBq2H_sJM6lQvZgP1w2qlwq1djpM8BMn.LpoacwAnhIj6mNzoVZbJSX1H2lAT25lvmVtXimWfL2wq_KJbSXxiRzKS06Z15JheUlILrjKyyCXOCq7E4Tn.w.3QsLiAfpzg7idb2adQiZqHRFmjJKTOMMd3bS0YbfZPEmfo; _ga_8FEWB057YH=GS2.1.s1764864548$o13$g1$t1764865755$j60$l0$h0"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grok Video Generator</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .main-container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .header h1 {
            color: white;
            font-size: 3em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            margin-bottom: 10px;
        }
        
        .header p {
            color: rgba(255,255,255,0.9);
            font-size: 1.2em;
        }
        
        .content-wrapper {
            display: grid;
            grid-template-columns: 450px 1fr;
            gap: 30px;
            align-items: start;
        }
        
        @media (max-width: 1024px) {
            .content-wrapper {
                grid-template-columns: 1fr;
            }
        }
        
        .left-panel {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            position: sticky;
            top: 20px;
        }
        
        .right-panel {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            min-height: 400px;
            display: none;
        }
        
        .right-panel.active {
            display: block;
        }
        
        .panel-title {
            color: #667eea;
            font-size: 1.8em;
            margin-bottom: 25px;
            text-align: center;
            font-weight: bold;
        }
        
        .upload-section {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 25px;
            border: 2px dashed #667eea;
            text-align: center;
            transition: all 0.3s;
        }
        
        .upload-section:hover {
            border-color: #764ba2;
            transform: translateY(-2px);
        }
        
        .file-input-wrapper {
            position: relative;
            overflow: hidden;
            display: inline-block;
            margin-bottom: 15px;
        }
        
        .file-input-wrapper input[type=file] {
            position: absolute;
            left: -9999px;
        }
        
        .file-input-label {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 35px;
            border-radius: 30px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s;
            display: inline-block;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        
        .file-input-label:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }
        
        .file-name {
            margin: 15px 0;
            color: #666;
            font-style: italic;
            font-size: 14px;
            min-height: 20px;
        }
        
        .input-group {
            margin-bottom: 20px;
        }
        
        .input-label {
            display: block;
            color: #667eea;
            font-weight: bold;
            margin-bottom: 8px;
            font-size: 14px;
        }
        
        input[type="text"] {
            width: 100%;
            padding: 14px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 30px;
            font-size: 16px;
            transition: all 0.3s;
            background: white;
        }
        
        input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
        }
        
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px 40px;
            border: none;
            border-radius: 30px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            width: 100%;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        
        .btn:hover:not(:disabled) {
            transform: translateY(-3px);
            box-shadow: 0 6px 25px rgba(102, 126, 234, 0.6);
        }
        
        .btn:disabled {
            background: linear-gradient(135deg, #ccc 0%, #999 100%);
            cursor: not-allowed;
            transform: none;
        }
        
        .progress-section {
            margin-bottom: 25px;
        }
        
        .progress-bar {
            width: 100%;
            height: 35px;
            background: #e0e0e0;
            border-radius: 20px;
            overflow: hidden;
            position: relative;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 14px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .log-section {
            background: #1e1e1e;
            color: #00ff00;
            padding: 20px;
            border-radius: 15px;
            height: 350px;
            min-height: 350px;
            max-height: 350px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            margin-bottom: 25px;
            box-shadow: inset 0 2px 8px rgba(0,0,0,0.3);
        }
        
        .log-section::-webkit-scrollbar {
            width: 10px;
        }
        
        .log-section::-webkit-scrollbar-track {
            background: #2a2a2a;
            border-radius: 10px;
        }
        
        .log-section::-webkit-scrollbar-thumb {
            background: #667eea;
            border-radius: 10px;
        }
        
        .log-entry {
            margin-bottom: 6px;
            line-height: 1.4;
        }
        
        .video-section {
            text-align: center;
        }
        
        .video-section h2 {
            color: #667eea;
            margin-bottom: 25px;
            font-size: 2em;
        }
        
        .video-container {
            position: relative;
            background: #000;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            margin-bottom: 20px;
        }
        
        video {
            width: 100%;
            height: auto;
            display: block;
        }
        
        .video-url-container {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 15px 20px;
            border-radius: 15px;
            margin-top: 20px;
            border: 2px solid #667eea;
        }
        
        .video-url-label {
            color: #667eea;
            font-weight: bold;
            margin-bottom: 8px;
            display: block;
        }
        
        .video-url {
            word-break: break-all;
            font-size: 13px;
            color: #666;
            background: white;
            padding: 10px;
            border-radius: 8px;
            font-family: monospace;
        }
        
        .loader {
            border: 5px solid #f3f3f3;
            border-top: 5px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 30px auto;
            display: none;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .status-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 20px;
        }
        
        .status-processing {
            background: #fff3cd;
            color: #856404;
        }
        
        .status-success {
            background: #d4edda;
            color: #155724;
        }
        
        .status-error {
            background: #f8d7da;
            color: #721c24;
        }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="header">
            <h1>🎬 Grok Video Generator</h1>
            <p>Resimlerinizi etkileyici videolara dönüştürün</p>
        </div>
        
        <div class="content-wrapper">
            <div class="left-panel">
                <h2 class="panel-title">Video Oluştur</h2>
                
                <form id="uploadForm" enctype="multipart/form-data">
                    <div class="upload-section">
                        <div class="file-input-wrapper">
                            <label class="file-input-label" for="imageFile">
                                📁 Resim Seç
                            </label>
                            <input type="file" id="imageFile" name="image" accept="image/*" required>
                        </div>
                        <div class="file-name" id="fileName">Henüz dosya seçilmedi</div>
                    </div>
                    
                    <div class="input-group">
                        <label class="input-label" for="prompt">🎨 Prompt (Hareket Türü)</label>
                        <input type="text" id="prompt" name="prompt" placeholder="Örn: kissing, dancing, walking..." value="kissing" required>
                    </div>
                    
                    <button type="submit" class="btn" id="submitBtn">🚀 Video Oluştur</button>
                </form>
            </div>
            
            <div class="right-panel" id="rightPanel">
                <div id="processingSection">
                    <h2 class="panel-title">İşlem Durumu</h2>
                    <div class="status-badge status-processing" id="statusBadge">⏳ İşleniyor...</div>
                    
                    <div class="loader" id="loader"></div>
                    
                    <div class="progress-section">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progressFill">0%</div>
                        </div>
                    </div>
                    
                    <div class="log-section" id="logSection"></div>
                </div>
                
                <div class="video-section" id="videoSection" style="display: none;">
                    <div class="status-badge status-success">✅ Başarıyla Tamamlandı!</div>
                    <h2>Videonuz Hazır!</h2>
                    <div class="video-container">
                        <video id="videoPlayer" controls autoplay loop></video>
                    </div>
                    <div class="video-url-container">
                        <span class="video-url-label">📎 Video Linki:</span>
                        <div class="video-url" id="videoUrl"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const fileInput = document.getElementById('imageFile');
        const fileName = document.getElementById('fileName');
        const form = document.getElementById('uploadForm');
        const submitBtn = document.getElementById('submitBtn');
        const loader = document.getElementById('loader');
        const progressFill = document.getElementById('progressFill');
        const logSection = document.getElementById('logSection');
        const rightPanel = document.getElementById('rightPanel');
        const processingSection = document.getElementById('processingSection');
        const videoSection = document.getElementById('videoSection');
        const videoPlayer = document.getElementById('videoPlayer');
        const videoUrl = document.getElementById('videoUrl');
        const statusBadge = document.getElementById('statusBadge');
        
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                fileName.textContent = '✓ ' + e.target.files[0].name;
                fileName.style.color = '#667eea';
                fileName.style.fontWeight = 'bold';
            }
        });
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(form);
            
            submitBtn.disabled = true;
            rightPanel.classList.add('active');
            processingSection.style.display = 'block';
            videoSection.style.display = 'none';
            loader.style.display = 'block';
            logSection.innerHTML = '';
            statusBadge.className = 'status-badge status-processing';
            statusBadge.textContent = '⏳ İşleniyor...';
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = ''; // Tampon bellek eklendi
                
                while (true) {
                    const {value, done} = await reader.read();
                    if (done) break;
                    
                    // Gelen veriyi tampona ekle
                    buffer += decoder.decode(value, {stream: true});
                    
                    // Satırlara böl
                    const lines = buffer.split('\\n');
                    
                    // Son parçayı tamponda tut (çünkü yarım kalmış olabilir)
                    buffer = lines.pop(); 
                    
                    for (let line of lines) {
                        line = line.trim();
                        if (line.startsWith('data: ')) {
                            try {
                                const jsonStr = line.slice(6);
                                const data = JSON.parse(jsonStr);
                                
                                if (data.type === 'log') {
                                    logSection.innerHTML += `<div class="log-entry">${data.message}</div>`;
                                    logSection.scrollTop = logSection.scrollHeight;
                                } else if (data.type === 'progress') {
                                    progressFill.style.width = data.percent + '%';
                                    progressFill.textContent = data.percent + '%';
                                } else if (data.type === 'video') {
                                    loader.style.display = 'none';
                                    processingSection.style.display = 'none';
                                    videoSection.style.display = 'block';
                                    
                                    videoPlayer.src = data.url;
                                    videoPlayer.load();
                                    
                                    videoPlayer.onloadeddata = function() {
                                        videoPlayer.play().catch(e => console.log('Autoplay engellendi:', e));
                                    };
                                    
                                    videoUrl.textContent = data.url;
                                } else if (data.type === 'error') {
                                    loader.style.display = 'none';
                                    statusBadge.className = 'status-badge status-error';
                                    statusBadge.textContent = '❌ Hata Oluştu';
                                    logSection.innerHTML += `<div class="log-entry" style="color:red">HATA: ${data.message}</div>`;
                                }
                            } catch (parseError) {
                                console.log("JSON Parse bekleniyor (parça henüz tamamlanmadı):", parseError);
                            }
                        }
                    }
                }
            } catch (error) {
                alert('❌ Bir hata oluştu: ' + error.message);
                loader.style.display = 'none';
                statusBadge.className = 'status-badge status-error';
                statusBadge.textContent = '❌ Bağlantı Hatası';
            } finally {
                submitBtn.disabled = false;
            }
        });
    </script>
</body>
</html>
"""

def get_mime_type(filename):
    ext = Path(filename).suffix.lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp'
    }
    return mime_types.get(ext, 'image/png')

def stream_log(message):
    return f"data: {json.dumps({'type': 'log', 'message': message})}\n\n"

def stream_progress(percent):
    return f"data: {json.dumps({'type': 'progress', 'percent': percent})}\n\n"

def stream_video(url):
    return f"data: {json.dumps({'type': 'video', 'url': url})}\n\n"

def stream_error(message):
    return f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload():
    # Request verisini önce al
    if 'image' not in request.files:
        return Response(stream_error('Dosya bulunamadı'), mimetype='text/event-stream')
    
    file = request.files['image']
    prompt = request.form.get('prompt', 'kissing')
    
    if file.filename == '':
        return Response(stream_error('Dosya seçilmedi'), mimetype='text/event-stream')
    
    # Dosya içeriğini oku
    file_content = file.read()
    file_name = file.filename
    
    def generate():
        try:
            # Step 1: Upload file
            yield stream_log('=== ADIM 1/6: Dosya yükleniyor ===')
            yield stream_progress(10)
            
            content = base64.b64encode(file_content).decode('utf-8')
            mime_type = get_mime_type(file_name)
            
            upload_data = {
                "fileName": file_name,
                "fileMimeType": mime_type,
                "content": content,
                "fileSource": "IMAGINE_SELF_UPLOAD_FILE_SOURCE"
            }
            
            base_headers = {
                'accept': '*/*',
                'accept-language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'baggage': 'sentry-environment=production,sentry-public_key=b311e0f2690c81f25e2c4cf6d4f7ce1c,sentry-trace_id=202b7d3952e2c60f10a15cc458a0fa35,sentry-org_id=4508179396558848,sentry-sampled=false,sentry-sample_rand=0.7954251187065458,sentry-sample_rate=0',
                'content-type': 'application/json',
                'origin': 'https://grok.com',
                'priority': 'u=1, i',
                'referer': 'https://grok.com/imagine/favorites',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
                'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'x-statsig-id': 'DXMG4qLzmlpIqv7NtEukJJn5niMDan0lX6hXOJjH+uUiWQSS0WW2l8iVdUHq7x1fXale7wnVGf7XNg+lhdIaSoNZn6T2Dg',
                'cookie': COOKIE_STRING
            }
            
            response = requests.post(
                'https://grok.com/rest/app-chat/upload-file',
                headers=base_headers,
                json=upload_data,
                impersonate="chrome131"
            )
            
            time.sleep(0.5)
            
            if response.status_code != 200:
                yield stream_error(f"Upload failed: {response.status_code} - {response.text}")
                return
            
            result = response.json()
            asset_id = result.get('fileMetadataId')
            
            if not asset_id:
                yield stream_error('Asset ID bulunamadı')
                return
            
            yield stream_log(f'✓ File Metadata ID: {asset_id}')
            yield stream_progress(30)
            
            # Step 2: Get asset
            yield stream_log('=== ADIM 2/6: Asset bilgisi alınıyor ===')
            
            headers2 = base_headers.copy()
            headers2['sentry-trace'] = '242f7189728a9f9da1e3fdee465a832a-99bea42027a80bfa-0'
            headers2['traceparent'] = '00-53ab23cd3ebb839159e93b6c8bacd7c4-15bbc37dc722f531-00'
            headers2['x-statsig-id'] = 'gKXy4mQ2oM2fj9kjr6rKDRTrvd+/JLyoLxsr6anBytdBSJ/ufQejK5kN1jPwKGv0QE29X4SU6wdPp+LU4merbJ6gnouogw'
            headers2['x-xai-request-id'] = '9702b39c-3274-44cd-b19c-cfc0a59d1f1d'
            del headers2['content-type']
            
            response = requests.get(
                f'https://grok.com/rest/assets/{asset_id}',
                headers=headers2,
                impersonate="chrome131"
            )
            
            time.sleep(0.5)
            
            if response.status_code != 200:
                yield stream_error(f'Get asset failed: {response.status_code}')
                return
            
            asset_data = response.json()
            file_uri = asset_data.get('key') or result.get('fileUri')
            
            if file_uri:
                media_url = f"https://assets.grok.com/{file_uri}"
            else:
                media_url = asset_data.get('url')
            
            yield stream_log(f'✓ Media URL: {media_url}')
            yield stream_progress(50)
            
            # Step 3: Create media post
            yield stream_log('=== ADIM 3/6: Media post oluşturuluyor ===')
            
            media_data = {
                "mediaType": "MEDIA_POST_TYPE_IMAGE",
                "mediaUrl": media_url
            }
            
            headers3 = base_headers.copy()
            headers3['sentry-trace'] = '242f7189728a9f9da1e3fdee465a832a-b40d59c71a5217b1-0'
            headers3['traceparent'] = '00-3f9832bdd7dc1da9a57cd712c5a11b4b-b2482a5d4b208ac1-00'
            headers3['x-statsig-id'] = '686ZiQ9dy6b05LJJxMGhZn+A1rTUT9fDRHBAgsKqobwqI/SFFmzIQPJmvVibQwCfKybWNO9Z1QqEplPEQzmgBOlRPo5V6A'
            headers3['x-xai-request-id'] = '84635c7b-abdc-4e75-9846-0a33e25947f9'
            
            response = requests.post(
                'https://grok.com/rest/media/post/create',
                headers=headers3,
                json=media_data,
                impersonate="chrome131"
            )
            
            time.sleep(0.5)
            yield stream_log(f'✓ Media post oluşturuldu: {response.status_code}')
            yield stream_progress(60)
            
            # Step 4: Skip CDN
            yield stream_log('=== ADIM 4/6: CDN analytics (atlandı) ===')
            yield stream_progress(70)
            
            # Step 5: Create conversation and wait for video
            yield stream_log('=== ADIM 5/6: Video oluşturuluyor (bu biraz sürebilir...) ===')
            
            conversation_data = {
                "temporary": True,
                "modelName": "grok-3",
                "message": f"{media_url} {prompt} --mode=custom",
                "fileAttachments": [asset_id],
                "toolOverrides": {"videoGen": True},
                "responseMetadata": {
                    "modelConfigOverride": {
                        "modelMap": {
                            "videoGenModelConfig": {
                                "parentPostId": asset_id,
                                "aspectRatio": "2:3",
                                "videoLength": 6
                            }
                        }
                    }
                }
            }
            
            headers5 = base_headers.copy()
            headers5['referer'] = f'https://grok.com/imagine/post/{asset_id}'
            
            response = requests.post(
                'https://grok.com/rest/app-chat/conversations/new',
                headers=headers5,
                json=conversation_data,
                impersonate="chrome131",
                stream=True
            )
            
            yield stream_progress(80)
            yield stream_log(f'Conversation response: {response.status_code}')
            
            if response.status_code == 200:
                video_url = None
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8'))
                            if 'result' in data and 'response' in data['result']:
                                streaming_response = data['result']['response'].get('streamingVideoGenerationResponse', {})
                                progress = streaming_response.get('progress', 0)
                                
                                if progress > 0:
                                    yield stream_log(f'Video oluşturma: %{progress}')
                                
                                if progress == 100:
                                    video_url = streaming_response.get('videoUrl')
                                    if video_url:
                                        full_video_url = f"https://assets.grok.com/{video_url}"
                                        yield stream_log(f'✓ Video URL: {full_video_url}')
                                        yield stream_progress(90)
                                        break
                        except Exception as e:
                            yield stream_log(f'Parse error: {str(e)}')
                
                if not video_url:
                    yield stream_error('Video URL bulunamadı')
                    return
            else:
                yield stream_error(f'Conversation oluşturulamadı: {response.status_code} - {response.text[:500]}')
                return
            
            # Step 6: Like post
            yield stream_log('=== ADIM 6/6: Post beğeniliyor ===')
            
            like_data = {"id": asset_id}
            headers6 = base_headers.copy()
            headers6['referer'] = f'https://grok.com/imagine/post/{asset_id}'
            headers6['sentry-trace'] = '242f7189728a9f9da1e3fdee465a832a-b6e6a95e1aaa213d-0'
            headers6['traceparent'] = '00-46104c8e3c097d077033910fe0b67c2c-e1abd21f92ffcf57-00'
            headers6['x-statsig-id'] = 'T2o9Lav5bwJQQBbsYGUFwtskchBw63Nn4NTkJmYOBRiOh1Ahsshs5FbCGfw/56Q7j4FykEs3PDMrYdu31xi1/2j7g+p6TA'
            headers6['x-xai-request-id'] = 'b9fc5407-8313-46b5-a7e6-54bc03211b2b'
            
            response = requests.post(
                'https://grok.com/rest/media/post/like',
                headers=headers6,
                json=like_data,
                impersonate="chrome131"
            )
            
            yield stream_log(f'✓ Like status: {response.status_code}')
            yield stream_progress(100)
            
            yield stream_log('=== ✓✓✓ TÜM İŞLEMLER TAMAMLANDI ✓✓✓ ===')
            yield stream_video(full_video_url)
            
        except Exception as e:
            yield stream_error(str(e))
            yield stream_log(f'✗ HATA: {str(e)}')
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
