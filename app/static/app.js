const $ = (id) => document.getElementById(id);
const STEPS = ["Script", "Voice + Images", "Compose", "Publish-ready"];
const STATE_INDEX = {
  queued: 0, scripting: 0, generating_assets: 1, composing: 2, done: 3, error: -1,
};

let pollTimer = null;

function renderSteps(state) {
  const active = STATE_INDEX[state] ?? 0;
  $("steps").innerHTML = STEPS.map((label, i) => {
    let cls = "step";
    if (state === "done" || i < active) cls += " done";
    else if (i === active) cls += " active";
    return `<div class="${cls}">${label}</div>`;
  }).join("");
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

async function start() {
  const topic = $("topic").value.trim();
  const hint = $("hint");
  hint.className = "hint";
  hint.textContent = "";
  if (topic.length < 2) {
    hint.className = "hint err";
    hint.textContent = "Please enter a topic.";
    return;
  }
  $("go").disabled = true;
  $("resultCard").classList.add("hidden");
  $("progressCard").classList.remove("hidden");
  renderSteps("queued");
  $("fill").style.width = "4%";
  $("msg").textContent = "Queued…";

  try {
    const job = await postJSON("/api/generate", {
      topic,
      scene_count: parseInt($("scenes").value, 10) || null,
      voice: $("voice").value,
      style: $("style").value.trim() || "cinematic, vibrant, highly detailed",
    });
    poll(job.id);
  } catch (e) {
    $("go").disabled = false;
    hint.className = "hint err";
    hint.textContent = "Could not start: " + e.message;
  }
}
function poll(jobId) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    let job;
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      job = await res.json();
    } catch (e) {
      return; // transient; try again next tick
    }
    renderSteps(job.state);
    $("fill").style.width = Math.round((job.progress || 0) * 100) + "%";
    $("msg").textContent = job.message || job.state;

    if (job.state === "done") {
      clearInterval(pollTimer);
      showResult(jobId, job);
    } else if (job.state === "error") {
      clearInterval(pollTimer);
      $("go").disabled = false;
      const hint = $("hint");
      hint.className = "hint err";
      hint.textContent = "Failed: " + (job.error || "unknown error");
      $("msg").textContent = "Pipeline failed.";
    }
  }, 1500);
}

function showResult(jobId, job) {
  $("go").disabled = false;
  $("resultCard").classList.remove("hidden");
  const v = $("video");
  v.src = job.video_url + "?t=" + Date.now();
  $("rTitle").textContent = job.title || job.topic;
  $("rCaption").value = job.caption || "";
  $("rTags").innerHTML = (job.hashtags || [])
    .map((h) => `<span class="chip">#${h.replace(/^#/, "")}</span>`).join("");
  const dl = $("download");
  dl.href = job.video_url;
  dl.setAttribute("download", (job.title || "qoneqt-video").replace(/[^a-z0-9]+/gi, "_") + ".mp4");

  const pbtn = $("publishBtn");
  const box = $("publishBox");
  box.classList.add("hidden");
  pbtn.onclick = async () => {
    if (!box.classList.contains("hidden")) { box.classList.add("hidden"); return; }
    try {
      const info = await (await fetch(`/api/jobs/${jobId}/publish`)).json();
      box.innerHTML =
        "<strong>Publish to the Qoneqt Global Feed</strong><ol>" +
        info.steps.map((s) => `<li>${s}</li>`).join("") +
        `</ol><p class="note">${info.note}</p>`;
      box.classList.remove("hidden");
    } catch (e) {
      box.innerHTML = `<p class="note">Could not load publish steps: ${e.message}</p>`;
      box.classList.remove("hidden");
    }
  };
}

$("go").addEventListener("click", start);
$("topic").addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") start();
});
