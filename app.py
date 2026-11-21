import os
import re
import sqlite3
import io
import base64
import qrcode
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, render_template_string, redirect, url_for, jsonify, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "arcut-pro-secret-2026")

FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY", "")
FIREBASE_AUTH_DOMAIN = os.environ.get("FIREBASE_AUTH_DOMAIN", "")
CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
UPLOAD_PRESET = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
DB_NAME = "arcut_cloud_v7.db"

FREE_QUOTA_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB Free per Gmail
ONE_GB_BYTES = 1 * 1024 * 1024 * 1024

class PgConnWrapper:
    def __init__(self, pg_conn):
        self.pg_conn = pg_conn

    def execute(self, query, params=()):
        q = query.replace("?", "%s").replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        cur = self.pg_conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(q, params)
        return cur

    def commit(self):
        self.pg_conn.commit()

    def close(self):
        self.pg_conn.close()

def get_db():
    if DATABASE_URL:
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1) if DATABASE_URL.startswith("postgres://") else DATABASE_URL
        return PgConnWrapper(psycopg2.connect(url))
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            display_name TEXT,
            studio_slug TEXT UNIQUE,
            studio_name TEXT,
            tagline TEXT,
            whatsapp TEXT,
            theme TEXT DEFAULT 'dark',
            quota_bytes BIGINT DEFAULT 5368709120,
            used_bytes BIGINT DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ar_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_email TEXT,
            studio_slug TEXT,
            title TEXT,
            photo_url TEXT,
            video_url TEXT,
            mind_url TEXT,
            size_bytes BIGINT DEFAULT 0,
            FOREIGN KEY(owner_email) REFERENCES users(email)
        )
    """)
    conn.commit()
    conn.close()

init_db()


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
    <meta name="google-site-verification" content="XnW5dppkPxWCpaxUsavU6_p07SI9CfBTH5pdufq8-PM" />
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
</head>    <div class="card">
        <span class="badge">AR CUT PRO</span>
        <h1>Creator Cloud Studio</h1>
        <p>Sign in with your Gmail to save your AR albums, personal studio link & 5 GB cloud storage.</p>

        <div class="info-box">
            <div>[OK] <b>5 GB Free Cloud Storage</b> per Gmail</div>
            <div>[OK] <b>Real Image-Tracking WebAR</b> Camera</div>
            <div>[OK] <b>Private Dashboard</b> linked to your Gmail</div>
        </div>

        {% if firebase_api_key %}
        <button type="button" class="google-btn" onclick="startGoogleLogin()">
            <span style="color:#4285F4; font-weight:900;">G</span> Continue with Google (Gmail)
        </button>
        <p id="authStatus" style="color:#00f2fe; font-size:12px; margin:10px 0 0;"></p>
        {% endif %}

        <form id="fallbackForm" method="POST" action="/auth_gmail" style="display:{{ 'none' if firebase_api_key else 'block' }}; margin-top:12px;">
            <input type="email" name="email" placeholder="Enter your Gmail (name@gmail.com)" required>
            <input type="text" name="name" placeholder="Studio / Creator Name" required>
            <button type="submit" class="sub-btn">Continue with Gmail</button>
        </form>
    </div>

    {% if firebase_api_key %}
    <script>
        function startGoogleLogin() {
            const st = document.getElementById("authStatus");
            st.innerText = "Connecting to Google...";
            if (window._firebaseGoogleLogin) {
                window._firebaseGoogleLogin();
            } else {
                st.innerText = "Google popup blocked on this browser — enter Gmail below:";
                document.getElementById("fallbackForm").style.display = "block";
            }
        }
    </script>
    <script type="module">
        import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
        import { getAuth, signInWithPopup, GoogleAuthProvider } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

        const app = initializeApp({
            apiKey: "{{ firebase_api_key }}",
            authDomain: "{{ firebase_auth_domain }}"
        });
        const auth = getAuth(app);
        const provider = new GoogleAuthProvider();

        window._firebaseGoogleLogin = async () => {
            const st = document.getElementById("authStatus");
            try {
                const res = await signInWithPopup(auth, provider);
                const u = res.user;
                st.innerText = "Welcome " + u.email + "! Loading Studio...";
                const form = document.createElement("form");
                form.method = "POST";
                form.action = "/auth_gmail";
                form.innerHTML = `<input name="email" value="${u.email}"><input name="name" value="${u.displayName || u.email.split('@')[0]}">`;
                document.body.appendChild(form);
                form.submit();
            } catch (e) {
                st.innerText = "Error: " + (e.code || e.message) + " — or sign in below:";
                document.getElementById("fallbackForm").style.display = "block";
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
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#00f2fe">
    <script>if ('serviceWorker' in navigator) { navigator.serviceWorker.register('/sw.js'); }</script>
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
      <div class="topbar">
    <div class="brand">AR Cut <span class="brand-badge">PRO</span></div>
    <div style="display:flex;gap:8px;align-items:center;">
      {% if is_admin %}
      <a href="/admin" class="export-btn" style="background:linear-gradient(135deg,#f59e0b,#fbbf24);color:#000;">Owner Panel</a>
      {% endif %}
      <a href="/studio/{{ user.studio_slug }}" target="_blank" class="export-btn">Live Site</a>
    </div>
  </div>

       \u003Cspan style=\"color:#00f2fe; font-size:11px; font-weight:600;\">5 GB Free Cloud Plan Active\u003C/span> <div class="brand">AR Cut <span class="brand-badge">PRO</span></div>
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
            const chunkSize = 1024 * 1024;
            const totalChunks = Math.ceil(file.size / chunkSize);
            const safeName = prefix + "_" + Date.now() + "_" + file.name.replace(/[^a-zA-Z0-9._-]/g, '');

            for (let i = 0; i < totalChunks; i++) {
                const start = i * chunkSize;
                const end = Math.min(file.size, start + chunkSize);
                const chunk = file.slice(start, end);

                let uploaded = false;
                for (let attempt = 1; attempt <= 3 && !uploaded; attempt++) {
                    try {
                        const formData = new FormData();
                        formData.append("chunk", chunk);
                        formData.append("filename", safeName);
                        formData.append("chunkIndex", i);
                        formData.append("totalChunks", totalChunks);

                        const res = await fetch("/upload_chunk", { method: "POST", body: formData });
                        if (!res.ok) throw new Error("Server error " + res.status);
                        uploaded = true;
                    } catch (e) {
                        if (attempt === 3) throw new Error("Upload network error: " + e.message);
                        await new Promise(r => setTimeout(r, 1500));
                    }
                }
                onProgress(Math.round(((i + 1) / totalChunks) * 100));
            }
            return "/static/uploads/" + safeName;
        }

        function loadImage(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = new Image();
                    img.onload = () => resolve(img);
                    img.onerror = () => reject(new Error("Photo format not supported (use JPG/PNG)"));
                    img.src = e.target.result;
                };
                reader.onerror = () => reject(new Error("Please re-select the Photo and try again"));
                reader.readAsDataURL(file);
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

                            status.innerText = "AR Published!";
            bar.style.width = "100%";

            const successOverlay = document.createElement("div");
            successOverlay.innerHTML = `
                <style>
                    @keyframes arPopIn { 0% { transform: scale(0.6); opacity: 0; } 70% { transform: scale(1.06); opacity: 1; } 100% { transform: scale(1); opacity: 1; } }
                    @keyframes arGlow { 0%, 100% { box-shadow: 0 0 25px rgba(0, 242, 254, 0.45); } 50% { box-shadow: 0 0 45px rgba(79, 172, 254, 0.85); } }
                    @keyframes checkDraw { to { stroke-dashoffset: 0; } }
                    .ar-done-backdrop { position: fixed; inset: 0; background: rgba(9, 9, 11, 0.92); backdrop-filter: blur(10px); z-index: 99999; display: flex; align-items: center; justify-content: center; font-family: -apple-system, sans-serif; }
                    .ar-done-card { background: #141417; border: 1px solid rgba(0, 242, 254, 0.35); border-radius: 24px; padding: 34px 28px; text-align: center; max-width: 310px; width: 88%; animation: arPopIn 0.45s cubic-bezier(0.22, 1, 0.36, 1) forwards, arGlow 2s infinite; }
                    .ar-logo-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 20px; font-weight: 800; color: #fff; margin-bottom: 18px; letter-spacing: 0.4px; }
                    .ar-logo-pro { background: linear-gradient(135deg, #00f2fe, #4facfe); color: #000; font-size: 11px; font-weight: 900; padding: 3px 8px; border-radius: 8px; }
                    .ar-check-circle { width: 68px; height: 68px; border-radius: 50%; background: linear-gradient(135deg, rgba(0,242,254,0.18), rgba(79,172,254,0.18)); border: 2px solid #00f2fe; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; }
                    .ar-check-path { stroke: #00f2fe; stroke-width: 3.5; stroke-linecap: round; stroke-linejoin: round; fill: none; stroke-dasharray: 48; stroke-dashoffset: 48; animation: checkDraw 0.55s 0.25s ease forwards; }
                </style>
                <div class="ar-done-backdrop">
                    <div class="ar-done-card">
                        <div class="ar-logo-badge">AR Cut <span class="ar-logo-pro">PRO</span></div>
                        <div class="ar-check-circle">
                            <svg width="34" height="34" viewBox="0 0 36 36"><path class="ar-check-path" d="M9 18.5 L15.5 25 L27 11.5"/></svg>
                        </div>
                        <div style="color:#fff; font-size:18px; font-weight:700; margin-bottom:6px;">AR Published!</div>
                        <div style="color:#a1a1aa; font-size:13px;">Synced to Cloud & Ready to Scan</div>
                    </div>
                </div>
            `;
            document.body.appendChild(successOverlay);
            setTimeout(() => location.reload(), 2200);


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
        {% if studio.whatsapp %}
<a class="btn wa-btn" href="https://wa.me/{{ studio.whatsapp }}?text=Hi {{ studio.studio_name }}, I saw your AR Portfolio!" target="_blank">Book / WhatsApp Studio</a>
{% endif %}

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
            <a-video id="arPlane" src="#arVid" position="0 0 0" height="1" width="1" rotation="0 0 0"></a-video>

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
        const arPlane = document.getElementById('arPlane');
        const hint = document.getElementById('scanHint');

        function syncVideoRatio() {
            if (vid.videoWidth && vid.videoHeight) {
                const ratio = vid.videoHeight / vid.videoWidth;
                arPlane.setAttribute('width', '1');
                arPlane.setAttribute('height', ratio.toFixed(4));
            }
        }

        vid.addEventListener('loadedmetadata', syncVideoRatio);
        if (vid.readyState >= 1) syncVideoRatio();

        target.addEventListener("targetFound", () => {
            syncVideoRatio();
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
    try:
        conn.execute("ALTER TABLE users ADD COLUMN is_co_owner INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass
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
    is_admin = (email.lower() == ADMIN_EMAIL.lower()) or (bool(user["is_co_owner"]) if "is_co_owner" in user.keys() else False)

    return render_template_string(
        CAPCUT_BUILDER_UI,
        user=user,
        items=items,
        used_gb=used_gb,
        quota_gb=quota_gb,
        pct_used=pct_used,
        qr_b64=qr_b64,
        cloud_name=CLOUD_NAME,
        upload_preset=UPLOAD_PRESET,
        is_admin=is_admin
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
            (email, name, slug, name + " Studio", "Capturing Timeless Memories in AR", "", FREE_QUOTA_BYTES)
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
    try:
        conn.execute("ALTER TABLE users ADD COLUMN max_generates INTEGER DEFAULT 5")
        conn.commit()
    except Exception:
        pass
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    gen_count = conn.execute("SELECT COUNT(*) AS cnt FROM ar_items WHERE owner_email = ?", (email,)).fetchone()["cnt"]
    max_gens = user["max_generates"] if "max_generates" in user.keys() and user["max_generates"] is not None else 5

    if gen_count >= max_gens:
        conn.close()
        return jsonify({"error": f"Free limit of {max_gens} AR Generates reached! Contact Admin to upgrade."}), 403

    if user["used_bytes"] + size_bytes > user["quota_bytes"]:
        conn.close()
        return jsonify({"error": "Storage Limit Reached! Contact Admin to upgrade."}), 403

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

ADMIN_EMAIL = "avinashnarisetti7@gmail.com"
@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    
    email = session.get("user_email", "")
    conn = get_db()
    for col in ["max_generates INTEGER DEFAULT 5", "is_co_owner INTEGER DEFAULT 0"]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col}")
            conn.commit()
        except Exception:
            pass
    me = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    is_co = bool(me["is_co_owner"]) if me and "is_co_owner" in me.keys() else False
    if email.lower() != ADMIN_EMAIL.lower() and not is_co:
        conn.close()
        return "Access Denied: Owner Only", 403

    if request.method == "POST":
        target_email = request.form.get("target_email")
        new_gb = float(request.form.get("quota_gb", 5))
        new_gens = int(request.form.get("max_generates", 5))
        new_co = 1 if request.form.get("is_co_owner") == "1" else 0
        if target_email.lower() == ADMIN_EMAIL.lower():
            new_co = 1
        conn.execute("UPDATE users SET quota_bytes = ?, max_generates = ?, is_co_owner = ? WHERE email = ?", (int(new_gb * 1024 * 1024 * 1024), new_gens, new_co, target_email))
        conn.commit()
        conn.close()
        return redirect(url_for("admin_panel"))

    users = conn.execute("""
        SELECT u.*, COUNT(a.id) AS gen_count
        FROM users u LEFT JOIN ar_items a ON u.email = a.owner_email
        GROUP BY u.email ORDER BY u.used_bytes DESC
    """).fetchall()
    conn.close()
    rows = ""
    for u in users:
        used_mb = round((u["used_bytes"] or 0) / (1024 * 1024), 1)
        quota_gb = round((u["quota_bytes"] or 5368709120) / (1024 * 1024 * 1024), 1)
        max_g = u["max_generates"] if "max_generates" in u.keys() and u["max_generates"] is not None else 5
        co_val = 1 if (u["email"].lower() == ADMIN_EMAIL.lower() or ("is_co_owner" in u.keys() and u["is_co_owner"])) else 0
        badge = '<span style="background:#f59e0b;color:#000;font-size:10px;padding:2px 6px;border-radius:5px;margin-left:6px;">OWNER</span>' if u["email"].lower() == ADMIN_EMAIL.lower() else ('<span style="background:#00f2fe;color:#000;font-size:10px;padding:2px 6px;border-radius:5px;margin-left:6px;">CO-OWNER</span>' if co_val else '')
        rows += f"""
        <div style="background:#141417;border:1px solid #2a2a32;border-radius:16px;padding:16px;margin-bottom:14px;">
            <div style="font-weight:700;font-size:15px;color:#00f2fe;">{u['studio_name'] or 'No Studio Name'}{badge}</div>
            <div style="font-size:12px;color:#a1a1aa;margin:3px 0;">{u['display_name'] or ''} ({u['email']})</div>
            <div style="font-size:12px;color:#fff;margin:6px 0;">WhatsApp: {u['whatsapp'] or 'N/A'} | Used: <b>{used_mb} MB / {quota_gb} GB</b> | Generates: <b>{u['gen_count']} / {max_g}</b></div>
            <form method="POST" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center;">
                <input type="hidden" name="target_email" value="{u['email']}">
                <label style="font-size:12px;">GB: <input type="number" step="0.5" name="quota_gb" value="{quota_gb}" style="width:60px;padding:6px;border-radius:8px;border:1px solid #333;background:#09090b;color:#fff;"></label>
                <label style="font-size:12px;">Gens: <input type="number" name="max_generates" value="{max_g}" style="width:60px;padding:6px;border-radius:8px;border:1px solid #333;background:#09090b;color:#fff;"></label>
                <label style="font-size:12px;">Role: <select name="is_co_owner" style="padding:6px;border-radius:8px;border:1px solid #333;background:#09090b;color:#fff;">
                    <option value="0" {'selected' if co_val == 0 else ''}>User</option>
                    <option value="1" {'selected' if co_val == 1 else ''}>Co-Owner</option>
                </select></label>
                <button type="submit" style="background:linear-gradient(135deg,#00f2fe,#4facfe);color:#000;border:none;padding:7px 14px;border-radius:8px;font-weight:800;cursor:pointer;">Update</button>
            </form>
        </div>"""
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>AR Cut PRO - Owner Admin</title></head>
    <body style="background:#09090b;color:#fff;font-family:-apple-system,sans-serif;padding:18px;max-width:600px;margin:auto;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
            <h2 style="margin:0;">AR Cut PRO <span style="background:#00f2fe;color:#000;font-size:11px;padding:3px 8px;border-radius:6px;">ADMIN</span></h2>
            <a href="/" style="color:#00f2fe;font-size:13px;text-decoration:none;">← Dashboard</a>
        </div>
        <div style="margin-bottom:14px;font-size:13px;color:#a1a1aa;">Total Registered Users: <b style="color:#fff;">{len(users)}</b></div>
        {rows}
    </body></html>"""

