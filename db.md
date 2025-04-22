# $HOME Tracker – Data Schema

This document describes the current and planned schema for the $HOME tracker project, which stores tagged image entries along with optional metadata like notes and timestamps. The current backend uses SQLite and stores image files in a Kubernetes PVC volume. Future plans include using Google Cloud Storage (GCS) for image files and Firestore for metadata.

---

## Current Implementation (SQLite + PVC)

### Table: `images`

| Column     | Type      | Description                              |
|------------|-----------|------------------------------------------|
| `id`       | TEXT      | UUID, primary key                        |
| `filename` | TEXT      | Original filename or slugified name      |
| `gcs_path` | TEXT      | Relative path to the image in GCS or PVC |
| `timestamp`| DATETIME  | When image was uploaded or captured      |
| `notes`    | TEXT      | Optional freeform notes or captions      |

---

### Table: `tags`

| Column | Type  | Description                     |
|--------|-------|---------------------------------|
| `id`   | TEXT  | UUID, primary key               |
| `name` | TEXT  | Tag name (e.g., "sunset")       |

---

### Table: `image_tags`

| Column     | Type | Description                         |
|------------|------|-------------------------------------|
| `image_id` | TEXT | Foreign key to `images.id`          |
| `tag_id`   | TEXT | Foreign key to `tags.id`            |

This join table allows each image to have multiple tags and each tag to be reused across images.

### Table: `users`

| Column         | Type   | Description                             |
|----------------|--------|-----------------------------------------|
| `id`           | TEXT   | UUID, primary key                       |
| `email`        | TEXT   | User email, unique                      |
| `display_name` | TEXT   | Name shown in UI                        |
| `auth_provider`| TEXT   | e.g., "google", "github"                |

Tracks user accounts and potential access roles (admin, read-only, etc).


Table of users and access - admin, read only, regular, etc

---

## Planned Cloud-Native Design (GCS + Firestore)

In future versions, images will be stored in a GCS bucket and metadata will be moved to Firestore. This reduces the need to manage PVC volumes or HA databases in Kubernetes.

### Firestore Document: `images`

Each image is represented as a document in the `images` collection.

```json
{
  "id": "uuid",
  "filename": "beach.jpg",
  "gcs_path": "uploads/2025-04-21-beach.jpg",
  "timestamp": "2025-04-21T16:40:00Z",
  "tags": ["sunset", "ocean"],
  "notes": "Low tide after the storm"
}
```

### Firestore Document: `tags`

Tags may be optional to track in Firestore if they are always embedded in image docs. If tracked separately:

```json
{
  "name": "sunset",
  "count": 5
}
```

---

## Notes

- Timestamps are stored in UTC in ISO8601 format.
- GCS paths are relative to a configured bucket and prefix (`uploads/`).
- SQLite DB is mountable and can be backed up via cron or sync job.
- Firestore migration would simplify multi-region and serverless setups.

---

*This schema is versioned alongside the API and frontend. Updates should include migration scripts or notes.*
```

## ☁️ Storage Strategy

- **Image Storage**: Utilize Google Cloud Storage (GCS) for storing original images and thumbnails.
- **Access Control**: Serve images via a proxy through `home.fogcat5.com` to manage access and authentication.
- **Scalability**: Centralized storage ensures scalability and facilitates recovery in case of server failures.

---
## Appendix

- [Firestore pricing](https://cloud.google.com/firestore/pricing)
- [GCS signed URL reference](https://cloud.google.com/storage/docs/access-control/signed-urls)
