#!/bin/bash

# lib/utils.sh - Funzioni di utilità e helper

# Funzione per parsare gli argomenti da riga di comando
parse_arguments() {
    SKIP_PLAN=false
    AUTO_APPROVE=false
    SKIP_ANSIBLE=false
    SKIP_NAT=false
    FORCE_REDEPLOY=false
    CONTINUE_IF_DEPLOYED=false
    WORKSPACE=""

    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-plan)
                SKIP_PLAN=true
                shift
                ;;
            --auto-approve)
                AUTO_APPROVE=true
                shift
                ;;
            --skip-ansible)
                SKIP_ANSIBLE=true
                shift
                ;;
            --skip-nat)
                SKIP_NAT=true
                shift
                ;;
            --force-redeploy)
                FORCE_REDEPLOY=true
                shift
                ;;
            --continue-if-deployed)
                CONTINUE_IF_DEPLOYED=true
                shift
                ;;
            --workspace)
                WORKSPACE="$2"
                shift 2
                ;;
            --proxmox-host)
                PROXMOX_HOST="$2"
                shift 2
                ;;
            --proxmox-user)
                PROXMOX_USER="$2"
                shift 2
                ;;
            --nat-port)
                NAT_START_PORT="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Opzione sconosciuta: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Funzione per selezionare il workspace Terraform/OpenTofu
select_workspace() {
    local workspace="$1"
    
    if [[ -n "$workspace" ]]; then
        print_status "Selezionando workspace: $workspace"
        # Determina comando Terraform
        if command -v tofu &> /dev/null; then
            TF_CMD="tofu"
        else
            TF_CMD="terraform"
        fi
        $TF_CMD workspace select "$workspace" || $TF_CMD workspace new "$workspace"
    fi
}


# Funzione per mostrare informazioni finali
show_final_info() {
    local vm_ip="$1"
    
    # Assicurati che VM_USERNAME sia impostato
    if [[ -z "${VM_USERNAME:-}" ]]; then
        VM_USERNAME=$(get_ci_user_from_tfvars) || VM_USERNAME="user"
    fi
    
    print_header "🎉 DEPLOYMENT COMPLETATO"
    
    echo -e "${GREEN}Deployment completato con successo!${NC}"
    echo
    echo "=== INFORMAZIONI VM ==="
    echo "IP Interno: $vm_ip"
    echo "Username: $VM_USERNAME"
    echo "Chiave SSH: $SSH_KEY_PATH"
    
    if [[ -n "${EXTERNAL_SSH_HOST:-}" ]] && [[ -n "${EXTERNAL_SSH_PORT:-}" ]]; then
        echo "IP Esterno: $EXTERNAL_SSH_HOST"
        echo "Porta SSH Esterna: $EXTERNAL_SSH_PORT"
        echo "Connessione Esterna: ssh -i $SSH_KEY_PATH -p $EXTERNAL_SSH_PORT $VM_USERNAME@$EXTERNAL_SSH_HOST"
    fi
    
    echo "Connessione Diretta: ssh -i $SSH_KEY_PATH $VM_USERNAME@$vm_ip"
    echo
    echo "=== COMANDI UTILI ==="
    echo "• Stato: $TF_CMD state list"
    echo "• Output: $TF_CMD output"
    echo "• Distruggere: $TF_CMD destroy"
    echo "• Riconfigurazione: ansible-playbook -i $INVENTORY_FILE $PLAYBOOK_FILE"
    echo "• Test Ansible: ansible -i $INVENTORY_FILE vms -m ping"
    echo
    echo "=== FILE GENERATI ==="
    echo "• Log: $LOG_FILE"
    echo "• Inventory: $INVENTORY_FILE"

    # Mostra tutti gli output Terraform se disponibili
    if $TF_CMD output &>/dev/null; then
        echo
        echo "=== OUTPUT TERRAFORM ==="
        $TF_CMD output
    fi
}

# Funzione per mostrare informazioni finali di multiple VM
show_final_info_multiple() {
    local vm_summary_json="$1"
    local vm_ports_str="$2"

    print_header "🎉 DEPLOYMENT COMPLETATO - RIEPILOGO VM"
    
    # Usa VM_USERNAME se già impostato, altrimenti leggilo da tfvars
    if [[ -z "${VM_USERNAME:-}" ]]; then
        if ! VM_USERNAME=$(get_ci_user_from_tfvars); then
            VM_USERNAME="ubuntu"  # fallback
        fi
    fi
    
    echo "$vm_summary_json" | jq -r 'to_entries[] | "\(.key) \(.value.ip) \(.value.id) \(.value.node)"' | while read -r vm_name vm_ip vm_id vm_node; do
        print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_status "VM: $vm_name"
        print_status "IP: $vm_ip"
        print_status "ID: $vm_id"
        print_status "Nodo: $vm_node"
        print_status "SSH: ssh $VM_USERNAME@$vm_ip"
        
        # Se abbiamo port forwarding configurato, mostra anche quello
        if [[ -n "$vm_ports_str" ]]; then
            local port_line
            port_line=$(echo "$vm_ports_str" | grep "^${vm_name}:")
            if [[ -n "$port_line" ]]; then
                local external_port
                external_port=$(echo "$port_line" | cut -d':' -f2)
                print_status "SSH Esterno: ssh -p $external_port $VM_USERNAME@$PROXMOX_HOST"
            fi
        fi
    done
    
    print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_status "Tutte le VM sono state create e configurate con successo!"
    
    # Mostra tutti gli output Terraform se disponibili
    if command -v tofu &>/dev/null; then
        TF_CMD="tofu"
    else
        TF_CMD="terraform"
    fi
    
    if $TF_CMD output &>/dev/null; then
        echo
        print_status "=== OUTPUT TERRAFORM ==="
        $TF_CMD output
    fi
}

# Funzione per mostrare l'help
show_help() {
    cat << EOF
Utilizzo: $0 [OPZIONI]

OPZIONI:
  --skip-plan           Salta la fase di planning di Terraform
  --auto-approve        Approva automaticamente le modifiche di Terraform
  --skip-ansible        Salta la configurazione con Ansible
  --skip-nat            Salta la configurazione del port forwarding
  --force-redeploy      Forza un nuovo deployment anche se le VM esistono già
  --continue-if-deployed Continua l'esecuzione anche se il deployment esiste già
  --workspace NOME      Seleziona workspace Terraform/OpenTofu
  --proxmox-host IP     IP del server Proxmox per port forwarding
  --proxmox-user USER   Username per connettersi al server Proxmox
  --nat-port PORT       Porta iniziale per il range del port forwarding
  --help, -h            Mostra questo messaggio di aiuto

ESEMPI:
  $0                                    # Deployment completo
  $0 --skip-plan --auto-approve         # Deployment veloce senza plan
  $0 --skip-nat                         # Deployment senza port forwarding
  $0 --workspace prod                   # Deployment su workspace 'prod'
  $0 --proxmox-host 192.168.1.100       # Specifica IP Proxmox

VARIABILI D'AMBIENTE:
  PROXMOX_HOST         IP del server Proxmox
  PROXMOX_USER         Username per Proxmox (default: root)
  NAT_START_PORT       Porta iniziale per NAT (default: 2200)
  EXTERNAL_INTERFACE   Interfaccia di rete esterna (default: vmbr0)

EOF
}