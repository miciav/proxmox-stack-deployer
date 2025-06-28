#!/bin/bash

set -e # Interrompe lo script in caso di errore

# Importa tutte le librerie
source "$(dirname "$0")/lib/common.sh"     # Funzioni di base e output
source "$(dirname "$0")/lib/prereq.sh"    # Verifica prerequisiti
source "$(dirname "$0")/lib/ssh.sh"       # Gestione SSH
source "$(dirname "$0")/lib/terraform.sh" # Gestione Terraform/OpenTofu
source "$(dirname "$0")/lib/proxmox.sh"   # Gestione server Proxmox
source "$(dirname "$0")/lib/networking.sh" # Gestione networking e port forwarding
source "$(dirname "$0")/lib/ansible.sh"   # Gestione Ansible
source "$(dirname "$0")/lib/utils.sh"     # Funzioni di utilità

# Assicura che cleanup venga chiamata all'uscita
trap cleanup EXIT

# Funzione principale di deployment
main() {
    # Parse argomenti
    parse_arguments "$@"
    
    # Header iniziale
    print_header "🚀 DEPLOYMENT VM CON TERRAFORM/OPENTOFU E ANSIBLE"
    print_status "Avvio deployment alle $(date)"
    
        # Verifica se il deployment esiste già
    if [[ "$FORCE_REDEPLOY" != "true" ]] && [[ -f "terraform.tfstate" ]] && [[ $(jq '.resources | length' terraform.tfstate) -gt 0 ]]; then
        print_warning "Il deployment sembra essere già stato eseguito."
        if [[ "$CONTINUE_IF_DEPLOYED" != "true" ]]; then
            print_warning "Usa --force-redeploy per forzare un nuovo deployment o --continue-if-deployed per continuare."
            exit 0
        else
            print_status "Flag --continue-if-deployed rilevato, l'esecuzione continua."
        fi
    fi
    
    # Verifica prerequisiti
    check_prerequisites
    
    # Valida il file terraform.tfvars e leggi ci_user e proxmox_host
    validate_tfvars_file
    local proxmox_host="${3:-$PROXMOX_HOST}"
    
    # Setup chiavi SSH
    setup_ssh_keys
    
    # Seleziona workspace se specificato
    select_workspace "$WORKSPACE"
    
    # Esegui workflow Terraform/OpenTofu
    if run_terraform_workflow; then 
        print_status "Nessuna modifica all'infrastruttura, verifica se la VM esiste già"
    fi
    
    # Ottieni informazioni di tutte le VM
    local vm_summary
    if ! vm_summary=$(get_vm_summary_from_terraform); then
        exit 1
    fi
    
    print_status "Informazioni VM ottenute:"
    echo "$vm_summary" | jq .
    
    # Ottieni array di IP delle VM
    local vm_ips
    if ! vm_ips=$(get_vm_ips_from_terraform); then
        print_error "Failed to get VM IPs from Terraform output."
        exit 1
    fi
    
    print_status "IP delle VM: $(echo "$vm_ips" | jq -r 'values | join(", ")')"
    
    # Configura port forwarding per tutte le VM se richiesto
    local vm_ports_str=""
    if [[ "$SKIP_NAT" != "true" ]]; then
        print_status "Configurazione del port forwarding per le VM..."
        vm_ports_str=$(setup_multiple_port_forwarding "$vm_ips" "$(basename "$(pwd)")" "$proxmox_host")
    fi
    print_status "Port forwarding configurato: $vm_ports_str"
    
    # Verifica connettività SSH per tutte le VM
    local failed_vms=()
    local successful_vms=()
    
    echo "$vm_ips" | jq -r 'to_entries[] | .key + " " + .value' | while read -r vm_name vm_ip; do
        print_status "Verificando connettività SSH per VM $vm_name \($vm_ip\)..."
        
        local ssh_port=22
        if [[ -n "$vm_ports_str" ]]; then
            local port_line
            port_line=$(echo "$vm_ports_str" | grep "^${vm_name}:")
            if [[ -n "$port_line" ]]; then
                ssh_port=$(echo "$port_line" | cut -d':' -f2)
            fi
        fi
        
        if wait_for_ssh "$vm_ip" "$vm_name" "$ssh_port"; then
            successful_vms+=("$vm_name:$vm_ip")
            print_status "✓ SSH OK per $vm_name \($vm_ip\) sulla porta $ssh_port"
        else
            failed_vms+=("$vm_name:$vm_ip")
            print_warning "✗ SSH fallito per $vm_name \($vm_ip\) sulla porta $ssh_port"
        fi
    done
    
    # Verifica se ci sono VM con problemi SSH
    if [[ ${#failed_vms[@]} -gt 0 ]]; then
        print_error "Connessione SSH fallita per ${#failed_vms[@]} VM\(s\):"
        for vm_info in "${failed_vms[@]}"; do
            print_error "  - ${vm_info/:/ \(}\)"
        done
        print_error "Verifica:"
        print_error "  1. Le VM sono effettivamente in esecuzione"
        print_error "  2. Il security group permette SSH \(porta 22\)"
        print_error "  3. La chiave SSH è configurata correttamente"
        print_error "  4. L'username in terraform.tfvars (ci_user) è corretto"
        if [[ "$SKIP_NAT" != "true" ]]; then
            print_error "  5. Le regole iptables per il port forwarding sul Proxmox"
            print_error "  6. La connettività tra client e server Proxmox"
        fi
        
        # Non uscire completamente, procedi con le VM funzionanti
        if [[ ${#successful_vms[@]} -eq 0 ]]; then
            print_error "Nessuna VM raggiungibile via SSH"
            exit 1
        else
            print_warning "Procedendo con le ${#successful_vms[@]} VM raggiungibili"
        fi
    fi
    
    print_status "test test"
    if [[ "${SKIP_ANSIBLE:-false}" != "true" ]]; then
        print_status "Avvio configurazione Ansible per ${#vm_ips[@]} VM..."
        
        if ! run_ansible_configuration_multiple "$vm_ips" "$vm_ports_str"; then
            print_error "Configurazione Ansible fallita per alcune VM"
            print_info "Infrastruttura creata con successo, solo la configurazione necessita intervento manuale"
            print_info "Comandi per la configurazione manuale:"
            print_info "  cd $(dirname $INVENTORY_FILE)"
            print_info "  ansible-playbook -i $INVENTORY_FILE $PLAYBOOK_FILE -v"
            
            # Opzionale: esportare le variabili per uso successivo
            export FAILED_ANSIBLE_INVENTORY="$INVENTORY_FILE"
            export FAILED_ANSIBLE_PLAYBOOK="$PLAYBOOK_FILE"
        else
            print_success "Configurazione Ansible completata con successo"
        fi
    else
        print_status "Configurazione Ansible saltata (SKIP_ANSIBLE=true)"
        print_info "Le VM sono state create ma non configurate"
    fi
    
    # Mostra informazioni finali per tutte le VM
    show_final_info_multiple "$vm_summary" "$vm_ports_str"
    
    print_status "Deployment completato alle $(date)"
}

# Esegui main se script chiamato direttamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
