// ── SVG gradient defs ─────────────────────────────────────────────────────
document.body.insertAdjacentHTML("afterbegin", `
<svg class="svg-defs">
  <defs>
    <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#7c6bff"/>
      <stop offset="100%" stop-color="#a855f7"/>
    </linearGradient>
    <linearGradient id="summaryGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#00e5b0"/>
      <stop offset="100%" stop-color="#7c6bff"/>
    </linearGradient>
  </defs>
</svg>`);

// ── Canvas particle background ────────────────────────────────────────────
const canvas = document.getElementById("bgCanvas");
const ctx = canvas.getContext("2d");
let particles = [];

function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}
resizeCanvas();
window.addEventListener("resize", resizeCanvas);

class Particle {
  constructor() { this.reset(); }
  reset() {
    this.x = Math.random() * canvas.width;
    this.y = Math.random() * canvas.height;
    this.r = Math.random() * 1.5 + 0.3;
    this.vx = (Math.random() - 0.5) * 0.25;
    this.vy = (Math.random() - 0.5) * 0.25;
    this.alpha = Math.random() * 0.4 + 0.1;
    const c = Math.random();
    this.color = c < 0.4 ? "124,107,255" : c < 0.7 ? "0,229,176" : "255,107,157";
  }
  update() {
    this.x += this.vx; this.y += this.vy;
    if (this.x < 0 || this.x > canvas.width || this.y < 0 || this.y > canvas.height) this.reset();
  }
  draw() {
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${this.color},${this.alpha})`;
    ctx.fill();
  }
}

for (let i = 0; i < 120; i++) particles.push(new Particle());

// Draw connecting lines between nearby particles
function drawLines() {
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x;
      const dy = particles[i].y - particles[j].y;
      const dist = Math.sqrt(dx*dx + dy*dy);
      if (dist < 100) {
        ctx.beginPath();
        ctx.moveTo(particles[i].x, particles[i].y);
        ctx.lineTo(particles[j].x, particles[j].y);
        ctx.strokeStyle = `rgba(124,107,255,${0.06 * (1 - dist/100)})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    }
  }
}

function animateCanvas() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawLines();
  particles.forEach(p => { p.update(); p.draw(); });
  requestAnimationFrame(animateCanvas);
}
animateCanvas();

// ── Step management ───────────────────────────────────────────────────────
let currentStep = 1;
const TOTAL_STEPS = 4;

function updateStepUI(step) {
  currentStep = step;
  // Fill bar
  const pct = ((step - 1) / (TOTAL_STEPS - 1)) * 100;
  document.getElementById("stepFill").style.width = pct + "%";

  // Node states
  document.querySelectorAll(".step-node").forEach(n => {
    const s = parseInt(n.dataset.step);
    n.classList.remove("active", "done");
    if (s === step) n.classList.add("active");
    else if (s < step) n.classList.add("done");
  });

  // Card visibility
  ["card1","card2","card3"].forEach((id, i) => {
    const card = document.getElementById(id);
    const cardStep = i + 1;
    if (cardStep === step) {
      card.classList.remove("card-hidden");
      card.classList.add("card-visible");
    } else {
      card.classList.remove("card-visible");
      card.classList.add("card-hidden");
    }
  });
}

function nextStep(n) {
  if (n === 2 && !document.getElementById("jobDesc").value.trim()) {
    shakeElement("card1"); return;
  }
  if (n === 3 && !document.getElementById("zipFile").files[0]) {
    shakeElement("card2"); return;
  }
  updateStepUI(n);
  document.getElementById("appSection").scrollIntoView({ behavior: "smooth", block: "start" });
}

function shakeElement(id) {
  const el = document.getElementById(id);
  el.style.animation = "shake 0.4s ease";
  setTimeout(() => el.style.animation = "", 400);
}

// Shake keyframe (injected once)
const shakeStyle = document.createElement("style");
shakeStyle.textContent = `@keyframes shake {
  0%,100%{transform:translateX(0)} 20%,60%{transform:translateX(-6px)} 40%,80%{transform:translateX(6px)}
}`;
document.head.appendChild(shakeStyle);

updateStepUI(1);

// ── Scroll to app ──────────────────────────────────────────────────────────
function scrollToApp() {
  document.getElementById("appSection").scrollIntoView({ behavior: "smooth" });
}

// ── Job description live analysis ─────────────────────────────────────────
const jobDesc   = document.getElementById("jobDesc");
const charCount = document.getElementById("charCount");
const wordChips = document.getElementById("wordChips");

const KEYWORDS = ["python","java","javascript","react","node","sql","aws","docker","kubernetes",
  "ml","ai","nlp","fastapi","django","flask","typescript","go","rust","excel","powerbi",
  "tableau","finance","hr","marketing","sales","data","analyst","engineer","manager","design"];

jobDesc.addEventListener("input", () => {
  const words = jobDesc.value.trim().split(/\s+/).filter(Boolean);
  charCount.textContent = `${words.length} words`;

  const found = KEYWORDS.filter(k => jobDesc.value.toLowerCase().includes(k)).slice(0, 6);
  wordChips.innerHTML = found.map(k => `<span class="word-chip">${k}</span>`).join("");
});

// ── Drop zone ──────────────────────────────────────────────────────────────
const dropZone   = document.getElementById("dropZone");
const zipInput   = document.getElementById("zipFile");
const filePreview= document.getElementById("filePreview");

dropZone.addEventListener("dragover",  e => { e.preventDefault(); dropZone.classList.add("over"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("over"));
dropZone.addEventListener("drop", e => {
  e.preventDefault(); dropZone.classList.remove("over");
  const f = e.dataTransfer.files[0];
  if (f && f.name.endsWith(".zip")) applyFile(f);
});

zipInput.addEventListener("change", () => {
  if (zipInput.files[0]) applyFile(zipInput.files[0]);
});

function applyFile(file) {
  const dt = new DataTransfer();
  dt.items.add(file);
  zipInput.files = dt.files;

  dropZone.classList.add("has-file");
  filePreview.hidden = false;
  document.getElementById("previewName").textContent = file.name;
  document.getElementById("previewSize").textContent = `${(file.size / 1024).toFixed(1)} KB`;
}

function removeFile() {
  zipInput.value = "";
  dropZone.classList.remove("has-file");
  filePreview.hidden = true;
}

// ── Threshold slider ───────────────────────────────────────────────────────
const threshold    = document.getElementById("threshold");
const thresholdVal = document.getElementById("thresholdVal");
const ringFg       = document.getElementById("ringFg");
const thresholdDesc= document.getElementById("thresholdDesc");
const CIRC = 213.6;

const descMap = [
  { max: 0.30, label: "Very Loose", desc: "Shows almost everyone — use for small resume pools" },
  { max: 0.40, label: "Loose",      desc: "Broad matching — includes loosely relevant candidates" },
  { max: 0.50, label: "Balanced",   desc: "Good mix of relevant and near-matches" },
  { max: 0.65, label: "Strict",     desc: "Only candidates with strong relevance to the job" },
  { max: 1.00, label: "Very Strict",desc: "Only near-perfect matches will appear" },
];

function updateRing(val) {
  const pct = (val - 0.20) / 0.60;
  ringFg.style.strokeDashoffset = CIRC * (1 - pct);
  thresholdVal.textContent = Math.round(val * 100) + "%";
  const d = descMap.find(d => val <= d.max) || descMap[descMap.length - 1];
  thresholdDesc.innerHTML = `<strong>${d.label}</strong> — ${d.desc}`;
}

threshold.addEventListener("input", () => updateRing(parseFloat(threshold.value)));
updateRing(0.35);

// ── Form submit ────────────────────────────────────────────────────────────
const matchForm  = document.getElementById("matchForm");
const submitBtn  = document.getElementById("submitBtn");
const btnText    = submitBtn.querySelector(".btn-text");
const btnLoader  = submitBtn.querySelector(".btn-loader");
const loaderText = document.getElementById("loaderText");
const errorBox   = document.getElementById("errorBox");

const loaderSteps = ["Extracting resumes…","Generating embeddings…","Calculating similarity…","Ranking candidates…"];
let loaderInterval;

matchForm.addEventListener("submit", async e => {
  e.preventDefault();
  errorBox.hidden = true;

  submitBtn.disabled = true;
  btnText.hidden = true;
  btnLoader.hidden = false;
  let li = 0;
  loaderText.textContent = loaderSteps[0];
  loaderInterval = setInterval(() => {
    li = (li + 1) % loaderSteps.length;
    loaderText.textContent = loaderSteps[li];
  }, 1800);

  updateStepUI(4);

  const fd = new FormData();
  fd.append("job_description", jobDesc.value);
  fd.append("resumes_zip", zipInput.files[0]);
  fd.append("threshold", threshold.value);

  try {
    const res  = await fetch("/match", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) { showError(data.error || "Something went wrong."); resetSubmit(); return; }
    renderResults(data);
  } catch (err) {
    showError("Network error — is the server running?");
    resetSubmit();
  }
});

function resetSubmit() {
  clearInterval(loaderInterval);
  submitBtn.disabled = false;
  btnText.hidden = false;
  btnLoader.hidden = true;
}

// ── Render results ─────────────────────────────────────────────────────────
const resultsSection = document.getElementById("resultsSection");
const candidateList  = document.getElementById("candidateList");
const allList        = document.getElementById("allList");
const summaryRing    = document.getElementById("summaryRing");
const SRING_CIRC     = 314;

function renderResults(data) {
  clearInterval(loaderInterval);
  resetSubmit();
  matchForm.hidden = true;
  resultsSection.hidden = false;

  // Summary ring
  const pct = data.total > 0 ? data.matched / data.total : 0;
  setTimeout(() => {
    summaryRing.style.strokeDashoffset = SRING_CIRC * (1 - pct);
  }, 100);

  document.getElementById("summaryMatched").textContent = data.matched;
  document.getElementById("summaryTotal").textContent   = `/ ${data.total}`;

  const matchRate = Math.round(pct * 100);
  document.getElementById("summaryHeading").textContent =
    data.matched > 0 ? `${data.matched} Candidate${data.matched > 1 ? "s" : ""} Selected` : "No Matches Found";
  document.getElementById("summaryDesc").textContent =
    `Analyzed ${data.total} resume${data.total !== 1 ? "s" : ""} · ${matchRate}% match rate · threshold ${Math.round(data.threshold * 100)}%`;

  const chips = document.getElementById("summaryChips");
  chips.innerHTML = `
    <span class="s-chip s-chip-green">✓ ${data.matched} matched</span>
    <span class="s-chip s-chip-gray">✗ ${data.total - data.matched} unmatched</span>
    <span class="s-chip s-chip-purple">⚡ threshold ${Math.round(data.threshold * 100)}%</span>`;

  // Candidate cards
  candidateList.innerHTML = "";
  if (data.candidates.length === 0) {
    document.getElementById("noMatchMsg").hidden = false;
  } else {
    document.getElementById("noMatchMsg").hidden = true;
    data.candidates.forEach((c, i) => {
      const pct  = Math.round(c.score * 100);
      const cls  = c.score >= 0.55 ? "score-high" : c.score >= 0.40 ? "score-mid" : "score-low";
      const tag  = c.score >= 0.55 ? "Strong" : c.score >= 0.40 ? "Good" : "Fair";
      const rnk  = i === 0 ? "rank1" : i === 1 ? "rank2" : i === 2 ? "rank3" : "";

      candidateList.insertAdjacentHTML("beforeend", `
        <div class="cand-card" style="animation-delay:${i * 0.07}s">
          <div class="cand-rank ${rnk}">#${i + 1}</div>
          <div class="cand-info">
            <div class="cand-name">${esc(c.name)}</div>
            <div class="cand-file">${esc(c.file)}</div>
          </div>
          <div class="cand-bar-wrap">
            <div class="cand-bar-label">${pct}%</div>
            <div class="cand-bar-track">
              <div class="cand-bar-fill" style="width:0%" data-w="${pct}%"></div>
            </div>
          </div>
          <div class="cand-score ${cls}">
            <span class="score-pct">${pct}%</span>
            <span class="score-tag">${tag}</span>
          </div>
        </div>`);
    });

    // Animate bars after render
    setTimeout(() => {
      document.querySelectorAll(".cand-bar-fill").forEach(el => {
        el.style.width = el.dataset.w;
      });
    }, 100);
  }

  // All table
  allList.innerHTML = "";
  data.all.forEach(c => {
    const matched = c.score >= data.threshold;
    const pct = Math.round(c.score * 100);
    allList.insertAdjacentHTML("beforeend", `
      <div class="all-row">
        <span class="all-row-name">${esc(c.name)}</span>
        <span class="all-row-file">${esc(c.file)}</span>
        <span class="all-row-score" style="color:${matched ? "var(--success)" : "var(--text2)"}">${pct}%</span>
        <span><span class="matched-badge ${matched ? "mb-yes" : "mb-no"}">${matched ? "Matched" : "Skip"}</span></span>
      </div>`);
  });

  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── New search ─────────────────────────────────────────────────────────────
function newSearch() {
  matchForm.reset();
  matchForm.hidden = false;
  resultsSection.hidden = false;
  resultsSection.hidden = true;
  removeFile();
  wordChips.innerHTML = "";
  charCount.textContent = "0 words";
  updateRing(0.35);
  threshold.value = 0.35;
  updateStepUI(1);
  errorBox.hidden = true;
  document.getElementById("heroSection").scrollIntoView({ behavior: "smooth" });
}

// ── Helpers ────────────────────────────────────────────────────────────────
function showError(msg) {
  errorBox.textContent = "⚠️ " + msg;
  errorBox.hidden = false;
  updateStepUI(3);
  matchForm.hidden = false;
  resultsSection.hidden = true;
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
