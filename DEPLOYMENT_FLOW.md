# Proxmox VM Deployment Flow

This document describes the complete deployment flow for creating multiple VMs on Proxmox using Terraform/OpenTofu.

## 🚀 Overview

The deployment process creates multiple VMs with staggered creation and sequential initialization to optimize resource usage and provide predictable deployment timing.

## 📋 Complete Deployment Flow

### Phase 1: VM Creation (Parallel with Staggered Timing)
```
┌─────────────────┐
│  Start Deploy   │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   Create VM 1   │ ─────┐
└─────────────────┘      │
         │                │
         ▼                │ Wait 30s (deployment_delay)
┌─────────────────┐      │
│   VM 1 Ready    │      │
└─────────────────┘      │
                          ▼
                 ┌─────────────────┐
                 │   Create VM 2   │
                 └─────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │   VM 2 Ready    │
                 └─────────────────┘
```

### Phase 2: Initialization Scripts (Sequential)
```
┌─────────────────┐    ┌─────────────────┐
│   VM 1 Created  │    │   VM 2 Created  │
└─────────────────┘    └─────────────────┘
         │                       │
         ▼                       │
┌─────────────────┐              │
│ VM 1 Wait Script│              │
│   (runs first)  │              │
└─────────────────┘              │
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│ VM 1 Wait Done  │───▶│ VM 2 Wait Script│
│                 │    │   (runs second) │
└─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│ VM 1 IP Ready   │    │ VM 2 IP Ready   │
└─────────────────┘    └─────────────────┘
```

## 🔧 Technical Details

### VM Creation Process
Each VM is created as a full clone of the template with:
- **Template**: `ubuntu` (cloud-init enabled)
- **Resources**: 32GB RAM, 8 CPU cores (4 cores × 2 sockets), 128GB disk
- **Network**: DHCP on bridge `vmbr1`
- **Boot**: UEFI with secure boot
- **Storage**: SSD storage with qcow2 format

### Wait Script Process
The `wait_for_vm.sh` script performs the following checks for each VM:

1. **IP Address Discovery** (up to 30 minutes)
   - Connects to Proxmox via SSH
   - Uses `qm guest cmd` to query network interfaces
   - Extracts private IP addresses (192.x, 10.x, 172.x)
   - Saves IP to `/tmp/vm_${VMID}_ip.txt`

2. **Guest Agent Verification**
   - Performs 3 consecutive ping tests to qemu-guest-agent
   - Ensures agent is responsive and stable
   - 30-second stabilization period

3. **System Verification**
   - Tests guest exec functionality
   - Verifies qemu-guest-agent service status
   - Performs system info check (`uname -a`)

### Sequential Execution Logic
```hcl
triggers = {
  vm_id = proxmox_vm_qemu.ubuntu-vm[count.index].vmid
  # VM 0 depends only on VM creation
  # VM 1+ depends on previous VM's wait completion
  dependency = count.index == 0 ? 
    proxmox_vm_qemu.ubuntu-vm[count.index].id : 
    null_resource.wait_for_vm[count.index - 1].id
}
```

## 📊 Output Files Generated

For each VM with ID `${VMID}`:
- `/tmp/vm_${VMID}_ip.txt` - Contains the discovered IP address
- `/tmp/vm_${VMID}_summary.txt` - Contains deployment summary and debug info

## ⚡ Benefits of Sequential Execution

1. **Reduced SSH Load**: One script connects to Proxmox at a time
2. **Predictable Progress**: Clear deployment order and timing
3. **Better Resource Management**: No concurrent load spikes
4. **Easier Debugging**: Sequential logs are easier to follow
5. **Maintains Deployment Delay**: VMs still get staggered creation timing

## 🔍 Monitoring Deployment

Watch the deployment progress with colored output:
- 🔵 **[INFO]** - General information and progress updates
- 🟢 **[SUCCESS]** - Successful operations and completions
- 🟡 **[WARNING]** - Non-critical issues or retries
- 🔴 **[ERROR]** - Critical failures requiring attention

## 📈 Scaling Considerations

- **VM Count**: Validated range 1-50 VMs
- **Memory per VM**: 32GB (ensure sufficient host memory)
- **Deployment Time**: ~2-5 minutes per VM (depends on boot time)
- **SSH Connections**: One at a time to avoid overwhelming Proxmox

## 🛠️ Configuration Variables

Key variables for controlling the deployment:

```hcl
vm_count = 2                    # Number of VMs to create
deployment_delay = 30           # Seconds between VM creations
vm_name_prefix = "ubuntu-opentofu"  # VM naming prefix
```

## 🔧 Customization Options

The configuration supports per-VM customization via the `vm_configs` variable:

```hcl
vm_configs = {
  "web-server-1" = {
    cores     = 4
    memory    = 16384
    disk_size = "128G"
  }
  "web-server-2" = {
    cores  = 2
    memory = 8192
  }
}
```

## 📚 Related Files

- `main.tf` - Main Terraform configuration
- `variables.tf` - Variable definitions
- `terraform.tfvars` - Environment-specific values
- `wait_for_vm.sh` - VM initialization script
- `README.md` - Main project documentation
