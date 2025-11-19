#!/usr/bin/env python3
"""Simple Flask server that exposes a UI to run deploy.py."""

from __future__ import annotations

import os
import re
import sys
import time
import threading
import subprocess
from pathlib import Path
from typing import Dict, List

from flask import Flask, jsonify, send_from_directory

BASE_DIR = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = BASE_DIR / "deploy.py"
ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

STAGE_DEFINITIONS = [
    {
        "id": "setup",
        "title": "Initial Setup & Validation",
        "description": "Checks prerequisites, terraform.tfvars, and SSH keys.",
    },
    {
        "id": "terraform",
        "title": "Terraform Deployment",
        "description": "Creates or updates the Proxmox VMs through Terraform/OpenTofu.",
    },
    {
        "id": "nat",
        "title": "NAT Rules",
        "description": "Configures NAT and port forwarding on the Proxmox host.",
    },
    {
        "id": "vm",
        "title": "VM Preparation",
        "description": "Runs the base VM configuration playbook.",
    },
    {
        "id": "k3s",
        "title": "K3s Installation",
        "description": "Installs the lightweight Kubernetes distribution.",
    },
    {
        "id": "docker",
        "title": "Docker Installation",
        "description": "Installs Docker Engine on the nodes.",
    },
    {
        "id": "openfaas",
        "title": "OpenFaaS Installation",
        "description": "Deploys OpenFaaS workloads on K3s.",
    },
]

STAGE_INDEX = {stage["id"]: idx for idx, stage in enumerate(STAGE_DEFINITIONS)}

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
}


class DeploymentRunner:
    """Background runner that executes deploy.py and tracks stage progress."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.running = False
        self.logs: List[str] = []
        self.stage_state: List[Dict[str, str]] = []
        self.current_stage: str | None = None
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.return_code: int | None = None
        self._reset_state()

    def start(self) -> bool:
        """Start a new deployment run if one is not already active."""
        with self._lock:
            if self.running:
                return False

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
            return {
                "running": self.running,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "return_code": self.return_code,
                "stages": [stage.copy() for stage in self.stage_state],
                "logs": list(self.logs),
            }

    # Internal helpers -----------------------------------------------------
    def _reset_state(self) -> None:
        self.stage_state = [
            {
                **stage,
                "status": "pending",
                "note": "Waiting to start.",
            }
            for stage in STAGE_DEFINITIONS
        ]
        self.logs = []
        self.current_stage = None
        self.started_at = None
        self.finished_at = None
        self.return_code = None

    def _append_log(self, line: str) -> None:
        with self._lock:
            self.logs.append(line)
            # Keep the last 400 log lines to avoid unbounded growth
            if len(self.logs) > 400:
                self.logs = self.logs[-400:]

    def _run_deploy(self) -> None:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        cmd = [sys.executable, "-u", str(DEPLOY_SCRIPT)]

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

        if "Deployment completed successfully" in line:
            if self.current_stage:
                self._complete_stage(self.current_stage, "completed", "Finished.")
            self._append_log("All stages completed.")

    def _start_stage(self, stage_id: str) -> None:
        with self._lock:
            if self.current_stage and self.current_stage != stage_id:
                previous = self.stage_state[STAGE_INDEX[self.current_stage]]
                previous["status"] = "completed"
                previous["note"] = "Finished."
            stage = self.stage_state[STAGE_INDEX[stage_id]]
            stage["status"] = "running"
            stage["note"] = "In progress..."
            self.current_stage = stage_id

    def _complete_stage(self, stage_id: str, status: str, note: str) -> None:
        with self._lock:
            stage = self.stage_state[STAGE_INDEX[stage_id]]
            stage["status"] = status
            stage["note"] = note
            if self.current_stage == stage_id:
                self.current_stage = None

    def _finalize_run(self, success: bool) -> None:
        with self._lock:
            if self.current_stage:
                final_status = "completed" if success else "failed"
                note = "Finished." if success else "Deployment stopped."
                stage = self.stage_state[STAGE_INDEX[self.current_stage]]
                stage["status"] = final_status
                stage["note"] = note
                self.current_stage = None

            for stage in self.stage_state:
                if stage["status"] == "pending":
                    stage["status"] = "skipped"
                    stage["note"] = "Not executed in this run."

            self.running = False
            self.finished_at = time.time()


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
    if not runner.start():
        return (
            jsonify({"started": False, "message": "Deployment already running."}),
            409,
        )
    return jsonify({"started": True})


if __name__ == "__main__":
    port = int(os.environ.get("DEPLOY_UI_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
