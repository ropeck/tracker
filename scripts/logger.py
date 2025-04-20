from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from datetime import datetime
import shutil
import os
import json

app = FastAPI()

# Config
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
META_FILE = UPLOAD_DIR / "metadata.json"
if not META_FILE.exists():
    META_FILE.write_text("[]")

# Allow phone testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html><body>
    <h2>Upload Item Photo</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file"><br>
        Label: <input type="text" name="label"><br>
        <input type="submit" value="Upload">
    </form>
    <a href="/photos">See All Uploaded Photos</a>
    </body></html>
    """

@app.post("/upload")
def upload(file: UploadFile = File(...), label: str = Form("")):
    timestamp = datetime.now().isoformat(timespec='seconds')
    filename = f"{timestamp.replace(':', '-')}_{file.filename}"
    file_path = UPLOAD_DIR / filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    meta = json.loads(META_FILE.read_text())
    meta.append({
        "filename": filename,
        "label": label,
        "timestamp": timestamp
    })
    META_FILE.write_text(json.dumps(meta, indent=2))

    return {"status": "ok", "filename": filename}

@app.get("/photos", response_class=HTMLResponse)
def photos():
    meta = json.loads(META_FILE.read_text())
    photo_html = "".join(
        f"<div><img src='/uploads/{m['filename']}' width='200'><br>{m['label']}<br><small>{m['timestamp']}</small></div>"
        for m in reversed(meta)
    )
    return f"""
    <html><body>
    <h2>Uploaded Photos</h2>
    {photo_html}
    <br><a href="/">Upload More</a>
    </body></html>
    """
