#!/bin/bash

# lib/proxmox.sh - Funzioni per la gestione del server Proxmox

# Funzione per testare connessione SSH al server Proxmox
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

# Funzione per trovare una porta libera sul server Proxmox
find_free_port_remote() {
    ssh -i "$PROXMOX_SSH_KEY" \
        -o ConnectTimeout=5 \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        "$PROXMOX_USER@$PROXMOX_HOST" "
        for port in \$(seq $NAT_START_PORT 65535); do
            # Considera solo regole non commentate
            grep -E '^[[:space:]]*[^#][^\n]*--dport[[:space:]]+\$port' /etc/network/interfaces &>/dev/null && continue
            ss -tuln | grep -q \":\$port \" && continue
            echo \$port
            break
        done"
}