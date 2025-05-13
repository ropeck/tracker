# Tracker Project: MVP Progress and TODOs

**Project Purpose**: AI-assisted physical inventory system with photo uploads, vision-based tagging, and smart querying.

## ✅ Completed
- [x] FastAPI + Uvicorn app with image upload.
- [x] Image metadata stored with thumbnails and tags.
- [x] GPT-4 Vision API integration (OpenAI).
- [x] Basic web gallery (`/photos`) with summaries.
- [x] Querying images by tag/summary via `/photos?q=wireless` etc.
- [x] Deployed to Kubernetes (`home.fogcat5.com`) with Docker image.
- [x] OAuth2 Google login required for uploads.
- [x] Environment secrets for keys via Kubernetes.
- [x] Tested from mobile: working live uploads and tagging.

## 🟡 In Progress
- [ ] Clean up / tighten Docker image (remove venv, static files)
- [ ] Auto-generate tags for older images (backfill)
- [x] Improve result display styling (no raw JSON, just tags)
- [ ] Add Makefile or helper scripts for build & deploy

## ⚡️ Next Priorities
- [ ] **Async tag processing queue**
  - Avoid blocking upload requests during OpenAI Vision call
  - Add status: “Pending…” then refresh with result
- [ ] **Tag model/brand if known**
  - Secondary prompt or enhanced prompt chain
  - Possibly request user for alternate views of item
- [ ] **Admin utilities**
  - Re-tag button for refining image labels
  - Mark/tag stale or unplaced items
- [ ] **Search UX**
  - Add filter by date, recent, or room
  - Show zone/area scores ("what’s out of place?")
- [ ] **README + docs**
  - Include project purpose, architecture, screenshots, pricing info
  - Add contributor guidelines if open-sourced


Last update: 2025-05-03

### ⭐ UI & Tag Interaction
- [ ] Add “⭐ Favorite” marker for photos (toggle per user or system-wide)
- [ ] Allow user to:
  - [ ] Add new tags to photos
  - [ ] Remove incorrect or noisy tags
  - [ ] Edit tag names (with validation)
- [ ] Render tags on photo results as pill-style labels with rounded background
  - [ ] Make each tag clickable → filters search by that tag

### 📊 Tag Explorer
- [ ] Show count of photos per tag in the **Top Tags** section
- [ ] Add a scrollable, sortable **Tag Index** page:
  - [ ] Sort by name or photo count
  - [ ] Paginate the list for usability (50–100 tags per page)
  - [ ] Option to filter by prefix or substring

### 🔁 General Enhancements
- [ ] Add `favorite` field to DB schema and photo model
- [ ] Create `/favorites` route to view starred images
- [ ] Add audit log for manual tag edits (optional, but useful for undo/debug)

---

Lazlo and the rest of your home inventory deserve clean, searchable metadata. This list will guide us in polishing the app into something genuinely useful and enjoyable to use.
# Tracker App TODO

This document outlines the planned enhancements and feature backlog for the Tracker App. The goal is to improve photo tagging, browsing, search, and overall usability.

---

## 1. Tagging Enhancements
- [ ] Add ability to mark photos as "favorite"
- [ ] UI support to add, edit, and delete tags per photo
- [ ] Display tag usage counts in the Top 10 list
- [ ] Add a scrollable list of all tags, sortable by name or count

---

## 2. Search and Display
- [ ] Improve tag display in search results
- [ ] Show additional metadata (timestamp, upload source)
- [ ] Implement pagination for gallery/search views
- [ ] Add sort options: by date, tag count, favorites, etc.

---

## 3. Upload & Processing
- [ ] Implement async queue for image processing (Vision API)
- [ ] Add support for drag-and-drop and multiple file uploads
- [ ] (Optional) Resize images client-side before upload
- [ ] Suggest tags after upload based on Vision API results

---

## 4. Backend / Admin Features
- [ ] Add bulk tagging tools (e.g., tag all photos from a time range)
- [ ] Allow photo deletion from UI
- [ ] Build admin page for upload and tag management
- [ ] Export tag usage and metadata as CSV or JSON

---

## 5. Styling and UX
- [ ] Add loading placeholders or blurred thumbnails
- [ ] Smooth CSS transitions for gallery items
- [ ] Add dark mode toggle
- [ ] Improve mobile responsiveness

---

## 6. Future Vision Features
- [ ] NFC tag support to link zones/bins to photos
- [ ] Track object presence across multiple images
- [ ] AI-powered clustering or duplicate detection
- [ ] Calendar-based navigation (e.g., view a location over time)

---

> Last updated: May 3, 2025
