# Project: Home Inventory & Object Memory System
# Description:
# This is a FastAPI-based app running on Kubernetes (GKE) that allows uploading photos via web UI.
# Photos are stored and viewed with metadata (timestamp, optional labels).
# The goal is to build an AI-powered system to help clean up and organize physical spaces.
# It will track objects, tools, gear, books, etc., across shelves, bins, and zones.
# Vision-based analysis is used to identify objects in photos and attach searchable tags.
#
# Current architecture:
# - FastAPI app deployed as home-app on GKE
# - Frontend: file upload form, basic gallery view
# - Photos uploaded via phone or web, stored in a flat /photos dir
# - Future: tie photos to NFC-tagged zones or storage bins
#
# Today's Goals (April 20, 2025):
# 1. Integrate OpenAI's GPT-4o Vision API to analyze uploaded images
#    - Accept .jpg/.png files
#    - Encode to base64 and send to /chat/completions
#    - Prompt GPT to label inventory items in tech/household context
#    - Store tags as JSON alongside the image
# 2. Add basic search/query route to ask:
#    - “What’s this item?”
#    - “Where’s the yellow cable?”
#    - “Show me all books or chargers”
# 3. (Optional) Display tags below each image in the gallery
#
# Copilot, focus on:
# - Vision API call function
# - Post-upload tagging
# - Search/filter by tags
# - Clean, readable FastAPI routes


import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from auth import get_current_user
from auth import router as auth_router
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image
from starlette.middleware.sessions import SessionMiddleware
from vision import analyze_image_with_openai

load_dotenv()

templates = Jinja2Templates(directory="templates")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="some-random-secret-you-wont-guess")
app.include_router(auth_router)

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
        <input type="file" name="upload"><br>
        Label: <input type="text" name="label"><br>
        <input type="submit" value="Upload">
    </form>
    <a href="/photos">See All Uploaded Photos</a>
    </body></html>
    """

@app.get("/unauthorized", response_class=HTMLResponse)
async def unauthorized():
    return "<h1>403 Forbidden</h1><p>This app is restricted to the authorized user only.</p>"

@app.post("/upload")
async def protected_upload(
    request: Request,
    upload: UploadFile = File(...),
    label: str = Form(""),
    user: dict = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    timestamp = datetime.now().isoformat(timespec='seconds')
    filename = f"{timestamp.replace(':', '-')}_{upload.filename}"
    file_path = UPLOAD_DIR / filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    
    # Analyze with Vision API
    result = analyze_image_with_openai(str(file_path))

    # Save tags or summary to a .txt or .json file
    summary_path = UPLOAD_DIR / f"{filename}.summary.txt"
    with open(summary_path, "w") as summary_file:
        summary_file.write(result["summary"])

    # Generate thumbnail
    thumb_path = UPLOAD_DIR / f"{filename}.thumb.jpg"
    with Image.open(file_path) as img:
        img.thumbnail((300, 300))
        img.save(thumb_path, "JPEG")

    meta = json.loads(META_FILE.read_text())
    meta.append({
        "filename": filename,
        "summary": result["summary"],
        "label": label,
        "timestamp": timestamp
    })
    META_FILE.write_text(json.dumps(meta, indent=2))

    return {"status": "ok", "filename": filename}

@app.get("/photos", response_class=HTMLResponse)
async def gallery(request: Request, q: str = ""):
    query = q.strip().lower()
    photos = []

    for file in sorted(UPLOAD_DIR.iterdir()):
        if file.suffix.lower() in [".jpg", ".jpeg", ".png"] and not file.name.endswith(".thumb.jpg"):
            thumb = file.with_suffix(file.suffix + ".thumb.jpg")
            summary_file = file.with_suffix(file.suffix + ".summary.txt")
            tags = []

            if summary_file.exists():
                summary_text = summary_file.read_text()
                tags = [line.strip("-• \n").lower() for line in summary_text.splitlines() if line.strip()]

            # Filter if a query is set
            if query and not any(query in tag for tag in tags):
                continue

            photos.append({
                "filename": file.name,
                "tags": tags,
                "timestamp": file.stat().st_mtime,
            })

    return templates.TemplateResponse("photo_gallery_template.html", {
        "request": request,
        "photos": photos,
        "query": q
    })