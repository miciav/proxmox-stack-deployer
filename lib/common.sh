#!/bin/bash

# lib/common.sh - Funzioni comuni e configurazione
[[ "${BASH_SOURCE[0]}" == "${0}" ]] && {
  echo "Questo script è una libreria, non dovrebbe essere eseguito direttamente."
  exit 1
}

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configurazione globale
PLAN_FILE="tfplan"
LOG_FILE="logs/deployment_$(date +%Y%m%d_%H%M%S).log"
INVENTORY_FILE="inventory.ini"
PLAYBOOK_FILE1="playbooks/configure-vms.yml"
PLAYBOOK_FILE2="playbooks/add_nat_rules.yml"
PLAYBOOK_FILE3="playbooks/k3s_install.yml"
SSH_KEY_PATH="$HOME/.ssh/id_rsa"
SSH_TIMEOUT=10
MAX_SSH_ATTEMPTS=12
VM_READY_WAIT=0

# Configurazione Proxmox remoto
PROXMOX_HOST="${PROXMOX_HOST:-}"
PROXMOX_USER="${PROXMOX_USER:-root}"
PROXMOX_SSH_KEY="${PROXMOX_SSH_KEY:-$SSH_KEY_PATH}"
EXTERNAL_INTERFACE="${EXTERNAL_INTERFACE:-vmbr0}"
INTERNAL_INTERFACE="${INTERNAL_INTERFACE:-vmbr1}"
NAT_START_PORT="${NAT_START_PORT:-20000}"
K3S_API_PORT="${K3S_API_PORT:-6443}"

#export DEBUG=true

# Funzioni di output
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

# Funzione per cleanup
cleanup() {
    local exit_code=$?
    [[ -f "$PLAN_FILE" ]] && rm -f "$PLAN_FILE"
    ((exit_code)) && print_error "Script terminato con errore. Log salvato in: $LOG_FILE" || print_status "Script completato. Log salvato in: $LOG_FILE"
}

# Funzione per mostrare help
show_help() {
    echo "Uso: $0 [opzioni]"
    echo
    echo "Script integrato per il deployment di VM con Terraform/OpenTofu e Ansible"
    echo
    echo "Opzioni:"
    echo "  --skip-plan         Salta la fase di pianificazione Terraform"
    echo "  --auto-approve      Non richiedere conferma per l'applicazione"
    echo "  --skip-ansible      Salta la configurazione con Ansible"
    echo "  --skip-nat          Salta la configurazione del port forwarding"
    echo "  --workspace NAME    Seleziona workspace Terraform specifico"
    echo "  --proxmox-host IP   IP del server Proxmox"
    echo "  --proxmox-user USER Username per SSH al Proxmox (default: root)"
    echo "  --nat-port PORT     Porta iniziale per port forwarding (default: 2000)"
    echo "  --continue-if-deployed Continua l'esecuzione anche se il deployment esiste già"
    echo "  --help              Mostra questo aiuto"
    echo
    echo "Variabili ambiente:"
    echo "  PROXMOX_HOST        IP del server Proxmox"
    echo "  PROXMOX_USER        Username per connessione SSH (default: root)"
    echo "  PROXMOX_SSH_KEY     Chiave SSH per Proxmox (default: \$SSH_KEY_PATH)"
    echo "  EXTERNAL_INTERFACE  Interface di rete esterna (default: vmbr0)"
    echo "  NAT_START_PORT      Porta iniziale per port forwarding (default: 2000)"
    echo
    echo "Esempi:"
    echo "  $0 --proxmox-host 192.168.1.100"
    echo "  $0 --auto-approve --proxmox-host 192.168.1.100"
    echo "  PROXMOX_HOST=192.168.1.100 $0 --auto-approve"
}