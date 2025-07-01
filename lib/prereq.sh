#!/bin/bash

# lib/prerequisites.sh - Verifica prerequisiti e validazione

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Funzione per verificare prerequisiti
check_prerequisites() {
    print_header "VERIFICA PREREQUISITI"
    
    if command -v tofu &> /dev/null; then
        export TERRAFORM_COMMAND="tofu"
    else
        export TERRAFORM_COMMAND="terraform"
    fi
    print_status "✓ Usando $TERRAFORM_COMMAND"
    
    # Verifica Ansible
    if ! command -v ansible &> /dev/null; then
        print_error "Ansible non è installato. Installalo prima di continuare."
        print_status "Suggerimento: pip install ansible"
        exit 1
    fi
    
    # Verifica ansible-playbook
    if ! command -v ansible-playbook &> /dev/null; then
        print_error "ansible-playbook non è disponibile."
        exit 1
    fi
    
    # Verifica file Terraform
    if ! ls *.tf &>/dev/null; then
        print_error "Nessun file .tf trovato nella directory corrente"
        exit 1
    fi
    
    # Verifica playbook Ansible
    if [[ ! -f "$PLAYBOOK_FILE1" ]]; then
        print_warning "Playbook Ansible '$PLAYBOOK_FILE1' non trovato"
        print_status "Lo script continuerà senza configurazione Ansible"
        SKIP_ANSIBLE=true
    fi
        # Verifica playbook Ansible
    if [[ ! -f "$PLAYBOOK_FILE2" ]]; then
        print_warning "Playbook Ansible '$PLAYBOOK_FILE2' non trovato"
        print_status "Lo script continuerà senza configurazione Ansible"
        SKIP_ANSIBLE=true
    fi
        # Verifica playbook Ansible
    if [[ ! -f "$PLAYBOOK_FILE3" ]]; then
        print_warning "Playbook Ansible '$PLAYBOOK_FILE3' non trovato"
        print_status "Lo script continuerà senza configurazione Ansible"
        SKIP_ANSIBLE=true
    fi
    
    print_status "✓ Tutti i prerequisiti sono soddisfatti"
}
# Funzione per leggere proxmox_host da terraform.tfvars
get_proxmox_host_from_tfvars() {
    local tfvars_file="terraform.tfvars"
    local hostname=""
    
    print_debug "Cerco proxmox_host in $tfvars_file..." >&2
    
    if [[ ! -f "$tfvars_file" ]]; then
        print_error "File $tfvars_file non trovato nella directory corrente" >&2
        return 1
    fi

    # Estrai proxmox_host ignorando commenti e spazi
    hostname=$(awk -F '=' '
        /^[[:space:]]*proxmox_host[[:space:]]*=/ {
            gsub(/#.*$/, "", $2);          # Rimuove commenti
            gsub(/^[[:space:]]+/, "", $2); # Trim iniziale
            gsub(/[[:space:]]+$/, "", $2); # Trim finale
            gsub(/^["'\'']|["'\'']$/, "", $2); # Rimuove virgolette
            print $2;
            exit;
        }
    ' "$tfvars_file")

    if [[ -n "$hostname" ]]; then
        print_status "✓ Hostname proxmox_host trovato in $tfvars_file: $hostname" >&2
        echo "$hostname"
        return 0
    else
        print_error "Variabile proxmox_host non trovata in $tfvars_file" >&2
        print_status "Assicurati che il file contenga una riga come: proxmox_host = \"192.168.1.100\"" >&2
        return 1
    fi
}

# Funzione per leggere ci_user da terraform.tfvars
get_ci_user_from_tfvars() {
    local tfvars_file="terraform.tfvars"
    local username=""
    
    print_debug "Cerco ci_user in $tfvars_file..." >&2
    
    if [[ ! -f "$tfvars_file" ]]; then
        print_error "File $tfvars_file non trovato nella directory corrente" >&2
        return 1
    fi

    # Estrai ci_user ignorando commenti e spazi
    username=$(awk -F '=' '
        /^[[:space:]]*ci_user[[:space:]]*=/ {
            gsub(/#.*$/, "", $2);          # Rimuove commenti
            gsub(/^[[:space:]]+/, "", $2); # Trim iniziale
            gsub(/[[:space:]]+$/, "", $2); # Trim finale
            gsub(/^["'\'']|["'\'']$/, "", $2); # Rimuove virgolette
            print $2;
            exit;
        }
    ' "$tfvars_file")

    if [[ -n "$username" ]]; then
        print_status "✓ Username ci_user trovato in $tfvars_file: $username" >&2
        echo "$username"
        return 0
    else
        print_error "Variabile ci_user non trovata in $tfvars_file" >&2
        print_status "Assicurati che il file contenga una riga come: ci_user = \"nomeutente\"" >&2
        return 1
    fi
}

# Funzione per validare terraform.tfvars
validate_tfvars_file() {
    local tfvars_file="terraform.tfvars" # dichiara il nome del file tfvars
    
    # FORZA DEBUG PER TROUBLESHOOTING (rimuovi dopo aver risolto)
    local OLD_DEBUG="$DEBUG"
    export DEBUG=true
    
    print_header "VALIDAZIONE FILE TERRAFORM.TFVARS"
    print_debug "Iniziando validazione del file: $tfvars_file"
    print_debug "Directory corrente: $(pwd)"
    
    # Verifica esistenza file
    print_debug "Verificando esistenza del file..."
    if [[ ! -f "$tfvars_file" ]]; then # controlla se il file non esiste
        print_error "File $tfvars_file non trovato!"
        print_debug "File cercato nel percorso: $(pwd)/$tfvars_file"
        print_debug "File presenti nella directory: $(ls -la | head -10)"
        print_status "Crea il file con contenuto simile a:"
        print_status "ci_user = \"nomeutente\""
        print_status "proxmox_host = \"192.168.1.100\""
        
        # RIPRISTINA DEBUG ORIGINALE
        export DEBUG="$OLD_DEBUG"
        return 1
    fi
    
    print_debug "✓ File $tfvars_file trovato"
    print_debug "Dimensione file: $(stat -c%s "$tfvars_file" 2>/dev/null || echo "N/A") bytes"
    print_debug "Contenuto del file:"
    print_debug "=== INIZIO CONTENUTO ==="
    while IFS= read -r line; do
        print_debug "$line"
    done < "$tfvars_file"
    print_debug "=== FINE CONTENUTO ==="
    
    # Validazione ci_user
    print_debug "Verificando presenza variabile ci_user..."
    if ! grep -q "ci_user" "$tfvars_file"; then # verifica se la variabile ci_user è non presente
        print_error "Variabile ci_user non trovata in $tfvars_file"
        print_debug "Ricerca esatta per 'ci_user': $(grep -n "ci_user" "$tfvars_file" || echo "nessun risultato")"
        print_status "Aggiungi una riga come: ci_user = \"nomeutente\""
        
        # RIPRISTINA DEBUG ORIGINALE
        export DEBUG="$OLD_DEBUG"
        return 1
    fi
    
    print_debug "✓ Variabile ci_user trovata"
    print_debug "Riga ci_user: $(grep -n "ci_user" "$tfvars_file")"
    
    # Validazione proxmox_host
    print_debug "Verificando presenza variabile proxmox_host..."
    if ! grep -q "proxmox_host" "$tfvars_file"; then # verifica se la variabile proxmox_host è non presente
        print_error "Variabile proxmox_host non trovata in $tfvars_file"
        print_debug "Ricerca esatta per 'proxmox_host': $(grep -n "proxmox_host" "$tfvars_file" || echo "nessun risultato")"
        print_status "Aggiungi una riga come: proxmox_host = \"192.168.1.100\""
        
        # RIPRISTINA DEBUG ORIGINALE
        export DEBUG="$OLD_DEBUG"
        return 1
    fi
    
    print_debug "✓ Variabile proxmox_host trovata"
    print_debug "Riga proxmox_host: $(grep -n "proxmox_host" "$tfvars_file")"
    
    # Verifica che le funzioni helper esistano
    print_debug "Verificando esistenza funzioni helper..."
    if ! declare -f get_ci_user_from_tfvars >/dev/null; then
        print_error "Funzione get_ci_user_from_tfvars non trovata"
        print_debug "Funzioni disponibili che contengono 'tfvars': $(declare -F | grep tfvars || echo "nessuna")"
        
        # RIPRISTINA DEBUG ORIGINALE
        export DEBUG="$OLD_DEBUG"
        return 1
    fi
    print_debug "✓ Funzione get_ci_user_from_tfvars trovata"
    
    if ! declare -f get_proxmox_host_from_tfvars >/dev/null; then
        print_error "Funzione get_proxmox_host_from_tfvars non trovata"
        print_debug "Funzioni disponibili che contengono 'tfvars': $(declare -F | grep tfvars || echo "nessuna")"
        
        # RIPRISTINA DEBUG ORIGINALE
        export DEBUG="$OLD_DEBUG"
        return 1
    fi
    print_debug "✓ Funzione get_proxmox_host_from_tfvars trovata"
    
    # Test lettura ci_user - ESPORTA COME VARIABILE GLOBALE
    print_debug "Testando lettura ci_user..."
    if CI_USER=$(get_ci_user_from_tfvars); then
        print_status "✓ Username configurato: $CI_USER"
        print_debug "Username estratto con successo: '$CI_USER'"
        export CI_USER  # Esporta per renderla disponibile globalmente
        print_debug "CI_USER esportato: $CI_USER"
        
        # Validazione formato username
        if [[ -z "$CI_USER" ]]; then
            print_warning "Username estratto è vuoto"
        elif [[ "$CI_USER" =~ ^[a-zA-Z0-9_-]+$ ]]; then
            print_debug "✓ Formato username valido"
        else
            print_warning "Username contiene caratteri speciali: '$CI_USER'"
        fi
    else
        print_error "Errore nella lettura del ci_user"
        print_debug "Output di get_ci_user_from_tfvars: '$CI_USER'"
        
        # RIPRISTINA DEBUG ORIGINALE
        export DEBUG="$OLD_DEBUG"
        return 1
    fi
    
    # Test lettura proxmox_host - ESPORTA COME VARIABILE GLOBALE
    print_debug "Testando lettura proxmox_host..."
    if PROXMOX_HOST=$(get_proxmox_host_from_tfvars); then
        print_status "✓ Host Proxmox configurato: $PROXMOX_HOST"
        print_debug "Host Proxmox estratto con successo: '$PROXMOX_HOST'"
        export PROXMOX_HOST  # Esporta per renderla disponibile globalmente
        print_debug "PROXMOX_HOST esportato: $PROXMOX_HOST"
        
        # Validazione formato IP/hostname
        if [[ -z "$PROXMOX_HOST" ]]; then
            print_warning "Host Proxmox estratto è vuoto"
        elif [[ "$PROXMOX_HOST" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            print_debug "✓ Formato IP valido"
            # Validazione range IP (opzionale)
            IFS='.' read -ra ADDR <<< "$PROXMOX_HOST"
            for i in "${ADDR[@]}"; do
                if [[ $i -gt 255 ]]; then
                    print_warning "IP non valido: $PROXMOX_HOST (ottetto $i > 255)"
                    break
                fi
            done
        elif [[ "$PROXMOX_HOST" =~ ^[a-zA-Z0-9.-]+$ ]]; then
            print_debug "✓ Formato hostname valido"
        else
            print_warning "Host contiene caratteri non validi: '$PROXMOX_HOST'"
        fi
    else
        print_error "Errore nella lettura del proxmox_host"
        print_debug "Output di get_proxmox_host_from_tfvars: '$PROXMOX_HOST'"
        
        # RIPRISTINA DEBUG ORIGINALE
        export DEBUG="$OLD_DEBUG"
        return 1
    fi
    
    # Validazioni aggiuntive del contenuto
    print_debug "Eseguendo validazioni aggiuntive..."
    
    # Controlla sintassi base HCL
    if grep -E '^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=.*[^"]$' "$tfvars_file" | grep -v '^\s*#'; then
        print_warning "Possibili valori non quotati trovati nel file tfvars"
        print_debug "Righe sospette: $(grep -E '^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=.*[^"]$' "$tfvars_file" | grep -v '^\s*#')"
    fi
    
    # Controlla righe vuote o solo spazi
    local empty_lines
    empty_lines=$(grep -c '^[[:space:]]*$' "$tfvars_file" 2>/dev/null || echo "0")
    print_debug "Righe vuote nel file: $empty_lines"
    
    # Controlla commenti
    local comment_lines
    comment_lines=$(grep -c '^\s*#' "$tfvars_file" 2>/dev/null || echo "0")
    print_debug "Righe di commento nel file: $comment_lines"
    
    print_status "✓ File $tfvars_file valido"
    print_debug "Validazione completata con successo"
    
    # Debug finale delle variabili esportate
    print_debug "=== VARIABILI ESPORTATE ==="
    print_debug "CI_USER: '$CI_USER'"
    print_debug "PROXMOX_HOST: '$PROXMOX_HOST'"
    print_debug "=========================="
    
    # RIPRISTINA DEBUG ORIGINALE
    export DEBUG="$OLD_DEBUG"
    
    return 0
}

# FUNZIONE HELPER PER OTTENERE LE VARIABILI DOPO LA VALIDAZIONE
get_validated_vars() {
    print_debug "=== VARIABILI DISPONIBILI DOPO VALIDAZIONE ==="
    print_debug "CI_USER: '${CI_USER:-NON_DEFINITA}'"
    print_debug "PROXMOX_HOST: '${PROXMOX_HOST:-NON_DEFINITA}'"
    print_debug "PROXMOX_USER: '${PROXMOX_USER:-NON_DEFINITA}'"
    print_debug "=============================================="
    
    # Verifica che le variabili siano state impostate
    if [[ -z "$CI_USER" ]]; then
        print_error "CI_USER non è definita dopo la validazione"
        return 1
    fi
    
    if [[ -z "$PROXMOX_HOST" ]]; then
        print_error "PROXMOX_HOST non è definita dopo la validazione"
        return 1
    fi
    
    # Imposta PROXMOX_USER se non è già definito (usando CI_USER come fallback)
    if [[ -z "$PROXMOX_USER" ]]; then
        export PROXMOX_USER="$CI_USER"
        print_debug "PROXMOX_USER impostato automaticamente a: $PROXMOX_USER"
    fi
    
    return 0
}