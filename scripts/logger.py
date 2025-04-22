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

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image
from starlette.middleware.sessions import SessionMiddleware
from google.cloud import storage

from scripts.auth import get_current_user
from scripts.auth import router as auth_router
from scripts.vision import analyze_image_with_openai

load_dotenv()

templates = Jinja2Templates(directory="scripts/templates")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="some-random-secret-you-wont-guess")
app.include_router(auth_router)

# Config
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
META_FILE = UPLOAD_DIR / "metadata.json"
if not META_FILE.exists():
    META_FILE.write_text("[]")

GCS_BUCKET = "fogcat5-home"
GCS_UPLOAD_PREFIX = "upload"

# Allow phone testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


def upload_file_to_gcs(bucket_name: str, destination_blob_name: str, file_obj) -> str:
    client = storage.Client.from_service_account_json("/app/service-account-key.json")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_file(file_obj, rewind=True)
    return blob.url

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
        with file_path.open("rb") as fh:
            upload_file_to_gcs(GCS_BUCKET, f"{GCS_UPLOAD_PREFIX}/{filename}", fh)


    # Analyze with Vision API
    result = analyze_image_with_openai(str(file_path))

    # Save tags or summary to a .txt or .json file
    summary_path = UPLOAD_DIR / f"{filename}.summary.txt"
    with open(summary_path, "w") as summary_file:
        summary_file.write(result["summary"])
    with open(summary_path, "rb") as fh:
        upload_file_to_gcs(GCS_BUCKET, f"{GCS_UPLOAD_PREFIX}/summary/{filename}.summary.txt", fh)

    # Generate thumbnail
    thumb_path = UPLOAD_DIR / f"{filename}.thumb.jpg"
    with Image.open(file_path) as img:
        img.thumbnail((300, 300))
        img.save(thumb_path, "JPEG")
    with thumb_path.open("rb") as fh:
        upload_file_to_gcs(GCS_BUCKET, f"{GCS_UPLOAD_PREFIX}/thumb/{filename}.thumb.jpg", fh)


    meta = json.loads(META_FILE.read_text())
    meta.append({
        "filename": filename,
        "summary": result["summary"],
        "label": label,
        "timestamp": timestamp
    })
    META_FILE.write_text(json.dumps(meta, indent=2))

    return {
        "status": "ok",
        "filename": filename,
        "label": label,
        "timestamp": timestamp,
        "gcs_path": f"{GCS_UPLOAD_PREFIX}/{filename}",
        "proxy_url": f"/images/{filename}",
        "thumb_url": f"/images/{filename}.thumb.jpg",
        "summary_url": f"/images/{filename}.summary.txt",
        "summary": result["summary"]
    }
from fastapi import Request
from fastapi.responses import HTMLResponse
from google.cloud import storage
from scripts.auth import get_current_user  # Optional if you want auth

@app.get("/photos", response_class=HTMLResponse)
async def gallery(request: Request, q: str = ""):
    query = q.strip().lower()
    photos = []

    client = storage.Client.from_service_account_json("/app/service-account-key.json")
    bucket = client.bucket(GCS_BUCKET)
    blobs = bucket.list_blobs(prefix="upload/")

    # Only keep main images (ignore thumbs and summaries)
    main_images = [blob for blob in blobs if blob.name.endswith((".jpg", ".jpeg", ".png")) and
                   not blob.name.endswith(".thumb.jpg") and not blob.name.endswith(".summary.txt")]

    for blob in main_images:
        filename = Path(blob.name).name
        timestamp = blob.updated.isoformat()
        tags = []

        # Try to fetch the summary file
        summary_name = f"{blob.name}.summary.txt"
        summary_blob = bucket.blob(summary_name)
        if summary_blob.exists():
            try:
                summary_text = summary_blob.download_as_text()
                tags = [
                    line.strip("-• \n").lower()
                    for line in summary_text.splitlines()
                    if line.strip()
                ]
            except Exception as e:
                print(f"Error reading summary for {filename}: {e}")

        # Filter by query
        if query and not any(query in tag for tag in tags):
            continue

        photos.append({
            "filename": filename,
            "tags": tags,
            "timestamp": timestamp,
            "proxy_url": f"/images/{filename}",
            "thumb_url": f"/images/{filename}.thumb.jpg"
        })

    return templates.TemplateResponse("photo_gallery_template.html", {
        "request": request,
        "photos": sorted(photos, key=lambda p: p["timestamp"], reverse=True),
        "query": q
    })
