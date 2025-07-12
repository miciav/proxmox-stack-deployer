#!/usr/bin/env python3
"""
lib/prereq.py - Prerequisite checks and validation

This module reimplements the functionality of prereq.sh in Python.
It checks for required tools, validates configuration files, and sets up
environment variables needed for deployment.
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

# Import common functions and variables
from lib.common import (
    print_status, print_success, print_warning, print_error, print_header,
    print_ansible, print_nat, print_debug, check_command_exists, run_command,
    PLAN_FILE, PLAYBOOK_FILE1, PLAYBOOK_FILE2, PLAYBOOK_FILE3, TERRAFORM_DIR,
    SSH_KEY_PATH, PROXMOX_HOST, PROXMOX_USER, PROXMOX_SSH_KEY,
    EXTERNAL_INTERFACE, INTERNAL_INTERFACE, NAT_START_PORT, K3S_API_PORT,
    DEBUG
)

def check_prerequisites():
    """
    Check if all required tools and files are available.

    Equivalent to check_prerequisites() in prereq.sh.
    """
    print_header("CHECK PREREQUISITES")

    # Check for Terraform or OpenTofu
    if check_command_exists("tofu"):
        os.environ["TERRAFORM_COMMAND"] = "tofu"
    else:
        os.environ["TERRAFORM_COMMAND"] = "terraform"
    print_status(f"✓ Using {os.environ['TERRAFORM_COMMAND']}")

    # Check for Ansible
    if not check_command_exists("ansible"):
        print_error("Ansible is not installed.")
        sys.exit(1)
    else:
        print_status("Ansible is installed.")

    # Check for ansible-playbook
    if not check_command_exists("ansible-playbook"):
        print_error("ansible-playbook command is not available.")
        sys.exit(1)
    else:
        print_status("ansible-playbook command is available.")

    # Check for Terraform files
    original_dir = os.getcwd()
    os.chdir(TERRAFORM_DIR)

    tf_files = list(Path(".").glob("*.tf"))
    if not tf_files:
        print_error("No .tf file has been found in the current directory")
        os.chdir(original_dir)
        sys.exit(1)
    print_status(".tf file has been found in the current directory")

    os.chdir(original_dir)

    # Check for Ansible playbooks
    if not os.path.isfile(PLAYBOOK_FILE1):
        print_error(f"Playbook Ansible '{PLAYBOOK_FILE1}' not found")
        sys.exit(1)
    print_status(f"Playbook Ansible '{PLAYBOOK_FILE1}' found")

    if not os.path.isfile(PLAYBOOK_FILE2):
        print_error(f"Playbook Ansible '{PLAYBOOK_FILE2}' not found")
        sys.exit(1)
    print_status(f"Playbook Ansible '{PLAYBOOK_FILE2}' found")

    if not os.path.isfile(PLAYBOOK_FILE3):
        print_error(f"Playbook Ansible '{PLAYBOOK_FILE3}' not found")
        sys.exit(1)
    print_status(f"Playbook Ansible '{PLAYBOOK_FILE3}' found")

    print_status("✓ All requirements are satisfied")
    return True

def get_proxmox_host_from_tfvars():
    """
    Extract proxmox_host from terraform.tfvars file.

    Equivalent to get_proxmox_host_from_tfvars() in prereq.sh.

    Returns:
        str: The proxmox_host value or empty string if not found
    """
    tfvars_file = "terraform.tfvars"
    hostname = ""

    print_debug(f"Looking for proxmox_host in {tfvars_file}...")

    if not os.path.isfile(tfvars_file):
        print_error(f"File {tfvars_file} not found in the current directory")
        return ""

    # Extract proxmox_host ignoring comments and spaces
    with open(tfvars_file, 'r') as f:
        for line in f:
            # Remove comments
            line = re.sub(r'#.*$', '', line)

            # Check if line contains proxmox_host
            match = re.match(r'^\s*proxmox_host\s*=\s*["\']?([^"\']+)["\']?\s*$', line)
            if match:
                hostname = match.group(1)
                break

    if hostname:
        print_status(f"✓ Hostname proxmox_host found in {tfvars_file}: {hostname}")
        return hostname
    else:
        print_error(f"Variable proxmox_host not found in {tfvars_file}")
        print_status(f'Make sure the file contains a line like: proxmox_host = "192.168.1.100"')
        return ""

def get_ci_user_from_tfvars():
    """
    Extract ci_user from terraform.tfvars file.

    Equivalent to get_ci_user_from_tfvars() in prereq.sh.

    Returns:
        str: The ci_user value or empty string if not found
    """
    tfvars_file = "terraform.tfvars"
    username = ""

    print_debug(f"Looking for ci_user in {tfvars_file}...")

    if not os.path.isfile(tfvars_file):
        print_error(f"File {tfvars_file} not found in the current directory")
        return ""

    # Extract ci_user ignoring comments and spaces
    with open(tfvars_file, 'r') as f:
        for line in f:
            # Remove comments
            line = re.sub(r'#.*$', '', line)

            # Check if line contains ci_user
            match = re.match(r'^\s*ci_user\s*=\s*["\']?([^"\']+)["\']?\s*$', line)
            if match:
                username = match.group(1)
                break

    if username:
        print_status(f"✓ Username ci_user found in {tfvars_file}: {username}")
        return username
    else:
        print_error(f"Variable ci_user not found in {tfvars_file}")
        print_status(f'Make sure the file contains a line like: ci_user = "username"')
        return ""

def validate_tfvars_file():
    """
    Validate terraform.tfvars file and extract variables.
    Equivalent to validate_tfvars_file() in prereq.sh.
    Returns:
        bool: True if validation succeeded, False otherwise
    """
    print_header("FILE VALIDATION TERRAFORM.TFVARS")
    original_dir = os.getcwd()
    os.chdir(TERRAFORM_DIR)
    tfvars_file = "terraform.tfvars"
    print_debug(f"Starting file validation: {tfvars_file}")

    # Check if file exists
    print_debug("Checking file existence...")
    if not os.path.isfile(tfvars_file):
        print_error(f"File {tfvars_file} not found!")
        print_debug(f"File searched in path: {os.getcwd()}/{tfvars_file}")
        print_debug(f"Files in directory: {', '.join(os.listdir('.')[:10])}")
        print_status("Create the file with content similar to:")
        print_status('ci_user = "username"')
        print_status('proxmox_host = "192.168.1.100"')
        os.chdir(original_dir)
        return False

    print_debug(f"✓ File {tfvars_file} found")

    # Read file once and store content
    try:
        with open(tfvars_file, 'r') as f:
            content = f.read()
            lines = content.splitlines()
    except (FileNotFoundError, PermissionError) as e:
        print_error(f"Error reading file {tfvars_file}: {e}")
        os.chdir(original_dir)
        return False

    # Debug file info
    file_size = os.path.getsize(tfvars_file)
    print_debug(f"File size: {file_size} bytes")
    print_debug("File content:")
    print_debug("=== START CONTENT ===")
    for line in lines:
        print_debug(line)
    print_debug("=== END CONTENT ===")

    # Validate ci_user with better regex
    print_debug("Checking for ci_user variable...")
    if not re.search(r'^\s*ci_user\s*=', content, re.MULTILINE):
        print_error(f"Variable ci_user not found in {tfvars_file}")
        print_debug(f"Searched for pattern: '^\\s*ci_user\\s*='")
        print_status('Add a line like: ci_user = "username"')
        os.chdir(original_dir)
        return False

    print_debug("✓ Variable ci_user found")

    # Validate proxmox_host with better regex
    print_debug("Checking for proxmox_host variable...")
    if not re.search(r'^\s*proxmox_host\s*=', content, re.MULTILINE):
        print_error(f"Variable proxmox_host not found in {tfvars_file}")
        print_debug(f"Searched for pattern: '^\\s*proxmox_host\\s*='")
        print_status('Add a line like: proxmox_host = "192.168.1.100"')
        os.chdir(original_dir)
        return False

    print_debug("✓ Variable proxmox_host found")

    # Test reading ci_user
    print_debug("Testing ci_user extraction...")
    ci_user = get_ci_user_from_tfvars()
    if not ci_user:
        print_error("Error reading ci_user")
        print_debug(f"Output of get_ci_user_from_tfvars: '{ci_user}'")
        os.chdir(original_dir)
        return False

    print_status(f"✓ Username configured: {ci_user}")
    print_debug(f"Username extracted successfully: '{ci_user}'")
    os.environ["CI_USER"] = ci_user
    print_debug(f"CI_USER exported: {os.environ['CI_USER']}")

    # Validate username format
    if re.match(r'^[a-zA-Z0-9_-]+$', ci_user):
        print_debug("✓ Valid username format")
    else:
        print_warning(f"Username contains special characters: '{ci_user}'")

    # Test reading proxmox_host
    print_debug("Testing proxmox_host extraction...")
    proxmox_host = get_proxmox_host_from_tfvars()
    if not proxmox_host:
        print_error("Error reading proxmox_host")
        print_debug(f"Output of get_proxmox_host_from_tfvars: '{proxmox_host}'")
        os.chdir(original_dir)
        return False

    print_status(f"✓ Proxmox host configured: {proxmox_host}")
    print_debug(f"Proxmox host extracted successfully: '{proxmox_host}'")
    os.environ["PROXMOX_HOST"] = proxmox_host
    print_debug(f"PROXMOX_HOST exported: {os.environ['PROXMOX_HOST']}")

    # Validate IP/hostname format with better error handling
    if re.match(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$', proxmox_host):
        print_debug("✓ Valid IP format")
        # Validate IP range with proper error handling
        try:
            octets = proxmox_host.split('.')
            for octet in octets:
                if not octet.isdigit() or int(octet) > 255:
                    print_warning(f"Invalid IP: {proxmox_host} (octet {octet} > 255 or not numeric)")
                    break
        except ValueError:
            print_warning(f"Invalid IP format: {proxmox_host}")
    elif re.match(r'^[a-zA-Z0-9.-]+$', proxmox_host):
        print_debug("✓ Valid hostname format")
    else:
        print_warning(f"Host contains invalid characters: '{proxmox_host}'")

    # Additional validations using already-read content
    print_debug("Performing additional validations...")

    # Check for unquoted values
    for line in lines:
        if re.match(r'^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=.*[^"]$', line) and not line.strip().startswith('#'):
            print_warning("Possible unquoted values found in tfvars file")
            print_debug(f"Suspicious line: {line.strip()}")

    # Count empty lines - Fixed regex
    empty_lines = sum(1 for line in lines if re.match(r'^\s*$', line))
    print_debug(f"Empty lines in file: {empty_lines}")

    # Count comment lines
    comment_lines = sum(1 for line in lines if re.match(r'^\s*#', line))
    print_debug(f"Comment lines in file: {comment_lines}")

    print_status(f"✓ File {tfvars_file} is valid")
    print_debug("Validation completed successfully")

    # Final debug of exported variables
    print_debug("=== EXPORTED VARIABLES ===")
    print_debug(f"CI_USER: '{os.environ.get('CI_USER', '')}'")
    print_debug(f"PROXMOX_HOST: '{os.environ.get('PROXMOX_HOST', '')}'")
    print_debug("==========================")

    os.chdir(original_dir)
    return True



def get_validated_vars():
    """
    Verify that variables are set after validation and set defaults if needed.

    Equivalent to get_validated_vars() in prereq.sh.

    Returns:
        bool: True if all required variables are set, False otherwise
    """
    print_header("GET VALIDATED VARIABLES")
    print_debug("=== VARIABLES AVAILABLE AFTER VALIDATION ===")
    print_debug(f"CI_USER: '{os.environ.get('CI_USER', 'NOT_DEFINED')}'")
    print_debug(f"PROXMOX_HOST: '{os.environ.get('PROXMOX_HOST', 'NOT_DEFINED')}'")
    print_debug(f"PROXMOX_USER: '{os.environ.get('PROXMOX_USER', 'NOT_DEFINED')}'")
    print_debug("============================================")

    # Verify that variables are set
    if not os.environ.get('CI_USER'):
        print_error("CI_USER is not defined after validation")
        return False

    if not os.environ.get('PROXMOX_HOST'):
        print_error("PROXMOX_HOST is not defined after validation")
        return False

    # Set PROXMOX_USER if not already defined (using CI_USER as fallback)
    if not os.environ.get('PROXMOX_USER'):
        os.environ['PROXMOX_USER'] = os.environ.get('CI_USER')
        print_debug(f"PROXMOX_USER automatically set to: {os.environ['PROXMOX_USER']}")

    print_status("All required variables are set")
    return True




# Constants
PRIVATE_KEY_PERMS = 0o600
PUBLIC_KEY_PERMS = 0o644
KEY_SIZE = 4096


def setup_ssh_keys() -> bool:
    """
    Set up SSH keys for deployment using cryptography library.

    Checks if SSH public key exists and generates one if it doesn't.
    Also ensures proper permissions on the key files.

    Returns:
        bool: True if setup was successful, False otherwise
    """
    print_header("SSH CONFIGURATION")

    ssh_key_path = Path(SSH_KEY_PATH)
    pub_key_path = ssh_key_path.with_suffix('.pub')

    # Check if SSH public key exists
    if not pub_key_path.exists():
        print_warning("SSH public key not found. Generating a new one...")

        if not _generate_ssh_key_cryptography(ssh_key_path, pub_key_path):
            return False

        print_status(f"✓ New SSH key generated: {pub_key_path}")
    else:
        print_status(f"✓ Existing SSH key found: {pub_key_path}")

    # Set correct permissions for SSH key files
    _set_key_permissions(ssh_key_path, pub_key_path)

    return True


def _generate_ssh_key_cryptography(private_key_path: Path, public_key_path: Path) -> bool:
    """Generate SSH key pair using cryptography library."""
    try:
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=KEY_SIZE,
            backend=default_backend()
        )

        # Get public key
        public_key = private_key.public_key()

        # Serialize private key (OpenSSH format)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Serialize public key (OpenSSH format)
        public_ssh = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )

        # Add comment to public key
        comment = _build_ssh_comment()
        public_ssh_with_comment = public_ssh.decode('utf-8') + f" {comment}\n"

        # Write private key
        private_key_path.write_bytes(private_pem)

        # Write public key
        public_key_path.write_text(public_ssh_with_comment)

        return True

    except Exception as e:
        print_error(f"Error generating SSH key: {e}")
        return False


def _build_ssh_comment() -> str:
    """Build SSH key comment string."""
    user = os.environ.get('USER', 'user')
    hostname = os.environ.get('HOSTNAME', 'localhost')
    date_str = datetime.now().strftime('%Y%m%d')
    return f"{user}@{hostname}-{date_str}"


def _set_key_permissions(private_key_path: Path, public_key_path: Path) -> None:
    """Set appropriate permissions on SSH key files."""
    try:
        private_key_path.chmod(PRIVATE_KEY_PERMS)
        public_key_path.chmod(PUBLIC_KEY_PERMS)
    except OSError as e:
        print_warning(f"Could not set key permissions: {e}")
