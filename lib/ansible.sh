#!/bin/bash

# lib/ansible.sh - Funzioni per la gestione di Ansible

# Funzione per generare inventory Ansible
# Accetta una lista di stringhe "nome_vm:ip_vm:porta_vm"
generate_ansible_inventory() {
    local inventory_file="$INVENTORY_FILE"

    print_ansible "Generazione dell'inventory Ansible..."

    # Inizia il file di inventory
    cat > "$inventory_file" << EOF
[vms]
EOF

    # Usa VM_USERNAME se già impostato, altrimenti leggilo da tfvars
    if [[ -z "${VM_USERNAME:-}" ]]; then
        if ! VM_USERNAME=$(get_ci_user_from_tfvars); then
            print_error "Impossibile ottenere l'username da terraform.tfvars"
            return 1
        fi
    fi

    local ssh_common_args="'-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'"
    # Se abbiamo configurato il port forwarding, usa quello per Ansible
    if [[ -n "${EXTERNAL_SSH_HOST:-}" ]] && [[ -n "${EXTERNAL_SSH_PORT:-}" ]]; then
        ssh_common_args="'-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p $EXTERNAL_SSH_PORT'"
    fi

    # Leggi ogni VM dallo standard input
    while IFS=':' read -r vm_name vm_ip vm_port vm_k3s_api_port; do
        local ansible_host="$vm_ip"
        local ansible_port="$vm_port"

        # Se il NAT è attivo (SKIP_NAT non è true), usa PROXMOX_HOST come ansible_host
        if [[ "$SKIP_NAT" != "true" ]] && [[ -n "${PROXMOX_HOST:-}" ]]; then
            ansible_host="$PROXMOX_HOST"
        fi

        local k3s_api_port_external_entry=""
        if [[ -n "$vm_k3s_api_port" ]]; then
            k3s_api_port_external_entry="k3s_api_port_external=$vm_k3s_api_port"
        fi

        echo "$vm_name ansible_host=$ansible_host ansible_port=$ansible_port ansible_user=$VM_USERNAME ansible_ssh_private_key_file=$SSH_KEY_PATH $k3s_api_port_external_entry" >> "$inventory_file"
    done

    # Aggiungi le variabili comuni
    cat >> "$inventory_file" << EOF

[vms:vars]
ansible_ssh_common_args=$ssh_common_args
ansible_python_interpreter=/usr/bin/python3
EOF

    print_ansible "✓ Inventory creato: $inventory_file"
    print_ansible "✓ Username utilizzato: $VM_USERNAME (da terraform.tfvars)"
}

# Funzione per testare la connettività Ansible
test_ansible_connectivity() {
    print_ansible "Test connettività Ansible..."
    if ansible -i "$INVENTORY_FILE" vms -m ping; then
        print_ansible "✓ Connettività Ansible verificata"
        return 0
    else
        print_error "Test connettività Ansible fallito"
        return 1
    fi
}

# Funzione per eseguire un playbook Ansible
run_ansible_playbook() {
    local playbook_file="$1"
    local verbosity="${2:--v}"
    
    print_ansible "Configuro la VM con Ansible..."
    if ansible-playbook -i "$INVENTORY_FILE" "$playbook_file" "$verbosity"; then
        print_ansible "✓ Configurazione Ansible completata con successo!"
        return 0
    else
        print_error "Configurazione Ansible fallita"
        return 1
    fi
}



# Funzione per eseguire configurazione Ansible su multiple VM
run_ansible_configuration_multiple() {
    local vm_ips_json="$1"
    local vm_ssh_ports_str="$2"
    local vm_k3s_ports_str="$3"

    print_header "CONFIGURAZIONE ANSIBLE PER MULTIPLE VM"

    # Verifica prerequisiti Ansible
    if ! command -v ansible &> /dev/null; then
        print_error "Ansible non è installato. Configura Ansible prima di eseguire."
        return 1
    fi

    local vm_entries_formatted
    vm_entries_formatted=$(echo "$vm_ips_json" | jq -r 'to_entries[] | "\(.key) \(.value)"' | while read -r vm_name vm_ip; do
        local vm_ssh_port
        if ! vm_ssh_port=$(get_port_for_vm "$vm_name" "$vm_ssh_ports_str"); then
            print_error "Impossibile trovare la porta SSH per VM $vm_name. Assicurati che il port forwarding sia configurato correttamente."
            return 1
        fi

        local vm_k3s_api_port
        if ! vm_k3s_api_port=$(get_port_for_vm "$vm_name" "$vm_k3s_ports_str"); then
            print_warning "Impossibile trovare la porta K3s API per VM $vm_name. Continuando senza di essa."
            vm_k3s_api_port=""
        fi
        echo "$vm_name:$vm_ip:$vm_ssh_port:$vm_k3s_api_port"
    done)

    # Genera l'inventario passando i dati tramite pipe
    echo -e "$vm_entries_formatted" | generate_ansible_inventory

    # Esegui il playbook Ansible
    print_ansible "Esecuzione playbook Ansible su tutte le VM..."
    if ! ansible-playbook -i "$INVENTORY_FILE" "$PLAYBOOK_FILE"; then
        print_error "Errore nell'esecuzione del playbook Ansible"
        return 1
    fi

    print_ansible "✓ Configurazione Ansible completata con successo"
    return 0
}

# Funzione per generare inventory per le regole NAT
generate_nat_rules_inventory() {
    local inventory_file="$1"
    local terraform_output_json="$2"

    print_ansible "Generazione dell'inventory per le regole NAT..."

    # Inizia il file di inventory
    cat > "$inventory_file" << EOF
[proxmox_hosts]
$PROXMOX_HOST ansible_host=$PROXMOX_HOST ansible_user=$PROXMOX_USER ansible_ssh_private_key_file=$PROXMOX_SSH_KEY

[proxmox_hosts:vars]
interfaces_file=/etc/network/interfaces
target_interface=$INTERNAL_INTERFACE
source_interface=$EXTERNAL_INTERFACE
ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
ansible_python_interpreter=/usr/bin/python3

[port_mappings]
EOF

    # Aggiungi le mappature delle porte
    echo "$terraform_output_json" | jq -r --arg user "$CI_USER" '.vm_summary.value | to_entries[] | .key as $name | .value | "\($name)_ssh vm_id=\(.id) vm_name=\($name) vm_ip=\(.ip) vm_port=22 service=SSH vm_user=\($user)"' >> "$inventory_file"
    echo "$terraform_output_json" | jq -r '.vm_summary.value | to_entries[] | .key as $name | .value | "\($name)_k3s vm_id=\(.id) vm_name=\($name) vm_ip=\(.ip) vm_port=6443 service=k3s"' >> "$inventory_file"

    print_ansible "✓ Inventory per regole NAT creato: $inventory_file"
}