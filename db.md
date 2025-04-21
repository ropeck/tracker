# 📄 Database Design Overview

This document outlines the proposed database schema and storage strategies for your photo management application.

## 📁 Tables

### `photos`

- **id**: UUID, primary key
- **filename**: string
- **upload_timestamp**: datetime
- **uploader_id**: foreign key to `users`
- **original_url**: string (GCS path)
- **thumbnail_url**: string (GCS path)
- **metadata**: JSON (e.g., EXIF data, AI tags)

### `tags`

- **id**: UUID, primary key
- **name**: string, unique

### `photo_tags`

- **photo_id**: foreign key to `photos`
- **tag_id**: foreign key to `tags`

### `users`

- **id**: UUID, primary key
- **email**: string, unique
- **display_name**: string
- **auth_provider**: string (e.g., Google)

## ☁️ Storage Strategy

- **Image Storage**: Utilize Google Cloud Storage (GCS) for storing original images and thumbnails.
- **Access Control**: Serve images via a proxy through `home.fogcat5.com` to manage access and authentication.
- **Scalability**: Centralized storage ensures scalability and facilitates recovery in case of server failures.
