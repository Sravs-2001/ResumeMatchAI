import streamlit as st
import zipfile
import io
import os
import re
import json
import pdfplumber
import docx2txt
import anthropic

st.set_page_config(page_title="ResumeMatch AI", page_icon="📄", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main { background: #f0f2f6; }
.block-container { padding: 2rem 3rem; max-width: 1200px; }

.app-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border-radius: 16px; padding: 2.5rem 2rem;
    margin-bottom: 2rem; color: white; text-align: center;
}
.app-header h1 { font-size: 2.2rem; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
.app-header p  { font-size: 1rem; opacity: 0.75; margin: 0.5rem 0 0; font-weight: 300; }

.match-card {
    background: white; border-radius: 12px; padding: 1.2rem 1.5rem;
    border: 1px solid #e8eaf0; border-left: 4px solid #10b981;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05); margin-bottom: 0.75rem;
}
.match-card.good    { border-left-color: #f59e0b; }
.match-card.partial { border-left-color: #ef4444; }

.candidate-name { font-size: 1rem; font-weight: 600; color: #111827; }
.candidate-file { font-size: 0.78rem; color: #9ca3af; margin-left: 8px; }
.highlight-text { font-size: 0.82rem; color: #1d4ed8; margin-top: 5px; font-style: italic; line-height: 1.5; }
.reason-text    { font-size: 0.82rem; color: #4b5563; margin-top: 4px; line-height: 1.5; }

.tag {
    display: inline-block; padding: 2px 9px; border-radius: 999px;
    font-size: 0.72rem; font-weight: 600; margin: 3px 3px 0 0;
}
.tag-green  { background:#d1fae5; color:#065f46; }
.tag-red    { background:#fee2e2; color:#991b1b; }
.tag-purple { background:#ede9fe; color:#5b21b6; }

.score-bar-bg   { background:#f3f4f6; border-radius:999px; height:6px; width:100%; margin-top:8px; }
.score-bar-fill { height:6px; border-radius:999px; }

.stat-box   { background:white; border-radius:10px; padding:1rem 1.2rem; border:1px solid #e8eaf0; text-align:center; }
.stat-num   { font-size:1.8rem; font-weight:700; color:#111827; }
.stat-label { font-size:0.75rem; color:#6b7280; font-weight:500; margin-top:2px; }

.cache-badge {
    background: #ecfdf5; border: 1px solid #6ee7b7; border-radius: 6px;
    padding: 4px 10px; font-size: 0.75rem; color: #065f46; font-weight: 500;
}

.stButton>button {
    background: linear-gradient(135deg,#0f3460,#1a1a2e); color:white;
    border:none; border-radius:10px; font-size:0.95rem; font-weight:600;
    font-family:'Inter',sans-serif; width:100%; height:3rem;
}
.stDownloadButton>button {
    background: linear-gradient(135deg,#10b981,#059669) !important;
    color:white !important; border:none !important; border-radius:10px !important;
    font-weight:600 !important; font-family:'Inter',sans-serif !important;
    width:100% !important; height:3rem !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="app-header">
    <h1>📄 ResumeMatch AI</h1>
    <p>Powered by Claude — holistic resume screening that thinks like a recruiter</p>
</div>
""", unsafe_allow_html=True)


# ── Text extractors ───────────────────────────────────────────────────────────
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


# ── Claude analysis with prompt caching ──────────────────────────────────────
SYSTEM_PREFIX = """You are an expert HR recruiter and talent acquisition specialist with 15+ years of experience.

Evaluate candidates HOLISTICALLY — think beyond keyword matching:
- **Transferable skills**: A data analyst who built ML pipelines = relevant ML experience
- **Project depth**: Side projects, open source, and personal work count
- **Career trajectory**: Growth rate matters — someone leveling up fast is often better than someone stagnant
- **Education context**: Top-tier CS degree or self-taught with strong portfolio — both can be excellent
- **Industry relevance**: Adjacent industry experience often transfers well
- **Soft signals**: Leadership, mentoring, cross-functional work, communication ability

Do NOT penalize for:
- Job title mismatches if the actual work matches
- Missing buzzwords if the underlying skills are evident
- Non-linear career paths
- Different tech stack if fundamentals are strong"""

INTENSITY_CONFIG = {
    # (model, max_tokens, resume_chars, skills_count, gaps_count, extra_instructions)
    "quick":    ("claude-haiku-4-5",   256,  1500, 4, 2,
                 "Be brief. Focus only on must-have requirements."),
    "standard": ("claude-haiku-4-5",   512,  2500, 6, 3,
                 "Balance speed and depth. Note transferable skills and career growth."),
    "deep":     ("claude-haiku-4-5",  1024,  3500, 8, 4,
                 "Thorough analysis. Examine projects, trajectory, soft signals, and cultural fit. "
                 "Be specific about what makes them stand out or fall short."),
    "max":      ("claude-sonnet-4-6", 1500,  4000, 10, 5,
                 "Exhaustive recruiter-level review. Analyze every signal: education depth, "
                 "project complexity, career velocity, leadership indicators, domain expertise, "
                 "and growth potential. Provide rich, specific observations a senior recruiter would."),
}

def intensity_to_tier(level: int) -> str:
    if level <= 3:   return "quick"
    if level <= 6:   return "standard"
    if level <= 9:   return "deep"
    return "max"

def analyze_resume(client, job_desc, resume, intensity: int = 5):
    """Analyze one resume. JD is cached in system prompt after first call."""
    tier = intensity_to_tier(intensity)
    model, max_tokens, resume_chars, skills_n, gaps_n, extra = INTENSITY_CONFIG[tier]

    system_content = f"""{SYSTEM_PREFIX}

{extra}

---
JOB DESCRIPTION TO MATCH AGAINST:
{job_desc}"""

    user_prompt = f"""Analyze this resume. Return ONLY valid JSON, no markdown fences.

RESUME — File: {resume['file']}
{resume['text'][:resume_chars]}

Return exactly:
{{
  "score": <integer 0-100>,
  "verdict": "<Strong Match|Good Match|Partial Match|Not a Match>",
  "matched_skills": ["<up to {skills_n} matching skills/experiences>"],
  "missing": ["<up to {gaps_n} important gaps>"],
  "highlights": "<specific strengths relevant to this role>",
  "reason": "<overall fit — mention trajectory, projects, or unique signals if relevant>"
}}"""

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[{
            "type": "text",
            "text": system_content,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    result = json.loads(raw)
    result["_cache_read"]  = response.usage.cache_read_input_tokens
    result["_cache_write"] = response.usage.cache_creation_input_tokens
    result["_model"]       = model
    return result


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    api_key = st.text_input(
        "Anthropic API Key", type="password",
        placeholder="sk-ant-...",
        help="Get a free key at console.anthropic.com"
    )
    st.caption("Key is used only for this session — never stored.")
    st.markdown("---")

    st.markdown("### 🔬 Analysis Intensity")
    intensity = st.slider("", 1, 10, 5, label_visibility="collapsed")

    tier = intensity_to_tier(intensity)
    tier_labels = {
        "quick":    ("⚡ Quick Scan",    "#6b7280", "Haiku · Fast · Surface-level"),
        "standard": ("✅ Standard",      "#3b82f6", "Haiku · Balanced · Transferable skills"),
        "deep":     ("🔍 Deep Analysis", "#8b5cf6", "Haiku · Thorough · Projects & trajectory"),
        "max":      ("🚀 Maximum",       "#ef4444", "Sonnet · Exhaustive · Every signal"),
    }
    label, color, desc = tier_labels[tier]
    bar_pct = int((intensity / 10) * 100)

    st.markdown(f"""
    <div style="margin-top:4px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
            <span style="font-weight:600;color:{color};font-size:0.9rem">{label}</span>
            <span style="font-size:0.8rem;color:#6b7280">{intensity}/10</span>
        </div>
        <div style="background:#f3f4f6;border-radius:999px;height:8px;width:100%">
            <div style="width:{bar_pct}%;height:8px;border-radius:999px;
                background:linear-gradient(90deg,#3b82f6,{color})"></div>
        </div>
        <div style="font-size:0.72rem;color:#6b7280;margin-top:5px">{desc}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Prompt caching:** ✅ JD cached")
    st.caption("JD cached after 1st call — subsequent resumes cheaper & faster.")


# ── Main layout ───────────────────────────────────────────────────────────────
left, right = st.columns([3, 2], gap="large")

with left:
    st.markdown('<p style="font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#6b7280">📋 Job Description</p>', unsafe_allow_html=True)
    job_desc = st.text_area("", height=240,
                            placeholder="Paste the full job description here...",
                            label_visibility="collapsed")

with right:
    st.markdown('<p style="font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#6b7280">📁 Upload Resumes ZIP</p>', unsafe_allow_html=True)
    zip_file = st.file_uploader("", type=["zip"], label_visibility="collapsed")

st.markdown("")
run = st.button("🔍 Analyze Candidates with Claude", type="primary")

if run:
    if not api_key:
        st.warning("Please enter your Anthropic API key in the sidebar. Get one free at console.anthropic.com")
    elif not job_desc.strip():
        st.warning("Please enter a job description.")
    elif zip_file is None:
        st.warning("Please upload a ZIP file of resumes.")
    else:
        with st.spinner("Reading resumes..."):
            resumes = parse_resumes_from_zip(zip_file.read())

        if not resumes:
            st.error("No readable resumes found (PDF / DOCX / TXT).")
        else:
            client = anthropic.Anthropic(api_key=api_key)
            results = []
            cache_hits = 0
            errors = []

            progress = st.progress(0, text="Analyzing resumes with Claude...")

            for i, resume in enumerate(resumes):
                try:
                    llm = analyze_resume(client, job_desc, resume, intensity)
                    if llm.get("_cache_read", 0) > 0:
                        cache_hits += 1
                    results.append({
                        "name": resume["name"],
                        "file": resume["file"],
                        "raw": resume["raw"],
                        "score": int(llm.get("score", 0)),
                        "verdict": llm.get("verdict", ""),
                        "matched_skills": llm.get("matched_skills", []),
                        "missing": llm.get("missing", []),
                        "highlights": llm.get("highlights", ""),
                        "reason": llm.get("reason", ""),
                    })
                except Exception as e:
                    errors.append(f"{resume['file']}: {e}")

                progress.progress((i + 1) / len(resumes),
                                  text=f"Analyzed {i+1}/{len(resumes)} resumes...")

            progress.empty()

            if errors:
                for err in errors:
                    st.warning(f"⚠️ {err}")

            if not results:
                st.error("No results could be generated.")
            else:
                st.markdown("---")

                # Stats
                s1, s2, s3, s4 = st.columns(4)
                strong = [r for r in results if r["score"] >= 70]
                good   = [r for r in results if 45 <= r["score"] < 70]
                top    = max(results, key=lambda x: x["score"])

                with s1:
                    st.markdown(f'<div class="stat-box"><div class="stat-num">{len(resumes)}</div><div class="stat-label">Scanned</div></div>', unsafe_allow_html=True)
                with s2:
                    st.markdown(f'<div class="stat-box"><div class="stat-num" style="color:#10b981">{len(strong)}</div><div class="stat-label">Strong Matches</div></div>', unsafe_allow_html=True)
                with s3:
                    st.markdown(f'<div class="stat-box"><div class="stat-num" style="color:#f59e0b">{len(good)}</div><div class="stat-label">Good Matches</div></div>', unsafe_allow_html=True)
                with s4:
                    st.markdown(f'<div class="stat-box"><div class="stat-num" style="color:#0f3460">{top["score"]}%</div><div class="stat-label">Top Score</div></div>', unsafe_allow_html=True)

                if cache_hits > 0:
                    st.markdown(f'<div style="margin-top:0.75rem"><span class="cache-badge">⚡ Prompt cache hit on {cache_hits}/{len(resumes)} calls — JD tokens reused</span></div>', unsafe_allow_html=True)

                st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)

                all_sorted = sorted(results, key=lambda x: -x["score"])
                min_score = st.slider("Minimum match score to show", 0, 100, 40, 5, format="%d%%")
                matched = [r for r in all_sorted if r["score"] >= min_score]

                if matched:
                    res_col, dl_col = st.columns([3, 1], gap="large")

                    with res_col:
                        st.markdown(f"### Candidates ({len(matched)} shown)")
                        for i, r in enumerate(matched, 1):
                            s = r["score"]
                            card_cls = "match-card" if s >= 70 else ("match-card good" if s >= 45 else "match-card partial")
                            bar_color = "#10b981" if s >= 70 else ("#f59e0b" if s >= 45 else "#ef4444")

                            skill_tags = "".join(
                                f'<span class="tag tag-green">{sk}</span>'
                                for sk in r["matched_skills"]
                            )
                            missing_tags = "".join(
                                f'<span class="tag tag-red">✗ {m}</span>'
                                for m in r["missing"]
                            )
                            verdict_tag = f'<span class="tag tag-purple">{r["verdict"]}</span>'

                            card_html = f"""
                            <div class="{card_cls}">
                                <div style="display:flex;justify-content:space-between;align-items:center">
                                    <span class="candidate-name">{i}. {r['name']}</span>
                                    <span style="font-size:0.9rem;font-weight:700;color:{bar_color}">{s}%</span>
                                </div>
                                <div><span class="candidate-file">{r['file']}</span> {verdict_tag}</div>
                                <div class="score-bar-bg">
                                    <div class="score-bar-fill" style="width:{s}%;background:{bar_color}"></div>
                                </div>
                                <div class="highlight-text">💡 {r['highlights']}</div>
                                <div class="reason-text">💬 {r['reason']}</div>
                                <div style="margin-top:8px">{skill_tags}</div>
                                <div style="margin-top:4px">{missing_tags}</div>
                            </div>
                            """
                            st.markdown(card_html, unsafe_allow_html=True)

                    with dl_col:
                        st.markdown("### Download")
                        zip_bytes = build_matched_zip(matched)
                        st.download_button(
                            label=f"⬇️ Download {len(matched)} Resumes",
                            data=zip_bytes,
                            file_name="matched_resumes.zip",
                            mime="application/zip",
                        )
                else:
                    st.warning("No candidates at this score threshold. Lower the slider.")

st.markdown("---")
st.markdown('<p style="text-align:center;color:#9ca3af;font-size:0.78rem">ResumeMatch AI · Claude Haiku 4.5 · Prompt Caching · Streamlit Cloud</p>', unsafe_allow_html=True)
