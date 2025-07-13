#!/usr/bin/env python3
"""
lib/common.py - Common functions and configuration

This module provides shared functionality used across the deployment scripts.
It reimplements the functionality of common.sh in Python.
"""

import os
import sys
import subprocess
import logging
import atexit
from pathlib import Path
from datetime import datetime

# Configure logging
LOG_FILE = f"logs/deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE)
    ]
)
logger = logging.getLogger(__name__)

# ANSI color codes for output formatting
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
PURPLE = '\033[0;35m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color

# Global configuration
PLAN_FILE = "tfplan"
LOG_FILE = f"logs/deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
PLAYBOOK_FILE1 = "playbooks/configure-vms.yml"
PLAYBOOK_FILE2 = "playbooks/add_nat_rules.yml"
PLAYBOOK_FILE3 = "playbooks/k3s_install.yml"
TERRAFORM_DIR = "terraform-opentofu"
SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa")

# Remote Proxmox configuration
PROXMOX_HOST = os.environ.get("PROXMOX_HOST", "")
PROXMOX_USER = os.environ.get("PROXMOX_USER", "root")
PROXMOX_SSH_KEY = os.environ.get("PROXMOX_SSH_KEY", SSH_KEY_PATH)
EXTERNAL_INTERFACE = os.environ.get("EXTERNAL_INTERFACE", "vmbr0")
INTERNAL_INTERFACE = os.environ.get("INTERNAL_INTERFACE", "vmbr1")
NAT_START_PORT = os.environ.get("NAT_START_PORT", "20000")
K3S_API_PORT = os.environ.get("K3S_API_PORT", "6443")

# Debug mode
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# Output functions
def print_status(message):
    """Print an informational status message."""
    logger.info(f"{GREEN}[INFO]{NC} {message}")

def print_success(message):
    """Print a success message."""
    logger.info(f"{GREEN}[SUCCESS]{NC} {message}")

def print_warning(message):
    """Print a warning message."""
    logger.warning(f"{YELLOW}[WARNING]{NC} {message}")

def print_error(message):
    """Print an error message."""
    logger.error(f"{RED}[ERROR]{NC} {message}")

def print_header(message):
    """Print a section header."""
    logger.info(f"{BLUE}=== {message} ==={NC}")

def print_ansible(message):
    """Print an Ansible-related message."""
    logger.info(f"{CYAN}[ANSIBLE]{NC} {message}")

def print_nat(message):
    """Print a NAT-related message."""
    logger.info(f"{PURPLE}[NAT]{NC} {message}")

def print_debug(message):
    """Print a debug message if DEBUG is enabled."""
    if DEBUG:
        logger.debug(f"{PURPLE}[DEBUG]{NC} {message}")

def check_command_exists(command):
    """Check if a command exists in the system PATH."""
    try:
        subprocess.run(["which", command], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

def run_command(command, check=True, capture_output=False):
    """
    Execute a shell command and return the result.

    Args:
        command (str): The shell command to execute
        check (bool): If True, raises an exception if the command returns a non-zero exit code
        capture_output (bool): If True, captures and returns stdout and stderr

    Returns:
        subprocess.CompletedProcess: The result of the command execution
    """
    print_debug(f"Executing: {command}")

    if capture_output:
        result = subprocess.run(command, shell=True, check=check, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                               text=True)
    else:
        result = subprocess.run(command, shell=True, check=check)

    return result

# Cleanup function
def cleanup():
    """
    Clean up temporary files and resources.

    This function is registered with atexit to ensure it runs when the script exits.
    """
    plan_file_path = Path(TERRAFORM_DIR) / PLAN_FILE
    if plan_file_path.exists():
        try:
            plan_file_path.unlink()
            print_debug(f"Removed temporary plan file: {plan_file_path}")
        except Exception as e:
            print_debug(f"Error removing plan file: {e}")
    
    exit_code = getattr(sys, 'last_value', 0) if hasattr(sys, 'last_value') else 0
    if exit_code:
        print_error(f"Script finished with an error. Log saved to: {LOG_FILE}")
    else:
        print_status(f"Script completed. Log saved to: {LOG_FILE}")

# Register cleanup function
atexit.register(cleanup)

# Function to show help
def show_help():
    """Display help information for the deployment script."""
    print("Usage: deploy.py [options]")
    print()
    print("Integrated script for deploying VMs with Terraform/OpenTofu and Ansible")
    print()
    print("Options:")
    print("  --force-redeploy       Force a new deployment even if one already exists")
    print("  --continue-if-deployed Continue execution even if the deployment already exists")
    print("  --skip-nat             Skip NAT rule configuration")
    print("  --skip-ansible         Skip Ansible configuration")
    print("  --workspace NAME       Select a specific Terraform workspace")
    print("  --auto-approve         Automatically approve Terraform changes")
    print("  --no-vm-update         Skip VM configuration playbook (configure-vms.yml)")
    print("  --no-k3s               Skip K3s installation playbook (k3s_install.yml)")
    print("  --no-docker            Skip Docker installation playbook (docker_install.yml)")
    print("  --no-openfaas          Skip OpenFaaS installation playbook (install_openfaas.yml)")
    print("  --destroy              Destroy the created infrastructure")
    print("  -h, --help             Show this help")
    print()
    print("Environment variables:")
    print("  PROXMOX_HOST        IP of the Proxmox server")
    print("  PROXMOX_USER        SSH username for connection (default: root)")
    print("  PROXMOX_SSH_KEY     SSH key for Proxmox (default: $SSH_KEY_PATH)")
    print("  EXTERNAL_INTERFACE  External network interface (default: vmbr0)")
    print("  NAT_START_PORT      Initial port for port forwarding (default: 20000)")
    print()
    print("Examples:")
    print("  deploy.py --proxmox-host 192.168.1.100")
    print("  deploy.py --auto-approve --proxmox-host 192.168.1.100")
    print("  PROXMOX_HOST=192.168.1.100 deploy.py --auto-approve")

# If run directly, show a message
if __name__ == "__main__":
    print("This is a library module and should not be run directly.")
    sys.exit(1)