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

# Funzione per il parsing degli argomenti
parse_arguments() {
    # Inizializza variabili globali con valori di default
    FORCE_REDEPLOY="false"
    CONTINUE_IF_DEPLOYED="false"
    SKIP_NAT="false"
    SKIP_ANSIBLE="false"
    WORKSPACE=""
    AUTO_APPROVE="false"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force-redeploy)
                FORCE_REDEPLOY="true"
                shift
                ;;
            --continue-if-deployed)
                CONTINUE_IF_DEPLOYED="true"
                shift
                ;;
            --skip-nat)
                SKIP_NAT="true"
                shift
                ;;
            --skip-ansible)
                SKIP_ANSIBLE="true"
                shift
                ;;
            --workspace)
                WORKSPACE="$2"
                shift 2
                ;;
            --auto-approve)
                AUTO_APPROVE="true"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "Argomento sconosciuto: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Esporta le variabili per renderle disponibili agli altri script
    export FORCE_REDEPLOY CONTINUE_IF_DEPLOYED SKIP_NAT SKIP_ANSIBLE WORKSPACE AUTO_APPROVE
}

# Funzione per mostrare l'help
show_help() {
    cat << EOF
Uso: $0 [OPZIONI]

OPZIONI:
    --force-redeploy        Forza un nuovo deployment anche se esiste già
    --continue-if-deployed  Continua l'esecuzione anche se il deployment esiste già
    --skip-nat             Salta la configurazione delle regole NAT
    --skip-ansible         Salta la configurazione Ansible
    --workspace NOME       Seleziona un workspace Terraform specifico
    --auto-approve         Approva automaticamente le modifiche Terraform
    -h, --help             Mostra questo help

ESEMPI:
    $0 --auto-approve --continue-if-deployed
    $0 --force-redeploy --skip-nat
    $0 --workspace production --auto-approve

EOF
}

# Funzione per selezionare il workspace Terraform/OpenTofu
select_workspace() {
    local workspace_name="$1"
    
    # Se non è specificato un workspace, usa il default
    if [[ -z "$workspace_name" ]]; then
        print_status "Nessun workspace specificato, uso workspace default"
        return 0
    fi
    
    # Determina quale comando usare (terraform o tofu)
    local terraform_cmd
    if command -v tofu >/dev/null 2>&1; then
        terraform_cmd="tofu"
    elif command -v terraform >/dev/null 2>&1; then
        terraform_cmd="terraform"
    else
        print_error "Né terraform né tofu sono installati"
        return 1
    fi
    
    # Esporta il comando per uso globale
    export TERRAFORM_COMMAND="$terraform_cmd"
    
    print_status "Selezionando workspace: $workspace_name"
    
    # Lista i workspace esistenti
    local existing_workspaces
    existing_workspaces=$($terraform_cmd workspace list 2>/dev/null)
    
    # Controlla se il workspace esiste già
    if echo "$existing_workspaces" | grep -q "^[* ]*$workspace_name$"; then
        print_status "Workspace '$workspace_name' trovato, selezionandolo..."
        if $terraform_cmd workspace select "$workspace_name"; then
            print_success "✓ Workspace '$workspace_name' selezionato"
        else
            print_error "Errore nella selezione del workspace '$workspace_name'"
            return 1
        fi
    else
        print_status "Workspace '$workspace_name' non esiste, creandolo..."
        if $terraform_cmd workspace new "$workspace_name"; then
            print_success "✓ Workspace '$workspace_name' creato e selezionato"
        else
            print_error "Errore nella creazione del workspace '$workspace_name'"
            return 1
        fi
    fi
    
    # Verifica il workspace corrente
    local current_workspace
    current_workspace=$($terraform_cmd workspace show)
    if [[ "$current_workspace" == "$workspace_name" ]]; then
        print_success "✓ Workspace attivo: $current_workspace"
        return 0
    else
        print_error "✗ Errore: workspace attivo ($current_workspace) non corrisponde a quello richiesto ($workspace_name)"
        return 1
    fi
}



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
#    local proxmox_host="${3:-$PROXMOX_HOST}"
    
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
 

    # Configura le regole NAT usando Ansible
    if [[ "$SKIP_NAT" != "true" ]]; then
        if [[ "${SKIP_ANSIBLE:-false}" != "true" ]]; then    
            print_status "Configurazione delle regole NAT per SSH e K3s API tramite Ansible..."
            NAT_INVENTORY_FILE="./inventories/inventory-nat-rules.ini"
            NAT_PLAYBOOK_FILE="./playbooks/add_nat_rules.yml"
    #        TERRAFORM_OUTPUT_JSON=$(get_output_in_json)
    #        print_debug "$TERRAFORM_OUTPUT_JSON"
    #        generate_nat_rules_inventory "$NAT_INVENTORY_FILE" "$TERRAFORM_OUTPUT_JSON"
            ansible-playbook -i "$NAT_INVENTORY_FILE" "$NAT_PLAYBOOK_FILE"
            echo "$ANSIBLE_OUTPUT" # Print the full output for debugging
            print_success "Regole NAT configurate con successo"
        fi
    fi
    

    if [[ "${SKIP_ANSIBLE:-false}" != "true" ]]; then
        print_status "Avvio configurazione Ansible per ${#vm_ips[@]} VM..."
        UPDATE_INVENTORY_FILE="./inventories/inventory_updates.ini"
        UPDATE_PLAYBOOK_FILE="./playbooks/configure-vms.yml"
        if ! ansible-playbook -i "$UPDATE_INVENTORY_FILE" "$UPDATE_PLAYBOOK_FILE"; then
            print_error "Configurazione Ansible fallita per alcune VM"
            
            # Opzionale: esportare le variabili per uso successivo
            export FAILED_ANSIBLE_INVENTORY="$UPDATE_INVENTORY_FILE"
            export FAILED_ANSIBLE_PLAYBOOK="$PLAYBOOK_FILE"
        else
            print_success "Configurazione Ansible completata con successo"
            # Esegui il playbook K3s
            print_status "Esecuzione playbook K3s..."
            K3S_PLAYBOOK_FILE="./playbooks/k3s_install.yml"
            if ! ansible-playbook -i "$UPDATE_INVENTORY_FILE" "$K3S_PLAYBOOK_FILE"; then
                print_error "Errore nell'esecuzione del playbook K3s"
                return 1
            fi
            print_success "✓ Playbook K3s completato con successo"
        fi
    else
        print_status "Configurazione Ansible saltata (SKIP_ANSIBLE=true)"
    fi
    
    print_status "Deployment completato alle $(date)"
}

# Esegui main se script chiamato direttamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi