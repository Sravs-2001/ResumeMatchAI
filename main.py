from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sentence_transformers import SentenceTransformer, util
import zipfile
import io
import os
import re
import pdfplumber
import docx2txt

app = FastAPI()

model = SentenceTransformer("all-MiniLM-L6-v2")


# ── text extractors ──────────────────────────────────────────────────────────

def extract_pdf(raw: bytes) -> str:
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except Exception:
        pass
    return text.strip()


def extract_docx(raw: bytes) -> str:
    try:
        return docx2txt.process(io.BytesIO(raw)).strip()
    except Exception:
        return ""


def extract_txt(raw: bytes) -> str:
    return raw.decode("utf-8", errors="ignore").strip()


def extract_name(text: str, filename: str) -> str:
    for line in [l.strip() for l in text.splitlines() if l.strip()][:5]:
        if re.match(r"^[A-Za-z][a-zA-Z .'-]{3,40}$", line) and len(line.split()) >= 2:
            return line
    return os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()


def parse_zip(zip_bytes: bytes) -> list[dict]:
    resumes = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.startswith("__MACOSX") or name.endswith("/"):
                continue
            ext = os.path.splitext(name)[1].lower()
            with zf.open(name) as f:
                raw = f.read()
            if ext == ".pdf":
                text = extract_pdf(raw)
            elif ext in (".docx", ".doc"):
                text = extract_docx(raw)
            elif ext == ".txt":
                text = extract_txt(raw)
            else:
                continue
            if text:
                fname = os.path.basename(name)
                resumes.append({"name": extract_name(text, fname), "file": fname, "text": text})
    return resumes


# ── API ──────────────────────────────────────────────────────────────────────

@app.post("/match")
async def match(
    job_description: str = Form(...),
    resumes_zip: UploadFile = File(...),
    threshold: float = Form(0.35),
):
    zip_bytes = await resumes_zip.read()
    resumes = parse_zip(zip_bytes)

    if not resumes:
        return JSONResponse({"error": "No readable resumes found (PDF/DOCX/TXT)."}, status_code=400)

    jd_vec = model.encode(job_description, convert_to_tensor=True)
    results = []
    for r in resumes:
        rv = model.encode(r["text"][:3000], convert_to_tensor=True)
        score = round(float(util.cos_sim(jd_vec, rv)), 3)
        results.append({"name": r["name"], "file": r["file"], "score": score})

    matched = sorted([r for r in results if r["score"] >= threshold], key=lambda x: -x["score"])
    all_sorted = sorted(results, key=lambda x: -x["score"])

    return {
        "total": len(resumes),
        "matched": len(matched),
        "threshold": threshold,
        "candidates": matched,
        "all": all_sorted,
    }


# ── static frontend ──────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")
