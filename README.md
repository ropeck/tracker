# Home Inventory & Object Memory System

![Cross-stitched $HOME](docs/crossstitch.png)

A smart, AI-assisted inventory and object tracking system designed to bring order to physical clutter. Combines NFC tagging, photo metadata, and domain-specific reasoning to support memory, cleanup, travel prep, and donation workflows.

---

## Why This Exists

We all accumulate gear, cables, tools, and sentimental objects that eventually blur into a pile. This system helps catalog them *with context* — where they are, what they're for, whether they're still needed — and gives gentle guidance when it's time to find, use, or let go.

---

## Core Ideas

- NFC tags + readers on bins, shelves, tools
- Photo recognition + AI tagging
- ChatGPT-style prompts like:
  - “Where does this go?”
  - “Do I already have one?”
  - “Is this ready to take on a trip?”
- Travel checklists, donation suggestions, usage stats


---

## Modules

- `/scripts/logger.py` – Web app, photo upload, search
- `/scripts/vision.py` – OpenAI Vision API wrapper
- `/scripts/auth.py` – Google OAuth2 integration
- `/templates/` – HTML templates for gallery and layout
- `/uploads/` – User images, thumbnails, and AI-generated summaries
- `/data/` – (Reserved) for structured object metadata and tag maps
- `/docs/` – Planning, vision, usage notes, and changelogs


---

## MVP Status - April 19, 2025 ✅

The following core system features are live at [https://home.fogcat5.com](https://home.fogcat5.com):

- Upload photos from the web interface
- View uploaded photo history with timestamps
- Deployed via Docker + Kubernetes on GKE
- Full domain name + HTTPS with cert-manager and Let's Encrypt
- NGINX ingress configured for larger image uploads

## [2025-04-20] MVP Deployment Complete

- 🧠 Added OpenAI Vision API integration with GPT-4o
- 📷 File uploads with image preview and thumbnailing
- 🔍 Inventory object detection and tagging from photos
- 🔐 OAuth2 login via Google, restricted to `fogcat5@gmail.com`
- 🔄 Working on K8s at `https://home.fogcat5.com`
- 🔎 Basic query/search for tags
- 🧼 Secrets and API keys now injected via K8s secret volume
- 📁 Auto-organizing project directory (`scripts`, `templates`, `uploads`, etc.)


## 🗓️ Daily Update: April 22, 2025

### ✅ What Got Done

- 📦 **Switched image uploads to Google Cloud Storage**
  - Full-size images, thumbnails, and summaries now land in `fogcat5-home/upload/`
- 🖼️ **Gallery page now reads from GCS**
  - `/photos` renders thumbnails and tags directly via GCS proxy route
- 🚀 **Added FastAPI proxy route to serve GCS files**
  - `/uploads/{filename}` handles image, thumb, and summary access with streaming
- 🧠 **Vision summaries stored alongside each image**
  - Parsed from OpenAI vision API and saved as `.summary.txt`
- 🛠️ **Improved gallery tag display**
  - Shows tags as stylized pills with links coming soon
- 🐳 **Created GitHub Actions CI pipeline**
  - Builds Docker image on `prod` branch push
  - Tags: `:latest`, `:v<run_number>`, and `:<short_sha>`
  - Pushes to Docker Hub and updates GKE deployment
- ☁️ **Auto-deploy to GKE now working!**
  - Cluster restarts pod with new image every `prod` commit

### 🍻 Vibe of the Day
- Dev soundtrack: Brad Mehldau – *"Look for the Silver Lining"*
- Beers on deck: Little Sumpin’ Sumpin’ → Atomic Torpedo IPA → CI/CD victory lap

## What's Next

- Queue background tasks to:
  - Enhance tagging with follow-up prompts
  - Suggest better naming/categories
  - Detect objects needing multiple views (e.g., mouse underside)
- Admin interface for tag cleanup and reprocessing
- NFC tag sync and label printing
- More natural language queries
