# Changelog

## [2025-04-19] MVP Deployed 🚀

- Created FastAPI app to upload and list photos
- Dockerized and deployed to GKE with persistent volume storage
- Configured Ingress with TLS at home.fogcat5.com
- Solved NGINX 413 upload limits and caching issues
- Successfully uploaded and viewed photos through the app

## [2025-04-20] MVP Deployment Complete

- 🧠 Added OpenAI Vision API integration with GPT-4o
- 📷 File uploads with image preview and thumbnailing
- 🔍 Inventory object detection and tagging from photos
- 🔐 OAuth2 login via Google, restricted to `fogcat5@gmail.com`
- 🔄 Working on K8s at `https://home.fogcat5.com`
- 🔎 Basic query/search for tags
- 🧼 Secrets and API keys now injected via K8s secret volume
- 📁 Auto-organizing project directory (`scripts`, `templates`, `uploads`, etc.)

Next up: background queue for post-upload AI tasks (e.g., refinement pass, brand/model detection).
# Changelog

## [2025-04-21]
### Added
- GCS upload support via `upload_file_to_gcs()` using service account key
- Thumbnails generated using PIL and uploaded to GCS
- `.summary.txt` files generated via OpenAI Vision API and uploaded
- Initial `/photos` route renders gallery from local uploads
- `db.md` schema draft created for images, tags, and future Firestore migration plan

### Planned
- Move metadata storage from JSON to SQLite or Firestore
- Search/filter UI and proxy-based image viewer


## [2025-04-22]
### Added
- Gallery now loads thumbnails and summaries directly from GCS via `/uploads/{filename}` proxy route
- GitHub Actions workflow to build and push Docker image on `prod` branch updates
- Tags parsed from `.summary.txt` now displayed under each image in the gallery
- Automatic thumbnail and summary upload to GCS on image upload
- Docker image now built with consistent GCS access logic (service account fallback)
- Support for case-insensitive file extension detection in image filter

### Changed
- Deployment process updated to use `fogcat5/home-app:v<run>` image tags
- Refactored proxy route to support streaming any path under `upload/`, including `thumb/` and `summary/`
## 📅 2025-05-03 – AI Tag Search Integration & Closet Cleanup

### ✅ Tracker App Progress

- Added `/search` page with:
  - Top 10 most-used tags (excluding junk via blocklist)
  - Clickable tag-based filtering of uploaded photos
  - Free-form search box for AI-powered tag matching
- Implemented `call_openai_chat()` using `openai>=1.0` with `AsyncOpenAI`
- Added `get_tags_from_prompt()` helper to extract relevant tags from natural language
- Cleaned tags before saving:
  - Normalized case
  - Stripped punctuation
  - Removed extra whitespace
- Fixed display of tags by removing quotes, commas, and other junk
- Verified full search feature locally

### 🔁 Next Steps
- Push to `prod` branch
- Deploy updated version to GKE
- Confirm OpenAI API key is set in cluster env

## ✅ `2025-05-04` – Search & Tag UX Upgrade

### 🎨 UI / UX Improvements
- Added responsive CSS with mobile support and dark styling
- Applied pill-style `.tag` labels to photo results and top tags
- Top tags converted from list to inline tag display
- Favicon and custom page title added
- Enabled proper mobile scaling with `<meta name="viewport">`

### 🔎 Search Features
- AI-powered free-form text search via OpenAI API (`/search/query`)
- Tag-based search and filtering with clickable tags
- Cleaned tag names using shared `clean_tag_name()` utility
- Blocklisted noise tags from top results

### 🧠 Backend Enhancements
- Factored `clean_tag_name()` into `scripts/util.py`
- Rebuild route added at `/rebuild` (auth-protected) to restore DB from GCS `summary.txt`
- GCS summary-based DB rebuild also runs on app startup

### 🛡️ Security
- `/rebuild` route now checks for authenticated user
- Avoids accidental triggering by crawlers or unauthenticated users


## \[v0.6.2] – 2025-05-04 – GCS Rebuild Live in Prod ✅

### 🔁 GCS Rebuild System

* Implemented `should_rebuild_db()` logic with robust handling of `force` triggers
* Added `FORCE_REBUILD` environment variable support for startup-time rebuilds
* Updated `/rebuild` route to support `?force=true` query param
* Clean logs show rebuild decisions, GCS summary parsing, and per-image progress
* Fully tested in local dev and now deployed and verified in **production (GKE)**

### 🛠️ DevOps & K8s Improvements

* Confirmed pod label `app=home-app` works for simplified log access:

  ```bash
  kubectl logs -l app=home-app -f
  ```
* Clean startup behavior validated both with and without rebuild triggers
* Pod logs confirm accurate summary syncing and no unexpected exceptions

### 🍻 Status

* Version **v0.6.2** deployed to `prod`
* System stable, responsive, and fully functional
* Celebrated with a Moon Time Hazy IPA from Morgan Territory Brewing
