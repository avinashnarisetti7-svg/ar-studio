import os
import re
import sqlite3
import io
import base64
import qrcode
from flask import Flask, request, render_template_string, redirect, url_for, jsonify, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "arcut-pro-secret-2026")

FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY", "")
FIREBASE_AUTH_DOMAIN = os.environ.get("FIREBASE_AUTH_DOMAIN", "")
CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
UPLOAD_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "")

UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
DB_NAME = "arcut_cloud_v7.db"

FREE_QUOTA_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB Free per Gmail
ONE_GB_BYTES = 1 * 1024 * 1024 * 1024

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            display_name TEXT,
            studio_slug TEXT UNIQUE,
            studio_name TEXT,
            tagline TEXT,
            whatsapp TEXT,
            theme TEXT DEFAULT 'dark',
            quota_bytes INTEGER DEFAULT 5368709120,
            used_bytes INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ar_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_email TEXT,
            studio_slug TEXT,
            title TEXT,
            photo_url TEXT,
            video_url TEXT,
            mind_url TEXT,
            size_bytes INTEGER DEFAULT 0,
            FOREIGN KEY(owner_email) REFERENCES users(email)
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def make_slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-') or "studio"

def generate_qr_base64(url):
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

LOGIN_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AR Cut PRO - Gmail Cloud Sign In</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 0; background: #09090b; color: #f4f4f5;
            display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px;
        }
        .card {
            background: #141417; border: 1px solid #2a2a32; border-radius: 22px;
            padding: 28px 22px; max-width: 400px; width: 100%; text-align: center;
        }
        .badge { background: linear-gradient(135deg, #00f2fe, #4facfe); color: #000; font-size: 11px; font-weight: 900; padding: 3px 9px; border-radius: 8px; }
        h1 { font-size: 23px; margin: 12px 0 6px; }
        p { color: #a1a1aa; font-size: 13px; margin-bottom: 18px; line-height: 1.5; }
        .info-box {
            background: #1f1f24; border: 1px solid #2e2e38; border-radius: 14px;
            padding: 12px; margin-bottom: 18px; font-size: 12px; text-align: left;
        }
        .info-box div { margin: 5px 0; }
        .google-btn {
            width: 100%; padding: 14px; border-radius: 12px; border: none;
            background: #ffffff; color: #09090b; font-weight: 800; font-size: 15px;
            cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 10px;
        }
        input {
            width: 100%; padding: 12px; border-radius: 10px; border: 1px solid #2a2a32;
            background: #1f1f24; color: #fff; margin: 8px 0; box-sizing: border-box; font-size: 14px;
        }
        .sub-btn {
            width: 100%; padding: 13px; border-radius: 12px; border: none; margin-top: 6px;
            background: linear-gradient(135deg, #00f2fe, #4facfe); color: #000;
            font-weight: 800; font-size: 14px; cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">AR CUT PRO</span>
        <h1>Creator Cloud Studio</h1>
        <p>Sign in with your Gmail to save your AR albums, personal studio link & 5 GB cloud storage.</p>

        <div class="info-box">
            <div>[OK] <b>5 GB Free Cloud Storage</b> per Gmail</div>
            <div>[OK] <b>Real Image-Tracking WebAR</b> Camera</div>
            <div>[OK] <b>Private Dashboard</b> linked to your Gmail</div>
        </div>

        {% if firebase_api_key %}
        <button type="button" class="google-btn" onclick="googleSignIn()">
            <span style="color:#4285F4; font-weight:900;">G</span> Continue with Google (Gmail)
        </button>
        {% else %}
        <form method="POST" action="/auth_gmail">
            <input type="email" name="email" placeholder="Enter your Gmail (name@gmail.com)" required>
            <input type="text" name="name" placeholder="Studio / Creator Name" required>
            <button type="submit" class="sub-btn">Continue with Gmail</button>
        </form>
        {% endif %}
    </div>

    {% if firebase_api_key %}
    <script type="module">
        import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.0/firebase-app.js";
        import { getAuth, signInWithPopup, GoogleAuthProvider } from "https://www.gstatic.com/firebasejs/11.0.0/firebase-auth.js";

        const app = initializeApp({
            apiKey: "{{ firebase_api_key }}",
            authDomain: "{{ firebase_auth_domain }}"
        });
        const auth = getAuth(app);
        const provider = new GoogleAuthProvider();

        window.googleSignIn = async () => {
            try {
                const res = await signInWithPopup(auth, provider);
                const u = res.user;
                const form = document.createElement("form");
                form.method = "POST";
                form.action = "/auth_gmail";
                form.innerHTML = `<input name="email" value="${u.email}"><input name="name" value="${u.displayName || u.email.split('@')[0]}">`;
                document.body.appendChild(form);
                form.submit();
            } catch (e) {
                alert("Google Sign-In Error: " + e.message);
            }
        };
    </script>
    {% endif %}
</body>
</html>
"""

CAPCUT_BUILDER_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>AR Cut Studio - {{ user.studio_name }}</title>
    <style>
        :root {
            --bg: #09090b; --surface: #141417; --surface-2: #1f1f24;
            --border: #2a2a32; --accent: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            --text: #f4f4f5; --muted: #a1a1aa;
        }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 0 0 85px 0; background: var(--bg); color: var(--text); }
        .topbar {
            position: sticky; top: 0; z-index: 50; background: rgba(9, 9, 11, 0.94); backdrop-filter: blur(12px);
            padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border);
        }
        .brand { font-weight: 800; font-size: 16px; display: flex; align-items: center; gap: 6px; }
        .brand-badge { background: var(--accent); color: #000; font-size: 10px; font-weight: 900; padding: 2px 7px; border-radius: 6px; }
        .export-btn { background: var(--accent); color: #000; text-decoration: none; font-weight: 700; font-size: 12px; padding: 8px 13px; border-radius: 20px; }
        .container { padding: 14px; max-width: 520px; margin: auto; }

        .storage-bar-card {
            background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
            padding: 12px 14px; margin-bottom: 14px;
        }
        .storage-top { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px; }
        .quota-track { width: 100%; height: 7px; background: #27272a; border-radius: 6px; overflow: hidden; }
        .quota-fill { height: 100%; background: {{ '#ef4444' if pct_used >= 90 else 'linear-gradient(90deg, #00f2fe, #4facfe)' }}; width: {{ pct_used }}%; }

        .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 15px; margin-bottom: 15px; }
        .panel-title { font-size: 12px; font-weight: 700; color: var(--muted); text-transform: uppercase; margin-bottom: 10px; display: flex; justify-content: space-between; }
        .canvas-box {
            background: #000; border: 1px solid var(--border); border-radius: 14px;
            height: 175px; display: flex; align-items: center; justify-content: center;
            overflow: hidden; margin-bottom: 12px; gap: 8px; padding: 8px;
        }
        .canvas-box img, .canvas-box video { height: 100%; width: 48%; object-fit: cover; border-radius: 10px; border: 1px solid #333; }
        .canvas-placeholder { color: var(--muted); font-size: 12px; text-align: center; }
        .track-row {
            background: var(--surface-2); border: 1px solid var(--border); border-radius: 12px;
            padding: 10px 12px; margin-bottom: 9px; display: flex; align-items: center; justify-content: space-between;
        }
        .track-info { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; }
        .track-tag { font-size: 10px; padding: 3px 7px; border-radius: 6px; font-weight: 800; }
        .tag-img { background: rgba(0, 242, 254, 0.15); color: #00f2fe; }
        .tag-vid { background: rgba(168, 85, 247, 0.2); color: #c084fc; }
        .file-trigger { background: #27272f; color: #fff; padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid #3f3f46; }
        input[type="text"], select { width: 100%; padding: 11px 12px; margin: 6px 0 12px; border-radius: 10px; border: 1px solid var(--border); background: var(--surface-2); color: #fff; font-size: 14px; }
        .primary-btn { width: 100%; padding: 14px; border: none; border-radius: 12px; background: var(--accent); color: #000; font-weight: 800; font-size: 15px; cursor: pointer; margin-top: 6px; }
        .primary-btn:disabled { background: #3f3f46; color: #a1a1aa; }
        .progress-wrap { display: none; margin-top: 12px; background: var(--surface-2); border-radius: 10px; padding: 12px; border: 1px solid #00f2fe44; }
        .bar-bg { width: 100%; height: 8px; background: #27272a; border-radius: 6px; overflow: hidden; margin-top: 8px; }
        .bar-fill { width: 0%; height: 100%; background: var(--accent); transition: width 0.2s; }

        .project-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .project-card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; overflow: hidden; }
        .project-card img { width: 100%; height: 125px; object-fit: cover; display: block; }
        .project-meta { padding: 10px; }
        .project-meta h4 { margin: 0 0 6px; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .project-actions { display: flex; gap: 6px; }
        .mini-btn { flex: 1; text-align: center; padding: 6px; border-radius: 8px; font-size: 11px; font-weight: 700; text-decoration: none; border: none; cursor: pointer; }
        .btn-scan { background: #00f2fe22; color: #00f2fe; }
        .btn-del { background: #ef444422; color: #f87171; }

        .bottom-nav {
            position: fixed; bottom: 0; left: 0; width: 100%; z-index: 60;
            background: rgba(14, 14, 18, 0.96); backdrop-filter: blur(14px);
            border-top: 1px solid var(--border); display: flex; justify-content: space-around; padding: 10px 0 12px;
        }
        .nav-item { background: none; border: none; color: var(--muted); font-size: 11px; font-weight: 600; display: flex; flex-direction: column; align-items: center; gap: 4px; cursor: pointer; }
        .nav-item.active { color: #00f2fe; }
        .tab-section { display: none; }
        .tab-section.active { display: block; }
        .qr-card { background: #fff; color: #000; padding: 18px; border-radius: 16px; text-align: center; }
    </style>
</head>
<body>
    <div class="topbar">
        <div class="brand">AR Cut <span class="brand-badge">PRO</span></div>
        <a href="/studio/{{ user.studio_slug }}" target="_blank" class="export-btn">Live Site</a>
    </div>

    <div class="container">
        <div class="storage-bar-card">
            <div class="storage-top">
                <span><b>{{ user.email }}</b></span>
                <span><b>{{ used_gb }} GB</b> / {{ quota_gb }} GB</span>
            </div>
            <div class="quota-track"><div class="quota-fill"></div></div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                <span style="color:#00f2fe; font-size:11px; font-weight:600;">5 GB Free Cloud Plan Active</span>
                <a href="/logout" style="color:#a1a1aa; font-size:11px; text-decoration:none;">Logout</a>
            </div>
        </div>

        <div id="tab-edit" class="tab-section active">
            <div class="panel">
                <div class="panel-title"><span>Preview Canvas</span><span>Auto AR</span></div>
                <div class="canvas-box" id="canvasPreview">
                    <div class="canvas-placeholder">Select Photo & Video tracks below to preview</div>
                </div>

                <input type="text" id="arTitle" placeholder="Project Name (Ex: Wedding Reception AR)">

                <div class="track-row">
                    <div class="track-info">
                        <span class="track-tag tag-img">PHOTO</span>
                        <span id="photoLabel">Target Album Photo</span>
                    </div>
                    <label class="file-trigger">
                        + Add Photo
                        <input type="file" id="arPhoto" accept="image/*" hidden onchange="previewMedia()">
                    </label>
                </div>

                <div class="track-row">
                    <div class="track-info">
                        <span class="track-tag tag-vid">VIDEO</span>
                        <span id="videoLabel">AR Overlay MP4</span>
                    </div>
                    <label class="file-trigger">
                        + Add Video
                        <input type="file" id="arVideo" accept="video/mp4,video/*" hidden onchange="previewMedia()">
                    </label>
                </div>

                <button type="button" id="uploadBtn" class="primary-btn" onclick="startFastARUpload()">Render & Publish AR</button>

                <div class="progress-wrap" id="progressWrap">
                    <div id="statusText" style="font-size:12px; font-weight:600; color:#00f2fe;">Initializing...</div>
                    <div class="bar-bg"><div class="bar-fill" id="barFill"></div></div>
                </div>
            </div>
        </div>

        <div id="tab-projects" class="tab-section">
            <div class="panel-title"><span>My AR Projects ({{ items|length }})</span><span>{{ user.studio_name }}</span></div>
            {% if not items %}
                <div class="panel" style="text-align:center; color:var(--muted); padding:35px 15px;">
                    No AR projects yet. Tap <b>Studio</b> tab to create one!
                </div>
            {% endif %}
            <div class="project-grid">
                {% for item in items %}
                <div class="project-card">
                    <img src="{{ item.photo_url }}">
                    <div class="project-meta">
                        <h4>{{ item.title }}</h4>
                        <div style="font-size:10px; color:var(--muted); margin-bottom:6px;">Size: {{ (item.size_bytes / (1024*1024))|round(1) }} MB</div>
                        <div class="project-actions">
                            <a href="/ar_scan/{{ user.studio_slug }}?id={{ item.id }}" class="mini-btn btn-scan">Test AR</a>
                            <form method="POST" action="/delete_ar/{{ item.id }}" style="flex:1; margin:0;">
                                <button type="submit" class="mini-btn btn-del" style="width:100%;">Delete</button>
                            </form>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <div id="tab-brand" class="tab-section">
            <div class="panel">
                <div class="panel-title"><span>Studio Branding</span></div>
                <form method="POST" action="/save_studio">
                    <input type="text" name="studio_name" value="{{ user.studio_name }}" placeholder="Studio Name" required>
                    <input type="text" name="tagline" value="{{ user.tagline }}" placeholder="Tagline" required>
                    <input type="text" name="whatsapp" value="{{ user.whatsapp }}" placeholder="WhatsApp (with 91)" required>
                    <select name="theme">
                        <option value="dark" {% if user.theme == 'dark' %}selected{% endif %}>Dark Luxury (Gold & Black)</option>
                        <option value="light" {% if user.theme == 'light' %}selected{% endif %}>Minimal Classic White</option>
                    </select>
                    <button type="submit" class="primary-btn">Save Studio Profile</button>
                </form>
            </div>

            <div class="panel">
                <div class="panel-title"><span>Album Print QR Code</span></div>
                <div class="qr-card">
                    <img src="data:image/png;base64,{{ qr_b64 }}" width="165" height="165"><br>
                    <strong style="font-size:13px;">{{ user.studio_name }} - AR Scanner</strong><br><br>
                    <a href="data:image/png;base64,{{ qr_b64 }}" download="{{ user.studio_slug }}-ar-qr.png" style="background:#09090b; color:#fff; padding:9px 16px; border-radius:10px; text-decoration:none; font-size:12px; font-weight:700;">Download Print QR</a>
                </div>
            </div>
        </div>
    </div>

    <div class="bottom-nav">
        <button type="button" class="nav-item active" onclick="switchTab('edit', this)">
            <span style="font-size:18px;">+</span><span>Studio</span>
        </button>
        <button type="button" class="nav-item" onclick="switchTab('projects', this)">
            <span style="font-size:18px;">#</span><span>Projects ({{ items|length }})</span>
        </button>
        <button type="button" class="nav-item" onclick="switchTab('brand', this)">
            <span style="font-size:18px;">*</span><span>Brand & QR</span>
        </button>
    </div>
    <script>
        const remainingBytes = {{ user.quota_bytes - user.used_bytes }};
        const CLOUD_NAME = "{{ cloud_name }}";
        const UPLOAD_PRESET = "{{ upload_preset }}";

        function switchTab(tabName, el) {
            document.querySelectorAll('.tab-section').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById('tab-' + tabName).classList.add('active');
            el.classList.add('active');
        }

        function previewMedia() {
            const pFile = document.getElementById('arPhoto').files[0];
            const vFile = document.getElementById('arVideo').files[0];
            const canvas = document.getElementById('canvasPreview');

            if (pFile) document.getElementById('photoLabel').innerText = pFile.name.slice(0, 18);
            if (vFile) document.getElementById('videoLabel').innerText = vFile.name.slice(0, 18);

            if (pFile || vFile) {
                canvas.innerHTML = '';
                if (pFile) {
                    const img = document.createElement('img');
                    img.src = URL.createObjectURL(pFile);
                    canvas.appendChild(img);
                }
                if (vFile) {
                    const vid = document.createElement('video');
                    vid.src = URL.createObjectURL(vFile);
                    vid.muted = true; vid.autoplay = true; vid.loop = true; vid.playsInline = true;
                    canvas.appendChild(vid);
                }
            }
        }

        function uploadToCloudinary(file, resourceType, onProgress) {
            return new Promise((resolve, reject) => {
                const url = `https://api.cloudinary.com/v1_1/${CLOUD_NAME}/${resourceType}/upload`;
                const xhr = new XMLHttpRequest();
                const fd = new FormData();
                fd.append("file", file);
                fd.append("upload_preset", UPLOAD_PRESET);

                xhr.open("POST", url, true);
                xhr.upload.onprogress = (e) => {
                    if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
                };
                xhr.onload = () => {
                    if (xhr.status === 200) {
                        resolve(JSON.parse(xhr.responseText).secure_url);
                    } else {
                        reject(new Error("Cloudinary upload failed"));
                    }
                };
                xhr.onerror = () => reject(new Error("Network error"));
                xhr.send(fd);
            });
        }

        async function uploadFileInChunks(file, prefix, onProgress) {
            const chunkSize = 2 * 1024 * 1024;
            const totalChunks = Math.ceil(file.size / chunkSize);
            const safeName = prefix + "_" + Date.now() + "_" + file.name.replace(/[^a-zA-Z0-9._-]/g, '');

            for (let i = 0; i < totalChunks; i++) {
                const start = i * chunkSize;
                const end = Math.min(file.size, start + chunkSize);
                const chunk = file.slice(start, end);

                const formData = new FormData();
                formData.append("chunk", chunk);
                formData.append("filename", safeName);
                formData.append("chunkIndex", i);
                formData.append("totalChunks", totalChunks);

                const res = await fetch("/upload_chunk", { method: "POST", body: formData });
                if (!res.ok) throw new Error("Chunk upload failed");
                onProgress(Math.round(((i + 1) / totalChunks) * 100));
            }
            return "/static/uploads/" + safeName;
        }

        function loadImage(file) {
            return new Promise((resolve, reject) => {
                const img = new Image();
                img.onload = () => resolve(img);
                img.onerror = () => reject(new Error("Image load failed"));
                img.src = URL.createObjectURL(file);
            });
        }
    </script>

        <script>
        async function startFastARUpload() {
            const title = document.getElementById("arTitle").value.trim();
            const photoFile = document.getElementById("arPhoto").files[0];
            const videoFile = document.getElementById("arVideo").files[0];

            if (!title || !photoFile || !videoFile) {
                alert("Please enter Project Name and add both Photo & Video!");
                return;
            }

            if ((photoFile.size + videoFile.size) > remainingBytes) {
                alert("5 GB Free Storage Limit Reached! Delete an old project to free space.");
                return;
            }

            const btn = document.getElementById("uploadBtn");
            const wrap = document.getElementById("progressWrap");
            const status = document.getElementById("statusText");
            const bar = document.getElementById("barFill");

            btn.disabled = true;
            wrap.style.display = "block";
            status.innerText = "1/3 Loading AR Engine & Compiling Photo...";
            bar.style.width = "10%";

            try {
                const img = await loadImage(photoFile);
                const mindarMod = await import("https://cdn.jsdelivr.net/npm/mind-ar@1.2.5/dist/mindar-image.prod.js");
                const CompilerClass = mindarMod.Compiler || (window.MINDAR && window.MINDAR.IMAGE && window.MINDAR.IMAGE.Compiler);
                if (!CompilerClass) throw new Error("AR Compiler could not initialize.");

                const compiler = new CompilerClass();
                await compiler.compileImageTargets([img], (progress) => {
                    bar.style.width = (10 + Math.round(progress * 0.30)) + "%";
                });
                const exportedBuffer = await compiler.exportData();
                const mindFile = new File([new Blob([exportedBuffer])], "target.mind");

                status.innerText = "2/3 Uploading Target Photo...";
                let photoUrl, mindUrl, videoUrl;

                if (CLOUD_NAME && UPLOAD_PRESET) {
                    photoUrl = await uploadToCloudinary(photoFile, "image", () => {});
                    mindUrl = await uploadToCloudinary(mindFile, "raw", () => {});
                    bar.style.width = "50%";
                    status.innerText = "3/3 Uploading Video to Cloud: 0%";
                    videoUrl = await uploadToCloudinary(videoFile, "video", (pct) => {
                        status.innerText = `3/3 Uploading Video to Cloud: ${pct}%`;
                        bar.style.width = (50 + Math.round(pct * 0.5)) + "%";
                    });
                } else {
                    photoUrl = await uploadFileInChunks(photoFile, "{{ user.studio_slug }}_img", () => {});
                    mindUrl = await uploadFileInChunks(mindFile, "{{ user.studio_slug }}_mind", () => {});
                    bar.style.width = "50%";
                    status.innerText = "3/3 Uploading Video: 0%";
                    videoUrl = await uploadFileInChunks(videoFile, "{{ user.studio_slug }}_vid", (pct) => {
                        status.innerText = `3/3 Uploading Video: ${pct}%`;
                        bar.style.width = (50 + Math.round(pct * 0.5)) + "%";
                    });
                }

                const totalSavedBytes = photoFile.size + videoFile.size + mindFile.size;
                const saveRes = await fetch("/save_ar_item", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        title, photo_url: photoUrl, video_url: videoUrl,
                        mind_url: mindUrl, size_bytes: totalSavedBytes
                    })
                });
                const saveData = await saveRes.json();
                if (!saveRes.ok) throw new Error(saveData.error || "Save failed");

                status.innerText = "Saved to your Gmail Cloud! Reloading...";
                setTimeout(() => location.reload(), 600);

            } catch (err) {
                alert("Error: " + err.message);
                btn.disabled = false;
                wrap.style.display = "none";
            }
        }
    </script>

</body>
</html>
"""

PORTFOLIO_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ studio.studio_name }} - AR Portfolio</title>
    <style>
        body {
            font-family: -apple-system, sans-serif; margin: 0; padding: 20px; text-align: center;
            background: {{ '#09090b' if studio.theme == 'dark' else '#f8fafc' }};
            color: {{ '#fafafa' if studio.theme == 'dark' else '#0f172a' }};
        }
        .hero { padding: 32px 12px; border-bottom: 1px solid #27272a; }
        .badge { background: linear-gradient(135deg, #00f2fe, #4facfe); color: #000; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 800; }
        .ar-card { background: {{ '#141417' if studio.theme == 'dark' else '#ffffff' }}; padding: 15px; border-radius: 18px; margin: 20px auto; max-width: 420px; border: 1px solid #27272a; }
        img { width: 100%; border-radius: 12px; margin-top: 10px; }
        .btn { display: inline-block; margin: 8px 4px; padding: 12px 22px; border-radius: 25px; text-decoration: none; font-weight: 700; font-size: 14px; }
        .wa-btn { background: #25D366; color: #fff; }
        .cam-btn { background: linear-gradient(135deg, #00f2fe, #4facfe); color: #000; }
    </style>
</head>
<body>
    <div class="hero">
        <h1>{{ studio.studio_name }}</h1>
        <p style="opacity:0.8;">{{ studio.tagline }}</p>
        <a class="btn wa-btn" href="https://wa.me/{{ studio.whatsapp }}?text=Hi {{ studio.studio_name }}, I saw your AR Portfolio!" target="_blank">Book on WhatsApp</a>
        <a class="btn cam-btn" href="/ar_scan/{{ studio.studio_slug }}">Open Live AR Scanner</a>
    </div>

    <h3>Interactive AR Albums</h3>
    {% for item in items %}
    <div class="ar-card">
        <span class="badge">REAL AR TRACKING</span>
        <h4>{{ item.title }}</h4>
        <img src="{{ item.photo_url }}">
        <br><br>
        <a class="btn cam-btn" href="/ar_scan/{{ studio.studio_slug }}?id={{ item.id }}">Scan This Photo</a>
    </div>
    {% endfor %}
</body>
</html>
"""

REAL_AR_SCANNER_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Live AR Scanner - {{ studio.studio_name }}</title>
    <script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/mind-ar@1.2.5/dist/mindar-image-aframe.prod.js"></script>
    <style>
        body { margin: 0; overflow: hidden; font-family: sans-serif; }
        .hud { position: fixed; top: 0; left: 0; width: 100%; z-index: 999; background: rgba(9,9,11,0.85); color: #fff; padding: 12px; text-align: center; border-bottom: 1px solid #27272a; }
        .bottom-hud { position: fixed; bottom: 18px; left: 0; width: 100%; z-index: 999; text-align: center; }
        .btn { background: #ef4444; color: #fff; padding: 10px 18px; border-radius: 20px; text-decoration: none; font-weight: bold; margin: 0 5px; border: none; font-size: 13px; }
        select { padding: 10px; border-radius: 12px; font-weight: bold; background: #141417; color: #fff; border: 1px solid #3f3f46; }
    </style>
</head>
<body>
    <div class="hud">
        <strong>{{ studio.studio_name }} - Live AR Camera</strong><br>
        <small id="scanHint" style="color:#00f2fe;">Point camera directly at the album photo</small>
    </div>

    {% if active_item %}
    <a-scene
        mindar-image="imageTargetSrc: {{ active_item.mind_url }}; autoStart: true; uiScanning: yes;"
        color-space="sRGB"
        renderer="colorManagement: true, physicallyCorrectLights"
        vr-mode-ui="enabled: false"
        device-orientation-permission-ui="enabled: false">
        
        <a-assets>
            <video id="arVid" src="{{ active_item.video_url }}" preload="auto" loop crossorigin="anonymous" playsinline webkit-playsinline></video>
        </a-assets>

        <a-camera position="0 0 0" look-controls="enabled: false"></a-camera>

        <a-entity id="targetEntity" mindar-image-target="targetIndex: 0">
            <a-video src="#arVid" position="0 0 0" height="0.75" width="1" rotation="0 0 0"></a-video>
        </a-entity>
    </a-scene>

    <div class="bottom-hud">
        {% if all_items|length > 1 %}
        <select onchange="location.href='/ar_scan/{{ studio.slug }}?id=' + this.value">
            {% for it in all_items %}
            <option value="{{ it.id }}" {% if it.id == active_item.id %}selected{% endif %}>{{ it.title }}</option>
            {% endfor %}
        </select>
        {% endif %}
        <button type="button" class="btn" style="background:#00f2fe; color:#000;" onclick="document.getElementById('arVid').muted=false; document.getElementById('arVid').play();">Unmute</button>
        <a class="btn" href="/studio/{{ studio.studio_slug }}">Exit</a>
    </div>

    <script>
        const target = document.getElementById('targetEntity');
        const vid = document.getElementById('arVid');
        const hint = document.getElementById('scanHint');

        target.addEventListener("targetFound", () => {
            hint.innerText = "Photo Detected! Playing AR Video...";
            vid.play();
        });

        target.addEventListener("targetLost", () => {
            hint.innerText = "Point camera directly at the album photo";
            vid.pause();
        });
    </script>
    {% else %}
    <div style="padding:100px 20px; text-align:center; background:#09090b; color:#fff; height:100vh;">
        <h3>No AR Photos Uploaded Yet!</h3>
        <a class="btn" href="/studio/{{ studio.studio_slug }}">Go Back</a>
    </div>
    {% endif %}
</body>
</html>
"""

@app.route("/")
def home():
    email = session.get("user_email")
    if not email:
        return render_template_string(
            LOGIN_UI,
            firebase_api_key=FIREBASE_API_KEY,
            firebase_auth_domain=FIREBASE_AUTH_DOMAIN
        )

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        session.clear()
        conn.close()
        return redirect(url_for("home"))

    items = conn.execute("SELECT * FROM ar_items WHERE owner_email = ? ORDER BY id DESC", (email,)).fetchall()
    conn.close()

    used_gb = round(user["used_bytes"] / ONE_GB_BYTES, 2)
    quota_gb = round(user["quota_bytes"] / ONE_GB_BYTES, 2)
    pct_used = min(100, round((user["used_bytes"] / user["quota_bytes"]) * 100, 1)) if user["quota_bytes"] > 0 else 100

    scan_url = request.host_url.rstrip("/") + url_for("ar_scan", slug=user["studio_slug"])
    qr_b64 = generate_qr_base64(scan_url)

    return render_template_string(
        CAPCUT_BUILDER_UI,
        user=user,
        items=items,
        used_gb=used_gb,
        quota_gb=quota_gb,
        pct_used=pct_used,
        qr_b64=qr_b64,
        cloud_name=CLOUD_NAME,
        upload_preset=UPLOAD_PRESET
    )

@app.route("/auth_gmail", methods=["POST"])
def auth_gmail():
    email = request.form["email"].strip().lower()
    name = request.form.get("name", email.split("@")[0]).strip()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        base_slug = make_slug(name)
        slug = base_slug
        counter = 1
        while conn.execute("SELECT 1 FROM users WHERE studio_slug = ?", (slug,)).fetchone():
            slug = f"{base_slug}-{counter}"
            counter += 1
        conn.execute(
            "INSERT INTO users (email, display_name, studio_slug, studio_name, tagline, whatsapp, theme, quota_bytes, used_bytes) VALUES (?, ?, ?, ?, ?, ?, 'dark', ?, 0)",
            (email, name, slug, name + " Studio", "Capturing Timeless Memories in AR", "919876543210", FREE_QUOTA_BYTES)
        )
        conn.commit()
    conn.close()
    session["user_email"] = email
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/save_studio", methods=["POST"])
def save_studio():
    email = session.get("user_email")
    if not email:
        return redirect(url_for("home"))
    conn = get_db()
    conn.execute(
        "UPDATE users SET studio_name = ?, tagline = ?, whatsapp = ?, theme = ? WHERE email = ?",
        (request.form["studio_name"], request.form["tagline"], request.form["whatsapp"], request.form["theme"], email)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/upload_chunk", methods=["POST"])
def upload_chunk():
    if not session.get("user_email"):
        return jsonify({"error": "Login required"}), 401
    chunk = request.files["chunk"]
    filename = secure_filename(request.form["filename"])
    chunk_index = int(request.form["chunkIndex"])
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    mode = "wb" if chunk_index == 0 else "ab"
    with open(filepath, mode) as f:
        f.write(chunk.read())
    return jsonify({"status": "ok"})

@app.route("/save_ar_item", methods=["POST"])
def save_ar_item():
    email = session.get("user_email")
    if not email:
        return jsonify({"error": "Login required"}), 401
    data = request.get_json()
    size_bytes = int(data.get("size_bytes", 0))

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user["used_bytes"] + size_bytes > user["quota_bytes"]:
        conn.close()
        return jsonify({"error": "5 GB Free Storage Limit Reached!"}), 403

    conn.execute(
        "INSERT INTO ar_items (owner_email, studio_slug, title, photo_url, video_url, mind_url, size_bytes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (email, user["studio_slug"], data["title"], data["photo_url"], data["video_url"], data["mind_url"], size_bytes)
    )
    conn.execute("UPDATE users SET used_bytes = used_bytes + ? WHERE email = ?", (size_bytes, email))
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})

@app.route("/delete_ar/<int:item_id>", methods=["POST"])
def delete_ar(item_id):
    email = session.get("user_email")
    if not email:
        return redirect(url_for("home"))
    conn = get_db()
    item = conn.execute("SELECT * FROM ar_items WHERE id = ? AND owner_email = ?", (item_id, email)).fetchone()
    if item:
        conn.execute("DELETE FROM ar_items WHERE id = ?", (item_id,))
        conn.execute("UPDATE users SET used_bytes = MAX(0, used_bytes - ?) WHERE email = ?", (item["size_bytes"], email))
        conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/studio/<slug>")
def studio_portfolio(slug):
    conn = get_db()
    studio = conn.execute("SELECT * FROM users WHERE studio_slug = ?", (slug,)).fetchone()
    if not studio:
        conn.close()
        return "Studio not found!", 404
    items = conn.execute("SELECT * FROM ar_items WHERE studio_slug = ? ORDER BY id DESC", (slug,)).fetchall()
    conn.close()
    return render_template_string(PORTFOLIO_UI, studio=studio, items=items)

@app.route("/ar_scan/<slug>")
def ar_scan(slug):
    conn = get_db()
    studio = conn.execute("SELECT * FROM users WHERE studio_slug = ?", (slug,)).fetchone()
    if not studio:
        conn.close()
        return "Studio not found!", 404
    all_items = conn.execute("SELECT * FROM ar_items WHERE studio_slug = ? ORDER BY id DESC", (slug,)).fetchall()
    item_id = request.args.get("id", type=int)
    active_item = next((it for it in all_items if it["id"] == item_id), all_items[0]) if all_items else None
    conn.close()
    return render_template_string(REAL_AR_SCANNER_UI, studio=studio, all_items=all_items, active_item=active_item)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
    
    
