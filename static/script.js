const form        = document.getElementById("matchForm");
const jobDesc     = document.getElementById("jobDesc");
const charCount   = document.getElementById("charCount");
const dropZone    = document.getElementById("dropZone");
const zipInput    = document.getElementById("zipFile");
const fileName    = document.getElementById("fileName");
const threshold   = document.getElementById("threshold");
const thresholdVal= document.getElementById("thresholdVal");
const submitBtn   = document.getElementById("submitBtn");
const btnText     = submitBtn.querySelector(".btn-text");
const btnLoader   = submitBtn.querySelector(".btn-loader");
const results     = document.getElementById("results");
const errorBox    = document.getElementById("errorBox");
const matchedStat = document.getElementById("matchedStat");
const candidateList=document.getElementById("candidateList");
const allList     = document.getElementById("allList");
const resetBtn    = document.getElementById("resetBtn");

// ── character counter ────────────────────────────────────────────────────────
jobDesc.addEventListener("input", () => {
  charCount.textContent = `${jobDesc.value.length.toLocaleString()} characters`;
});

// ── threshold slider ─────────────────────────────────────────────────────────
threshold.addEventListener("input", () => {
  thresholdVal.textContent = parseFloat(threshold.value).toFixed(2);
});

// ── drop zone ────────────────────────────────────────────────────────────────
dropZone.addEventListener("click", () => zipInput.click());

dropZone.addEventListener("dragover", e => {
  e.preventDefault();
  dropZone.classList.add("over");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("over"));

dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("over");
  const file = e.dataTransfer.files[0];
  if (file && file.name.endsWith(".zip")) setFile(file);
});

zipInput.addEventListener("change", () => {
  if (zipInput.files[0]) setFile(zipInput.files[0]);
});

function setFile(file) {
  const dt = new DataTransfer();
  dt.items.add(file);
  zipInput.files = dt.files;
  fileName.textContent = `✓ ${file.name}  (${(file.size / 1024).toFixed(1)} KB)`;
  dropZone.classList.add("has-file");
}

// ── form submit ──────────────────────────────────────────────────────────────
form.addEventListener("submit", async e => {
  e.preventDefault();
  hideError();
  setLoading(true);

  const fd = new FormData();
  fd.append("job_description", jobDesc.value);
  fd.append("resumes_zip", zipInput.files[0]);
  fd.append("threshold", threshold.value);

  try {
    const res = await fetch("/match", { method: "POST", body: fd });
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || "Something went wrong.");
      return;
    }

    renderResults(data);
  } catch (err) {
    showError("Network error — is the server running?");
  } finally {
    setLoading(false);
  }
});

// ── reset ─────────────────────────────────────────────────────────────────────
resetBtn.addEventListener("click", () => {
  results.hidden = true;
  form.hidden = false;
  errorBox.hidden = true;
  form.reset();
  fileName.textContent = "";
  dropZone.classList.remove("has-file");
  charCount.textContent = "0 characters";
  thresholdVal.textContent = "0.35";
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// ── helpers ──────────────────────────────────────────────────────────────────
function setLoading(on) {
  submitBtn.disabled = on;
  btnText.hidden = on;
  btnLoader.hidden = !on;
}

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.hidden = false;
}

function hideError() {
  errorBox.hidden = true;
}

function scoreClass(s) {
  if (s >= 0.55) return "score-high";
  if (s >= 0.40) return "score-mid";
  return "score-low";
}

function scoreColor(s) {
  if (s >= 0.55) return "var(--success)";
  if (s >= 0.40) return "var(--accent)";
  return "var(--warn)";
}

function renderResults(data) {
  form.hidden = true;
  candidateList.innerHTML = "";
  allList.innerHTML = "";

  matchedStat.textContent =
    data.matched > 0
      ? `✅ ${data.matched} matched out of ${data.total} resumes`
      : `⚠️ No matches found in ${data.total} resumes — try lowering sensitivity`;

  // Matched candidates
  if (data.candidates.length === 0) {
    candidateList.innerHTML = `<p style="color:var(--muted);text-align:center;padding:20px 0">No candidates met the threshold. Try lowering the slider.</p>`;
  } else {
    data.candidates.forEach((c, i) => {
      const pct = Math.round(c.score * 100);
      candidateList.insertAdjacentHTML("beforeend", `
        <div class="candidate-card" style="animation-delay:${i * 0.06}s">
          <div class="rank">#${i + 1}</div>
          <div class="candidate-info">
            <div class="candidate-name">${esc(c.name)}</div>
            <div class="candidate-file">${esc(c.file)}</div>
          </div>
          <div class="score-bar-wrap">
            <div class="score-bar-fill" style="width:${pct}%;background:${scoreColor(c.score)}"></div>
          </div>
          <div class="score-pill ${scoreClass(c.score)}">${pct}% match</div>
        </div>
      `);
    });
  }

  // All resumes table
  data.all.forEach(c => {
    const matched = c.score >= data.threshold;
    const pct = Math.round(c.score * 100);
    allList.insertAdjacentHTML("beforeend", `
      <div class="all-row ${matched ? "matched-row" : "unmatched-row"}">
        <span class="all-row-name">${esc(c.name)}</span>
        <span class="all-row-file">${esc(c.file)}</span>
        <span class="all-row-score">${pct}%</span>
      </div>
    `);
  });

  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
