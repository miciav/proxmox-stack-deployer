#!/usr/bin/env python3
"""Simple Flask server that exposes a UI to run deploy.py."""

from __future__ import annotations

import os
import re
import sys
import time
import json
import threading
import subprocess
from pathlib import Path
from typing import Dict, List

from flask import Flask, jsonify, send_from_directory

try:
    from proxmoxer import ProxmoxAPI

    HAS_PROXMOXER = True
except ImportError:
    HAS_PROXMOXER = False

BASE_DIR = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = BASE_DIR / "deploy.py"
ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
ANSIBLE_TASK_PATTERN = re.compile(r"TASK\s+\[(.+?)\]")

TFVARS_FILE = BASE_DIR / "terraform-opentofu" / "terraform.tfvars"
TFVARS_EXAMPLE_FILE = BASE_DIR / "terraform-opentofu" / "terraform.tfvars.example"
TFSTATE_FILE = BASE_DIR / "terraform-opentofu" / "terraform.tfstate"


def determine_vm_role_usage() -> Dict[str, bool]:
    """Parse terraform.tfvars to detect whether k3s and docker roles are requested."""
    vm_count = 1
    default_role = "k3s"
    explicit_roles: Dict[str, str] = {}
    tfvars_path = TFVARS_FILE if TFVARS_FILE.exists() else TFVARS_EXAMPLE_FILE

    if not tfvars_path.exists():
        return {"k3s": True, "docker": False}

    try:
        with tfvars_path.open("r", encoding="utf-8") as tf_file:
            in_vm_roles = False
            for raw_line in tf_file:
                line = re.sub(r"(#|//).*", "", raw_line).strip()
                if not line:
                    continue

                if in_vm_roles:
                    if line.startswith("}"):
                        in_vm_roles = False
                        continue
                    match = re.match(r'"([^"]+)"\s*=\s*"([^"]+)"', line)
                    if match:
                        explicit_roles[match.group(1)] = match.group(2)
                    continue

                if line.startswith("vm_roles"):
                    if "{" in line:
                        brace_index = line.find("{")
                        remainder = line[brace_index + 1 :].strip()
                        if remainder and remainder != "}":
                            match = re.match(r'"([^"]+)"\s*=\s*"([^"]+)"', remainder)
                            if match:
                                explicit_roles[match.group(1)] = match.group(2)
                            if remainder.endswith("}"):
                                continue
                        if not remainder.endswith("}"):
                            in_vm_roles = True
                    else:
                        in_vm_roles = True
                    continue

                match_count = re.match(r"vm_count\s*=\s*(\d+)", line)
                if match_count:
                    vm_count = int(match_count.group(1))
                    continue

                match_default = re.match(
                    r'default_vm_role\s*=\s*"([^"]+)"', line
                )
                if match_default:
                    default_role = match_default.group(1)
                    continue

        has_k3s = any(role == "k3s" for role in explicit_roles.values())
        has_docker = any(role == "docker" for role in explicit_roles.values())

        unspecified = max(vm_count - len(explicit_roles), 0)
        if unspecified > 0:
            if default_role == "k3s":
                has_k3s = True
            elif default_role == "docker":
                has_docker = True

        return {"k3s": has_k3s, "docker": has_docker}
    except Exception:
        # Fallback to defaults if parsing fails
        return {"k3s": True, "docker": False}


def parse_proxmox_credentials() -> Dict[str, str]:
    """Extract Proxmox connection details from terraform.tfvars with fallbacks."""
    defaults = {
        "url": "",
        "host": "",
        "user": "",
        "password": "",
        "node": "",
        "host_user": "",
    }
    tfvars_path = TFVARS_FILE if TFVARS_FILE.exists() else TFVARS_EXAMPLE_FILE
    if not tfvars_path.exists():
        return defaults

    try:
        with tfvars_path.open("r", encoding="utf-8") as tf_file:
            content = tf_file.read()

        url_match = re.search(r'proxmox_api_url\s*=\s*"([^"]+)"', content)
        user_match = re.search(r'proxmox_user\s*=\s*"([^"]+)"', content)
        host_user_match = re.search(r'proxmox_host_user\s*=\s*"([^"]+)"', content)
        host_match = re.search(r'proxmox_host\s*=\s*"([^"]+)"', content)
        pass_match = re.search(r'proxmox_password\s*=\s*"([^"]+)"', content)
        node_match = re.search(r'target_node\s*=\s*"([^"]+)"', content)

        user = user_match.group(1) if user_match else ""
        host_user = host_user_match.group(1) if host_user_match else ""
        # Fallback: if proxmox_user is not set, build it from host user and pam realm
        if not user:
            candidate = host_user or "root"
            user = candidate if "@" in candidate else f"{candidate}@pam"
        elif "@" not in user:
            user = f"{user}@pam"

        return {
            "url": url_match.group(1) if url_match else "",
            "host": host_match.group(1) if host_match else "",
            "user": user,
            "host_user": host_user,
            "password": pass_match.group(1) if pass_match else "",
            "node": node_match.group(1) if node_match else "",
        }
    except Exception:
        return defaults


def _parse_tfstate_outputs(outputs: Dict) -> List[Dict]:
    """Parse VM info from Terraform/OpenTofu outputs."""
    summary = outputs.get("vm_summary")
    if isinstance(summary, dict):
        data = summary.get("value") if "value" in summary else summary
        if isinstance(data, dict):
            items = []
            for name, info in data.items():
                vm_id = info.get("id") or info.get("vm_id")
                if vm_id is None:
                    continue
                items.append(
                    {
                        "id": str(vm_id),
                        "name": name,
                        "node": info.get("node"),
                        "ip": info.get("ip"),
                        "role": info.get("role"),
                    }
                )
            if items:
                return items

    vm_ids = outputs.get("vm_ids")
    if isinstance(vm_ids, dict):
        data = vm_ids.get("value") if "value" in vm_ids else vm_ids
        if isinstance(data, dict):
            return [
                {"id": str(vm_id), "name": name, "node": None, "ip": None, "role": None}
                for name, vm_id in data.items()
                if vm_id is not None
            ]
    return []


def get_tfstate_vm_info() -> List[Dict]:
    """Read terraform.tfstate to build a VM inventory list."""
    if not TFSTATE_FILE.exists():
        return []

    try:
        data = json.loads(TFSTATE_FILE.read_text())
    except Exception:
        return []

    outputs = data.get("outputs", {})
    vms = _parse_tfstate_outputs(outputs)
    if vms:
        return vms

    resources = data.get("resources", [])
    for res in resources:
        if res.get("type") not in {
            "proxmox_virtual_environment_vm",
            "proxmox_vm_qemu",
        }:
            continue
        for instance in res.get("instances", []):
            attributes = instance.get("attributes", {})
            vm_id = (
                attributes.get("vm_id")
                or attributes.get("vmid")
                or attributes.get("id")
            )
            name = attributes.get("name")
            if vm_id and name:
                vms.append(
                    {
                        "id": str(vm_id),
                        "name": name,
                        "node": attributes.get("node_name")
                        or attributes.get("node")
                        or attributes.get("hostname"),
                        "ip": attributes.get("ip"),
                        "role": None,
                    }
                )
    return vms


def connect_proxmox(creds: Dict) -> ProxmoxAPI | None:
    """Create a proxmoxer client from credentials."""
    if not HAS_PROXMOXER:
        return None

    url = creds.get("url", "")
    host_override = creds.get("host", "")
    user = creds.get("user", "")
    password = creds.get("password", "")
    if not (url or host_override) or not user or not password:
        return None

    # Extract host/port from full API URL (e.g. https://host:8006/api2/json)
    host_port_source = url or host_override
    host_port = host_port_source.replace("https://", "").replace("http://", "")
    host_port = host_port.split("/")[0]
    if ":" in host_port:
        host, port_str = host_port.split(":", 1)
    else:
        host, port_str = host_port, "8006"

    try:
        return ProxmoxAPI(
            host,
            user=user,
            password=password,
            verify_ssl=False,
            port=int(port_str),
        )
    except Exception:
        return None


STAGE_DEFINITIONS = {
    "deploy": [
        {
            "id": "setup",
            "title": "Initial Setup & Validation",
            "description": "Checks prerequisites, terraform.tfvars, and SSH keys.",
            "tool": "Setup",
            "tasks": [
                "Check prerequisites",
                "Validate terraform.tfvars",
                "Load validated variables",
                "Ensure SSH keys",
            ],
        },
        {
            "id": "terraform",
            "title": "Terraform Deployment",
            "description": "Creates or updates the Proxmox VMs through Terraform/OpenTofu.",
            "tool": "Terraform",
            "progress_event": "terraform_step",
            "tasks": [
                "Initialize & validate",
                "Create execution plan",
                "Apply infrastructure",
            ],
        },
        {
            "id": "nat",
            "title": "NAT Rules",
            "description": "Configures NAT and port forwarding on the Proxmox host.",
            "tool": "Ansible",
            "progress_event": "ansible_task",
            "tasks": [
                "Build inventories",
                "Configure SSH NAT rules",
                "Configure service NAT rules",
                "Validate NAT connectivity",
                "Summarize port mappings",
            ],
        },
        {
            "id": "vm",
            "title": "VM Preparation",
            "description": "Runs the base VM configuration playbook.",
            "tool": "Ansible",
            "progress_event": "ansible_task",
            "tasks": [
                "Update package cache",
                "Install base packages",
                "Configure firewall",
                "Create system directories",
                "Apply timezone",
                "Reboot if required",
            ],
        },
        {
            "id": "k3s",
            "title": "K3s Installation",
            "description": "Installs the lightweight Kubernetes distribution.",
            "tool": "Ansible",
            "progress_event": "ansible_task",
            "requires_role": "k3s",
            "tasks": [
                "Install K3s binaries",
                "Start K3s service",
                "Verify API server",
                "Fetch kubeconfig",
                "Update kubeconfig endpoint",
                "Set kubeconfig permissions",
            ],
        },
        {
            "id": "docker",
            "title": "Docker Installation",
            "description": "Installs Docker Engine on the nodes.",
            "tool": "Ansible",
            "progress_event": "ansible_task",
            "requires_role": "docker",
            "tasks": [
                "Install prerequisites",
                "Deploy Docker packages",
                "Enable Docker services",
            ],
        },
        {
            "id": "openfaas",
            "title": "OpenFaaS Installation",
            "description": "Deploys OpenFaaS workloads on K3s.",
            "tool": ["Ansible", "Helm"],
            "progress_event": "ansible_task",
            "tasks": [
                "Install Helm if needed",
                "Add OpenFaaS repo",
                "Install OpenFaaS chart",
                "Wait for gateway pods",
                "Retrieve admin password",
                "Verify OpenFaaS pods",
            ],
        },
    ],
    "destroy": [
        {
            "id": "destroy_nat",
            "title": "Remove NAT Rules",
            "description": "Reverts NAT and port forwarding rules on Proxmox.",
            "tool": "Ansible",
            "progress_event": "ansible_task",
            "tasks": [
                "Load inventories",
                "Remove SSH NAT rules",
                "Remove service NAT rules",
                "Validate removal",
            ],
        },
        {
            "id": "destroy_tf",
            "title": "Terraform Destroy",
            "description": "Destroys all Terraform-managed infrastructure.",
            "tool": "Terraform",
            "progress_event": "terraform_destroy",
            "tasks": [
                "Select Terraform/OpenTofu",
                "Destroy VM resources",
            ],
        },
    ],
}
DEFAULT_MODE = "deploy"

TERRAFORM_TASK_SEQUENCE = [
    {
        "label": "Initialize & validate",
        "keywords": ["Initializing", "Validating configuration"],
        "complete_keywords": ["✓ Configuration valid"],
    },
    {
        "label": "Create execution plan",
        "keywords": ["Planning deployment", "PLAN SUMMARY", "✓ No changes needed"],
        "complete_keywords": [
            "✓ Plan created",
            "✓ No changes needed",
        ],
    },
    {
        "label": "Apply infrastructure",
        "keywords": ["Creating VM", "[INFO] Creating"],
        "complete_keywords": ["✓ Infrastructure created successfully"],
    },
]
TERRAFORM_KEYWORDS = set()
for task in TERRAFORM_TASK_SEQUENCE:
    TERRAFORM_KEYWORDS.update(task.get("keywords", []))
    TERRAFORM_KEYWORDS.update(task.get("complete_keywords", []))

DESTROY_TASK_SEQUENCE = [
    {
        "label": "Select Terraform/OpenTofu",
        "keywords": [],
        "complete_keywords": ["Using Terraform", "Using OpenTofu"],
    },
    {
        "label": "Destroy VM resources",
        "keywords": [
            "Performing terraform destroy",
            "Performing tofu destroy",
            "Performing terraform destroy -auto-approve",
            "Performing tofu destroy -auto-approve",
            "Destroying...",
            "destroy -auto-approve",
        ],
        "complete_keywords": [
            "Destroy complete!",
            "Destroy complete",
            "Destruction complete",
        ],
    },
]
DESTROY_KEYWORDS = set()
for task in DESTROY_TASK_SEQUENCE:
    DESTROY_KEYWORDS.update(task.get("keywords", []))
    DESTROY_KEYWORDS.update(task.get("complete_keywords", []))
DESTROY_KEYWORDS.update({"Destroying...", "Destruction complete"})

HEADER_STAGE_MAP = {
    "INITIAL SETUP AND VALIDATION": "setup",
    "TERRAFORM DEPLOYMENT": "terraform",
}

ANSIBLE_STAGE_KEYWORDS = {
    "NAT configuration": "nat",
    "VM configuration": "vm",
    "K3s installation": "k3s",
    "Docker installation": "docker",
    "OpenFaaS installation": "openfaas",
    "NAT rule removal": "destroy_nat",
}


class DeploymentRunner:
    """Background runner that executes deploy.py and tracks stage progress."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.running = False
        self.logs: List[str] = []
        self.stage_state: List[Dict] = []
        self.current_stage: str | None = None
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.return_code: int | None = None
        self.mode = DEFAULT_MODE
        self._stage_lookup: Dict[str, int] = {}
        self.role_usage = determine_vm_role_usage()
        self._reset_state()

    def start(self, mode: str = DEFAULT_MODE) -> bool:
        """Start a new deployment run if one is not already active."""
        with self._lock:
            if self.running:
                return False

            if mode not in STAGE_DEFINITIONS:
                mode = DEFAULT_MODE
            self.mode = mode
            self.role_usage = determine_vm_role_usage()
            self._reset_state()
            self.running = True
            self.started_at = time.time()
            self._thread = threading.Thread(
                target=self._run_deploy, name="deploy-runner", daemon=True
            )
            self._thread.start()
            return True

    def status_snapshot(self) -> Dict:
        """Return a copy of the current status for API responses."""
        with self._lock:
            stages = []
            for stage in self.stage_state:
                stage_copy = stage.copy()
                stage_copy["tasks"] = [
                    task.copy() for task in stage.get("tasks", [])
                ]
                stages.append(stage_copy)

            return {
                "running": self.running,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "return_code": self.return_code,
                "mode": self.mode,
                "stages": stages,
                "logs": list(self.logs),
            }

    # Internal helpers -----------------------------------------------------
    def _reset_state(self) -> None:
        self.stage_state = []
        definitions = STAGE_DEFINITIONS.get(self.mode, [])
        for stage in definitions:
            required_role = stage.get("requires_role")
            if required_role and not self.role_usage.get(required_role, False):
                continue
            stage_entry = {
                "id": stage["id"],
                "title": stage["title"],
                "description": stage["description"],
                "tool": stage.get("tool", "Ansible"),
                "progress_event": stage.get("progress_event"),
                "tasks": [
                    {"label": task, "status": "pending"}
                    for task in stage.get("tasks", [])
                ],
                "status": "pending",
                "note": "Waiting to start.",
            }
            stage_entry["base_task_count"] = len(stage_entry["tasks"])
            self.stage_state.append(stage_entry)
        self._stage_lookup = {
            stage["id"]: idx for idx, stage in enumerate(self.stage_state)
        }
        self.logs = []
        self.current_stage = None
        self.started_at = None
        self.finished_at = None
        self.return_code = None

    def _append_log(self, line: str) -> None:
        with self._lock:
            self.logs.append(line)
            # Keep the last 200 log lines to avoid unbounded growth
            if len(self.logs) > 200:
                self.logs = self.logs[-200:]

    def _run_deploy(self) -> None:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        cmd = [sys.executable, "-u", str(DEPLOY_SCRIPT)]
        if self.mode == "destroy":
            cmd.append("--destroy")

        process = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )

        if not process.stdout:
            self._append_log("Failed to attach to deploy.py stdout.")
            self._finalize_run(False)
            return

        try:
            for raw_line in process.stdout:
                line = ANSI_ESCAPE.sub("", raw_line).strip()
                if not line:
                    continue
                self._handle_line(line)
        finally:
            process.stdout.close()
            return_code = process.wait()
            success = return_code == 0
            with self._lock:
                self.return_code = return_code
            if not success and self.current_stage:
                self._complete_stage(
                    self.current_stage,
                    "failed",
                    "deploy.py exited abruptly.",
                )
                self._append_log(f"deploy.py exited with code {return_code}")
            self._finalize_run(success)

    def _handle_line(self, line: str) -> None:
        self._append_log(line)
        if "TASK [" in line:
            self._record_progress_event("ansible_task", line)

        # Detect headers for high level stages
        for header_text, stage_id in HEADER_STAGE_MAP.items():
            if header_text in line:
                self._start_stage(stage_id)
                return

        # Detect Ansible stage events
        for label, stage_id in ANSIBLE_STAGE_KEYWORDS.items():
            if f"Running Ansible {label}" in line:
                self._start_stage(stage_id)
                return
            if f"Ansible {label} completed successfully" in line:
                self._complete_stage(stage_id, "completed", "Finished.")
                return
            if f"Ansible {label} failed" in line or f"{label} failed" in line:
                self._complete_stage(
                    stage_id, "failed", "Failed. Check deployment logs."
                )
                return

        if any(keyword in line for keyword in TERRAFORM_KEYWORDS):
            self._record_progress_event("terraform_step", line)

        if any(keyword in line for keyword in DESTROY_KEYWORDS):
            self._record_progress_event("terraform_destroy", line)

        if "Performing" in line and "destroy" in line.lower():
            self._start_stage("destroy_tf")
            return

        if "Deployment completed successfully" in line:
            if self.current_stage:
                self._complete_stage(self.current_stage, "completed", "Finished.")
            self._append_log("All stages completed.")

    def _start_stage(self, stage_id: str) -> None:
        with self._lock:
            if stage_id not in self._stage_lookup:
                return
            if self.current_stage and self.current_stage != stage_id:
                previous = self.stage_state[self._stage_lookup[self.current_stage]]
                previous["status"] = "completed"
                previous["note"] = "Finished."
                self._mark_tasks(previous, "complete")
            stage = self.stage_state[self._stage_lookup[stage_id]]
            stage["status"] = "running"
            stage["note"] = "In progress..."
            self._mark_tasks(stage, "start")
            self.current_stage = stage_id

    def _complete_stage(self, stage_id: str, status: str, note: str) -> None:
        with self._lock:
            if stage_id not in self._stage_lookup:
                return
            stage = self.stage_state[self._stage_lookup[stage_id]]
            stage["status"] = status
            stage["note"] = note
            if status == "completed":
                self._mark_tasks(stage, "complete")
            elif status == "failed":
                self._mark_tasks(stage, "fail")
            elif status == "skipped":
                self._mark_tasks(stage, "skip")
            if self.current_stage == stage_id:
                self.current_stage = None

    def _finalize_run(self, success: bool) -> None:
        with self._lock:
            if self.current_stage:
                final_status = "completed" if success else "failed"
                note = "Finished." if success else "Deployment stopped."
                stage = self.stage_state[self._stage_lookup[self.current_stage]]
                stage["status"] = final_status
                stage["note"] = note
                if success:
                    self._mark_tasks(stage, "complete")
                else:
                    self._mark_tasks(stage, "fail")
                self.current_stage = None

            for stage in self.stage_state:
                if stage["status"] == "pending":
                    stage["status"] = "skipped"
                    stage["note"] = "Not executed in this run."
                    self._mark_tasks(stage, "skip")

            self.running = False
            self.finished_at = time.time()

    def _record_progress_event(self, event_type: str, line: str | None = None) -> None:
        with self._lock:
            if not self.current_stage or self.current_stage not in self._stage_lookup:
                return
            stage = self.stage_state[self._stage_lookup[self.current_stage]]
            if stage.get("progress_event") != event_type:
                return
            if event_type == "ansible_task":
                task_name = self._extract_ansible_task_name(line)
                self._advance_task(stage, task_name=task_name)
            elif event_type == "terraform_step":
                self._advance_terraform_task(stage, line)
            elif event_type == "terraform_destroy":
                self._advance_destroy_task(stage, line)

    def _advance_task(self, stage: Dict, task_name: str | None = None) -> None:
        tasks = stage.get("tasks", [])
        if not tasks and not task_name:
            return

        if task_name:
            # Complete current running tasks before starting a new one
            for task in tasks:
                if task["status"] == "running":
                    task["status"] = "completed"
            # Ensure unique labels for repeated task names
            label = task_name
            existing_running = next(
                (task for task in tasks if task["label"] == label and task["status"] == "running"),
                None,
            )
            if existing_running:
                return

            duplicate_count = sum(
                1 for task in tasks if task["label"].startswith(task_name)
            )
            if duplicate_count:
                label = f"{task_name} ({duplicate_count + 1})"

            tasks.append({"label": label, "status": "running"})
            return

        running_index = None
        for idx, task in enumerate(tasks):
            if task["status"] == "running":
                running_index = idx
                break

        if running_index is not None:
            tasks[running_index]["status"] = "completed"
            for next_idx in range(running_index + 1, len(tasks)):
                if tasks[next_idx]["status"] == "pending":
                    tasks[next_idx]["status"] = "running"
                    break
            return

        for task in tasks:
            if task["status"] == "pending":
                task["status"] = "running"
                break

    def _extract_ansible_task_name(self, line: str | None) -> str | None:
        if not line:
            return None
        match = ANSIBLE_TASK_PATTERN.search(line)
        if not match:
            return None
        return match.group(1).strip()

    def _advance_terraform_task(self, stage: Dict, line: str | None) -> None:
        if not line:
            return
        tasks = stage.get("tasks", [])
        if not tasks:
            return

        for idx, config in enumerate(TERRAFORM_TASK_SEQUENCE):
            keywords = config.get("keywords", [])
            complete_keywords = config.get("complete_keywords", [])

            if any(keyword in line for keyword in keywords):
                self._ensure_base_task_progress(
                    stage, idx, complete=False, sequence=TERRAFORM_TASK_SEQUENCE
                )
                if "[INFO] Creating" in line:
                    self._add_creation_task(stage, line)
                return

            if any(keyword in line for keyword in complete_keywords):
                self._ensure_base_task_progress(
                    stage, idx, complete=True, sequence=TERRAFORM_TASK_SEQUENCE
                )
                if config["label"] == "Apply infrastructure":
                    self._complete_dynamic_tasks(stage)
                return

    def _ensure_base_task_progress(
        self, stage: Dict, target_index: int, complete: bool, sequence: List[Dict]
    ) -> None:
        tasks = stage.get("tasks", [])
        base_count = stage.get("base_task_count")
        if base_count is None:
            base_count = min(len(tasks), len(sequence))
        if target_index >= base_count:
            return

        for i in range(base_count):
            if i < target_index and tasks[i]["status"] != "completed":
                tasks[i]["status"] = "completed"
            elif i == target_index:
                if complete:
                    tasks[i]["status"] = "completed"
                    if i + 1 < base_count and tasks[i + 1]["status"] == "pending":
                        tasks[i + 1]["status"] = "running"
                else:
                    if tasks[i]["status"] != "completed":
                        tasks[i]["status"] = "running"
                break

    def _add_creation_task(self, stage: Dict, line: str) -> None:
        tasks = stage.get("tasks", [])
        base_count = stage.get("base_task_count", len(tasks))
        if base_count == 0:
            return
        # Mark base apply task as running
        self._ensure_base_task_progress(
            stage,
            min(base_count - 1, 2),
            complete=False,
            sequence=TERRAFORM_TASK_SEQUENCE,
        )

        # Complete any currently running creation task
        for task in tasks[base_count:]:
            if task["status"] == "running":
                task["status"] = "completed"

        label = line.split("Creating", 1)[-1].strip(" .:")
        if not label:
            label = "resource"
        base_label = f"Creating {label}"
        existing = [
            task["label"]
            for task in tasks[base_count:]
            if task["label"].startswith(base_label)
        ]
        if base_label in existing:
            suffix = sum(1 for task in existing if task.startswith(base_label))
            task_label = f"{base_label} ({suffix + 1})"
        else:
            task_label = base_label
        tasks.append({"label": task_label, "status": "running"})

    def _complete_dynamic_tasks(self, stage: Dict) -> None:
        tasks = stage.get("tasks", [])
        base_count = stage.get("base_task_count", len(tasks))
        for task in tasks[base_count:]:
            if task["status"] in {"pending", "running"}:
                task["status"] = "completed"

    def _advance_destroy_task(self, stage: Dict, line: str | None) -> None:
        if not line:
            return
        tasks = stage.get("tasks", [])
        if not tasks:
            return

        line_lower = line.lower()
        for idx, config in enumerate(DESTROY_TASK_SEQUENCE):
            keywords = config.get("keywords", [])
            complete_keywords = config.get("complete_keywords", [])

            if any(keyword.lower() in line_lower for keyword in keywords):
                self._ensure_base_task_progress(
                    stage, idx, complete=False, sequence=DESTROY_TASK_SEQUENCE
                )

            if any(keyword.lower() in line_lower for keyword in complete_keywords):
                self._ensure_base_task_progress(
                    stage, idx, complete=True, sequence=DESTROY_TASK_SEQUENCE
                )
                if config["label"] == "Destroy VM resources":
                    self._complete_destroy_dynamic_tasks(stage)

        if "Destroying..." in line:
            self._add_destroy_task(stage, line)
        elif "Destruction complete" in line or "Destroy complete" in line:
            self._complete_matching_destroy_task(stage, line)

    def _add_destroy_task(self, stage: Dict, line: str) -> None:
        tasks = stage.get("tasks", [])
        base_count = stage.get("base_task_count", len(tasks))
        if base_count == 0:
            return

        self._ensure_base_task_progress(
            stage,
            min(base_count - 1, len(DESTROY_TASK_SEQUENCE) - 1),
            complete=False,
            sequence=DESTROY_TASK_SEQUENCE,
        )

        for task in tasks[base_count:]:
            if task["status"] == "running":
                task["status"] = "completed"

        if ": Destroying" in line:
            resource = line.split(": Destroying", 1)[0].strip()
        else:
            resource = line.strip().split()[0]
        base_label = f"Destroying {resource}"
        existing = [
            task["label"]
            for task in tasks[base_count:]
            if task["label"].startswith(base_label)
        ]
        if base_label in existing:
            suffix = sum(1 for task in existing if task.startswith(base_label))
            label = f"{base_label} ({suffix + 1})"
        else:
            label = base_label
        tasks.append({"label": label, "status": "running"})

    def _complete_matching_destroy_task(self, stage: Dict, line: str) -> None:
        tasks = stage.get("tasks", [])
        base_count = stage.get("base_task_count", len(tasks))
        resource = line.split(":")[0].strip()
        prefix = f"Destroying {resource}"
        for task in tasks[base_count:]:
            if task["label"].startswith(prefix):
                task["status"] = "completed"

    def _complete_destroy_dynamic_tasks(self, stage: Dict) -> None:
        tasks = stage.get("tasks", [])
        base_count = stage.get("base_task_count", len(tasks))
        for task in tasks[base_count:]:
            if task["status"] in {"pending", "running"}:
                task["status"] = "completed"

    def _mark_tasks(self, stage: Dict, action: str) -> None:
        tasks = stage.get("tasks", [])
        if not tasks:
            return

        if action == "start":
            for task in tasks:
                if task["status"] == "pending":
                    task["status"] = "running"
                    break
            return

        if action == "complete":
            for task in tasks:
                if task["status"] in {"pending", "running"}:
                    task["status"] = "completed"
            return

        if action == "fail":
            for task in tasks:
                if task["status"] == "running":
                    task["status"] = "failed"
                elif task["status"] == "pending":
                    task["status"] = "skipped"
            return

        if action == "skip":
            for task in tasks:
                if task["status"] == "pending":
                    task["status"] = "skipped"


runner = DeploymentRunner()

app = Flask(__name__, static_folder="static")


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/status")
def get_status():
    return jsonify(runner.status_snapshot())


@app.route("/api/run", methods=["POST"])
def run_deploy():
    if not runner.start("deploy"):
        return (
            jsonify({"started": False, "message": "Deployment already running."}),
            409,
        )
    return jsonify({"started": True})


@app.route("/api/destroy", methods=["POST"])
def destroy_infrastructure():
    if not runner.start("destroy"):
        return (
            jsonify({"started": False, "message": "Deployment already running."}),
            409,
        )
    return jsonify({"started": True})


@app.route("/api/vms")
def list_vms():
    """Return VM inventory based on terraform state."""
    vms = get_tfstate_vm_info()
    return jsonify({"vms": vms, "count": len(vms)})


@app.route("/api/vm-metrics")
def vm_metrics():
    """Return CPU and memory usage for VMs created by OpenTofu."""
    vms = get_tfstate_vm_info()
    if not vms:
        return jsonify({"available": False, "message": "No VMs found."}), 404

    creds = parse_proxmox_credentials()
    client = connect_proxmox(creds)
    if client is None:
        message = (
            "Proxmox client unavailable. "
            "Check proxmoxer installation and credentials in terraform.tfvars."
        )
        return jsonify({"available": False, "message": message}), 503

    try:
        stats = client.cluster.resources.get(type="vm")
    except Exception:
        return jsonify({"available": False, "message": "Unable to reach Proxmox API."}), 502

    stats_by_id = {
        str(entry.get("vmid")): entry
        for entry in stats
        if entry.get("vmid") is not None
    }

    enriched = []
    for vm in vms:
        vm_stat = stats_by_id.get(str(vm["id"]))
        if not vm_stat:
            enriched.append({**vm, "cpu_pct": None, "mem": None, "online": False})
            continue

        maxmem = vm_stat.get("maxmem") or 0
        mem = vm_stat.get("mem") or 0
        mem_pct = round(mem / maxmem * 100, 2) if maxmem else 0.0
        cpu_pct = round((vm_stat.get("cpu") or 0) * 100, 2)
        enriched.append(
            {
                **vm,
                "cpu_pct": cpu_pct,
                "mem": {
                    "used_bytes": mem,
                    "total_bytes": maxmem,
                    "used_pct": mem_pct,
                },
                "online": True,
                "node": vm.get("node") or vm_stat.get("node"),
            }
        )

    return jsonify({"available": True, "vms": enriched})


if __name__ == "__main__":
    port = int(os.environ.get("DEPLOY_UI_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
