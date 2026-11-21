import os
import re
from flask import Flask, request, render_template_string, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Upload folder setup
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Studios storage (Slug-based multi-studio support)
studios_db = {
    "srinikitha": {
        "name": "Sri Nikitha Photography",
        "tagline": "Capturing Timeless Wedding Memories in AR",
        "whatsapp": "919876543210",
        "theme": "dark",
        "ar_items": []
    }
}

def make_slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-') or "my-studio"

BUILDER_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AR Studio Builder - Step 2</title>
    <style>
        body { font-family: sans-serif; margin: 0; padding: 15px; background: #0f172a; color: #f8fafc; }
        .card { background: #1e293b; padding: 16px; border-radius: 12px; margin-bottom: 16px; border: 1px solid #334155; }
        input, select { width: 100%; padding: 10px; margin: 6px 0 14px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #fff; box-sizing: border-box; }
        input[type="file"] { padding: 8px; background: #1e293b; }
        button { width: 100%; padding: 12px; background: #f59e0b; color: #000; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; font-size: 15px; }
        .btn-green { background: #10b981; color: #fff; text-decoration: none; display: block; text-align: center; padding: 13px; border-radius: 8px; font-weight: bold; margin-top: 10px; }
        .link-box { background: #020617; padding: 10px; border-radius: 8px; font-family: monospace; color: #38bdf8; word-break: break-all; margin-top: 8px; }
    </style>
</head>
<body>
    <h2>📸 AR Website Builder (v2.0)</h2>
    
    <div class="card">
        <h3>1. Studio Profile & Custom Link</h3>
        <form method="POST" action="/save_studio">
            <label>Studio Name</label>
            <input type="text" name="name" value="{{ studio.name }}" required>
            
            <label>Tagline</label>
            <input type="text" name="tagline" value="{{ studio.tagline }}" required>
            
            <label>WhatsApp Number (with 91)</label>
            <input type="text" name="whatsapp" value="{{ studio.whatsapp }}" required>
            
            <label>Website Theme</label>
            <select name="theme">
                <option value="dark" {% if studio.theme == 'dark' %}selected{% endif %}>Dark Luxury (Gold & Black)</option>
                <option value="light" {% if studio.theme == 'light' %}selected{% endif %}>Minimal Classic White</option>
            </select>
            
            <button type="submit">Save & Generate Studio Link</button>
        </form>
        <div class="link-box">Your Link: /studio/{{ slug }}</div>
    </div>

    <div class="card">
        <h3>2. Upload AR Photo + Video (From Gallery)</h3>
        <form method="POST" action="/upload_ar/{{ slug }}" enctype="multipart/form-data">
            <label>Album / Event Title</label>
            <input type="text" name="title" placeholder="Ex: Wedding Highlight" required>
            
            <label>Select Album Photo (JPG/PNG)</label>
            <input type="file" name="photo" accept="image/*" required>
            
            <label>Select AR Video (MP4)</label>
            <input type="file" name="video" accept="video/mp4,video/*" required>
            
            <button type="submit">⬆️ Upload & Create AR Card</button>
        </form>
    </div>

    <a href="/studio/{{ slug }}" class="btn-green" target="_blank">🚀 Open Live Studio Website</a>
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
        img, video { width: 100%; border-radius: 10px; margin-top: 10px; }
        .btn { display: inline-block; margin: 8px 4px; padding: 11px 20px; border-radius: 25px; text-decoration: none; font-weight: bold; font-size: 14px; }
        .wa-btn { background: #25D366; color: #fff; }
        .cam-btn { background: #6366f1; color: #fff; }
    </style>
</head>
<body>
    <div class="hero">
        <h1>{{ studio.name }}</h1>
        <p>{{ studio.tagline }}</p>
        <a class="btn wa-btn" href="https://wa.me/{{ studio.whatsapp }}?text=Hi {{ studio.name }}, I want to book a shoot!" target="_blank">💬 Book on WhatsApp</a>
        <a class="btn cam-btn" href="/ar_scan/{{ slug }}">📷 Open AR Album Scanner</a>
    </div>

    <h3>✨ AR Wedding & Event Albums</h3>
    <p style="font-size:13px; opacity:0.8;">Tap any photo to preview AR Video</p>

    {% if not studio.ar_items %}
        <p style="opacity:0.6; margin-top:30px;">No AR albums uploaded yet. Add from builder!</p>
    {% endif %}

    {% for item in studio.ar_items %}
    <div class="ar-card">
        <span class="badge">✨ AR ENABLED</span>
        <h4>{{ item.title }}</h4>
        <img src="{{ item.photo_url }}" onclick="this.style.display='none'; this.nextElementSibling.style.display='block'; this.nextElementSibling.play();">
        <video src="{{ item.video_url }}" controls playsinline style="display:none;"></video>
    </div>
    {% endfor %}
</body>
</html>
"""

AR_SCANNER_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AR Album Scanner - {{ studio.name }}</title>
    <style>
        body { margin: 0; background: #000; color: #fff; font-family: sans-serif; overflow: hidden; text-align: center; }
        video#cam { width: 100vw; height: 100vh; object-fit: cover; }
        .overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: space-between; pointer-events: none; }
        .top-bar { background: rgba(0,0,0,0.6); padding: 15px; pointer-events: auto; }
        .scan-frame { width: 260px; height: 260px; border: 3px solid #f59e0b; border-radius: 20px; margin: auto; box-shadow: 0 0 0 9999px rgba(0,0,0,0.45); position: relative; }
        .bottom-bar { background: rgba(0,0,0,0.75); padding: 15px; pointer-events: auto; }
        select, a { padding: 10px 15px; border-radius: 8px; font-weight: bold; }
        #ar-player { display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 85%; max-width: 360px; border: 3px solid #10b981; border-radius: 12px; z-index: 20; }
    </style>
</head>
<body>
    <video id="cam" autoplay playsinline></video>
    <video id="ar-player" controls playsinline></video>

    <div class="overlay">
        <div class="top-bar">
            <strong>📷 {{ studio.name }} AR Scanner</strong><br>
            <small>Point camera at printed album photo</small>
        </div>

        <div class="scan-frame"></div>

        <div class="bottom-bar">
            {% if studio.ar_items %}
            <select id="albumSelect" onchange="triggerAR(this.value)">
                <option value="">-- Select Photo to Simulate Scan --</option>
                {% for item in studio.ar_items %}
                <option value="{{ item.video_url }}">{{ item.title }}</option>
                {% endfor %}
            </select>
            {% else %}
            <p>Upload an AR album first to test scanner!</p>
            {% endif %}
            <br><br>
            <a href="/studio/{{ slug }}" style="background:#ef4444; color:#fff; text-decoration:none;">Exit Scanner</a>
        </div>
    </div>

    <script>
        navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
            .then(stream => { document.getElementById('cam').srcObject = stream; })
            .catch(err => { alert("Camera access requires HTTPS or localhost permission."); });

        function triggerAR(videoUrl) {
            const player = document.getElementById('ar-player');
            if (!videoUrl) { player.style.display = 'none'; player.pause(); return; }
            player.src = videoUrl;
            player.style.display = 'block';
            player.play();
        }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    default_slug = list(studios_db.keys())[0]
    return render_template_string(BUILDER_UI, studio=studios_db[default_slug], slug=default_slug)

@app.route("/save_studio", methods=["POST"])
def save_studio():
    name = request.form["name"]
    slug = make_slug(name)
    old_items = list(studios_db.values())[0]["ar_items"]
    studios_db.clear()
    studios_db[slug] = {
        "name": name,
        "tagline": request.form["tagline"],
        "whatsapp": request.form["whatsapp"],
        "theme": request.form["theme"],
        "ar_items": old_items
    }
    return render_template_string(BUILDER_UI, studio=studios_db[slug], slug=slug)

@app.route("/upload_ar/<slug>", methods=["POST"])
def upload_ar(slug):
    if slug not in studios_db:
        return "Studio not found", 404
    
    photo = request.files["photo"]
    video = request.files["video"]
    title = request.form["title"]

    photo_filename = secure_filename(photo.filename)
    video_filename = secure_filename(video.filename)

    photo.save(os.path.join(app.config["UPLOAD_FOLDER"], photo_filename))
    video.save(os.path.join(app.config["UPLOAD_FOLDER"], video_filename))

    studios_db[slug]["ar_items"].append({
        "title": title,
        "photo_url": f"/static/uploads/{photo_filename}",
        "video_url": f"/static/uploads/{video_filename}"
    })
    return redirect(url_for("home"))

@app.route("/studio/<slug>")
def studio_portfolio(slug):
    studio = studios_db.get(slug)
    if not studio:
        return "Studio not found!", 404
    return render_template_string(PORTFOLIO_UI, studio=studio, slug=slug)

@app.route("/ar_scan/<slug>")
def ar_scan(slug):
    studio = studios_db.get(slug)
    if not studio:
        return "Studio not found!", 404
    return render_template_string(AR_SCANNER_UI, studio=studio, slug=slug)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
