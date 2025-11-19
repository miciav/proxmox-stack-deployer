const startBtn = document.getElementById("startBtn");
const runStatus = document.getElementById("runStatus");
const stagesContainer = document.getElementById("stages");
const logOutput = document.getElementById("logOutput");
const destroyBtn = document.getElementById("destroyBtn");

const STATUS_LABELS = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  skipped: "Skipped",
};

const TASK_ICONS = {
  pending: "•",
  running: "…",
  completed: "✓",
  failed: "×",
  skipped: "–",
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
    toggleControls(payload.running, payload.mode || "deploy");
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

    const header = document.createElement("div");
    header.className = "stage-header";

    const statusIcon = document.createElement("span");
    statusIcon.className = "status-icon";
    statusIcon.setAttribute("aria-hidden", "true");

    const titleStack = document.createElement("div");

    const metaRow = document.createElement("div");
    metaRow.className = "stage-meta";

    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = STATUS_LABELS[stage.status] || stage.status;
    metaRow.appendChild(badge);

    if (stage.tool) {
      const tools = Array.isArray(stage.tool) ? stage.tool : [stage.tool];
      tools.forEach((toolName) => {
        const toolBadge = document.createElement("span");
        toolBadge.className = "tool-badge";
        toolBadge.dataset.tool = toolName;
        toolBadge.textContent = toolName;
        metaRow.appendChild(toolBadge);
      });
    }

    const title = document.createElement("h3");
    title.textContent = stage.title;

    titleStack.appendChild(metaRow);
    titleStack.appendChild(title);
    header.appendChild(statusIcon);
    header.appendChild(titleStack);

    const desc = document.createElement("p");
    desc.textContent = stage.description;

    const note = document.createElement("p");
    note.className = "stage-note";
    note.textContent = stage.note || "";

    card.appendChild(header);
    card.appendChild(desc);

    if (stage.tasks && stage.tasks.length) {
      const taskWrapper = document.createElement("div");
      taskWrapper.className = "task-list-wrapper";
      const taskList = document.createElement("ul");
      taskList.className = "task-list";
      stage.tasks.forEach((task) => {
        const li = document.createElement("li");
        li.className = `task task-${task.status}`;

        const icon = document.createElement("span");
        icon.className = "task-icon";
        icon.textContent = TASK_ICONS[task.status] || "•";

        const label = document.createElement("span");
        label.className = "task-label";
        label.textContent = task.label;

        li.appendChild(icon);
        li.appendChild(label);
        taskList.appendChild(li);
      });
      taskWrapper.appendChild(taskList);
      card.appendChild(taskWrapper);
    }

    if (note.textContent.trim().length) {
      card.appendChild(note);
    }
    stagesContainer.appendChild(card);
  });
}

function renderLogs(logs) {
  logOutput.textContent = logs.length
    ? logs.slice(-100).join("\n")
    : "No log output yet.";
  logOutput.scrollTop = logOutput.scrollHeight;
}

function toggleControls(isRunning, mode) {
  startBtn.disabled = isRunning;
  destroyBtn.disabled = isRunning;
  if (isRunning) {
    runStatus.textContent =
      mode === "destroy" ? "Destroying infrastructure…" : "Deployment running…";
  } else {
    runStatus.textContent = "Idle";
  }
}

async function startDeployment() {
  startBtn.disabled = true;
  destroyBtn.disabled = true;
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
    destroyBtn.disabled = false;
  }
}

async function destroyInfrastructure() {
  if (!confirm("Are you sure you want to destroy the infrastructure?")) {
    return;
  }
  destroyBtn.disabled = true;
  startBtn.disabled = true;
  runStatus.textContent = "Starting destroy…";
  try {
    const response = await fetch("/api/destroy", { method: "POST" });
    if (response.status === 409) {
      runStatus.textContent = "Another run is already in progress";
      destroyBtn.disabled = true;
      startBtn.disabled = true;
      return;
    }
    if (!response.ok) {
      throw new Error("Unable to start destroy");
    }
    const payload = await response.json();
    if (!payload.started) {
      runStatus.textContent = "Destroy not started";
    } else {
      runStatus.textContent = "Destroying infrastructure…";
    }
  } catch (err) {
    console.error(err);
    runStatus.textContent = "Failed to trigger destroy";
    destroyBtn.disabled = false;
    startBtn.disabled = false;
  }
}

startBtn.addEventListener("click", startDeployment);
destroyBtn.addEventListener("click", destroyInfrastructure);
requestStatus();
setInterval(requestStatus, 2500);
