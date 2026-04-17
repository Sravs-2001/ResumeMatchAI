# ResumeMatchAI

Upload a **job description** + ZIP of resumes → instantly see **only matching candidates** ranked by score.

**Stack:** FastAPI backend · Vanilla JS/HTML/CSS frontend · sentence-transformers (no API key)

---

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
# open http://localhost:8000
```

---

## Deploy FREE

### Option 1 — Render (recommended, always-on free tier)
1. Push this folder to a GitHub repo
2. Go to **render.com** → New → Web Service → connect your repo
3. Set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Deploy → get a public HTTPS URL

### Option 2 — Railway
1. Push to GitHub
2. **railway.app** → New Project → Deploy from GitHub
3. It auto-detects FastAPI; set start command same as above
4. Free $5/month credit (enough for light use)

### Option 3 — Hugging Face Spaces (Gradio/Docker)
Use Docker SDK:
- Add a `Dockerfile` pointing to uvicorn
- HF Spaces serves it free

---

## File structure

```
├── main.py          ← FastAPI app + matching logic
├── requirements.txt
├── static/
│   ├── index.html   ← Frontend UI
│   ├── style.css    ← Dark theme styling
│   └── script.js    ← Drag-drop, fetch, results render
└── README.md
```
