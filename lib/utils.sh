#!/bin/bash

# lib/utils.sh - Funzioni di utilità

# Funzione per estrarre la porta per una specifica VM da una stringa di mappature
# $1: vm_name
# $2: stringa di mappature (es. "vm1:123\nvm2:456")
get_port_for_vm() {
    local vm_name="$1"
    local port_mappings="$2"
    
    local port
    port=$(echo "$port_mappings" | grep "^${vm_name}:" | cut -d':' -f2 | tr -d '\r')
    
    if [[ -n "$port" ]]; then
        echo "$port"
        return 0
    else
        return 1
    fi
}
