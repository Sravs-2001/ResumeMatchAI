import streamlit as st
import zipfile
import io
import os
import re
import pdfplumber
import docx2txt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

st.set_page_config(page_title="Resume Matcher", page_icon="📄", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #f8f9fb; }
    .block-container { padding-top: 2rem; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3rem; font-size: 1rem; }
    .candidate-card {
        background: white;
        border-left: 5px solid #4CAF50;
        border-radius: 8px;
        padding: 12px 18px;
        margin-bottom: 10px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    </style>
""", unsafe_allow_html=True)

st.title("📄 Resume Job Matcher")
st.markdown("Upload a **job description** and **ZIP of resumes** — download only the best matched candidates.")
st.markdown("---")


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
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:5]:
        if re.match(r"^[A-Za-z][a-zA-Z .'-]{3,40}$", line) and len(line.split()) >= 2:
            return line
    return os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()


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
                resumes.append({"name": candidate_name, "file": os.path.basename(name), "text": text, "raw": raw})
    return resumes


def build_matched_zip(matched):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in matched:
            zf.writestr(r["file"], r["raw"])
    buf.seek(0)
    return buf.read()


def score_label(score):
    if score >= 0.6:
        return "🟢 Strong Match"
    elif score >= 0.35:
        return "🟡 Good Match"
    else:
        return "🟠 Partial Match"


# --- UI ---
col1, col2 = st.columns([1, 1])

with col1:
    job_desc = st.text_area("📋 Paste Job Description", height=220,
                            placeholder="e.g. Looking for a Python developer with 3+ years experience in ML...")

with col2:
    zip_file = st.file_uploader("📁 Upload ZIP of Resumes (PDF / DOCX / TXT)", type=["zip"])

    st.markdown("#### 🎯 Match Level")
    match_level = st.radio(
        "Select how strict the matching should be:",
        options=["🟢 Best Matches Only", "🟡 Good Matches", "🟠 Show All Possible"],
        index=1,
        help="Best = very relevant only | Good = balanced | All = broader results"
    )

    threshold_map = {
        "🟢 Best Matches Only": 0.50,
        "🟡 Good Matches": 0.25,
        "🟠 Show All Possible": 0.10,
    }
    threshold = threshold_map[match_level]

st.markdown("---")

if st.button("🔍 Find Matching Candidates", type="primary"):
    if not job_desc.strip():
        st.warning("⚠️ Please enter a job description.")
    elif zip_file is None:
        st.warning("⚠️ Please upload a ZIP file of resumes.")
    else:
        with st.spinner("Analyzing resumes..."):
            resumes = parse_resumes_from_zip(zip_file.read())
            if not resumes:
                st.error("❌ No readable resumes found in the ZIP (supported: PDF, DOCX, TXT).")
            else:
                texts = [job_desc] + [r["text"][:3000] for r in resumes]
                vectorizer = TfidfVectorizer(stop_words="english")
                tfidf_matrix = vectorizer.fit_transform(texts)
                scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])[0]

                results = [{**r, "score": float(scores[i])} for i, r in enumerate(resumes)]
                matched = sorted([r for r in results if r["score"] >= threshold], key=lambda x: -x["score"])

                if matched:
                    st.success(f"✅ **{len(matched)} candidate(s) matched** out of {len(resumes)} resumes")

                    st.markdown("### 👥 Matched Candidates")
                    for i, r in enumerate(matched, 1):
                        st.markdown(f"""
                        <div class="candidate-card">
                            <b>{i}. {r['name']}</b> &nbsp;&nbsp;
                            <span style="color:gray; font-size:0.85rem">{r['file']}</span><br/>
                            <span style="font-size:0.9rem">{score_label(r['score'])}</span>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("")
                    zip_bytes = build_matched_zip(matched)
                    st.download_button(
                        label="⬇️ Download Matched Resumes (ZIP)",
                        data=zip_bytes,
                        file_name="matched_resumes.zip",
                        mime="application/zip",
                        type="primary",
                    )
                else:
                    st.warning(f"⚠️ No candidates matched. {len(resumes)} resumes scanned. Try **'Show All Possible'** match level.")

st.markdown("---")
st.caption("Powered by TF-IDF · Deployed on Streamlit Cloud")
