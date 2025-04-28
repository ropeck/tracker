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
# 📋 Goals You Just Described

# | Feature | Details |
# |:--------|:--------|
# | 🛠️ Add queuing | Queue the Vision API/image processing instead of blocking during upload |
# | 🛠️ Show tags for each photo | Display tags (objects/summary) in the photo gallery view |
# | 🛠️ Show uploaded photo immediately | After upload, show the uploaded photo + summary without needing a manual refresh |

# ---

# # 🛠 Summary of Upgrades

# | Feature | Status |
# |:--------|:-------|
# | ✅ Background queue for image processing | (fast uploads, async backend) |
# | ✅ Display tags next to each photo | (improved gallery info) |
# | ✅ Instant upload preview | (better feedback to user) |

# ---
#
# Copilot, focus on:
# - Post-upload tagging
# - Search/filter by tags
# - Clean, readable FastAPI routes


import asyncio
import json
import logging
import mimetypes
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.cloud import storage
from PIL import Image
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

from scripts.auth import get_current_user
from scripts.auth import router as auth_router
from scripts.vision import analyze_image_with_openai

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
templates = Jinja2Templates(directory="scripts/templates")

# Global queue
processing_queue = asyncio.Queue()

# Background task holder (optional, for clean shutdown)
upload_worker_task = None


async def process_uploads():
    while True:
        upload_info = await processing_queue.get()
        await process_image(upload_info)
        processing_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global upload_worker_task

    # Startup: Launch background worker
    upload_worker_task = asyncio.create_task(process_uploads())
    logging.info("🚀 Upload processing queue started.")

    yield

    # Shutdown: Cancel background worker cleanly (optional now)
    if upload_worker_task:
        upload_worker_task.cancel()
        try:
            await upload_worker_task
        except asyncio.CancelledError:
            logging.info("🛑 Upload processing queue stopped.")


app = FastAPI(lifespan=lifespan)

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


async def process_image(upload_info):
    file_path, filename, label = upload_info
    logging.info(f"🔧 Processing file: {filename}")

    # Run your analysis, thumbnail creation, GCS uploads here
    # (Move the analysis and thumb code out of /upload into this)

    try:
        result = analyze_image_with_openai(str(file_path))

        # Save summary
        summary_path = UPLOAD_DIR / f"{filename}.summary.txt"
        with open(summary_path, "w") as summary_file:
            summary_file.write(result["summary"])
        with open(summary_path, "rb") as fh:
            upload_file_to_gcs(
                GCS_BUCKET, f"{GCS_UPLOAD_PREFIX}/summary/{filename}.summary.txt", fh
            )

        # Create thumbnail
        thumb_path = UPLOAD_DIR / f"{filename}.thumb.jpg"
        with Image.open(file_path) as img:
            img.thumbnail((300, 300))
            img.save(thumb_path, "JPEG")
        with thumb_path.open("rb") as fh:
            upload_file_to_gcs(
                GCS_BUCKET, f"{GCS_UPLOAD_PREFIX}/thumb/{filename}.thumb.jpg", fh
            )

        # Update metadata
        meta = json.loads(META_FILE.read_text())
        meta.append(
            {
                "filename": filename,
                "summary": result["summary"],
                "label": label,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
        )
        META_FILE.write_text(json.dumps(meta, indent=2))

    except Exception as e:
        logging.exception(f"Error processing {filename}: {e}")


@app.get("/uploads/{path:path}")
async def gcs_proxy(path: str, request: Request):
    gcs_path = f"{GCS_UPLOAD_PREFIX}/{path}"
    logging.info(f"📦 GCS proxy requested: {gcs_path}")

    try:
        key_path = "/app/service-account-key.json"
        if os.path.exists(key_path):
            client = storage.Client.from_service_account_json(key_path)
        else:
            client = storage.Client()  # ADC fallback
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(gcs_path)

        if not blob.exists():
            logging.warning(f"❌ GCS file not found: {gcs_path}")
            return JSONResponse(
                status_code=404, content={"error": "File not found", "path": gcs_path}
            )

        stream = blob.open("rb")

        content_type = blob.content_type
        if not content_type:
            content_type, _ = mimetypes.guess_type(path)
        if not content_type:
            content_type = "application/octet-stream"  # fallback

        return StreamingResponse(
            stream,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{path}"'},
        )
    except Exception as e:
        logging.exception(f"🔥 Error serving GCS file: {gcs_path}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal error accessing GCS",
                "message": str(e),
                "path": gcs_path,
            },
        )


def upload_file_to_gcs(bucket_name: str, destination_blob_name: str, file_obj) -> str:
    client = storage.Client.from_service_account_json("/app/service-account-key.json")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_file(file_obj, rewind=True)
    return destination_blob_name


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/unauthorized", response_class=HTMLResponse)
async def unauthorized():
    return "<h1>403 Forbidden</h1><p>This app is restricted to the authorized user only.</p>"


@app.post("/uploadtest")
async def uploadtest(request: Request):
    print("DEBUG: /uploadtest called")

    form = await request.form()
    print("==== FORM FIELDS ====")
    for key, value in form.items():
        print(f"{key} -> {value}")

    return {"status": "ok"}


@app.post("/upload")
async def protected_upload(
    request: Request,
    upload: UploadFile = File(...),
    label: str = Form(""),
    user: dict = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    timestamp = datetime.now().isoformat(timespec="seconds")
    filename = f"{timestamp.replace(':', '-')}_{upload.filename}"
    file_path = UPLOAD_DIR / filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)

    with file_path.open("rb") as fh:
        upload_file_to_gcs(GCS_BUCKET, f"{GCS_UPLOAD_PREFIX}/{filename}", fh)

    # 🎯 Instead of analyzing now, add to processing queue
    await processing_queue.put((file_path, filename, label))

    return {
        "status": "ok",
        "filename": filename,
        "label": label,
        "timestamp": timestamp,
        "gcs_path": f"{GCS_UPLOAD_PREFIX}/{filename}",
        "proxy_url": f"/uploads/{filename}",
        "thumb_url": f"/uploads/thumb/{filename}.thumb.jpg",
        "summary_url": f"/uploads/summary/{filename}.summary.txt",
    }


@app.get("/photos", response_class=HTMLResponse)
async def gallery(request: Request, q: str = ""):
    query = q.strip().lower()
    photos = []

    client = storage.Client.from_service_account_json("/app/service-account-key.json")
    bucket = client.bucket(GCS_BUCKET)
    blobs = bucket.list_blobs(prefix="upload/")

    # Only keep main images (ignore thumbs and summaries)
    main_images = [
        blob
        for blob in blobs
        if blob.name.lower().endswith((".jpg", ".jpeg", ".png"))
        and not blob.name.endswith(".thumb.jpg")
        and not blob.name.endswith(".summary.txt")
    ]

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

        photos.append(
            {
                "filename": filename,
                "tags": tags,
                "timestamp": timestamp,
                "proxy_url": f"/images/{filename}",
                "thumb_url": f"/images/{filename}.thumb.jpg",
            }
        )

    return templates.TemplateResponse(
        "photo_gallery_template.html",
        {
            "request": request,
            "photos": sorted(photos, key=lambda p: p["timestamp"], reverse=True),
            "query": q,
        },
    )
