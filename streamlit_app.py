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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main { background: #f5f7fa; }
.block-container { padding: 2rem 2rem; max-width: 800px; }

.app-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);
    border-radius: 14px; padding: 2rem 1.5rem;
    margin-bottom: 1.8rem; color: white; text-align: center;
}
.app-header h1 { font-size: 1.9rem; font-weight: 700; margin: 0; }
.app-header p  { font-size: 0.9rem; opacity: 0.7; margin: 0.4rem 0 0; }

.match-card {
    background: white; border-radius: 10px; padding: 1rem 1.2rem;
    border: 1px solid #e5e7eb; border-left: 4px solid #10b981;
    margin-bottom: 0.6rem; box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.match-card.consider { border-left-color: #f59e0b; }
.match-card.pass     { border-left-color: #ef4444; }

.cname   { font-size: 0.95rem; font-weight: 600; color: #111827; }
.cfile   { font-size: 0.74rem; color: #9ca3af; margin-left: 6px; }
.creason { font-size: 0.8rem; color: #4b5563; margin-top: 5px; line-height: 1.5; }

.tag { display:inline-block; padding:2px 8px; border-radius:999px;
       font-size:0.7rem; font-weight:600; margin:3px 2px 0 0; }
.tg  { background:#d1fae5; color:#065f46; }
.tr  { background:#fee2e2; color:#991b1b; }

.bar-bg   { background:#f3f4f6; border-radius:999px; height:5px; width:100%; margin-top:6px; }
.bar-fill { height:5px; border-radius:999px; }

.tier-lbl { font-size:0.95rem; font-weight:700; margin:1.2rem 0 0.5rem;
            padding-bottom:4px; border-bottom:2px solid; }

.reject-card {
    background: #fff8f8; border-radius: 8px; padding: 0.6rem 1rem;
    border: 1px solid #fecaca; border-left: 3px solid #ef4444;
    margin-bottom: 0.4rem; font-size: 0.8rem; color: #6b7280;
}
.reject-name { font-weight: 600; color: #374151; }
.reject-why  { color: #ef4444; font-size: 0.75rem; margin-left: 6px; }

.stButton>button {
    background:linear-gradient(135deg,#0f3460,#1a1a2e); color:white;
    border:none; border-radius:10px; font-weight:600;
    font-family:'Inter',sans-serif; width:100%; height:3rem; font-size:0.95rem;
}
.stDownloadButton>button {
    background:linear-gradient(135deg,#10b981,#059669) !important;
    color:white !important; border:none !important; border-radius:8px !important;
    font-weight:600 !important; width:100% !important; height:2.6rem !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="app-header">
    <h1>📄 Resume Matcher</h1>
    <p>Screens resumes like a recruiter — filters first, then ranks the best fits</p>
</div>
""", unsafe_allow_html=True)

# ── Skill synonyms ────────────────────────────────────────────────────────────
SYNONYMS = {
    "js": "javascript", "reactjs": "react", "nodejs": "node", "vuejs": "vue",
    "angularjs": "angular", "py": "python", "ml": "machine learning",
    "ai": "artificial intelligence", "dl": "deep learning",
    "nlp": "natural language processing", "k8s": "kubernetes",
    "tf": "tensorflow", "cv": "computer vision", "oop": "object oriented",
    "ci/cd": "devops", "rest api": "api", "restful": "api",
    "ms sql": "sql server", "mssql": "sql server",
    "postgres": "postgresql", "mongo": "mongodb",
    "aws": "cloud", "azure": "cloud", "gcp": "cloud", "rdbms": "sql",
}

KNOWN_SKILLS = [
    "python","java","javascript","typescript","react","angular","vue","node",
    "django","flask","fastapi","spring","sql","mysql","postgresql","mongodb",
    "redis","aws","azure","gcp","cloud","docker","kubernetes","git","linux",
    "machine learning","deep learning","nlp","tensorflow","pytorch","pandas",
    "numpy","scikit","spark","hadoop","kafka","airflow","tableau","power bi",
    "c++","c#","golang","rust","scala","kotlin","swift","php","ruby",
    "api","graphql","microservices","devops","terraform","jenkins","agile","scrum",
    "html","css","selenium","jira","llm","openai","langchain","computer vision",
    "object oriented","data structures","algorithms","excel",
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def extract_pdf(b):
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(b)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: text += t + "\n"
    except: pass
    return text.strip()

def extract_docx(b):
    try: return docx2txt.process(io.BytesIO(b)).strip()
    except: return ""

def extract_txt(b):
    try: return b.decode("utf-8", errors="ignore").strip()
    except: return ""

def get_name(text, filename):
    for line in [l.strip() for l in text.splitlines() if l.strip()][:5]:
        if re.match(r"^[A-Za-z][a-zA-Z .'-]{3,40}$", line) and len(line.split()) >= 2:
            return line
    return os.path.splitext(filename)[0].replace("_"," ").replace("-"," ").title()

def normalize(text):
    text = text.lower()
    for v, c in SYNONYMS.items():
        text = re.sub(r'\b' + re.escape(v) + r'\b', c, text)
    return text

def extract_years(text):
    patterns = [
        r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
        r'experience\s+of\s+(\d+)\+?\s*years?',
        r'(\d+)\+?\s*(?:yr|yrs)\s+(?:of\s+)?experience',
    ]
    for p in patterns:
        m = re.search(p, text.lower())
        if m:
            y = int(m.group(1))
            if 0 < y < 40: return y
    return None

def get_skills_in_text(text):
    norm = normalize(text)
    return [s for s in KNOWN_SKILLS if re.search(r'\b' + re.escape(s) + r'\b', norm)]

def extract_primary_skills(jd_text):
    """Skills that appear to be required/must-have in the JD."""
    norm = normalize(jd_text.lower())
    found = []
    # Skills near "required", "must", "need", "experience in/with"
    required_zone = re.findall(
        r'(?:required|must.have|need|looking for|experience (?:in|with)|proficiency in|expertise in)'
        r'[^.]{0,120}', norm)
    required_text = " ".join(required_zone)
    for s in KNOWN_SKILLS:
        if re.search(r'\b' + re.escape(s) + r'\b', required_text):
            found.append(s)
    # Also count frequency — skills mentioned 2+ times in JD are primary
    for s in KNOWN_SKILLS:
        matches = re.findall(r'\b' + re.escape(s) + r'\b', norm)
        if len(matches) >= 2 and s not in found:
            found.append(s)
    # Fall back: any skill in JD counts as primary if list is small
    if len(found) < 3:
        found = get_skills_in_text(jd_text)
    return found

def parse_zip(zb):
    out = []
    with zipfile.ZipFile(io.BytesIO(zb)) as zf:
        for name in zf.namelist():
            if name.startswith("__MACOSX") or name.endswith("/"): continue
            ext = os.path.splitext(name)[1].lower()
            with zf.open(name) as f: raw = f.read()
            if   ext == ".pdf":           text = extract_pdf(raw)
            elif ext in (".docx",".doc"): text = extract_docx(raw)
            elif ext == ".txt":           text = extract_txt(raw)
            else: continue
            if text:
                out.append({"name": get_name(text, os.path.basename(name)),
                            "file": os.path.basename(name),
                            "text": text, "raw": raw})
    return out

def make_zip(candidates):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
        for r in candidates: zf.writestr(r["file"], r["raw"])
    buf.seek(0); return buf.read()


# ── Core matching — human-like recruiter logic ────────────────────────────────
def human_match(jd, resumes):
    jd_norm        = normalize(jd)
    primary_skills = extract_primary_skills(jd)
    all_jd_skills  = get_skills_in_text(jd)
    jd_exp         = extract_years(jd)

    # TF-IDF for overall content similarity
    texts      = [jd_norm] + [normalize(r["text"][:4000]) for r in resumes]
    vec        = TfidfVectorizer(stop_words="english", ngram_range=(1,2))
    mat        = vec.fit_transform(texts)
    tfidf_sims = cosine_similarity(mat[0:1], mat[1:])[0]

    qualified = []
    rejected  = []

    for i, r in enumerate(resumes):
        rtext  = r["text"]
        rnorm  = normalize(rtext)
        r_exp  = extract_years(rtext)
        r_skills = get_skills_in_text(rtext)

        # ── STEP 1: Experience gate ───────────────────────────────────────
        exp_fail = False
        if jd_exp and r_exp is not None and r_exp < jd_exp - 2:
            exp_fail = True

        # ── STEP 2: Primary skills gate ───────────────────────────────────
        if primary_skills:
            pri_matched = [s for s in primary_skills if s in r_skills]
            pri_rate    = len(pri_matched) / len(primary_skills)
        else:
            pri_matched = []
            pri_rate    = 1.0

        skill_fail = pri_rate < 0.25  # missing >75% of primary skills → reject

        # ── Hard reject ───────────────────────────────────────────────────
        if exp_fail and skill_fail:
            why = []
            if exp_fail:   why.append(f"needs {jd_exp}+ yrs, has {r_exp}")
            if skill_fail: why.append(f"only {int(pri_rate*100)}% primary skills match")
            rejected.append({**r, "why": " · ".join(why)})
            continue

        # ── STEP 3: Score qualified candidates ───────────────────────────
        all_matched = [s for s in all_jd_skills if s in r_skills]
        skill_score = len(all_matched) / len(all_jd_skills) if all_jd_skills else 0.0
        gaps        = [s for s in primary_skills if s not in r_skills][:4]

        # weighted: 50% TF-IDF content + 50% skill overlap
        raw = 0.5 * tfidf_sims[i] + 0.5 * skill_score
        # soft penalty for exp shortfall (not enough to reject but worth noting)
        if exp_fail:
            raw *= 0.85

        score_pct = min(int(raw * 200), 100)

        if score_pct >= 70:   verdict = "Strong Match"
        elif score_pct >= 45: verdict = "Good Match"
        else:                  verdict = "Partial Match"

        parts = []
        if all_matched:
            parts.append(f"Has: {', '.join(all_matched[:4])}")
        if r_exp:
            parts.append(f"{r_exp} yrs exp")
            if jd_exp:
                parts.append("✓ meets requirement" if not exp_fail else f"⚠ below required {jd_exp} yrs")
        if gaps:
            parts.append(f"Missing: {', '.join(gaps[:2])}")
        summary = " · ".join(parts) if parts else "Good overall profile match."

        qualified.append({**r,
            "score":   score_pct,
            "verdict": verdict,
            "matched": all_matched[:6],
            "gaps":    gaps[:3],
            "summary": summary,
        })

    qualified.sort(key=lambda x: -x["score"])
    return qualified, rejected


# ── UI ────────────────────────────────────────────────────────────────────────
job_desc = st.text_area("📋 Job Description", height=200,
                        placeholder="Paste the job description here...")

zip_file = st.file_uploader("📁 Upload ZIP of Resumes (PDF / DOCX / TXT)", type=["zip"])

st.markdown("")
run = st.button("Find Matching Candidates", type="primary")

if run:
    if not job_desc.strip():
        st.warning("Please paste a job description.")
    elif zip_file is None:
        st.warning("Please upload a ZIP of resumes.")
    else:
        with st.spinner("Screening resumes..."):
            resumes  = parse_zip(zip_file.read())

        if not resumes:
            st.error("No readable resumes found (PDF / DOCX / TXT).")
        else:
            with st.spinner("Ranking candidates..."):
                qualified, rejected = human_match(job_desc, resumes)

            shortlist = [r for r in qualified if r["score"] >= 70]
            consider  = [r for r in qualified if r["score"] < 70]

            st.markdown("---")
            st.success(
                f"✅ Scanned **{len(resumes)}** resumes — "
                f"**{len(shortlist)}** shortlisted · **{len(consider)}** to consider · "
                f"**{len(rejected)}** filtered out"
            )

            def render_qualified(candidates, label, color, css, offset=0):
                if not candidates: return
                st.markdown(
                    f'<div class="tier-lbl" style="color:{color};border-color:{color}30">'
                    f'{label} &nbsp;<span style="font-size:0.8rem;opacity:0.7">({len(candidates)})</span>'
                    f'</div>', unsafe_allow_html=True)
                for i, r in enumerate(candidates, offset+1):
                    s  = r["score"]
                    mt = "".join(f'<span class="tag tg">{t}</span>' for t in r["matched"])
                    gt = "".join(f'<span class="tag tr">✗ {t}</span>' for t in r["gaps"])
                    card = (
                        f'<div class="match-card {css}">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center">'
                        f'<span class="cname">#{i} {r["name"]}</span>'
                        f'<span style="font-weight:700;color:{color};font-size:0.88rem">{s}%</span>'
                        f'</div>'
                        f'<span class="cfile">{r["file"]}</span>'
                        f'<div class="bar-bg"><div class="bar-fill" style="width:{s}%;background:{color}"></div></div>'
                        f'<div class="creason">{r["summary"]}</div>'
                        f'<div style="margin-top:6px">{mt}{gt}</div>'
                        f'</div>'
                    )
                    st.markdown(card, unsafe_allow_html=True)

            render_qualified(shortlist, "✅ Shortlist — Interview these",    "#10b981", "")
            render_qualified(consider,  "🤔 Consider — Worth a closer look", "#f59e0b", "consider", len(shortlist))

            # Rejected section — collapsed by default
            if rejected:
                with st.expander(f"❌ Filtered Out ({len(rejected)}) — missing experience or key skills"):
                    for r in rejected:
                        card = (
                            f'<div class="reject-card">'
                            f'<span class="reject-name">{r["name"]}</span>'
                            f'<span class="cfile">{r["file"]}</span>'
                            f'<span class="reject-why"> — {r["why"]}</span>'
                            f'</div>'
                        )
                        st.markdown(card, unsafe_allow_html=True)

            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            with c1:
                if shortlist:
                    st.download_button(f"⬇️ Shortlist ({len(shortlist)})",
                        make_zip(shortlist),"shortlist.zip","application/zip",key="d1")
            with c2:
                if consider:
                    st.download_button(f"⬇️ Consider ({len(consider)})",
                        make_zip(consider),"consider.zip","application/zip",key="d2")
            with c3:
                if shortlist or consider:
                    st.download_button(f"⬇️ All Qualified ({len(shortlist)+len(consider)})",
                        make_zip(shortlist+consider),"qualified.zip","application/zip",key="d3")

st.markdown("---")
st.caption("Resume Matcher · No API key needed · Streamlit Cloud")
