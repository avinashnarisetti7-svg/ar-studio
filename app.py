import os
import re
import sqlite3
import io
import base64
import qrcode
from flask import Flask, request, render_template_string, redirect, url_for, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
DB_NAME = "ar_studios_v4.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS studios (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tagline TEXT,
            whatsapp TEXT,
            theme TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ar_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            studio_slug TEXT,
            title TEXT,
            photo_url TEXT,
            video_url TEXT,
            mind_url TEXT,
            FOREIGN KEY(studio_slug) REFERENCES studios(slug)
        )
    """)
    c.execute("SELECT COUNT(*) FROM studios")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO studios VALUES (?, ?, ?, ?, ?)",
            ("srinikitha", "Sri Nikitha Photography", "Capturing Timeless Memories in AR", "919876543210", "dark")
        )
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def make_slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-') or "my-studio"

def generate_qr_base64(url):
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

BUILDER_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AR Studio Builder v4 - Real WebAR</title>
    <script type="importmap">
    {
      "imports": {
        "mindar-image-three": "https://cdn.jsdelivr.net/npm/mind-ar@1.2.5/dist/mindar-image-three.prod.js"
      }
    }
    </script>
    <style>
        body { font-family: sans-serif; margin: 0; padding: 15px; background: #0f172a; color: #f8fafc; }
        .card { background: #1e293b; padding: 16px; border-radius: 12px; margin-bottom: 16px; border: 1px solid #334155; }
        input, select { width: 100%; padding: 10px; margin: 6px 0 14px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #fff; box-sizing: border-box; }
        button { width: 100%; padding: 13px; background: #f59e0b; color: #000; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; font-size: 15px; }
        button:disabled { background: #64748b; cursor: not-allowed; }
        .btn-green { background: #10b981; color: #fff; text-decoration: none; display: block; text-align: center; padding: 13px; border-radius: 8px; font-weight: bold; margin-top: 10px; }
        .qr-box { text-align: center; background: #fff; color: #000; padding: 15px; border-radius: 12px; margin-top: 12px; }
        .studio-pill { display: inline-block; background: #334155; color: #38bdf8; padding: 6px 12px; border-radius: 20px; text-decoration: none; margin: 4px; font-size: 13px; }
        .progress-wrap { display: none; margin-top: 12px; background: #0f172a; border-radius: 8px; padding: 10px; border: 1px solid #38bdf8; }
        .bar-bg { width: 100%; height: 12px; background: #334155; border-radius: 6px; overflow: hidden; margin-top: 6px; }
        .bar-fill { width: 0%; height: 100%; background: #10b981; transition: width 0.2s; }
    </style>
</head>
<body>
    <h2>📸 Real AR Studio Builder (v4.0)</h2>

    <div class="card">
        <strong>Active Studio:</strong><br>
        {% for s in all_studios %}
            <a class="studio-pill" href="/?slug={{ s.slug }}">{{ s.name }}</a>
        {% endfor %}
    </div>
    
    <div class="card">
        <h3>1. Studio Profile</h3>
        <form method="POST" action="/save_studio">
            <label>Studio Name</label>
            <input type="text" name="name" value="{{ studio.name }}" required>
            <label>Tagline</label>
            <input type="text" name="tagline" value="{{ studio.tagline }}" required>
            <label>WhatsApp Number (with 91)</label>
            <input type="text" name="whatsapp" value="{{ studio.whatsapp }}" required>
            <label>Theme</label>
            <select name="theme">
                <option value="dark" {% if studio.theme == 'dark' %}selected{% endif %}>Dark Luxury (Gold & Black)</option>
                <option value="light" {% if studio.theme == 'light' %}selected{% endif %}>Minimal Classic White</option>
            </select>
            <button type="submit">💾 Save Studio Profile</button>
        </form>
    </div>

    <div class="card">
        <h3>2. Upload AR Photo + Large Video (Fast Upload)</h3>
        <label>Album / Event Title</label>
        <input type="text" id="arTitle" placeholder="Ex: Wedding Highlight" required>
        
        <label>Select Album Photo (Clear high-contrast photo)</label>
        <input type="file" id="arPhoto" accept="image/*" required>
        
        <label>Select AR Video (MP4 - Any size supported)</label>
        <input type="file" id="arVideo" accept="video/mp4,video/*" required>
        
        <button id="uploadBtn" onclick="startFastARUpload()">⚡ Compile AR & Fast Upload</button>

        <div class="progress-wrap" id="progressWrap">
            <div id="statusText">Preparing...</div>
            <div class="bar-bg"><div class="bar-fill" id="barFill"></div></div>
        </div>
    </div>

    <div class="card">
        <h3>3. Album Print QR Code (Direct AR Scanner)</h3>
        <div class="qr-box">
            <img src="data:image/png;base64,{{ qr_b64 }}" width="180" height="180"><br>
            <small><strong>Scan to launch AR Camera: {{ studio.name }}</strong></small><br><br>
            <a href="data:image/png;base64,{{ qr_b64 }}" download="{{ studio.slug }}-ar-qr.png" style="background:#0f172a; color:#fff; padding:8px 14px; border-radius:6px; text-decoration:none; font-size:13px;">⬇️ Download QR PNG</a>
        </div>
    </div>

    <a href="/studio/{{ studio.slug }}" class="btn-green" target="_blank">🚀 Open Live Studio Website</a>

    <script type="module">
        import { Compiler } from 'mindar-image-three';

        async function uploadFileInChunks(file, prefix, onProgress) {
            const chunkSize = 2 * 1024 * 1024; // 2MB per chunk (fast & timeout-proof)
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
                img.onerror = reject;
                img.src = URL.createObjectURL(file);
            });
        }

        window.startFastARUpload = async function() {
            const title = document.getElementById("arTitle").value.trim();
            const photoFile = document.getElementById("arPhoto").files[0];
            const videoFile = document.getElementById("arVideo").files[0];

            if (!title || !photoFile || !videoFile) {
                alert("Please enter title and select both Photo & Video!");
                return;
            }

            const btn = document.getElementById("uploadBtn");
            const wrap = document.getElementById("progressWrap");
            const status = document.getElementById("statusText");
            const bar = document.getElementById("barFill");

            btn.disabled = true;
            wrap.style.display = "block";

            try {
                // Step 1: Compile AR Image Target (.mind) in Browser
                status.innerText = "Step 1/3: Compiling AR Photo Target (10-15s)...";
                bar.style.width = "15%";
                const img = await loadImage(photoFile);
                const compiler = new Compiler();
                await compiler.compileImageTargets([img], (progress) => {
                    bar.style.width = (15 + Math.round(progress * 0.25)) + "%";
                });
                const exportedBuffer = await compiler.exportData();
                const mindBlob = new Blob([exportedBuffer], { type: "application/octet-stream" });
                const mindFile = new File([mindBlob], "target.mind");

                // Step 2: Upload Photo & .mind file
                status.innerText = "Step 2/3: Uploading Photo & AR Target...";
                const photoUrl = await uploadFileInChunks(photoFile, "{{ studio.slug }}_img", () => {});
                const mindUrl = await uploadFileInChunks(mindFile, "{{ studio.slug }}_mind", () => {});
                bar.style.width = "50%";

                // Step 3: Fast Chunked Upload for Large Video
                status.innerText = "Step 3/3: Fast Uploading Video: 0%";
                const videoUrl = await uploadFileInChunks(videoFile, "{{ studio.slug }}_vid", (pct) => {
                    status.innerText = `Step 3/3: Fast Uploading Video: ${pct}%`;
                    bar.style.width = (50 + Math.round(pct * 0.5)) + "%";
                });

                // Save record to database
                await fetch("/save_ar_item/{{ studio.slug }}", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title, photo_url: photoUrl, video_url: videoUrl, mind_url: mindUrl })
                });

                status.innerText = "✅ AR Album Ready! Reloading...";
                setTimeout(() => location.reload(), 800);

            } catch (err) {
                alert("Error: " + err.message);
                btn.disabled = false;
            }
        };
    </script>
</body>
</html>
"""

PORTFOLIO_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ studio.name }} - AR Portfolio</title>
    <style>
        body {
            font-family: sans-serif; margin: 0; padding: 20px; text-align: center;
            background: {{ '#09090b' if studio.theme == 'dark' else '#f8fafc' }};
            color: {{ '#fafafa' if studio.theme == 'dark' else '#0f172a' }};
        }
        .hero { padding: 30px 10px; border-bottom: 1px solid #27272a; }
        .badge { background: #f59e0b; color: #000; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .ar-card { background: {{ '#18181b' if studio.theme == 'dark' else '#ffffff' }}; padding: 15px; border-radius: 16px; margin: 20px auto; max-width: 420px; box-shadow: 0 4px 20px rgba(0,0,0,0.25); }
        img { width: 100%; border-radius: 10px; margin-top: 10px; }
        .btn { display: inline-block; margin: 8px 4px; padding: 12px 22px; border-radius: 25px; text-decoration: none; font-weight: bold; font-size: 14px; }
        .wa-btn { background: #25D366; color: #fff; }
        .cam-btn { background: #6366f1; color: #fff; }
    </style>
</head>
<body>
    <div class="hero">
        <h1>{{ studio.name }}</h1>
        <p>{{ studio.tagline }}</p>
        <a class="btn wa-btn" href="https://wa.me/{{ studio.whatsapp }}?text=Hi {{ studio.name }}, I saw your AR Portfolio!" target="_blank">💬 Book on WhatsApp</a>
        <a class="btn cam-btn" href="/ar_scan/{{ studio.slug }}">📷 Scan Printed Album (Live AR)</a>
    </div>

    <h3>✨ AR Enabled Album Photos</h3>
    <p style="font-size:13px; opacity:0.8;">Open AR Scanner & point camera at any photo below to watch it come alive!</p>

    {% for item in items %}
    <div class="ar-card">
        <span class="badge">✨ REAL AR TRACKING</span>
        <h4>{{ item.title }}</h4>
        <img src="{{ item.photo_url }}">
        <br><br>
        <a class="btn cam-btn" href="/ar_scan/{{ studio.slug }}?id={{ item.id }}">📷 Scan This Photo Now</a>
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
    <title>Live AR Scanner - {{ studio.name }}</title>
    <script src="https://aframe.io/releases/1.5.0/aframe.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/mind-ar@1.2.5/dist/mindar-image-aframe.prod.js"></script>
    <style>
        body { margin: 0; overflow: hidden; font-family: sans-serif; }
        .hud { position: fixed; top: 0; left: 0; width: 100%; z-index: 999; background: rgba(0,0,0,0.65); color: #fff; padding: 12px; text-align: center; }
        .bottom-hud { position: fixed; bottom: 15px; left: 0; width: 100%; z-index: 999; text-align: center; }
        .btn { background: #ef4444; color: #fff; padding: 10px 18px; border-radius: 20px; text-decoration: none; font-weight: bold; margin: 0 5px; border: none; font-size: 14px; }
        select { padding: 10px; border-radius: 10px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="hud">
        <strong>📷 {{ studio.name }} — Live AR Camera</strong><br>
        <small id="scanHint">Point camera directly at the album photo</small>
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
        <button class="btn" style="background:#10b981;" onclick="document.getElementById('arVid').muted=false; document.getElementById('arVid').play();">🔊 Unmute Audio</button>
        <a class="btn" href="/studio/{{ studio.slug }}">Exit</a>
    </div>

    <script>
        const target = document.getElementById('targetEntity');
        const vid = document.getElementById('arVid');
        const hint = document.getElementById('scanHint');

        target.addEventListener("targetFound", () => {
            hint.innerText = "✨ Photo Detected! Playing AR Video...";
            vid.play();
        });

        target.addEventListener("targetLost", () => {
            hint.innerText = "Point camera directly at the album photo";
            vid.pause();
        });
    </script>
    {% else %}
    <div style="padding:100px 20px; text-align:center; background:#000; color:#fff; height:100vh;">
        <h3>No AR Photos Uploaded Yet!</h3>
        <a class="btn" href="/studio/{{ studio.slug }}">Go Back</a>
    </div>
    {% endif %}
</body>
</html>
"""

@app.route("/")
def home():
    conn = get_db()
    all_studios = conn.execute("SELECT * FROM studios").fetchall()
    slug = request.args.get("slug") or all_studios[0]["slug"]
    studio = conn.execute("SELECT * FROM studios WHERE slug = ?", (slug,)).fetchone()
    if not studio:
        studio = all_studios[0]
    conn.close()

    scan_url = request.host_url.rstrip("/") + url_for("ar_scan", slug=studio["slug"])
    qr_b64 = generate_qr_base64(scan_url)
    return render_template_string(BUILDER_UI, studio=studio, all_studios=all_studios, qr_b64=qr_b64)

@app.route("/save_studio", methods=["POST"])
def save_studio():
    name = request.form["name"]
    slug = make_slug(name)
    conn = get_db()
    conn.execute("""
        INSERT INTO studios (slug, name, tagline, whatsapp, theme)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            name=excluded.name,
            tagline=excluded.tagline,
            whatsapp=excluded.whatsapp,
            theme=excluded.theme
    """, (slug, name, request.form["tagline"], request.form["whatsapp"], request.form["theme"]))
    conn.commit()
    conn.close()
    return redirect(url_for("home", slug=slug))

@app.route("/upload_chunk", methods=["POST"])
def upload_chunk():
    chunk = request.files["chunk"]
    filename = secure_filename(request.form["filename"])
    chunk_index = int(request.form["chunkIndex"])
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    mode = "wb" if chunk_index == 0 else "ab"
    with open(filepath, mode) as f:
        f.write(chunk.read())
    return jsonify({"status": "ok"})

@app.route("/save_ar_item/<slug>", methods=["POST"])
def save_ar_item(slug):
    data = request.get_json()
    conn = get_db()
    conn.execute(
        "INSERT INTO ar_items (studio_slug, title, photo_url, video_url, mind_url) VALUES (?, ?, ?, ?, ?)",
        (slug, data["title"], data["photo_url"], data["video_url"], data["mind_url"])
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})

@app.route("/studio/<slug>")
def studio_portfolio(slug):
    conn = get_db()
    studio = conn.execute("SELECT * FROM studios WHERE slug = ?", (slug,)).fetchone()
    if not studio:
        conn.close()
        return "Studio not found!", 404
    items = conn.execute("SELECT * FROM ar_items WHERE studio_slug = ?", (slug,)).fetchall()
    conn.close()
    return render_template_string(PORTFOLIO_UI, studio=studio, items=items)

@app.route("/ar_scan/<slug>")
def ar_scan(slug):
    conn = get_db()
    studio = conn.execute("SELECT * FROM studios WHERE slug = ?", (slug,)).fetchone()
    if not studio:
        conn.close()
        return "Studio not found!", 404
    all_items = conn.execute("SELECT * FROM ar_items WHERE studio_slug = ? ORDER BY id DESC", (slug,)).fetchall()
    item_id = request.args.get("id", type=int)
    active_item = None
    if all_items:
        active_item = next((it for it in all_items if it["id"] == item_id), all_items[0])
    conn.close()
    return render_template_string(REAL_AR_SCANNER_UI, studio=studio, all_items=all_items, active_item=active_item)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
