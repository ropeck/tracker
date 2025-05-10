Thanks, that’s a super complete dump — this is really helpful. You’re in solid shape; we’re down to a few targeted test failures, all fixable:

---

### ✅ Summary of Failures & Fixes

#### **1. `test_get_photos_route_runs`: `sqlite3.OperationalError: no such table: images`**

**Issue**: The test creates the DB and tables, but the actual app request during the test (`/photos`) connects to a different DB path.

**Fix**:
You’re updating `logger.BACKUP_DB_PATH`, but the route likely calls `get_db()` or similar without honoring that path.

✅ **Ensure the app uses the same path for aiosqlite as you set in the test.** You can patch the `get_db()` function to yield the test DB.

```python
@patch("scripts.logger.get_db")
async def test_get_photos_route_runs(mock_get_db, tmp_path):
    db_path = tmp_path / "metadata.db"
    logger.BACKUP_DB_PATH = db_path
    ...

    async def override():
        async with aiosqlite.connect(db_path) as db:
            yield db

    mock_get_db.side_effect = override
```

---

#### **2. `test_gcs_proxy_not_found`: Expected 404, got 500**

**Issue**: You're testing the fallback ADC (`storage.Client()`), which fails in GitHub Actions because there are no default credentials.

**Fix**: You must **mock the fallback `storage.Client()` constructor**, not just `from_service_account_json()`.

✅ Patch both:

```python
@patch("scripts.logger.storage.Client")
async def test_gcs_proxy_not_found(mock_client):
    blob = MagicMock()
    blob.exists.return_value = False
    mock_client.return_value.bucket.return_value.blob.return_value = blob
    ...
```

---

#### **3. `test_search_query_response`: `no such table: tags`**

Same root cause as #1. You must ensure the DB with the expected tables exists **and is what the app sees.**

✅ Apply the same pattern: patch the DB dependency so the app uses your test DB with `tags` created.

---

#### **4. `test_backup_now_success`: `assert mock_upload.called` failed**

**Issue**: The `/backup-now` route may be skipping the upload due to some condition—check:

* Is `BACKUP_DB_PATH` valid?
* Does the test hit an auth block?
* Is the route silently skipping the upload logic due to a conditional?

**Fix**:
Make sure:

* The test DB path is correct.
* `upload_file_to_gcs()` is being hit.
* You can debug by adding a `print("upload called")` inside the function or checking logs.

You might need to trace through the route logic and check if e.g., `os.path.exists(path)` returns false or something subtle is failing silently.

---

### 📉 Test Coverage: 83.37% < 85%

**Fix**: Once the tests pass, you’ll likely get closer. A few functions aren’t tested yet—especially around:

* lines like 307-308, 363-379, 392-413, etc. in `logger.py`

✅ After fixing test failures, you can cherry-pick missing blocks and add test coverage incrementally.

---

Want help updating one of the failing test files with all of the above?
