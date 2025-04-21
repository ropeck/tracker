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
