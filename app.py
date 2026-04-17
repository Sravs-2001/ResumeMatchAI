import streamlit as st
import zipfile
import io
import os
import re
from sentence_transformers import SentenceTransformer, util
import pdfplumber
import docx2txt

st.set_page_config(page_title="Resume Matcher", page_icon="📄", layout="centered")

st.title("📄 Resume Job Matcher")
st.markdown("Upload a **job description** and a **ZIP of resumes** — get only the matched candidates.")

@st.cache_resource
def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = load_model()


def extract_text_from_pdf(file_bytes):
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception:
        pass
    return text.strip()


def extract_text_from_docx(file_bytes):
    try:
        return docx2txt.process(io.BytesIO(file_bytes)).strip()
    except Exception:
        return ""


def extract_text_from_txt(file_bytes):
    try:
        return file_bytes.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def extract_name_from_text(text, filename):
    """Try to extract candidate name from top lines of resume, fallback to filename."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:5]:
        # A name is typically 2-4 words, no special chars, no digits
        if re.match(r"^[A-Za-z][a-zA-Z .'-]{3,40}$", line) and len(line.split()) >= 2:
            return line
    # Fallback: use filename without extension
    name = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()
    return name


def parse_resumes_from_zip(zip_bytes):
    resumes = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.startswith("__MACOSX") or name.endswith("/"):
                continue
            ext = os.path.splitext(name)[1].lower()
            with zf.open(name) as f:
                raw = f.read()
            if ext == ".pdf":
                text = extract_text_from_pdf(raw)
            elif ext in (".docx", ".doc"):
                text = extract_text_from_docx(raw)
            elif ext == ".txt":
                text = extract_text_from_txt(raw)
            else:
                continue
            if text:
                candidate_name = extract_name_from_text(text, os.path.basename(name))
                resumes.append({"name": candidate_name, "file": os.path.basename(name), "text": text})
    return resumes


# --- UI ---
job_desc = st.text_area("Paste Job Description here", height=200, placeholder="e.g. We are looking for a Python developer with 3+ years of experience...")

zip_file = st.file_uploader("Upload ZIP file of resumes (PDF / DOCX / TXT)", type=["zip"])

threshold = st.slider("Match sensitivity (lower = more results)", 0.20, 0.80, 0.35, 0.05,
                      help="Cosine similarity threshold. Raise it to be stricter.")

if st.button("Find Matching Candidates", type="primary"):
    if not job_desc.strip():
        st.warning("Please enter a job description.")
    elif zip_file is None:
        st.warning("Please upload a ZIP file of resumes.")
    else:
        with st.spinner("Analyzing resumes..."):
            resumes = parse_resumes_from_zip(zip_file.read())
            if not resumes:
                st.error("No readable resumes found in the ZIP (support: PDF, DOCX, TXT).")
            else:
                jd_embedding = model.encode(job_desc, convert_to_tensor=True)
                results = []
                for r in resumes:
                    res_embedding = model.encode(r["text"][:3000], convert_to_tensor=True)
                    score = float(util.cos_sim(jd_embedding, res_embedding))
                    results.append({**r, "score": score})

                matched = [r for r in results if r["score"] >= threshold]
                matched.sort(key=lambda x: x["score"], reverse=True)

                st.markdown("---")
                if matched:
                    st.success(f"✅ {len(matched)} candidate(s) matched out of {len(resumes)}")
                    st.markdown("### Selected Candidates")
                    for i, r in enumerate(matched, 1):
                        st.markdown(f"**{i}. {r['name']}** &nbsp;&nbsp; `score: {r['score']:.2f}`")
                else:
                    st.warning(f"No candidates matched. {len(resumes)} resumes scanned. Try lowering the sensitivity.")

st.markdown("---")
st.caption("Powered by `sentence-transformers/all-MiniLM-L6-v2` · Deploy free on Hugging Face Spaces or Streamlit Cloud")
