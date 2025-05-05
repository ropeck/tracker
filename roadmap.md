# 🛣️ Project Development Roadmap

This roadmap outlines the planned features and improvements for the application.

## ✅ Milestone 1: Core Functionality (Completed)

* [x] Implement photo upload and thumbnail generation
* [x] Integrate AI-based tagging for uploaded photos
* [x] Deploy application on Kubernetes with HTTPS support
* [x] Enable user authentication via Google OAuth
* [x] Ensure mobile compatibility for photo uploads
* [x] Add tag-based filtering and basic AI-powered search
* [x] Deploy GCS summary.txt-based rebuild mechanism
* [x] Allow forced DB rebuild via `/rebuild?force=true` or `FORCE_REBUILD` env
* [x] Tag v0.6.2 — stable rebuild system deployed and validated in prod

---

## 🚧 Milestone 2: Administrative Tools

* [ ] Develop UI for renaming and deleting photos
* [ ] Implement tag management features
* [ ] Add user management capabilities
* [ ] Add tag editing UI (planned for `v0.6.5`)

---

## 📦 Milestone 3: Backend Enhancements

* [ ] Design and integrate a relational database (e.g., PostgreSQL) for metadata storage
* [ ] Migrate existing metadata to the new database schema
* [ ] Establish robust access control mechanisms for image serving
* [ ] Implement DB snapshot backups and incremental rebuild (`v0.6.4`)

---

## 🌐 Milestone 4: User Experience Improvements

* [ ] Enhance navigation and UI/UX design
* [ ] Implement search and filtering capabilities
* [x] Add AI-powered free-form tag search (`v0.6.2`)
* [ ] Paginate `/photos` and `/search` pages for large galleries (`v0.6.5`)
* [ ] Clean and normalize tags in UI (`v0.6.5`)

---

## 🔮 Milestone 5: Future Considerations

* [ ] Introduce background processing for intensive tasks (e.g., AI tagging)
* [ ] Develop a queuing system for handling uploads and processing
* [ ] Explore multi-user support with role-based access controls