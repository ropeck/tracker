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