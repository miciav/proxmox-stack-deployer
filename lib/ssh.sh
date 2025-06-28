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

# Funzione per testare SSH con debug dettagliato
test_ssh_connection() {
    local host="$1"
    local port="$2"
    local username="$3"
    local ssh_key="$4"
    
    print_debug "Test SSH: $username@$host:$port con chiave $ssh_key"
    
    # Test di base con timeout più lungo e debug
    ssh -i "$ssh_key" \
        -o ConnectTimeout=30 \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o LogLevel=ERROR \
        -o BatchMode=yes \
        -o PasswordAuthentication=no \
        -o PubkeyAuthentication=yes \
        -p "$port" \
        "$username@$host" \
        "echo 'SSH connection successful'" 2>/dev/null
}

# Funzione per attendere connettività SSH
wait_for_ssh() {
    local vm_ip="$1"
    local vm_name="$2"
    local ssh_port="${3:-22}"
    
    
    print_header "VERIFICA CONNETTIVITÀ SSH PER $vm_name"
    
    # Leggi username da terraform.tfvars
    if ! VM_USERNAME=$(get_ci_user_from_tfvars); then
        print_error "Impossibile ottenere l'username da terraform.tfvars"
        exit 1
    fi
    
    print_status "Attendo che la VM sia pronta (${VM_READY_WAIT}s)..."
    sleep "$VM_READY_WAIT"
    
    # Determina come connettersi
    local ssh_host="$vm_ip"
    local connection_type="diretta"
    
    if [[ -n "${PROXMOX_HOST:-}" ]]; then # Se è configurato un host SSH esterno
        ssh_host="$PROXMOX_HOST"
        connection_type="port forwarding"
    fi
    
    print_status "Verifico connettività SSH via $connection_type:"
    print_status "  Host: $ssh_host"
    print_status "  Porta: $ssh_port"
    print_status "  Username: $VM_USERNAME"
    print_status "  Chiave SSH: $SSH_KEY_PATH"
    
    # Verifica che la chiave SSH esista e abbia i permessi corretti
    if [[ ! -f "$SSH_KEY_PATH" ]]; then
        print_error "Chiave SSH privata non trovata: $SSH_KEY_PATH"
        return 1
    fi
    
    if [[ ! -r "$SSH_KEY_PATH" ]]; then
        print_error "Chiave SSH non leggibile: $SSH_KEY_PATH"
        return 1
    fi
    
    local attempt=1
    
    while [[ $attempt -le $MAX_SSH_ATTEMPTS ]]; do
        print_status "Tentativo $attempt/$MAX_SSH_ATTEMPTS - Test SSH..."
        
        if test_ssh_connection "$ssh_host" "$ssh_port" "$VM_USERNAME" "$SSH_KEY_PATH"; then
            print_status "✓ Connessione SSH stabilita con successo!"
            print_status "✓ Host: $ssh_host:$ssh_port"
            print_status "✓ Username: $VM_USERNAME"
            return 0
        else
            print_warning "SSH non ancora disponibile, attendo 15 secondi..."
            print_debug "Comando SSH fallito: ssh -i $SSH_KEY_PATH -p $ssh_port $VM_USERNAME@$ssh_host"
            
            # Test di connettività di base
            if [[ $attempt -eq 1 ]]; then
                print_debug "Test connettività di rete..."
                if ping -c 1 -W 5 "$ssh_host" &>/dev/null; then
                    print_debug "✓ Host $ssh_host raggiungibile via ping"
                else
                    print_warning "✗ Host $ssh_host non risponde al ping"
                fi
                
                # Test porta SSH
                if nc -z -w5 "$ssh_host" "$ssh_port" 2>/dev/null; then
                    print_debug "✓ Porta SSH $ssh_port aperta su $ssh_host"
                else
                    print_warning "✗ Porta SSH $ssh_port non risponde su $ssh_host"
                fi
            fi
            
            sleep 15
            ((attempt++))
        fi
    done
    
    print_error "Impossibile stabilire connessione SSH dopo $MAX_SSH_ATTEMPTS tentativi"
    print_error ""
    print_error "Configurazione utilizzata:"
    print_error "  Host: $ssh_host"
    print_error "  Porta: $ssh_port"
    print_error "  Username: $VM_USERNAME (da terraform.tfvars)"
    print_error "  Chiave SSH: $SSH_KEY_PATH"
    print_error ""
    print_error "Verifica manualmente con:"
    print_error "  ssh -i $SSH_KEY_PATH -p $ssh_port $VM_USERNAME@$ssh_host"
    print_error ""
    print_error "Possibili cause:"
    print_error "  1. La VM non è completamente avviata"
    print_error "  2. Il servizio SSH non è in esecuzione"
    print_error "  3. La chiave SSH pubblica non è installata nella VM"
    print_error "  4. Il security group/firewall blocca la porta SSH"
    print_error "  5. Username errato in terraform.tfvars"
    if [[ "$connection_type" == "port forwarding" ]]; then
        print_error "  6. Regole iptables non configurate correttamente sul Proxmox"
        print_error "  7. Problemi di connettività con il server Proxmox"
    fi
    
    return 1
}