const startBtn = document.getElementById("startBtn");
const runStatus = document.getElementById("runStatus");
const stagesContainer = document.getElementById("stages");
const logOutput = document.getElementById("logOutput");
const destroyBtn = document.getElementById("destroyBtn");
const usageCard = document.getElementById("usageCard");
const metricsGrid = document.getElementById("metricsGrid");
const metricsStatus = document.getElementById("metricsStatus");
const themeToggle = document.getElementById("themeToggle");

let vmInventory = [];
let metricsTimer = null;
let currentTheme = null;

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

function toggleUsagePanel(visible) {
  usageCard.hidden = !visible;
  if (!visible) {
    metricsStatus.textContent = "Waiting for VMs…";
    metricsGrid.innerHTML = '<p class="muted">No VM metrics available yet.</p>';
    metricsGrid.classList.add("empty");
  }
}

function formatBytes(bytes) {
  if (!bytes || bytes < 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let idx = 0;
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024;
    idx += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[idx]}`;
}

function renderMetricRow(label, valueText, percent, fillClass = "") {
  const wrapper = document.createElement("div");
  wrapper.className = "metric-usage-row";

  const labelRow = document.createElement("div");
  labelRow.className = "metric-label";
  labelRow.innerHTML = `<span>${label}</span><span>${valueText}</span>`;

  const bar = document.createElement("div");
  bar.className = "metric-bar";
  const fill = document.createElement("div");
  fill.className = `metric-bar-fill${fillClass ? " " + fillClass : ""}`;
  fill.style.width = `${Math.min(Math.max(percent || 0, 0), 100)}%`;
  bar.appendChild(fill);

  wrapper.appendChild(labelRow);
  wrapper.appendChild(bar);
  return wrapper;
}

function renderMetrics(payload) {
  const vms = payload?.vms || [];
  if (!vms.length) {
    metricsGrid.classList.add("empty");
    metricsGrid.innerHTML = '<p class="muted">No VM metrics available yet.</p>';
    return;
  }

  metricsGrid.classList.remove("empty");
  metricsGrid.innerHTML = "";

  vms.forEach((vm) => {
    const card = document.createElement("div");
    card.className = "metric-card";

    const header = document.createElement("div");
    header.className = "metric-header";

    const name = document.createElement("p");
    name.className = "metric-name";
    name.textContent = vm.name || `VM ${vm.id}`;

    const pill = document.createElement("span");
    pill.className = `pill${vm.online ? "" : " offline"}`;
    pill.textContent = vm.online ? "Online" : "Offline";

    header.appendChild(name);
    header.appendChild(pill);
    card.appendChild(header);

    const meta = document.createElement("p");
    meta.className = "metric-meta";
    const parts = [`ID ${vm.id}`];
    if (vm.node) parts.push(`Node ${vm.node}`);
    meta.textContent = parts.join(" • ");
    card.appendChild(meta);

    const usage = document.createElement("div");
    usage.className = "metric-usage";

    const cpuLabel =
      vm.cpu_pct !== null && vm.cpu_pct !== undefined
        ? `${vm.cpu_pct}%`
        : "n/a";
    usage.appendChild(renderMetricRow("CPU", cpuLabel, vm.cpu_pct || 0));

    const mem = vm.mem || {};
    const memPct = mem.used_pct || 0;
    const memLabel =
      mem.used_bytes !== undefined && mem.total_bytes
        ? `${formatBytes(mem.used_bytes)} / ${formatBytes(
            mem.total_bytes
          )} (${memPct}%)`
        : "n/a";
    usage.appendChild(
      renderMetricRow("Memory", memLabel, memPct, "memory")
    );

    card.appendChild(usage);
    metricsGrid.appendChild(card);
  });
}

async function refreshInventory() {
  try {
    const response = await fetch("/api/vms");
    if (!response.ok) throw new Error("Inventory request failed");
    const payload = await response.json();
    vmInventory = payload.vms || [];
    toggleUsagePanel(vmInventory.length > 0);

    if (vmInventory.length && !metricsTimer) {
      await refreshMetrics();
      metricsTimer = setInterval(refreshMetrics, 5000);
    } else if (!vmInventory.length && metricsTimer) {
      clearInterval(metricsTimer);
      metricsTimer = null;
    }
  } catch (_err) {
    // Leave the previous state untouched on errors
  }
}

async function refreshMetrics() {
  if (!vmInventory.length) {
    toggleUsagePanel(false);
    return;
  }
  metricsStatus.textContent = "Updating…";
  try {
    const response = await fetch("/api/vm-metrics");
    const payload = await response.json();
    if (!response.ok || !payload.available) {
      metricsStatus.textContent = payload.message || "Metrics unavailable";
      metricsGrid.classList.add("empty");
      metricsGrid.innerHTML = '<p class="muted">No VM metrics available yet.</p>';
      return;
    }
    metricsStatus.textContent = "Live from Proxmox";
    renderMetrics(payload);
  } catch (_err) {
    metricsStatus.textContent = "Unable to load metrics";
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
refreshInventory();
setInterval(refreshInventory, 5000);

function applyTheme(theme) {
  currentTheme = theme;
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("psd-theme", theme);
  if (themeToggle) {
    themeToggle.textContent = theme === "dark" ? "Light mode" : "Dark mode";
  }
}

function initTheme() {
  const stored = localStorage.getItem("psd-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = stored || (prefersDark ? "dark" : "light");
  applyTheme(theme);
}

initTheme();

if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const next = currentTheme === "dark" ? "light" : "dark";
    applyTheme(next);
  });
}
