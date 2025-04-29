# 🛠️ Tracker App: SQLite Upgrade Plan

---

## 1. **Database Schema**

You'll need a tiny but powerful set of tables:  
![alt text](static/home-app-schema-diagram.png)

```sql
CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE,
    label TEXT,
    timestamp TEXT
);

CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
);

CREATE TABLE image_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER,
    tag_id INTEGER,
    FOREIGN KEY(image_id) REFERENCES images(id),
    FOREIGN KEY(tag_id) REFERENCES tags(id)
);
```

✅ **One image → multiple tags**  
✅ **One tag → multiple images**  
✅ **Simple join queries for filtering**

---

## 2. **Install Tiny Dependency**

Add `aiosqlite`:

```bash
pip install aiosqlite
```

_(Or regular `sqlite3` if you prefer blocking queries — for now async is nice.)_

---

## 3. **New Python Module**

Create a new file: `scripts/db.py`

It'll have helper functions like:

```python
import aiosqlite

DB_PATH = "uploads/metadata.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(open("scripts/schema.sql").read())
        await db.commit()

async def add_image(filename, label, timestamp):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO images (filename, label, timestamp) VALUES (?, ?, ?)",
            (filename, label, timestamp)
        )
        await db.commit()

async def add_tag(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO tags (name) VALUES (?)",
            (name,)
        )
        await db.commit()

async def link_image_tag(filename, tag_name):
    async with aiosqlite.connect(DB_PATH) as db:
        image_row = await db.execute_fetchone(
            "SELECT id FROM images WHERE filename = ?", (filename,)
        )
        tag_row = await db.execute_fetchone(
            "SELECT id FROM tags WHERE name = ?", (tag_name,)
        )
        if image_row and tag_row:
            await db.execute(
                "INSERT INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                (image_row[0], tag_row[0])
            )
            await db.commit()
```

_(I'll help polish these once you're ready!)_

---

## 4. **Patch Upload Handler**

After the photo is uploaded and AI tagging is done:

```python
await add_image(filename, label, timestamp)
for tag in tags:
    await add_tag(tag)
    await link_image_tag(filename, tag)
```

**Boom** — every photo gets inserted into the DB with attached tags.

---

## 5. **Patch `/photos` Gallery Route**

Instead of reading from GCS blobs, you:

- Query all images from `images` table.
- Join to tags via `image_tags`.
- Filter by tag if `q=...` is passed.

Simple example query:

```sql
SELECT images.filename, images.timestamp, GROUP_CONCAT(tags.name)
FROM images
LEFT JOIN image_tags ON images.id = image_tags.image_id
LEFT JOIN tags ON image_tags.tag_id = tags.id
GROUP BY images.id
```

---

## 6. **Persistent Volume Claim (PVC) for SQLite**

We’ll add a **PVC** to keep the SQLite database persistent across pod restarts and upgrades.

**PVC Example:**

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: tracker-sqlite-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: standard-rwo
```

**Mount it in the Pod Deployment:**

```yaml
spec:
  containers:
  - name: tracker-app
    volumeMounts:
    - mountPath: /uploads
      name: uploads-volume
  volumes:
  - name: uploads-volume
    persistentVolumeClaim:
      claimName: tracker-sqlite-pvc
```

**Notes:**

- SQLite database file (`metadata.db`) will live in `/uploads/metadata.db`.
- We can share this volume with the upload images if needed, or split them if preferred later.
- If you're using Kubernetes namespaces, make sure PVC and Deployment are in the same namespace.

✅ **Database survives pod restarts**  
✅ **Keeps uploads + metadata tightly together**

---

# ✨ Timeline

| Step | Estimate |
|:---|:---|
| Schema + helper file | ~20 minutes |
| Hook into upload pipeline | ~10 minutes |
| Update gallery query | ~30 minutes |
| PVC YAML + volume mount updates | ~15 minutes |
| Testing local uploads | ~30 minutes |
| PR and GKE push | ~1 hour total 🚀 |

---
# backup notes

### 📁 Step 1: Add a PersistentVolumeClaim (PVC)

Ensure your Kubernetes deployment includes a PVC to persist the SQLite database. Here's a sample YAML configuration:


```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: tracker-sqlite-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: standard
```


Mount this PVC to the appropriate path in your pod where the SQLite database resides.

---

### 🔄 Step 2: Implement Daily Backups to GCS

To back up your SQLite database daily to GCS, you can use a Kubernetes CronJob. Here's how:

1. **Create a Backup Script**: Write a script that uses the `.backup` command to safely back up the SQLite database. ([How to backup sqlite database? - Stack Overflow](https://stackoverflow.com/questions/25675314/how-to-backup-sqlite-database?utm_source=chatgpt.com))

   ```bash
   #!/bin/bash
   TIMESTAMP=$(date +"%Y%m%d%H%M%S")
   BACKUP_FILE="metadata_$TIMESTAMP.db"
   sqlite3 /uploads/metadata.db ".backup '/backups/$BACKUP_FILE'"
   gsutil cp /backups/$BACKUP_FILE gs://your-gcs-bucket/sqlite-backups/
   rm /backups/$BACKUP_FILE
   ```


   Ensure that the script has execute permissions and that `gsutil` is authenticated to access your GCS bucket.

2. **Create a Kubernetes CronJob**: Set up a CronJob that runs the backup script daily. ([Cron-based backup - Litestream](https://litestream.io/alternatives/cron/?utm_source=chatgpt.com))

   ```yaml
   apiVersion: batch/v1
   kind: CronJob
   metadata:
     name: sqlite-backup
   spec:
     schedule: "0 2 * * *"  # Runs daily at 2 AM
     jobTemplate:
       spec:
         template:
           spec:
             containers:
             - name: backup
               image: google/cloud-sdk:latest
               volumeMounts:
               - name: uploads
                 mountPath: /uploads
               - name: backups
                 mountPath: /backups
               command: ["/bin/bash", "-c"]
               args:
               - |
                 TIMESTAMP=$(date +"%Y%m%d%H%M%S")
                 BACKUP_FILE="metadata_$TIMESTAMP.db"
                 sqlite3 /uploads/metadata.db ".backup '/backups/$BACKUP_FILE'"
                 gsutil cp /backups/$BACKUP_FILE gs://your-gcs-bucket/sqlite-backups/
                 rm /backups/$BACKUP_FILE
             restartPolicy: OnFailure
             volumes:
             - name: uploads
               persistentVolumeClaim:
                 claimName: tracker-sqlite-pvc
             - name: backups
               emptyDir: {}
   ```


   Replace `your-gcs-bucket` with the name of your GCS bucket.

---

### 🔄 Step 3: Restore from GCS if Local File is Missing or Empty

Modify your application startup logic to check if the local SQLite database file exists and is not empty. If it's missing or empty, download the latest backup from GCS.


```python
import os
import subprocess
from google.cloud import storage

DB_PATH = "/uploads/metadata.db"
GCS_BUCKET = "your-gcs-bucket"
GCS_BACKUP_PREFIX = "sqlite-backups/"

def restore_db_from_gcs():
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blobs = list(bucket.list_blobs(prefix=GCS_BACKUP_PREFIX))
    if not blobs:
        print("No backups found in GCS.")
        return
    latest_blob = max(blobs, key=lambda b: b.updated)
    latest_blob.download_to_filename(DB_PATH)
    print(f"Restored database from {latest_blob.name}")

if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
    restore_db_from_gcs()
```


Ensure that your application has the necessary permissions to access GCS and that the `google-cloud-storage` Python package is installed.
 