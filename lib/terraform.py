#!/usr/bin/env python3
"""
lib/terraform.py - Terraform/OpenTofu workflow management

This module implements the functionality of terraform.sh in Python.
It handles Terraform/OpenTofu initialization, validation, formatting,
planning, and applying infrastructure changes.
"""

import os
import sys
import subprocess
import json
import logging
import shutil
import atexit
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"logs/deployment_{os.popen('date +%Y%m%d_%H%M%S').read().strip()}.log")
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
TERRAFORM_DIR = "terraform-opentofu"

# Debug mode
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

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

# Register cleanup function
atexit.register(cleanup)

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

def print_debug(message):
    """Print a debug message if DEBUG is enabled."""
    if DEBUG:
        logger.debug(f"{PURPLE}[DEBUG]{NC} {message}")

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

def check_command_exists(command):
    """Check if a command exists in the system PATH."""
    try:
        subprocess.run(["which", command], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

def run_terraform_workflow():
    """
    Run the Terraform/OpenTofu workflow.

    This function handles initialization, validation, formatting, planning,
    and applying infrastructure changes.

    Returns:
        int: 0 if no changes were applied, 1 if changes were applied

    Raises:
        SystemExit: If there's an error during planning or user cancels the deployment
    """
    print_header("WORKFLOW TERRAFORM/OPENTOFU")

    # Change to terraform directory
    original_dir = os.getcwd()
    os.chdir(TERRAFORM_DIR)

    # Determine which command to use (OpenTofu or Terraform)
    if check_command_exists("tofu"):
        tf_cmd = "tofu"
        tf_version_result = run_command(f"{tf_cmd} version", capture_output=True)
        tf_version = tf_version_result.stdout.splitlines()[0] if tf_version_result.stdout else "Unknown version"
        print_status(f"Using OpenTofu: {tf_version}")
    else:
        tf_cmd = "terraform"
        tf_version_result = run_command(f"{tf_cmd} version", capture_output=True)
        tf_version = tf_version_result.stdout.splitlines()[0] if tf_version_result.stdout else "Unknown version"
        print_status(f"Using Terraform: {tf_version}")

    # Initialization
    print_status(f"Initializing {tf_cmd}...")
    if Path(".terraform").is_dir():
        run_command(f"{tf_cmd} init -upgrade")
    else:
        run_command(f"{tf_cmd} init")

    # Validation
    print_status("Validating configuration...")
    run_command(f"{tf_cmd} validate")
    print_status("✓ Configuration valid")

    # Formatting
    print_status("Checking formatting...")
    fmt_result = run_command(f"{tf_cmd} fmt -check -recursive", check=False)
    if fmt_result.returncode != 0:
        print_warning("Formatting code...")
        run_command(f"{tf_cmd} fmt -recursive")
    print_status("✓ Code formatted correctly")

    # Planning
    skip_plan = os.environ.get("SKIP_PLAN", "").lower() == "true"
    plan_exit_code = 0

    if not skip_plan:
        print_status("Planning deployment...")
        plan_result = run_command(f"{tf_cmd} plan -out={PLAN_FILE} -detailed-exitcode", check=False)
        plan_exit_code = plan_result.returncode

        if plan_exit_code == 0:
            print_status("✓ No changes needed")
            os.chdir(original_dir)
            return 0
        elif plan_exit_code == 1:
            print_error("✗ Error during planning")
            os.chdir(original_dir)
            sys.exit(1)
        elif plan_exit_code == 2:
            print_status("✓ Plan created with changes to apply")

        # Show the plan
        print_header("PLAN SUMMARY")
        run_command(f"{tf_cmd} show {PLAN_FILE}")

    # If there are no changes to apply, exit without applying
    if plan_exit_code == 0:
        os.chdir(original_dir)
        return 0

    # User confirmation
    auto_approve = os.environ.get("AUTO_APPROVE", "").lower() == "true"
    if not auto_approve:
        print()
        response = input("Do you want to proceed with VM creation? (y/N): ")
        print()
        if not response.lower().startswith('y'):
            print_warning("Deployment canceled by user")
            os.chdir(original_dir)
            sys.exit(0)

    # Apply changes
    if skip_plan:
        print_status("Skipping apply phase, showing only outputs defined in main.tf...")
        run_command(f"{tf_cmd} output")
    else:
        print_status(f"Creating VM with {tf_cmd}...")
        if auto_approve:
            run_command(f"{tf_cmd} apply -auto-approve {PLAN_FILE}")
        else:
            run_command(f"{tf_cmd} apply {PLAN_FILE}")

    print_status("✓ Infrastructure created successfully!")
    os.chdir(original_dir)
    return 1  # Indicates that changes were applied

def select_terraform_workspace(workspace):
    """
    Select or create a Terraform workspace.

    Args:
        workspace (str): The name of the workspace to select or create
    """
    if not workspace:
        return

    original_dir = os.getcwd()
    os.chdir("terraform-opentofu")

    print_status(f"Selecting workspace: {workspace}")

    # Determine which command to use
    tf_cmd = "tofu" if check_command_exists("tofu") else "terraform"

    # Try to select workspace, create if it doesn't exist
    select_result = run_command(f"{tf_cmd} workspace select {workspace}", check=False)
    if select_result.returncode != 0:
        run_command(f"{tf_cmd} workspace new {workspace}")

    os.chdir(original_dir)

def get_vm_ips_from_terraform():
    """
    Get VM IPs from Terraform outputs.

    Returns:
        str: JSON string containing VM IPs or None if error

    Example:
        >>> ips = get_vm_ips_from_terraform()
        >>> if ips:
        ...     vm_ips = json.loads(ips)
        ...     for vm, ip in vm_ips.items():
        ...         print(f"VM {vm}: {ip}")
    """
    # Determine which command to use
    tf_cmd = "tofu" if check_command_exists("tofu") else "terraform"

    original_dir = os.getcwd()
    os.chdir(TERRAFORM_DIR)

    try:
        output_result = run_command(f"{tf_cmd} output -json vm_ips", capture_output=True, check=False)
        if output_result.returncode != 0:
            print_error("Unable to get VM IPs from Terraform output")
            print_error("Make sure there is an output called 'vm_ips' in your configuration")
            os.chdir(original_dir)
            return None

        vm_ips = output_result.stdout
        os.chdir(original_dir)
        return vm_ips

    except Exception as e:
        print_error(f"Error during command execution: {e}")
        os.chdir(original_dir)
        return None

def get_vm_summary_from_terraform():
    """
    Get VM summary from Terraform outputs.

    Returns:
        str: JSON string containing VM summary or None if error
    """
    # Determine which command to use
    tf_cmd = "tofu" if check_command_exists("tofu") else "terraform"

    original_dir = os.getcwd()
    os.chdir(TERRAFORM_DIR)

    try:
        output_result = run_command(f"{tf_cmd} output -json vm_summary", capture_output=True, check=False)
        if output_result.returncode != 0:
            print_error("Unable to get VM summary from Terraform output")
            print_error("Make sure there is an output called 'vm_summary' in your configuration")
            os.chdir(original_dir)
            return None

        vm_summary = output_result.stdout
        os.chdir(original_dir)
        return vm_summary

    except Exception as e:
        print_error(f"Error during command execution: {e}")
        os.chdir(original_dir)
        return None

def run_terraform_destroy():
    """
    Destroy the infrastructure created by Terraform/OpenTofu.

    Raises:
        SystemExit: If there's an error during the destruction process
    """
    print_header("INFRASTRUCTURE DESTRUCTION")

    original_dir = os.getcwd()
    os.chdir(TERRAFORM_DIR)

    # Determine which command to use
    tf_cmd = "tofu" if check_command_exists("tofu") else "terraform"

    print_status(f"Starting destruction process with {tf_cmd}...")

    # Add --auto-approve if requested
    auto_approve = os.environ.get("AUTO_APPROVE", "").lower() == "true"

    if auto_approve:
        print_status("Auto-approve mode ENABLED.")
        destroy_args = "--auto-approve"
    else:
        print_warning("Manual confirmation required.")
        print()
        response = input("Do you want to proceed with infrastructure destruction? (y/N): ")
        print()
        if not response.lower().startswith('y'):
            print_warning("Destruction canceled by user")
            os.chdir(original_dir)
            sys.exit(0)
        destroy_args = ""

    # Execute the destroy command
    destroy_result = run_command(f"{tf_cmd} destroy {destroy_args}", check=False)
    if destroy_result.returncode != 0:
        print_error("Error during infrastructure destruction.")
        os.chdir(original_dir)
        sys.exit(1)

    print_success("Infrastructure destroyed successfully.")
    os.chdir(original_dir)

# If run directly, show a message
if __name__ == "__main__":
    print("This is a library module and should not be run directly.")
    sys.exit(1)
