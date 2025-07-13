#!/bin/bash

# lib/terraform.sh - Gestione workflow Terraform/OpenTofu

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Funzione per il workflow Terraform/OpenTofu
run_terraform_workflow() {
    print_header "WORKFLOW TERRAFORM/OPENTOFU"

    # Change to terraform directory
    cd "$TERRAFORM_DIR" || exit

    # Usa OpenTofu se disponibile, altrimenti Terraform
    if command -v tofu &> /dev/null; then
        TF_CMD="tofu"
        TF_VERSION=$(tofu version | head -n1)
        print_status "Usando OpenTofu: $TF_VERSION"
    else
        TF_CMD="terraform"
        TF_VERSION=$(terraform version | head -n1)
        print_status "Usando Terraform: $TF_VERSION"
    fi

    # Inizializzazione
    print_status "Inizializzo $TF_CMD..."
    if [[ -d ".terraform" ]]; then
        $TF_CMD init -upgrade
    else
        $TF_CMD init
    fi

    # Validazione
    print_status "Valido la configurazione..."
    $TF_CMD validate
    print_status "✓ Configurazione valida"

    # Formattazione
    print_status "Verifico formattazione..."
    if ! $TF_CMD fmt -check -recursive; then
        print_warning "Formattando il codice..."
        $TF_CMD fmt -recursive
    fi
    print_status "✓ Codice formattato correttamente"

    # Pianificazione
    if [[ "$SKIP_PLAN" != "true" ]]; then
        print_status "Pianifico il deployment..."
        $TF_CMD plan -out="$PLAN_FILE" -detailed-exitcode
        PLAN_EXIT_CODE=$?
        case $PLAN_EXIT_CODE in
            0)
                print_status "✓ Nessuna modifica necessaria"
                cd ..
                return 0
                ;;
            1)
                print_error "✗ Errore durante la pianificazione"
                cd ..
                exit 1
                ;;
            2)
                print_status "✓ Piano creato con modifiche da applicare"
                ;;
        esac

        # Mostra il piano
        print_header "RIEPILOGO PIANO"
        $TF_CMD show "$PLAN_FILE"
    fi

    # Se non ci sono modifiche da applicare, esci senza applicare
    if [[ "$PLAN_EXIT_CODE" == "0" ]]; then
        cd ..
        return 0
    fi

    # Conferma dall'utente
    if [[ "$AUTO_APPROVE" != "true" ]]; then
        echo
        read -p "Vuoi procedere con la creazione della VM? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_warning "Deployment annullato dall'utente"
            cd ..
            exit 0
        fi
    fi

    # Applicazione
    if [[ "$SKIP_PLAN" == "true" ]]; then
        print_status "Salto la fase di apply, mostro solo gli output definiti in main.tf..."
        $TF_CMD output
    else
        print_status "Creo la VM con $TF_CMD..."
        if [[ "$AUTO_APPROVE" == "true" ]]; then
            $TF_CMD apply -auto-approve "$PLAN_FILE"
        else
            $TF_CMD apply "$PLAN_FILE"
        fi
    fi

    print_status "✓ Infrastruttura creata con successo!"
    cd ..
    return 1  # Indica che sono state applicate modifiche
}

# Funzione per selezionare workspace
select_terraform_workspace() {
    local workspace="$1"

    if [[ -n "$workspace" ]]; then
        cd terraform-opentofu || exit
        print_status "Selezionando workspace: $workspace"
        # Determina comando Terraform
        if command -v tofu &> /dev/null; then
            TF_CMD="tofu"
        else
            TF_CMD="terraform"
        fi
        $TF_CMD workspace select "$workspace" || $TF_CMD workspace new "$workspace"
        cd ..
    fi
}

# Funzione per ottenere tutti gli IP delle VM dai output Terraform
get_vm_ips_from_terraform() {
    # Determina comando Terraform
    if command -v tofu &> /dev/null; then
        TF_CMD="tofu"
    else
        TF_CMD="terraform"
    fi

    cd "$TERRAFORM_DIR" || exit
    if ! VM_IPS=$($TF_CMD output -json vm_ips 2>/dev/null); then
        print_error "Impossibile ottenere gli IP delle VM dall'output Terraform"
        print_error "Assicurati che ci sia un output chiamato 'vm_ips' nella tua configurazione"
        cd ..
        return 1
    fi
    cd ..

    echo "$VM_IPS"
}

# Funzione per ottenere il summary completo delle VM
get_vm_summary_from_terraform() {
    # Determina comando Terraform
    if command -v tofu &> /dev/null; then
        TF_CMD="tofu"
    else
        TF_CMD="terraform"
    fi

    cd "$TERRAFORM_DIR" || exit
    if ! VM_SUMMARY=$($TF_CMD output -json vm_summary 2>/dev/null); then
        print_error "Impossibile ottenere il summary delle VM dall'output Terraform"
        print_error "Assicurati che ci sia un output chiamato 'vm_summary' nella tua configurazione"
        cd ..
        return 1
    fi
    cd ..

    echo "$VM_SUMMARY"
}

# Funzione per distruggere l'infrastruttura
run_terraform_destroy() {
    print_header "DESTRUCTION DE L'INFRASTRUCTURE"

    cd "$TERRAFORM_DIR" || exit

    # Determina comando Terraform
    if command -v tofu &> /dev/null; then
        TF_CMD="tofu"
    else
        TF_CMD="terraform"
    fi

    print_status "Avvio del processo di distruzione con $TF_CMD..."

    # Aggiungi --auto-approve se richiesto
    local destroy_args=""
    if [[ "$AUTO_APPROVE" == "true" ]]; then
        print_status "Modalità auto-approve ATTIVATA."
        destroy_args="--auto-approve"
    else
        print_warning "L'approvazione manuale sarà richiesta."
    fi

    # Esegui il comando di distruzione
    if ! $TF_CMD destroy $destroy_args; then
        print_error "Errore durante la distruzione dell'infrastruttura."
        cd ..
        exit 1
    fi

    print_success "Infrastruttura distrutta con successo."
    cd ..
}
