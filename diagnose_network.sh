#!/bin/bash

# Network diagnosis script for Proxmox VMs
set -e

PROXMOX_HOST="${1:-titan-inside.disco.unimib.it}"
PROXMOX_USER="${2:-root}"

echo "🔍 Diagnosing network configuration for VMs..."
echo "Proxmox Host: $PROXMOX_HOST"
echo "User: $PROXMOX_USER"
echo

# Check if we can connect to Proxmox
if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$PROXMOX_USER@$PROXMOX_HOST" "echo 'Connected to Proxmox'" 2>/dev/null; then
    echo "❌ Cannot connect to Proxmox host. Please check SSH connectivity."
    exit 1
fi

echo "✅ Connected to Proxmox successfully"
echo

# Get VM information
for vm_id in 109 110; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🖥️  VM ID: $vm_id"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check VM status
    echo "📊 VM Status:"
    ssh -o StrictHostKeyChecking=no "$PROXMOX_USER@$PROXMOX_HOST" "qm status $vm_id" 2>/dev/null || echo "VM not found"
    echo
    
    # Check VM configuration (network section)
    echo "🌐 Network Configuration:"
    ssh -o StrictHostKeyChecking=no "$PROXMOX_USER@$PROXMOX_HOST" "qm config $vm_id | grep -E '^(net|mac)'" 2>/dev/null || echo "No network config found"
    echo
    
    # Check VM network interfaces via guest agent
    echo "🔌 Guest Agent Network Interfaces:"
    if ssh -o StrictHostKeyChecking=no "$PROXMOX_USER@$PROXMOX_HOST" "qm guest cmd $vm_id network-get-interfaces" 2>/dev/null; then
        echo "Guest agent responsive"
    else
        echo "Guest agent not responsive or VM not running"
    fi
    echo
    
    # Check DHCP lease if available
    echo "📋 VM Network Info (from Proxmox):"
    ssh -o StrictHostKeyChecking=no "$PROXMOX_USER@$PROXMOX_HOST" "qm agent $vm_id network-get-interfaces" 2>/dev/null | head -20 || echo "Cannot get network info"
    echo
done

# Check DHCP server logs if available
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Network Infrastructure Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check bridge configuration
echo "🌉 Bridge Configuration:"
ssh -o StrictHostKeyChecking=no "$PROXMOX_USER@$PROXMOX_HOST" "ip link show | grep vmbr" 2>/dev/null || echo "No bridges found"
echo

# Check if there's a DHCP server running
echo "🏠 DHCP Server Check:"
ssh -o StrictHostKeyChecking=no "$PROXMOX_USER@$PROXMOX_HOST" "ps aux | grep -i dhcp | grep -v grep" 2>/dev/null || echo "No DHCP server found on Proxmox host"
echo

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💡 Recommendations:"
echo "1. Check if VMs have different MAC addresses"
echo "2. Verify DHCP server has sufficient IP range"
echo "3. Check if VMs are on the same network bridge"
echo "4. Consider using static IPs instead of DHCP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
