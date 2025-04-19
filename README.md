# Slack Thread Watcher

A personal web app that shows the most recent Slack threads from selected internal channels. Useful for reviewing team updates each morning — especially on mobile.

---

## 🔧 Features

- Extracts thread content from specific Slack channels using Playwright automation
- Displays messages in a clean, mobile-friendly web interface
- Built with FastAPI + vanilla HTML/JS
- Deployable to GKE or locally via Docker/Kubernetes

---

## 📸 Screenshot

> _(optional — add a screenshot of the UI here)_

---

## 🛠️ Setup Instructions

### 1. Clone and Setup Virtualenv
```bash
git clone https://github.com/yourname/slack-thread-watcher.git
cd slack-thread-watcher
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Fetch Script
This opens Slack via Playwright (with saved login) and extracts active threads:
```bash
python scraper/fetch_threads.py
```

Output is written to:
```
output/threads.json
```

### 3. Start the Web UI
```bash
uvicorn slack_status_webapp:app --reload
```

Then visit: [http://localhost:8000](http://localhost:8000)

---

## 🔒 Authentication

This app currently uses a saved browser session. A Slack app is not required (and may not be allowed on your corporate workspace). GCP OAuth login support is planned.

---

## 🚀 Deployment Ideas

- ✅ Run as a local tool on your laptop
- ☁️ Deploy to GKE with SSL on `slack.fogcat5.com`
- 🔁 Set up a Kubernetes CronJob to update threads hourly
- 🔐 Add Google OAuth to restrict access

---

## 📂 Project Structure

```
slack-thread-watcher/
├── scraper/                  # Python script using Playwright
├── output/threads.json       # Saved thread data
├── slack_status_webapp.py    # FastAPI server
├── static/                   # Static JS/CSS assets (optional)
├── templates/                # HTML templates (optional)
├── run.sh                    # Shortcut launcher (optional)
└── requirements.txt
```

---

## 🙋‍♂️ Author

**Rodney Peck** — [fogcat5.com](https://fogcat5.com)

---

## 📄 License

MIT License (or feel free to customize for internal use)
