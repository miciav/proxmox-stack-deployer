#!/bin/bash

# lib/ssh.sh - Gestione chiavi SSH e connettività

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
source "$(dirname "${BASH_SOURCE[0]}")/prereq.sh"

# Funzione per gestire le chiavi SSH
setup_ssh_keys() {
    print_header "CONFIGURAZIONE SSH"
    
    if [[ ! -f "${SSH_KEY_PATH}.pub" ]]; then
        print_warning "Chiave SSH pubblica non trovata. Generandone una nuova..."
        ssh-keygen -t rsa -b 4096 -f "$SSH_KEY_PATH" -N "" -C "$(whoami)@$(hostname)-$(date +%Y%m%d)"
        print_status "✓ Nuova chiave SSH generata: ${SSH_KEY_PATH}.pub"
    else
        print_status "✓ Chiave SSH esistente trovata: ${SSH_KEY_PATH}.pub"
    fi
    
    # Verifica permessi chiave privata
    chmod 600 "$SSH_KEY_PATH" 2>/dev/null || true
    chmod 644 "${SSH_KEY_PATH}.pub" 2>/dev/null || true
}


test_proxmox_connection() {
    local proxmox_host="$1"
    local proxmox_user="$2"

    print_nat "Testo connessione SSH al server Proxmox..."
    if ssh -i "$PROXMOX_SSH_KEY" \
           -o ConnectTimeout=5 \
           -o StrictHostKeyChecking=no \
           -o UserKnownHostsFile=/dev/null \
           -o LogLevel=ERROR \
           "$proxmox_user@$proxmox_host" \
           "echo 'Connessione Proxmox OK'" 2>/dev/null; then
        print_nat "✓ Connessione al Proxmox stabilita"
        return 0
    else
        print_error "Impossibile connettersi al server Proxmox $proxmox_host"
        print_error "Verifica:"
        print_error "  1. IP del server Proxmox corretto"
        print_error "  2. Chiave SSH autorizzata sul server"
        print_error "  3. Connettività di rete"
        return 1
    fi
}
