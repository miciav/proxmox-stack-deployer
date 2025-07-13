#!/bin/bash

# lib/common.sh - Common functions and configuration
[[ "${BASH_SOURCE[0]}" == "${0}" ]] && {
  echo "This script is a library, it should not be run directly."
  exit 1
}

# Output colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Global configuration
PLAN_FILE="tfplan"
LOG_FILE="$PWD/logs/deployment_$(date +%Y%m%d_%H%M%S).log"
PLAYBOOK_FILE1="playbooks/configure-vms.yml"
PLAYBOOK_FILE2="playbooks/add_nat_rules.yml"
PLAYBOOK_FILE3="playbooks/k3s_install.yml"
TERRAFORM_DIR="terraform-opentofu"
SSH_KEY_PATH="$HOME/.ssh/id_rsa"

# Remote Proxmox configuration
PROXMOX_HOST="${PROXMOX_HOST:-}"
PROXMOX_USER="${PROXMOX_USER:-root}"
PROXMOX_SSH_KEY="${PROXMOX_SSH_KEY:-$SSH_KEY_PATH}"
EXTERNAL_INTERFACE="${EXTERNAL_INTERFACE:-vmbr0}"
INTERNAL_INTERFACE="${INTERNAL_INTERFACE:-vmbr1}"
NAT_START_PORT="${NAT_START_PORT:-20000}"
K3S_API_PORT="${K3S_API_PORT:-6443}"



# Output functions
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}" | tee -a "$LOG_FILE"
}

print_ansible() {
    echo -e "${CYAN}[ANSIBLE]${NC} $1" | tee -a "$LOG_FILE"
}

print_nat() {
    echo -e "${PURPLE}[NAT]${NC} $1" | tee -a "$LOG_FILE"
}

print_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${PURPLE}[DEBUG]${NC} $1" | tee -a "$LOG_FILE"
    fi
}

# Cleanup function
cleanup() {
    local exit_code=$?
    [[ -f "$PLAN_FILE" ]] && rm -f "$PLAN_FILE"
    ((exit_code)) && print_error "Script finished with an error. Log saved to: $LOG_FILE" || print_status "Script completed. Log saved to: $LOG_FILE"
}

# Function to show help
show_help() {
    echo "Usage: $0 [options]"
    echo
    echo "Integrated script for deploying VMs with Terraform/OpenTofu and Ansible"
    echo
    echo "Options:"
    echo "  --skip-plan         Skip the Terraform planning phase"
    echo "  --auto-approve      Do not ask for confirmation before applying"
    echo "  --skip-ansible      Skip Ansible configuration"
    echo "  --skip-nat          Skip port forwarding configuration"
    echo "  --workspace NAME    Select a specific Terraform workspace"
    echo "  --proxmox-host IP   IP of the Proxmox server"
    echo "  --proxmox-user USER SSH username for Proxmox (default: root)"
    echo "  --nat-port PORT     Initial port for port forwarding (default: 2000)"
    echo "  --continue-if-deployed Continue execution even if the deployment already exists"
    echo "  --help              Show this help"
    echo
    echo "Environment variables:"
    echo "  PROXMOX_HOST        IP of the Proxmox server"
    echo "  PROXMOX_USER        SSH username for connection (default: root)"
    echo "  PROXMOX_SSH_KEY     SSH key for Proxmox (default: \$SSH_KEY_PATH)"
    echo "  EXTERNAL_INTERFACE  External network interface (default: vmbr0)"
    echo "  NAT_START_PORT      Initial port for port forwarding (default: 2000)"
    echo
    echo "Examples:"
    echo "  $0 --proxmox-host 192.168.1.100"
    echo "  $0 --auto-approve --proxmox-host 192.168.1.100"
    echo "  PROXMOX_HOST=192.168.1.100 $0 --auto-approve"
}
