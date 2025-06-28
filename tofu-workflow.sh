#!/bin/bash

set -e

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Configurazione
PLAN_FILE="tfplan"
LOG_FILE="terraform_$(date +%Y%m%d_%H%M%S).log"

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${PURPLE}[DEBUG]${NC} $1"
    fi
}

# Funzione per cleanup
cleanup() {
    local exit_code=$?
    
    if [[ -f "$PLAN_FILE" ]]; then
        print_warning "Rimuovo il file di piano..."
        rm -f "$PLAN_FILE"
    fi
    
    if [[ $exit_code -ne 0 ]]; then
        print_error "Script terminato con errore (codice: $exit_code)"
        if [[ -f "$LOG_FILE" ]]; then
            print_error "Log salvato in: $LOG_FILE"
        fi
    fi
}

# Trap per cleanup in caso di errore
trap cleanup EXIT

# Funzione per mostrare l'aiuto
show_help() {
    cat << EOF
OpenTofu/Terraform Workflow Script

UTILIZZO:
    $0 [opzioni]

OPZIONI:
    --auto-approve      Non richiedere conferma prima dell'apply
    --destroy           Modalità distruzione (destroy)
    --workspace NAME    Seleziona workspace specifico
    --skip-plan         Salta la fase di pianificazione
    --debug             Abilita output di debug dettagliato
    --help, -h          Mostra questo aiuto

ESEMPI:
    $0                           # Workflow normale con conferma
    $0 --auto-approve            # Apply automatico senza conferma
    $0 --destroy                 # Distruggi tutte le risorse
    $0 --workspace staging       # Usa workspace staging
    $0 --auto-approve --debug    # Apply automatico con debug

DESCRIZIONE:
    Questo script automatizza il workflow OpenTofu/Terraform:
    1. Inizializzazione (init)
    2. Validazione (validate)
    3. Formattazione (fmt)
    4. Pianificazione (plan)
    5. Conferma utente (se non --auto-approve)
    6. Applicazione (apply)
    7. Mostra output e informazioni utili

EOF
}

# Parse argomenti
AUTO_APPROVE=true
DESTROY_MODE=false
WORKSPACE=""
SKIP_PLAN=false
DEBUG=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --auto-approve)
            AUTO_APPROVE=true
            shift
            ;;
        --destroy)
            DESTROY_MODE=true
            shift
            ;;
        --workspace)
            WORKSPACE="$2"
            shift 2
            ;;
        --skip-plan)
            SKIP_PLAN=true
            shift
            ;;
        --debug)
            DEBUG=true
            export TF_LOG=DEBUG
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            print_error "Opzione sconosciuta: $1"
            echo "Usa --help per vedere le opzioni disponibili"
            exit 1
            ;;
    esac
done

print_header "OpenTofu/Terraform WORKFLOW"
print_status "Avvio script alle $(date)"

if [[ "$DEBUG" == "true" ]]; then
    print_debug "Modalità debug attiva"
    print_debug "Auto-approve: $AUTO_APPROVE"
    print_debug "Destroy mode: $DESTROY_MODE"
    print_debug "Workspace: ${WORKSPACE:-default}"
fi

# Verifica prerequisiti
if ! command -v terraform &> /dev/null && ! command -v tofu &> /dev/null; then
    print_error "Né Terraform né OpenTofu sono installati. Installa uno dei due."
    print_status "Installazione OpenTofu: https://opentofu.org/docs/intro/install/"
    exit 1
fi

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

# Verifica che siamo in una directory con file .tf
if ! ls *.tf &>/dev/null; then
    print_error "Nessun file .tf trovato nella directory corrente"
    print_status "Assicurati di essere in una directory con file di configurazione Terraform/OpenTofu"
    exit 1
fi

print_debug "File .tf trovati: $(ls *.tf | tr '\n' ' ')"

# Seleziona workspace se specificato
if [[ -n "$WORKSPACE" ]]; then
    print_status "Gestione workspace: $WORKSPACE"
    if $TF_CMD workspace list | grep -q "^\*\?\s*$WORKSPACE$"; then
        $TF_CMD workspace select "$WORKSPACE"
        print_status "Workspace '$WORKSPACE' selezionato"
    else
        $TF_CMD workspace new "$WORKSPACE"
        print_status "Workspace '$WORKSPACE' creato e selezionato"
    fi
fi

# Mostra workspace attivo
current_workspace=$($TF_CMD workspace show 2>/dev/null || echo "default")
print_status "Workspace attivo: $current_workspace"

# Controllo di sicurezza per workspace di produzione
if [[ "$current_workspace" =~ ^(production|prod)$ ]] && [[ "$AUTO_APPROVE" == "false" ]]; then
    print_warning "⚠️  ATTENZIONE: Stai lavorando sul workspace di PRODUZIONE!"
    read -p "Sei sicuro di voler continuare? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Operazione annullata per sicurezza"
        exit 0
    fi
fi

# Inizializzazione
print_header "INIZIALIZZAZIONE"
if [[ -d ".terraform" ]]; then
    print_status "Directory .terraform esistente, eseguendo upgrade..."
    $TF_CMD init -upgrade -input=false
else
    print_status "Prima inizializzazione..."
    $TF_CMD init -input=false
fi

# Validazione
print_header "VALIDAZIONE"
$TF_CMD validate
print_status "✓ Configurazione valida"

# Formattazione
print_header "FORMATTAZIONE"
if $TF_CMD fmt -check -recursive; then
    print_status "✓ Codice già formattato correttamente"
else
    print_warning "Formattando il codice..."
    $TF_CMD fmt -recursive
    print_status "✓ Codice formattato"
fi

# Security scan opzionale (se tfsec è disponibile)
if command -v tfsec &>/dev/null; then
    print_header "SECURITY SCAN"
    if tfsec --no-color . 2>/dev/null; then
        print_status "✓ Nessun problema di sicurezza rilevato"
    else
        print_warning "Problemi di sicurezza rilevati (non bloccanti)"
    fi
fi

if [[ "$SKIP_PLAN" == "false" ]]; then
    # Pianificazione
    print_header "PIANIFICAZIONE"
    
    # Prepara il comando plan
    if [[ "$DESTROY_MODE" == "true" ]]; then
        print_warning "⚠️  MODALITÀ DISTRUZIONE ATTIVA"
        plan_cmd="$TF_CMD plan -destroy -out=$PLAN_FILE -detailed-exitcode -input=false"
    else
        plan_cmd="$TF_CMD plan -out=$PLAN_FILE -detailed-exitcode -input=false"
    fi
    
    print_debug "Eseguendo: $plan_cmd"
    
    # Esegui il plan con gestione corretta degli exit codes
    set +e  # Disabilita temporaneamente exit on error
    eval "$plan_cmd"
    PLAN_EXIT_CODE=$?
    set -e  # Riabilita exit on error
    
    print_debug "Plan exit code: $PLAN_EXIT_CODE"
    
    case $PLAN_EXIT_CODE in
        0)
            print_status "✓ Nessuna modifica necessaria"
            exit 0
            ;;
        1)
            print_error "✗ Errore durante la pianificazione"
            print_status "Suggerimenti per il debug:"
            print_status "• Controlla le credenziali cloud (AWS_*, AZURE_*, etc.)"
            print_status "• Verifica le variabili richieste"
            print_status "• Esegui: $TF_CMD plan (per vedere l'errore completo)"
            exit 1
            ;;
        2)
            if [[ "$DESTROY_MODE" == "true" ]]; then
                print_status "✓ Piano di distruzione creato"
            else
                print_status "✓ Piano creato con modifiche da applicare"
            fi
            ;;
        *)
            print_error "✗ Codice di uscita inaspettato: $PLAN_EXIT_CODE"
            exit 1
            ;;
    esac
    
    # Mostra il piano
    print_header "RIEPILOGO PIANO"
    $TF_CMD show "$PLAN_FILE"
fi

# Conferma dall'utente (solo se non auto-approve)
if [[ "$AUTO_APPROVE" == "false" ]]; then
    echo
    print_header "CONFERMA"
    
    if [[ "$DESTROY_MODE" == "true" ]]; then
        print_warning "⚠️  ATTENZIONE: Stai per DISTRUGGERE tutte le risorse!"
        print_warning "Questa operazione è IRREVERSIBILE!"
        read -p "Digita 'destroy' per confermare la distruzione: " CONFIRM
        if [[ "$CONFIRM" != "destroy" ]]; then
            print_warning "Operazione annullata dall'utente"
            exit 0
        fi
    else
        read -p "Vuoi applicare queste modifiche? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_warning "Operazione annullata dall'utente"
            exit 0
        fi
    fi
else
    if [[ "$DESTROY_MODE" == "true" ]]; then
        print_status "🤖 Auto-approve abilitato: procedendo con la DISTRUZIONE"
    else
        print_status "🤖 Auto-approve abilitato: procedendo con l'applicazione"
    fi
fi

# Applicazione
print_header "APPLICAZIONE"

if [[ "$SKIP_PLAN" == "true" ]]; then
    # Se abbiamo saltato il plan, dobbiamo applicare direttamente
    if [[ "$DESTROY_MODE" == "true" ]]; then
        if [[ "$AUTO_APPROVE" == "true" ]]; then
            $TF_CMD destroy -auto-approve -input=false
        else
            $TF_CMD destroy -input=false
        fi
    else
        if [[ "$AUTO_APPROVE" == "true" ]]; then
            $TF_CMD apply -auto-approve -input=false
        else
            $TF_CMD apply -input=false
        fi
    fi
else
    # Applica il piano che abbiamo creato
    $TF_CMD apply "$PLAN_FILE"
fi

# Messaggi finali
if [[ "$DESTROY_MODE" == "true" ]]; then
    print_status "✅ Distruzione completata con successo!"
    print_status "Tutte le risorse sono state rimosse"
else
    print_status "✅ Deployment completato con successo!"
    
    # Output utili solo se non in modalità distruzione
    print_header "INFORMAZIONI DEPLOYMENT"
    
    # Mostra tutti gli output disponibili
    if $TF_CMD output &>/dev/null; then
        $TF_CMD output
    else
        print_warning "Nessun output definito nei file di configurazione"
    fi
    
    # Informazioni specifiche VM se disponibili
    echo
    if $TF_CMD output vm_ip &>/dev/null; then
        VM_IP=$($TF_CMD output -raw vm_ip)
        print_status "🖥️  Informazioni VM:"
        echo "   IP: $VM_IP"
        echo "   SSH: ssh ubuntu@$VM_IP"
    fi
    
    if $TF_CMD output vm_public_ip &>/dev/null; then
        VM_PUBLIC_IP=$($TF_CMD output -raw vm_public_ip)
        print_status "🌐 IP Pubblico: $VM_PUBLIC_IP"
    fi
fi

print_header "COMANDI UTILI"
echo "• Stato risorse:      $TF_CMD state list"
echo "• Output completo:    $TF_CMD output"
echo "• Piano distruzione:  $TF_CMD plan -destroy"
echo "• Distruzione:        $TF_CMD destroy"
echo "• Aggiorna stato:     $TF_CMD refresh"
echo "• Lista workspace:    $TF_CMD workspace list"
echo "• Importa risorsa:    $TF_CMD import <tipo.nome> <id>"

if [[ "$DEBUG" == "true" ]]; then
    print_header "INFORMAZIONI DEBUG"
    echo "• Log file: $LOG_FILE"
    echo "• Workspace: $current_workspace"
    echo "• Tool: $TF_CMD"
    echo "• Version: $TF_VERSION"
fi

print_status "🎉 Workflow completato alle $(date)"

# Salva un riassunto nel log
{
    echo "=== WORKFLOW SUMMARY ==="
    echo "Date: $(date)"
    echo "Tool: $TF_CMD"
    echo "Workspace: $current_workspace"
    echo "Mode: $([ "$DESTROY_MODE" == "true" ] && echo "DESTROY" || echo "DEPLOY")"
    echo "Auto-approve: $AUTO_APPROVE"
    echo "Status: SUCCESS"
    echo "======================="
} >> "$LOG_FILE"