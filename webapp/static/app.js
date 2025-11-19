const startBtn = document.getElementById("startBtn");
const runStatus = document.getElementById("runStatus");
const stagesContainer = document.getElementById("stages");
const logOutput = document.getElementById("logOutput");

const STATUS_LABELS = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  skipped: "Skipped",
};

async function requestStatus() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) {
      throw new Error("Request failed");
    }
    const payload = await response.json();
    renderStages(payload.stages || []);
    renderLogs(payload.logs || []);
    toggleControls(payload.running);
  } catch (err) {
    runStatus.textContent = "Connection error";
    runStatus.classList.add("error");
  }
}

function renderStages(stages) {
  stagesContainer.innerHTML = "";
  if (!stages.length) {
    stagesContainer.innerHTML = "<p>No stage data available.</p>";
    return;
  }

  stages.forEach((stage) => {
    const card = document.createElement("article");
    card.className = "stage";
    card.dataset.status = stage.status;

    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = STATUS_LABELS[stage.status] || stage.status;

    const title = document.createElement("h3");
    title.textContent = stage.title;

    const desc = document.createElement("p");
    desc.textContent = stage.description;

    const note = document.createElement("p");
    note.className = "stage-note";
    note.textContent = stage.note || "";

    card.appendChild(badge);
    card.appendChild(title);
    card.appendChild(desc);
    if (note.textContent.trim().length) {
      card.appendChild(note);
    }
    stagesContainer.appendChild(card);
  });
}

function renderLogs(logs) {
  logOutput.textContent = logs.length
    ? logs.slice(-200).join("\n")
    : "No log output yet.";
  logOutput.scrollTop = logOutput.scrollHeight;
}

function toggleControls(isRunning) {
  startBtn.disabled = isRunning;
  runStatus.textContent = isRunning ? "Deployment running…" : "Idle";
}

async function startDeployment() {
  startBtn.disabled = true;
  runStatus.textContent = "Starting…";
  try {
    const response = await fetch("/api/run", { method: "POST" });
    if (response.status === 409) {
      runStatus.textContent = "Deployment already running";
      startBtn.disabled = true;
      return;
    }
    if (!response.ok) {
      throw new Error("Unable to start deployment");
    }
    const payload = await response.json();
    if (!payload.started) {
      runStatus.textContent = "Deployment not started";
    } else {
      runStatus.textContent = "Deployment running…";
    }
  } catch (err) {
    console.error(err);
    runStatus.textContent = "Failed to launch deploy.py";
    startBtn.disabled = false;
  }
}

startBtn.addEventListener("click", startDeployment);
requestStatus();
setInterval(requestStatus, 2500);
