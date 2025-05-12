"""Endpoints for tracker app."""

import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import shutil
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from os import getenv
from pathlib import Path
from typing import Annotated, BinaryIO

import aiofiles  # make sure this is imported
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
from google.cloud import storage
from PIL import Image
from starlette.middleware.sessions import SessionMiddleware

from scripts.auth import get_current_user
from scripts.auth import router as auth_router
from scripts.config import BACKUP_DB_PATH, DB_BACKUP_DIR
from scripts.db import add_image, add_tag, get_db, init_db, link_image_tag
from scripts.rebuild import rebuild_db_from_gcs, restore_db_from_gcs_snapshot
from scripts.util import clean_tag_name, utc_now_iso
from scripts.vision import analyze_image_with_openai, call_openai_chat

load_dotenv()

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)

templates = Jinja2Templates(directory="scripts/templates")

# Global queue
processing_queue = asyncio.Queue()

# Background task holder (optional, for clean shutdown)
upload_worker_task = None


async def process_uploads() -> None:
    """Continuously process items in the upload queue."""
    while True:
        upload_info = await processing_queue.get()
        await process_image(upload_info)
        processing_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handles startup and shutdown tasks for the FastAPI app."""
    global upload_worker_task  # noqa: PLW0603

    del app   # unused arg
    upload_worker_task = asyncio.create_task(process_uploads())
    log.info("🚀 Upload processing queue started.")

    restored = BACKUP_DB_PATH.exists() and await restore_db_from_gcs_snapshot(
        GCS_BUCKET
    )
    if restored:
        log.info("Restoring DB from GCS snapshot and delta sync...")
        await perform_backup()
    else:
        if not BACKUP_DB_PATH.exists():
            log.info(f"No database backup found at {BACKUP_DB_PATH}.")
        log.info("Fallback: rebuilding DB from summary.txt")

    await rebuild_db_from_gcs(bucket_name=GCS_BUCKET, prefix=GCS_UPLOAD_PREFIX)

    log.info("Initialized sqlite database.")

    await init_db()
    await perform_backup()

    yield

    if upload_worker_task:
        upload_worker_task.cancel()
        try:
            await upload_worker_task
        except asyncio.CancelledError:
            log.info("🛑 Upload processing queue stopped.")


app = FastAPI(lifespan=lifespan)


secret_key = getenv("SESSION_SECRET", "dev-only-secret")
app.add_middleware(SessionMiddleware, secret_key=secret_key)
app.include_router(auth_router)

auth_scheme = HTTPBearer(auto_error=False)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
META_FILE = UPLOAD_DIR / "metadata.json"
if not META_FILE.exists():
    META_FILE.write_text("[]")

GCS_BUCKET = "fogcat5-home"
GCS_UPLOAD_PREFIX = "upload"

MIN_BACKUPS = 15
MAX_BACKUP_AGE_DAYS = 30

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
    "quantity 1",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def health_check() -> JSONResponse:
    """Simple health check endpoint to verify DB is reachable."""
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
        log.exception("🩺 Health check failed")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


app.mount("/static", StaticFiles(directory="scripts/static"), name="static")

async def process_image(upload_info: tuple) -> None:
    """Process an uploaded image file.

    - Generates a summary using OpenAI Vision
    - Saves the summary and thumbnail
    - Uploads both to GCS
    - Updates local metadata and SQLite DB with tags.
    """
    file_path, filename, label = upload_info
    log.info(f"🔧 Processing file: {filename}")

    try:
        result = analyze_image_with_openai(str(file_path))

        # Save summary
        summary_path = UPLOAD_DIR / f"{filename}.summary.txt"
        async with aiofiles.open(summary_path, "w") as summary_file:
            await summary_file.write(result["summary"])
        async with aiofiles.open(summary_path, "rb") as fh:
            upload_file_to_gcs(
                GCS_BUCKET,
                f"{GCS_UPLOAD_PREFIX}/summary/{filename}.summary.txt",
                fh,
            )

        # Create thumbnail (PIL is still sync; okay here)
        thumb_path = UPLOAD_DIR / f"{filename}.thumb.jpg"
        with Image.open(file_path) as img:
            img.thumbnail((300, 300))
            img.save(thumb_path, "JPEG")
        async with aiofiles.open(thumb_path, "rb") as fh:
            upload_file_to_gcs(
                GCS_BUCKET,
                f"{GCS_UPLOAD_PREFIX}/thumb/{filename}.thumb.jpg",
                fh,
            )

        await add_image(filename, label, utc_now_iso())
        for tag in result["summary"].splitlines():
            clean_tag = clean_tag_name(tag)
            if clean_tag:
                await add_tag(clean_tag)
                await link_image_tag(filename, clean_tag)

        async with aiofiles.open(META_FILE) as f:
            meta_text = await f.read()
            meta = json.loads(meta_text)
        meta.append({
            "filename": filename,
            "summary": result["summary"],
            "label": label,
            "timestamp": utc_now_iso(),
        })
        async with aiofiles.open(META_FILE, "w") as f:
            await f.write(json.dumps(meta, indent=2))

    except Exception:
        log.exception("Error processing %s", filename)


def upload_file_to_gcs(bucket_name: str, destination_blob_name: str,
                       file_obj: BinaryIO) -> str:
    """Store an image file in GCS bucket.

    Args:
        bucket_name (str): Name of the GCS bucket.
        destination_blob_name (str): Name of blob in GCS,
        file_obj (file): File object to upload.
    """
    client = storage.Client.from_service_account_json(
        "/app/service-account-key.json")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_file(file_obj, rewind=True)
    return destination_blob_name


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the home page with the file upload form."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/unauthorized", response_class=HTMLResponse)
async def unauthorized() -> str:
    """Return a simple 403 Forbidden message for unauthorized access."""
    return ("<h1>403 Forbidden</h1><p>This app is restricted to the authorized "
            "user only.</p>")


@app.get("/rebuild", response_class=HTMLResponse)
async def manual_rebuild(
    request: Request,
    user: dict = Depends(get_current_user),
    force: str = Query(default="false"),
) -> HTMLResponse:
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
        
@app.post("/upload")
async def protected_upload(
    request: Request,
    upload: Annotated[UploadFile, File()] = ...,
    label: Annotated[str, Form()] = "",
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Enqueue file uploads from authenticated users for processing."""
    if not user:
        return RedirectResponse("/login", status_code=302)
    del request  # unused arg

    timestamp = utc_now_iso()
    filename = f"{timestamp.replace(':', '-')}_{upload.filename}"
    file_path = UPLOAD_DIR / filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)

    with file_path.open("rb") as fh:
        upload_file_to_gcs(GCS_BUCKET, f"{GCS_UPLOAD_PREFIX}/{filename}", fh)

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
    """Send a natural language query to the OpenAI API and return matched
    tags.
    """
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
        tags = json.loads(response)
        if isinstance(tags, list):
            return [clean_tag_name(tag) for tag in tags if isinstance(tag, str)]
    except Exception as e:
        log.warning(f"AI response parsing failed: {e} -- raw: {response}")
    return []


@app.get("/photos", response_class=HTMLResponse)
async def view_photos(
    request: Request, db: Annotated[aiosqlite.Connection, Depends(get_db)]
):
    """Render the photo gallery view with associated tags and timestamps."""
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
        photos.append({
            "filename": filename,
            "timestamp": timestamp,
            "tags": tags,
            "proxy_url": f"/uploads/{filename}",
            "thumb_url": f"/uploads/thumb/{filename}.thumb.jpg",
        })
    return templates.TemplateResponse(
        request, "photo_gallery_template.html", {"photos": photos}
    )


@app.get("/search", response_class=HTMLResponse)
async def search_photos(request: Request, q: str = ""):
    """Search photos by matching tags from a query string and display
    results.
    """
    query = q.strip().lower()
    async with aiosqlite.connect("uploads/metadata.db") as db:
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
            photos.append({
                "filename": filename,
                "timestamp": timestamp,
                "tags": tags,
                "proxy_url": f"/uploads/{filename}",
                "thumb_url": f"/uploads/thumb/{filename}.thumb.jpg",
            })
    return templates.TemplateResponse(
        request,
        "search.html",
        {"photos": photos, "top_tags": top_tags, "q": q},
    )


@app.post("/search/query", response_class=HTMLResponse)
async def search_by_prompt(
    request: Request, db: Annotated[aiosqlite.Connection, Depends(get_db)]
):
    """Search photos using a free-form prompt interpreted by the AI model.

    Args:
        request: The FastAPI request object.
        db: Async database connection.

    Returns:
        HTML page with matched photos and extracted tags.
    """
    form = await request.form()
    prompt = form.get("prompt", "").strip()

    cursor = await db.execute("SELECT DISTINCT name FROM tags")
    tag_rows = await cursor.fetchall()
    all_tags = [clean_tag_name(row[0]) for row in tag_rows]

    matched_tags = await get_tags_from_prompt(prompt, all_tags)

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
        photos.append({
            "filename": filename,
            "timestamp": timestamp,
            "tags": tags,
            "proxy_url": f"/uploads/{filename}",
            "thumb_url": f"/uploads/thumb/{filename}.thumb.jpg",
        })

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
    user: Annotated[dict, Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Security(auth_scheme)],
):
    """Trigger a backup of the current metadata DB to GCS.

    Authorization is enforced via OAuth2 user or Kubernetes service account.

    Args:
        request: The incoming request.
        user: The authenticated OAuth2 user.
        credentials: Service account credentials for in-cluster auth.

    Returns:
        JSON result indicating success or skipped backup.
    """
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

    if os.getenv("DISABLE_BACKUP_AUTH", "").lower() == "true":
        log.warning(
            "⚠️  Auth bypassed for /backup-now (DISABLE_BACKUP_AUTH=true)"
        )
    elif user:
        email = user.get("email")
        if email in allowed_users:
            log.info(
                f"✅ Authenticated user '{email}' allowed to trigger backup"
            )
        else:
            log.warning(f"❌ User '{email}' not in allowlist")
            raise HTTPException(status_code=403, detail="Unauthorized user")
    else:
        token = credentials.credentials if credentials else None
        if not token:
            raise HTTPException(
                status_code=403, detail="Missing Authorization token"
            )

        try:
            info = jwt.decode(token, verify=False)
            subject = info.get("sub")
            if subject in allowed_sas:
                log.info(
                    f"✅ Authenticated service account '{subject}' allowed to trigger backup"
                )
            else:
                log.warning(
                    f"❌ Service account '{subject}' not in allowlist"
                )
                raise HTTPException(
                    status_code=403, detail="Unauthorized service account"
                )
        except Exception as e:
            log.warning(f"❌ JWT decode error: {e}")
            raise HTTPException(
                status_code=403, detail="Invalid service account token"
            )

    return await perform_backup()


async def perform_backup():
    """Perform a snapshot backup of the SQLite DB to a local file and upload to
    GCS.

    Returns:
        JSON result containing the backup status and path.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_filename = f"backup-{today}.sqlite3"
    backup_path = DB_BACKUP_DIR / backup_filename

    if not BACKUP_DB_PATH.exists():
        raise HTTPException(status_code=500, detail="No DB to back up")

    async with aiosqlite.connect(BACKUP_DB_PATH) as src_db:
        async with aiosqlite.connect(backup_path) as dest_db:
            await src_db.backup(dest_db)

    if backup_path.exists():
        with open(BACKUP_DB_PATH, "rb") as f:
            current_hash = hashlib.md5(f.read()).hexdigest()  # nosec B324
        with open(backup_path, "rb") as f:
            backup_hash = hashlib.md5(f.read()).hexdigest()  # nosec B324
        if current_hash == backup_hash:
            log.info("📦 No DB changes since last backup. Skipping upload.")
            return {"status": "skipped", "reason": "No changes detected."}

    log.info(f"📦 DB backup created: {backup_filename}")
    with open(backup_path, "rb") as f:
        gcs_path = f"db-backups/{backup_filename}"
        upload_file_to_gcs(GCS_BUCKET, gcs_path, f)
        return None


async def cleanup_old_backups() -> None:
    """Delete local backup files that exceed the retention policy.

    Keeps the most recent N backups or those newer than the max age.
    """
    backups = sorted(
        DB_BACKUP_DIR.glob("backup-*.sqlite3"),
        key=os.path.getmtime,
        reverse=True,
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
            log.info(f"🧹 Removing old backup: {path}")
            try:
                path.unlink()
            except Exception as e:
                log.warning(f"Could not delete {path}: {e}")
