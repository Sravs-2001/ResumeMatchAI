import streamlit as st
import zipfile
import io
import os
import re
import pdfplumber
import docx2txt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

st.set_page_config(page_title="ResumeMatch AI", page_icon="📄", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.main { background: #f0f2f6; }
.block-container { padding: 2rem 3rem; max-width: 1200px; }

.app-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border-radius: 16px;
    padding: 2.5rem 2rem;
    margin-bottom: 2rem;
    color: white;
    text-align: center;
}
.app-header h1 { font-size: 2.2rem; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
.app-header p { font-size: 1rem; opacity: 0.75; margin: 0.5rem 0 0; font-weight: 300; }

.card {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    border: 1px solid #e8eaf0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    margin-bottom: 1rem;
}
.card-title {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #6b7280;
    margin-bottom: 0.75rem;
}

.match-card {
    background: white;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    border: 1px solid #e8eaf0;
    border-left: 4px solid #10b981;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
    margin-bottom: 0.75rem;
    transition: box-shadow 0.2s;
}
.match-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.1); }
.match-card.good { border-left-color: #f59e0b; }
.match-card.partial { border-left-color: #ef4444; }

.candidate-name { font-size: 1rem; font-weight: 600; color: #111827; }
.candidate-file { font-size: 0.78rem; color: #9ca3af; margin-left: 8px; }

.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    margin-right: 6px;
    margin-top: 6px;
}
.badge-green { background: #d1fae5; color: #065f46; }
.badge-blue  { background: #dbeafe; color: #1e40af; }
.badge-gray  { background: #f3f4f6; color: #374151; }
.badge-exp   { background: #ede9fe; color: #5b21b6; }

.score-bar-bg {
    background: #f3f4f6;
    border-radius: 999px;
    height: 6px;
    width: 100%;
    margin-top: 8px;
}
.score-bar-fill {
    height: 6px;
    border-radius: 999px;
    background: linear-gradient(90deg, #10b981, #059669);
}

.stat-box {
    background: white;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    border: 1px solid #e8eaf0;
    text-align: center;
}
.stat-num { font-size: 1.8rem; font-weight: 700; color: #111827; }
.stat-label { font-size: 0.75rem; color: #6b7280; font-weight: 500; margin-top: 2px; }

.stButton > button {
    background: linear-gradient(135deg, #0f3460, #1a1a2e);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 0.6rem 2rem;
    font-size: 0.95rem;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
    width: 100%;
    height: 3rem;
    cursor: pointer;
}
.stButton > button:hover { opacity: 0.9; }

.stDownloadButton > button {
    background: linear-gradient(135deg, #10b981, #059669) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    width: 100% !important;
    height: 3rem !important;
}

div[data-testid="stRadio"] label { font-size: 0.9rem; font-weight: 500; }
div[data-testid="stTextArea"] textarea {
    border-radius: 10px !important;
    border: 1px solid #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.88rem !important;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>📄 ResumeMatch AI</h1>
    <p>Upload a job description & ZIP of resumes — instantly find your best candidates</p>
</div>
""", unsafe_allow_html=True)

# ── Text extractors ────────────────────────────────────────────────────────────
def extract_text_from_pdf(file_bytes):
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
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
                resumes.append({
                    "name": extract_name_from_text(text, os.path.basename(name)),
                    "file": os.path.basename(name),
                    "text": text,
                    "raw": raw,
                })
    return resumes

def build_matched_zip(matched):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in matched:
            zf.writestr(r["file"], r["raw"])
    buf.seek(0)
    return buf.read()

# ── Skill & experience extraction ─────────────────────────────────────────────
TECH_KEYWORDS = [
    "python","java","javascript","typescript","react","angular","vue","node","nodejs",
    "fastapi","django","flask","spring","express","sql","mysql","postgresql","mongodb",
    "redis","aws","azure","gcp","docker","kubernetes","git","linux","html","css",
    "machine learning","deep learning","nlp","tensorflow","pytorch","pandas","numpy",
    "scikit","spark","hadoop","kafka","airflow","tableau","power bi","excel",
    "c++","c#","golang","rust","scala","kotlin","swift","php","ruby","r",
    "rest","api","graphql","microservices","ci/cd","devops","terraform","jenkins",
    "selenium","pytest","jira","agile","scrum","llm","openai","langchain",
]

def extract_skills(text):
    text_lower = text.lower()
    return [kw for kw in TECH_KEYWORDS if re.search(r'\b' + re.escape(kw) + r'\b', text_lower)]

def extract_experience_years(text):
    patterns = [
        r'(\d+)\+?\s*years?\s+of\s+experience',
        r'(\d+)\+?\s*years?\s+experience',
        r'experience\s+of\s+(\d+)\+?\s*years?',
        r'(\d+)\+?\s*yrs?\s+of\s+experience',
    ]
    years = []
    for p in patterns:
        for m in re.finditer(p, text.lower()):
            y = int(m.group(1))
            if 0 < y < 40:
                years.append(y)
    return max(years) if years else None

def compute_score(jd_text, resume_text, jd_skills, tfidf_score):
    res_skills = extract_skills(resume_text)
    if jd_skills:
        matched_skills = [s for s in jd_skills if s in res_skills]
        skill_score = len(matched_skills) / len(jd_skills)
    else:
        matched_skills = []
        skill_score = 0.0
    # weighted: 50% tfidf + 50% skill overlap
    final = 0.5 * tfidf_score + 0.5 * skill_score
    return round(final, 3), matched_skills, res_skills

def badge_html(text, style="gray"):
    return f'<span class="badge badge-{style}">{text}</span>'

# ── Main layout ───────────────────────────────────────────────────────────────
left, right = st.columns([3, 2], gap="large")

with left:
    st.markdown('<div class="card-title">📋 Job Description</div>', unsafe_allow_html=True)
    job_desc = st.text_area("", height=240,
                            placeholder="Paste the job description here — skills, experience, responsibilities...",
                            label_visibility="collapsed")

with right:
    st.markdown('<div class="card-title">📁 Upload Resumes</div>', unsafe_allow_html=True)
    zip_file = st.file_uploader("", type=["zip"], label_visibility="collapsed",
                                help="ZIP containing PDF, DOCX, or TXT resume files")

    st.markdown('<div style="height:0.8rem"></div>', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🎯 Match Level</div>', unsafe_allow_html=True)
    match_level = st.radio("", [
        "⭐ Best Matches Only",
        "✅ Good Matches",
        "📋 Show All Possible",
    ], index=1, label_visibility="collapsed")

    threshold_map = {
        "⭐ Best Matches Only": 0.55,
        "✅ Good Matches": 0.30,
        "📋 Show All Possible": 0.10,
    }
    threshold = threshold_map[match_level]

st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)

run = st.button("🔍 Find Matching Candidates", type="primary")

if run:
    if not job_desc.strip():
        st.warning("Please enter a job description.")
    elif zip_file is None:
        st.warning("Please upload a ZIP file of resumes.")
    else:
        with st.spinner("Scanning resumes..."):
            resumes = parse_resumes_from_zip(zip_file.read())

        if not resumes:
            st.error("No readable resumes found (PDF / DOCX / TXT).")
        else:
            jd_skills = extract_skills(job_desc)
            jd_exp = extract_experience_years(job_desc)

            texts = [job_desc] + [r["text"][:3000] for r in resumes]
            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf_matrix = vectorizer.fit_transform(texts)
            tfidf_scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])[0]

            results = []
            for i, r in enumerate(resumes):
                final_score, matched_skills, res_skills = compute_score(
                    job_desc, r["text"], jd_skills, float(tfidf_scores[i])
                )
                res_exp = extract_experience_years(r["text"])
                results.append({**r, "score": final_score,
                                "matched_skills": matched_skills,
                                "res_skills": res_skills,
                                "exp": res_exp})

            matched = sorted([r for r in results if r["score"] >= threshold],
                             key=lambda x: -x["score"])

            st.markdown("---")

            # Stats row
            s1, s2, s3, s4 = st.columns(4)
            with s1:
                st.markdown(f'<div class="stat-box"><div class="stat-num">{len(resumes)}</div><div class="stat-label">Resumes Scanned</div></div>', unsafe_allow_html=True)
            with s2:
                st.markdown(f'<div class="stat-box"><div class="stat-num" style="color:#10b981">{len(matched)}</div><div class="stat-label">Candidates Matched</div></div>', unsafe_allow_html=True)
            with s3:
                st.markdown(f'<div class="stat-box"><div class="stat-num" style="color:#0f3460">{len(jd_skills)}</div><div class="stat-label">Skills in JD</div></div>', unsafe_allow_html=True)
            with s4:
                exp_txt = f"{jd_exp}+ yrs" if jd_exp else "—"
                st.markdown(f'<div class="stat-box"><div class="stat-num" style="color:#7c3aed">{exp_txt}</div><div class="stat-label">Experience Required</div></div>', unsafe_allow_html=True)

            st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)

            if matched:
                res_col, dl_col = st.columns([3, 1], gap="large")

                with res_col:
                    st.markdown("### Matched Candidates")
                    for i, r in enumerate(matched, 1):
                        s = r["score"]
                        card_cls = "match-card" if s >= 0.55 else ("match-card good" if s >= 0.30 else "match-card partial")
                        bar_pct = int(s * 100)
                        bar_color = "#10b981" if s >= 0.55 else ("#f59e0b" if s >= 0.30 else "#ef4444")

                        skill_badges = "".join(badge_html(sk, "blue") for sk in r["matched_skills"][:8])
                        if not skill_badges:
                            skill_badges = badge_html("No direct skill match", "gray")

                        exp_badge = badge_html(f"🕐 {r['exp']} yrs exp", "exp") if r["exp"] else ""

                        st.markdown(f"""
                        <div class="{card_cls}">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span class="candidate-name">{i}. {r['name']}</span>
                                <span style="font-size:0.85rem; font-weight:600; color:{bar_color}">{bar_pct}% match</span>
                            </div>
                            <div class="candidate-file">{r['file']}</div>
                            <div class="score-bar-bg">
                                <div class="score-bar-fill" style="width:{bar_pct}%; background:{bar_color}"></div>
                            </div>
                            <div style="margin-top:8px">
                                {exp_badge}
                                {skill_badges}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                with dl_col:
                    st.markdown("### Download")
                    zip_bytes = build_matched_zip(matched)
                    st.download_button(
                        label=f"⬇️ Download {len(matched)} Resumes",
                        data=zip_bytes,
                        file_name="matched_resumes.zip",
                        mime="application/zip",
                    )
                    st.markdown(f"""
                    <div class="card" style="margin-top:1rem">
                        <div class="card-title">Skills in JD</div>
                        {"".join(badge_html(s, "blue") for s in jd_skills) or badge_html("None detected", "gray")}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.warning(f"No candidates matched from {len(resumes)} resumes. Try **'Show All Possible'**.")

st.markdown("---")
st.markdown('<p style="text-align:center; color:#9ca3af; font-size:0.78rem">ResumeMatch AI · TF-IDF + Skill Matching · Streamlit Cloud</p>', unsafe_allow_html=True)
