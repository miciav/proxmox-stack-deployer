#!/bin/bash

# lib/networking.sh - Funzioni per la configurazione del networking e port forwarding

# Script remoto per la configurazione del port forwarding
# Script remoto per la configurazione del port forwarding
get_remote_port_forwarding_script() {
    cat << 'EOF_REMOTE_SCRIPT'
#!/bin/bash
set -e

# Debug: stampa informazioni di avvio
echo "[DEBUG] Avvio script networking.sh" >&2
echo "[DEBUG] Parametri ricevuti: VM_IP=$1, EXTERNAL_PORT=$2, VM_NAME=$3, EXTERNAL_INTERFACE=$4, TARGET_PORT=$5" >&2

VM_IP="$1"
EXTERNAL_PORT="$2"
VM_NAME="$3"
EXTERNAL_INTERFACE="$4"
TARGET_PORT="${5:-22}" # Default a 22 se non specificato

# Verifica parametri obbligatori
if [[ -z "$VM_IP" || -z "$EXTERNAL_PORT" || -z "$VM_NAME" || -z "$EXTERNAL_INTERFACE" ]]; then
    echo "[ERROR] Parametri mancanti!" >&2
    echo "Uso: $0 <VM_IP> <EXTERNAL_PORT> <VM_NAME> <EXTERNAL_INTERFACE> [TARGET_PORT]" >&2
    exit 1
fi

echo "[DEBUG] Parametri validati con successo" >&2

# Funzione per trovare una porta esistente per questa VM e target port
find_existing_port() {
    echo "[DEBUG] Esecuzione find_existing_port per VM_IP: $VM_IP, TARGET_PORT: $TARGET_PORT" >&2
    
    if [[ ! -f "/etc/network/interfaces" ]]; then
        echo "[DEBUG] File /etc/network/interfaces non trovato" >&2
        return 1
    fi
    
    local result
    result=$(awk -v vm_ip="$VM_IP" -v target_port="$TARGET_PORT" '
        /post-up/ && /--to/ && $0 ~ vm_ip":"target_port {
            for (i=1; i<=NF; i++) {
                if ($i == "--dport") {
                    print $(i+1);
                    exit;
                }
            }
        }
    ' /etc/network/interfaces)
    
    if [[ -n "$result" ]]; then
        echo "[DEBUG] Porta esistente trovata: $result" >&2
        echo "$result"
    else
        echo "[DEBUG] Nessuna porta esistente trovata" >&2
    fi
}

echo "[DEBUG] Funzione find_existing_port definita" >&2

# Controlla se esiste già una regola per questa VM
echo "[DEBUG] Chiamata a find_existing_port..." >&2
existing_port=$(find_existing_port)
echo "[DEBUG] Risultato find_existing_port: '$existing_port'" >&2

if [[ -n "$existing_port" ]]; then
    echo "[DEBUG] Regola esistente trovata, ritorno porta: $existing_port" >&2
    # STDOUT: solo il risultato finale
    echo "$existing_port"
    exit 0
fi

echo "[DEBUG] Nessuna regola esistente, procedo con la configurazione" >&2

# Backup del file interfaces
backup_file="/etc/network/interfaces.backup.$(date +%Y%m%d_%H%M%S)"
echo "[DEBUG] Creazione backup: $backup_file" >&2
cp /etc/network/interfaces "$backup_file"

# Verifica che l'interfaccia esista nel file
if ! grep -q "^[[:space:]]*iface[[:space:]]\+$EXTERNAL_INTERFACE[[:space:]]" /etc/network/interfaces; then
    echo "[ERROR] Interfaccia $EXTERNAL_INTERFACE non trovata in /etc/network/interfaces" >&2
    exit 1
fi

# Definisci le regole da aggiungere - usa up/down invece di post-up/post-down
POST_UP="    post-up iptables -t nat -A PREROUTING -i $EXTERNAL_INTERFACE -p tcp --dport $EXTERNAL_PORT -j DNAT --to $VM_IP:$TARGET_PORT"
POST_DOWN="    post-down iptables -t nat -D PREROUTING -i $EXTERNAL_INTERFACE -p tcp --dport $EXTERNAL_PORT -j DNAT --to $VM_IP:$TARGET_PORT"

echo "[DEBUG] Regole definite:" >&2
echo "[DEBUG] POST_UP: $POST_UP" >&2
echo "[DEBUG] POST_DOWN: $POST_DOWN" >&2

# Usa un approccio più semplice e sicuro con awk
temp_file=$(mktemp)
echo "[DEBUG] File temporaneo creato: $temp_file" >&2

# Usa awk per processare il file in modo più sicuro
echo "[DEBUG] Inizio processamento con AWK" >&2
awk -v interface="$EXTERNAL_INTERFACE" \
    -v post_up="$POST_UP" \
    -v post_down="$POST_DOWN" \
    -v vm_name="$VM_NAME" \
    -v vm_ip="$VM_IP" \
    -v target_port="$TARGET_PORT" \
    -v external_port="$EXTERNAL_PORT" '
BEGIN { 
    in_target_interface = 0
    rules_added = 0
    print "[DEBUG] AWK: Cerco interfaccia: " interface > "/dev/stderr"
}

# Rileva inizio della sezione dell interfaccia target
/^[[:space:]]*iface[[:space:]]+/ {
    print "[DEBUG] AWK: Trovata riga iface: " $0 > "/dev/stderr"
    if ($2 == interface && in_target_interface == 0) {
        print "[DEBUG] AWK: Entro nella sezione " interface > "/dev/stderr"
        in_target_interface = 1
        print $0
        next
    } else if (in_target_interface == 1 && $2 != interface) {
        # Nuova interfaccia trovata, aggiungi le regole prima di questa
        if (rules_added == 0) {
            print "[DEBUG] AWK: Aggiungo regole prima della nuova interfaccia " $2 > "/dev/stderr"
            print ""
            print "    # Port forwarding per " vm_name " (" vm_ip ":" target_port " -> " external_port ")"
            print post_up
            print post_down
            rules_added = 1
        }
        in_target_interface = 0
    }
}

# Stampa tutte le altre righe
{
    print $0
}

END {
    # Se siamo ancora nell interfaccia target alla fine del file
    if (in_target_interface == 1 && rules_added == 0) {
        print "[DEBUG] AWK: Aggiungo regole alla fine del file" > "/dev/stderr"
        print ""
        print "    # Port forwarding per " vm_name " (" vm_ip ":" target_port " -> " external_port ")"
        print post_up
        print post_down
    }
    print "[DEBUG] AWK: Processamento completato, rules_added=" rules_added > "/dev/stderr"
}
' /etc/network/interfaces > "$temp_file"

echo "[DEBUG] Processamento file completato" >&2

# Verifica che il file temporaneo non sia vuoto
if [[ ! -s "$temp_file" ]]; then
    echo "[ERROR] Il file temporaneo è vuoto - possibile errore nel processamento" >&2
    rm "$temp_file"
    exit 1
fi

echo "[DEBUG] Dimensione file temporaneo: $(wc -l < "$temp_file") righe" >&2
echo "[DEBUG] Prime 10 righe del file temporaneo:" >&2
head -10 "$temp_file" >&2
echo "[DEBUG] Ultime 10 righe del file temporaneo:" >&2
tail -10 "$temp_file" >&2

# Sostituisci il file originale
echo "[DEBUG] Sostituzione file interfaces" >&2
mv "$temp_file" /etc/network/interfaces

# Verifica la sintassi del nuovo file
echo "[DEBUG] Verifica sintassi del nuovo file interfaces" >&2
echo "[DEBUG] Contenuto del nuovo file:" >&2
cat /etc/network/interfaces >&2
echo "[DEBUG] Fine contenuto file" >&2

# Verifica più permissiva - controlla solo che il file non sia malformato
if ! ifquery --list &>/dev/null; then
    echo "[ERROR] Sintassi del file interfaces non valida" >&2
    echo "[DEBUG] Ripristino backup: $backup_file" >&2
    mv "$backup_file" /etc/network/interfaces
    exit 1
fi

# Applica configurazione con ifreload - ma prima prova solo l'interfaccia specifica
echo "[DEBUG] Test ricaricamento solo interfaccia $EXTERNAL_INTERFACE" >&2
if ! ifreload "$EXTERNAL_INTERFACE"; then
    echo "[WARNING] Errore ricaricando solo $EXTERNAL_INTERFACE, provo con tutte le interfacce" >&2
    # Se fallisce, prova con tutte
    if ! sudo ifreload -a; then
        echo "[ERROR] Errore durante il ricaricamento delle interfacce" >&2
        echo "[DEBUG] Ripristino backup: $backup_file" >&2
        mv "$backup_file" /etc/network/interfaces
        # Prova a ricaricare il backup
        sudo ifreload -a || true
        exit 1
    fi
fi

echo "[DEBUG] Configurazione completata con successo" >&2
# STDOUT: solo il risultato finale
echo "$EXTERNAL_PORT"
EOF_REMOTE_SCRIPT
}

# Funzione per configurare il port forwarding sul server Proxmox remoto
setup_remote_port_forwarding() {
    local vm_ip="$1"
    local vm_name="${2:-vm1}"
    
    print_header "CONFIGURAZIONE PORT FORWARDING REMOTO"
    
    # Verifica se abbiamo le informazioni del Proxmox
    if [[ -z "$PROXMOX_HOST" ]]; then
        print_warning "IP del server Proxmox non specificato"
        print_status "Configura con: export PROXMOX_HOST=YOUR_PROXMOX_IP"
        print_status "Oppure usa: $0 --proxmox-host YOUR_PROXMOX_IP"
        print_status ""
        print_status "Per configurare manualmente il port forwarding sul server Proxmox:"
        print_status "1. Connettiti al server: ssh root@YOUR_PROXMOX_IP"
        print_status "2. Modifica /etc/network/interfaces aggiungendo:"
        print_status "   post-up iptables -t nat -A PREROUTING -i $EXTERNAL_INTERFACE -p tcp --dport PORTA_ESTERNA -j DNAT --to $vm_ip:22"
        print_status "   post-down iptables -t nat -D PREROUTING -i $EXTERNAL_INTERFACE -p tcp --dport PORTA_ESTERNA -j DNAT --to $vm_ip:22"
        print_status "3. Applica: iptables -t nat -A PREROUTING -i $EXTERNAL_INTERFACE -p tcp --dport PORTA_ESTERNA -j DNAT --to $vm_ip:22"
        return 0
    fi
    
    # Testa connessione al Proxmox
    if ! test_proxmox_connection "$PROXMOX_HOST" "$PROXMOX_USER"; then
        return 1
    fi
    
    # Trova porta libera
    print_nat "Cerco porta libera sul server Proxmox..."
    local external_port
    if ! external_port=$(find_free_port_remote "$PROXMOX_HOST" "$PROXMOX_USER" "$NAT_START_PORT"); then
        print_error "Impossibile trovare porta libera sul server Proxmox"
        return 1
    fi
    
    print_nat "Configurazione port forwarding:"
    print_nat "  Server Proxmox: $PROXMOX_HOST"
    print_nat "  VM IP: $vm_ip:22"
    print_nat "  Porta esterna: $external_port"
    print_nat "  Interface: $EXTERNAL_INTERFACE"
    
    # Genera script per la configurazione remota
    local remote_script
    remote_script=$(get_remote_port_forwarding_script)
    
    # Esegui script remoto
    print_nat "Configuro port forwarding sul server Proxmox..."
    local configured_port
    configured_port=$(ssh -i "$PROXMOX_SSH_KEY" \
           -o StrictHostKeyChecking=no \
           -o UserKnownHostsFile=/dev/null \
           -o LogLevel=ERROR \
           "$PROXMOX_USER@$PROXMOX_HOST" \
           "bash -s" "$vm_ip" "$external_port" "$vm_name" "$EXTERNAL_INTERFACE" <<< "$remote_script")
    
    if [[ -n "$configured_port" ]]; then
        print_nat "✓ Port forwarding configurato con successo"
        print_nat "✓ Connessione esterna: ssh -p $configured_port ubuntu@$PROXMOX_HOST"
        
        # Aggiorna variabili globali
        EXTERNAL_SSH_HOST="$PROXMOX_HOST"
        EXTERNAL_SSH_PORT="$configured_port"
        
        return 0
    else
        print_error "Errore nella configurazione del port forwarding"
        return 1
    fi
}

# Funzione per configurare port forwarding per multiple VM
setup_multiple_port_forwarding() {
    local vm_ips_json="$1"
    local project_name="${2:-proxmox-vms}"
    local proxmox_host="${3:-$PROXMOX_HOST}"
    local target_port="${4:-22}" # Nuovo parametro per la porta target (es. 22 per SSH, 6443 per K3s API)
    # FORZA DEBUG PER TROUBLESHOOTING (rimuovi dopo aver risolto)
    local OLD_DEBUG="$DEBUG"
    export DEBUG=true
    
    
    print_header "CONFIGURAZIONE PORT FORWARDING PER MULTIPLE VM"
    print_debug "Raw vm_ips_json in setup_multiple_port_forwarding: $vm_ips_json"
    print_debug "Project name: $project_name"
    print_debug "Proxmox host: $proxmox_host"
    print_debug "Target port: $target_port"
    
    # Verifica se abbiamo le informazioni del Proxmox
    print_debug "Verificando variabili di ambiente..."
    if [[ -z "$PROXMOX_HOST" ]]; then
        print_warning "IP del server Proxmox non specificato"
        print_status "Configura con: export PROXMOX_HOST=YOUR_PROXMOX_IP"
        return 0
    fi
    print_debug "PROXMOX_HOST: $PROXMOX_HOST"
    print_debug "PROXMOX_USER: $PROXMOX_USER"
    print_debug "NAT_START_PORT: $NAT_START_PORT"
    print_debug "EXTERNAL_INTERFACE: $EXTERNAL_INTERFACE"
    
    # Verifica che jq sia disponibile
    if ! command -v jq >/dev/null 2>&1; then
        print_error "jq non è installato. Installa jq per continuare."
        return 1
    fi
    print_debug "jq è disponibile"
    
    # Valida il JSON di input
    print_debug "Validando JSON di input..."
    if ! echo "$vm_ips_json" | jq empty 2>/dev/null; then
        print_error "JSON delle VM non valido: $vm_ips_json"
        return 1
    fi
    
    # Conta le VM nel JSON
    local vm_count
    vm_count=$(echo "$vm_ips_json" | jq 'length' 2>/dev/null)
    print_debug "Numero di VM trovate nel JSON: $vm_count"
    
    if [[ "$vm_count" -eq 0 ]]; then
        print_warning "Nessuna VM trovata nel JSON"
        return 0
    fi
    
    # Testa connessione al Proxmox
    print_debug "Testando connessione a Proxmox..."
    if ! test_proxmox_connection "$PROXMOX_HOST" "$PROXMOX_USER"; then
        print_error "Test connessione a Proxmox fallito"
        return 1
    fi
    print_debug "Connessione a Proxmox OK"
    
    local port_counter=0
    local configured_ports=""
    
    print_debug "Iniziando iterazione sulle VM..."
    
    # CORREZIONE: Usa process substitution invece di pipe per evitare subshell
    while IFS=' ' read -r vm_name vm_ip; do
        print_debug "=== Elaborando VM: $vm_name con IP: $vm_ip ==="
        print_nat "Configurando port forwarding per VM $vm_name ($vm_ip) sulla porta $target_port..."
        
        # Verifica che vm_name e vm_ip non siano vuoti
        if [[ -z "$vm_name" || -z "$vm_ip" ]]; then
            print_error "Nome VM o IP vuoto per entry: '$vm_name' '$vm_ip'"
            ((port_counter++))
            continue
        fi
        
        # Calcola porta esterna
        local external_port_to_try=$((NAT_START_PORT + port_counter))
        print_debug "Porta esterna calcolata: $external_port_to_try (NAT_START_PORT: $NAT_START_PORT + counter: $port_counter)"
        
        # Verifica che la funzione get_remote_port_forwarding_script esista
        if ! declare -f get_remote_port_forwarding_script >/dev/null; then
            print_error "Funzione get_remote_port_forwarding_script non trovata"
            return 1
        fi
        
        # Genera script per la configurazione remota
        print_debug "Generando script remoto..."
        local remote_script
        remote_script=$(get_remote_port_forwarding_script)
        
        if [[ -z "$remote_script" ]]; then
            print_error "Script remoto vuoto per VM $vm_name"
            ((port_counter++))
            continue
        fi
        
        print_debug "Script remoto generato (${#remote_script} caratteri)"
        
        # Verifica che la chiave SSH esista
        if [[ ! -f "$PROXMOX_SSH_KEY" ]]; then
            print_error "Chiave SSH non trovata: $PROXMOX_SSH_KEY"
            return 1
        fi
        
        print_debug "Eseguendo SSH su $PROXMOX_USER@$PROXMOX_HOST..."
        print_debug "Parametri SSH: vm_ip=$vm_ip, external_port=$external_port_to_try, vm_name=$vm_name, interface=$EXTERNAL_INTERFACE, target_port=$target_port"
        
        # Esegui script remoto e cattura l'output (la porta)
        local configured_port ssh_exit_code
        ssh_stderr_file=$(mktemp)
        configured_port=$(ssh -i "$PROXMOX_SSH_KEY" \
            -o StrictHostKeyChecking=no \
            -o UserKnownHostsFile=/dev/null \
            -o LogLevel=ERROR \
            -o ConnectTimeout=30 \
            -o ServerAliveInterval=10 \
            -o ServerAliveCountMax=3 \
            "$PROXMOX_USER@$PROXMOX_HOST" \
            "bash -s \"$vm_ip\" \"$external_port_to_try\" \"$vm_name\" \"$EXTERNAL_INTERFACE\" \"$target_port\"" <<<"$remote_script" 2>"$ssh_stderr_file")
        ssh_exit_code=$?

        print_debug "SSH exit code: $ssh_exit_code"
        print_debug "SSH output: '$configured_port'"
        print_debug "SSH stderr: $(cat "$ssh_stderr_file")"
        rm "$ssh_stderr_file"
        
        if [[ $ssh_exit_code -eq 0 && -n "$configured_port" ]]; then
            # Rimuovi eventuali caratteri di controllo dall'output
            configured_port=$(echo "$configured_port" | tr -d '\r\n' | grep -o '[0-9]*' | head -1)
            
            if [[ -n "$configured_port" && "$configured_port" =~ ^[0-9]+$ ]]; then
                print_nat "✓ Port forwarding per $vm_name ($vm_ip) è sulla porta $configured_port"
                echo "$vm_name:$configured_port"
                configured_ports="$configured_ports $vm_name:$configured_port"
                print_debug "Porta configurata con successo: $configured_port"
            else
                print_error "Output SSH non contiene una porta valida per $vm_name: '$configured_port'"
            fi
        else
            print_error "Errore nella configurazione del port forwarding per $vm_name"
            print_debug "SSH output completo: $configured_port"
        fi
        
        ((port_counter++))
        print_debug "Incrementato port_counter a: $port_counter"
        
    done < <(echo "$vm_ips_json" | jq -r 'to_entries[] | (.key + " " + .value)')
    
    print_debug "=== Fine iterazione VM ==="
    print_debug "Totale VM elaborate: $port_counter"
    print_debug "Porte configurate: $configured_ports"
    
    if [[ $port_counter -gt 0 ]]; then
        print_nat "Port forwarding configurato per tutte le VM raggiungibili"
        print_debug "Configurazione completata con successo"
    else
        print_warning "Nessuna VM è stata elaborata"
    fi
    
    return 0
}