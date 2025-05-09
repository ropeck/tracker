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
import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import aiosqlite
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Security,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.auth import jwt
from google.auth.transport import requests as google_requests
from google.cloud import storage
from PIL import Image
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

from scripts.auth import get_current_user
from scripts.auth import router as auth_router
from scripts.db import DB_PATH, add_image, add_tag, init_db, link_image_tag
from scripts.rebuild import rebuild_db_from_gcs, restore_db_from_gcs_snapshot
from scripts.util import clean_tag_name, utc_now_iso
from scripts.vision import analyze_image_with_openai, call_openai_chat

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

    # ⬇️ Initialize database on startup
    restored = await restore_db_from_gcs_snapshot(GCS_BUCKET)
    if restored:
        logging.info("Restoring DB from GCS snapshot and delta sync...")
        await perform_backup()
    else:
        logging.info("Fallback: rebuilding DB from summary.txt")

    await rebuild_db_from_gcs(bucket_name=GCS_BUCKET, prefix=GCS_UPLOAD_PREFIX)

    logging.info("Initialized sqlite database.")

    await init_db()
    await perform_backup()

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

auth_scheme = HTTPBearer(auto_error=False)

# Config
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
META_FILE = UPLOAD_DIR / "metadata.json"
if not META_FILE.exists():
    META_FILE.write_text("[]")

GCS_BUCKET = "fogcat5-home"
GCS_UPLOAD_PREFIX = "upload"


DB_BACKUP_DIR = Path("backups")
DB_BACKUP_DIR.mkdir(exist_ok=True)
BACKUP_DB_PATH = UPLOAD_DIR / "metadata.db"
MIN_BACKUPS = 15
MAX_BACKUP_AGE_DAYS = 30

# tags to ignore in the top 10 list
BLOCKED_TAGS = {
    "objects",
    "elements",
    "quantity",
    "1",
    "true",
    "false",
    "yes",
    "no",
    "null",
    "none",
    "json",
    "objects",
    "elements",
    "quantity 1",
}


# Allow phone testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def health_check():
    try:
        async with aiosqlite.connect(BACKUP_DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM images")
            row = await cursor.fetchone()
            image_count = row[0] if row else 0
        return {
            "status": "ok",
            "db_file": str(BACKUP_DB_PATH),
            "image_count": image_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logging.warning(f"🩺 Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


app.mount("/static", StaticFiles(directory="scripts/static"), name="static")


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

        # After uploading thumb/summary
        await add_image(filename, label, utc_now_iso())
        for tag in result["summary"].splitlines():
            clean_tag = clean_tag_name(tag)
            if clean_tag:
                await add_tag(clean_tag)
                await link_image_tag(filename, clean_tag)

        # Update metadata
        meta = json.loads(META_FILE.read_text())
        meta.append(
            {
                "filename": filename,
                "summary": result["summary"],
                "label": label,
                "timestamp": utc_now_iso(),
            }
        )
        META_FILE.write_text(json.dumps(meta, indent=2))

    except Exception as e:
        logging.exception(f"Error processing {filename}: {e}")


@app.get("/rebuild", response_class=HTMLResponse)
async def manual_rebuild(
    request: Request,
    user: dict = Depends(get_current_user),
    force: str = Query(default="false"),
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    force_flag = force.strip().lower() not in ("", "0", "false", "no", "off")

    await rebuild_db_from_gcs(
        bucket_name=GCS_BUCKET, prefix=GCS_UPLOAD_PREFIX, force=force_flag
    )
    return templates.TemplateResponse(request, "rebuild.html")


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
    file_obj.seek(0)
    blob.upload_from_file(file_obj, rewind=True)
    return destination_blob_name


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/unauthorized", response_class=HTMLResponse)
async def unauthorized():
    return "<h1>403 Forbidden</h1><p>This app is restricted to the authorized user only.</p>"


@app.post("/upload")
async def protected_upload(
    request: Request,
    upload: UploadFile = File(...),
    label: str = Form(""),
    user: dict = Depends(get_current_user),
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    timestamp = utc_now_iso()
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


async def get_tags_from_prompt(prompt: str, all_tags: list[str]) -> list[str]:
    tag_str = ", ".join(sorted(set(all_tags)))
    system_prompt = f"""
You are a helpful assistant for organizing home inventory items.

The user will ask a question like "Show photos with power cables" or "Where is the audio gear?"

Given their query, return the most relevant tags from this list:
{tag_str}

Reply with a JSON array of tag names. For example:
["usb", "power", "audio"]
"""
    response = await call_openai_chat(prompt, system_prompt=system_prompt)

    try:
        # Safely evaluate returned JSON array
        tags = json.loads(response)
        if isinstance(tags, list):
            return [clean_tag_name(tag) for tag in tags if isinstance(tag, str)]
    except Exception as e:
        logging.warning(f"AI response parsing failed: {e} -- raw: {response}")
    return []


@app.get("/photos", response_class=HTMLResponse)
async def view_photos(request: Request):
    async with aiosqlite.connect("uploads/metadata.db") as db:
        cursor = await db.execute(
            """
            SELECT images.filename, images.timestamp, GROUP_CONCAT(tags.name)
            FROM images
            LEFT JOIN image_tags ON images.id = image_tags.image_id
            LEFT JOIN tags ON image_tags.tag_id = tags.id
            GROUP BY images.id
            ORDER BY images.timestamp DESC
        """
        )
        rows = await cursor.fetchall()
        photos = []
        for row in rows:
            filename, timestamp, tags_str = row
            tags = tags_str.split(",") if tags_str else []
            photos.append(
                {
                    "filename": filename,
                    "timestamp": timestamp,
                    "tags": tags,
                    "proxy_url": f"/uploads/{filename}",
                    "thumb_url": f"/uploads/thumb/{filename}.thumb.jpg",
                }
            )
    return templates.TemplateResponse(
        request, "photo_gallery_template.html", {"photos": photos}
    )


@app.get("/search", response_class=HTMLResponse)
async def search_photos(request: Request, q: str = ""):
    query = q.strip().lower()
    async with aiosqlite.connect("uploads/metadata.db") as db:
        # Get top 10 tags
        tag_cursor = await db.execute(
            """
            SELECT tags.name, COUNT(image_tags.tag_id) as usage_count
            FROM tags
            JOIN image_tags ON tags.id = image_tags.tag_id
            GROUP BY tags.name
            ORDER BY usage_count DESC
            LIMIT 50
        """
        )
        tag_rows = await tag_cursor.fetchall()
        top_tags = []

        for row in tag_rows:
            clean_tag = clean_tag_name(row[0])
            if clean_tag and clean_tag not in BLOCKED_TAGS:
                top_tags.append(clean_tag)
            if len(top_tags) >= 10:
                break

        # Get matching photos
        cursor = await db.execute(
            """
            SELECT images.filename, images.timestamp, GROUP_CONCAT(tags.name)
            FROM images
            LEFT JOIN image_tags ON images.id = image_tags.image_id
            LEFT JOIN tags ON image_tags.tag_id = tags.id
            GROUP BY images.id
            ORDER BY images.timestamp DESC
            """
        )
        rows = await cursor.fetchall()
        photos = []
        for row in rows:
            filename, timestamp, tags_str = row
            tags = tags_str.split(",") if tags_str else []
            if query and not any(query in tag.lower() for tag in tags):
                continue
            photos.append(
                {
                    "filename": filename,
                    "timestamp": timestamp,
                    "tags": tags,
                    "proxy_url": f"/uploads/{filename}",
                    "thumb_url": f"/uploads/thumb/{filename}.thumb.jpg",
                }
            )
    return templates.TemplateResponse(
        request,
        "search.html",
        {"photos": photos, "top_tags": top_tags, "q": q},
    )


@app.post("/search/query", response_class=HTMLResponse)
async def search_by_prompt(request: Request):
    form = await request.form()
    prompt = form.get("prompt", "").strip()

    # Get all tags from DB
    async with aiosqlite.connect("uploads/metadata.db") as db:
        cursor = await db.execute("SELECT DISTINCT name FROM tags")
        tag_rows = await cursor.fetchall()
        all_tags = [clean_tag_name(row[0]) for row in tag_rows]

    matched_tags = await get_tags_from_prompt(prompt, all_tags)

    # Fetch photos matching the tags
    async with aiosqlite.connect("uploads/metadata.db") as db:
        cursor = await db.execute(
            """
            SELECT images.filename, images.timestamp, GROUP_CONCAT(tags.name)
            FROM images
            LEFT JOIN image_tags ON images.id = image_tags.image_id
            LEFT JOIN tags ON image_tags.tag_id = tags.id
            GROUP BY images.id
            ORDER BY images.timestamp DESC
            """
        )
        rows = await cursor.fetchall()
        photos = []
        for row in rows:
            filename, timestamp, tags_str = row
            tags = tags_str.split(",") if tags_str else []
            normalized_tags = [clean_tag_name(t) for t in tags]
            if not any(tag in matched_tags for tag in normalized_tags):
                continue
            photos.append(
                {
                    "filename": filename,
                    "timestamp": timestamp,
                    "tags": tags,
                    "proxy_url": f"/uploads/{filename}",
                    "thumb_url": f"/uploads/thumb/{filename}.thumb.jpg",
                }
            )

    return templates.TemplateResponse(
        request,
        "search.html",
        {
            "photos": photos,
            "top_tags": matched_tags,
            "q": prompt,
        },
    )


@app.get("/backup-now")
async def trigger_backup(
    request: Request,
    user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(auth_scheme),
):
    allowed_users = [
        email.strip()
        for email in os.getenv("ALLOWED_USER_EMAILS", "").split(",")
        if email.strip()
    ]
    allowed_sas = [
        sa.strip()
        for sa in os.getenv("ALLOWED_SERVICE_ACCOUNT_IDS", "").split(",")
        if sa.strip()
    ]

    # AUTH BYPASS (dev/testing only)
    if os.getenv("DISABLE_BACKUP_AUTH", "").lower() == "true":
        logging.warning("⚠️  Auth bypassed for /backup-now (DISABLE_BACKUP_AUTH=true)")
    else:
        # 1. OAuth2 user
        if user:
            email = user.get("email")
            if email in allowed_users:
                logging.info(
                    f"✅ Authenticated user '{email}' allowed to trigger backup"
                )
            else:
                logging.warning(f"❌ User '{email}' not in allowlist")
                raise HTTPException(status_code=403, detail="Unauthorized user")

        # 2. Kubernetes Service Account
        else:
            token = credentials.credentials if credentials else None
            if not token:
                raise HTTPException(
                    status_code=403, detail="Missing Authorization token"
                )

            try:
                info = jwt.decode(token, verify=False)  # in-cluster: skip verify
                subject = info.get("sub")
                if subject in allowed_sas:
                    logging.info(
                        f"✅ Authenticated service account '{subject}' allowed to trigger backup"
                    )
                else:
                    logging.warning(f"❌ Service account '{subject}' not in allowlist")
                    raise HTTPException(
                        status_code=403, detail="Unauthorized service account"
                    )
            except Exception as e:
                logging.warning(f"❌ JWT decode error: {e}")
                raise HTTPException(
                    status_code=403, detail="Invalid service account token"
                )

    return await perform_backup()


async def perform_backup():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_filename = f"backup-{today}.sqlite3"
    backup_path = DB_BACKUP_DIR / backup_filename

    if not BACKUP_DB_PATH.exists():
        raise HTTPException(status_code=500, detail="No DB to back up")

    async with aiosqlite.connect(BACKUP_DB_PATH) as src_db:
        async with aiosqlite.connect(backup_path) as dest_db:
            await src_db.backup(dest_db)

    # Detect if backup already exists and contents are identical
    if backup_path.exists():
        with open(BACKUP_DB_PATH, "rb") as f:
            current_hash = hashlib.md5(f.read()).hexdigest()
        with open(backup_path, "rb") as f:
            backup_hash = hashlib.md5(f.read()).hexdigest()
        if current_hash == backup_hash:
            logging.info("📦 No DB changes since last backup. Skipping upload.")
            return {"status": "skipped", "reason": "No changes detected."}

    logging.info(f"📦 DB backup created: {backup_filename}")
    with open(backup_path, "rb") as f:
        gcs_path = f"db-backups/{backup_filename}"
        upload_file_to_gcs(GCS_BUCKET, gcs_path, f)

    logging.info(f"✅ DB backup uploaded: {gcs_path}")
    await cleanup_old_backups()

    return {"status": "uploaded", "gcs_path": gcs_path}


async def cleanup_old_backups():
    backups = sorted(
        DB_BACKUP_DIR.glob("backup-*.sqlite3"), key=os.path.getmtime, reverse=True
    )
    if len(backups) <= MIN_BACKUPS:
        return

    now = datetime.now(timezone.utc).timestamp()

    cutoff = now - (MAX_BACKUP_AGE_DAYS * 86400)
    kept = 0

    for path in backups:
        if kept < MIN_BACKUPS:
            kept += 1
            continue
        if os.path.getmtime(path) < cutoff:
            logging.info(f"🧹 Removing old backup: {path}")
            try:
                path.unlink()
            except Exception as e:
                logging.warning(f"Could not delete {path}: {e}")
