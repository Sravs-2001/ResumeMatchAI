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

st.title("📄 Resume Job Matcher")
st.markdown("Upload a **job description** and a **ZIP of resumes** — get only the matched candidates.")


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


# --- UI ---
job_desc = st.text_area("Paste Job Description here", height=200,
                        placeholder="e.g. We are looking for a Python developer with 3+ years of experience...")

zip_file = st.file_uploader("Upload ZIP file of resumes (PDF / DOCX / TXT)", type=["zip"])

threshold = st.slider("Match sensitivity (lower = more results)", 0.10, 0.80, 0.25, 0.05,
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
                texts = [job_desc] + [r["text"][:3000] for r in resumes]
                vectorizer = TfidfVectorizer(stop_words="english")
                tfidf_matrix = vectorizer.fit_transform(texts)
                scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])[0]

                results = []
                for i, r in enumerate(resumes):
                    results.append({**r, "score": float(scores[i])})

                matched = [r for r in results if r["score"] >= threshold]
                matched.sort(key=lambda x: x["score"], reverse=True)

                st.markdown("---")
                if matched:
                    st.success(f"✅ {len(matched)} candidate(s) matched out of {len(resumes)}")
                    st.markdown("### Selected Candidates")
                    for i, r in enumerate(matched, 1):
                        st.markdown(f"**{i}. {r['name']}** &nbsp;&nbsp; `score: {r['score']:.2f}`")

                    buf = io.BytesIO()
                    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        for r in matched:
                            zf.writestr(r["file"], r["raw"])
                    buf.seek(0)
                    st.download_button("⬇️ Download Matched Resumes (ZIP)",
                                       buf.read(), "matched_resumes.zip", "application/zip")
                else:
                    st.warning(f"No candidates matched. {len(resumes)} resumes scanned. Try lowering the sensitivity.")

st.markdown("---")
st.caption("Powered by TF-IDF · Deployed on Streamlit Cloud")
