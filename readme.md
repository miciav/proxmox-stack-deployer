# Creating VMs on Proxmox with OpenTofu

This guide explains how to use [OpenTofu](https://opentofu.org/) (an open-source Terraform fork) to provision virtual machines on a Proxmox VE cluster.

## Prerequisites

- Proxmox VE server (API enabled)
- OpenTofu installed (`brew install opentofu` or see [installation guide](https://opentofu.org/docs/cli/install/))
- Proxmox user with API permissions
- [Proxmox provider for Terraform](https://registry.terraform.io/providers/Telmate/proxmox/latest)

## Setup

1. **Initialize your project:**

    ```sh
    mkdir proxmox-vms && cd proxmox-vms
    tofu init
    ```

2. **Create a `main.tf`:**

    ```hcl
    terraform {
      required_providers {
         proxmox = {
            source  = "Telmate/proxmox"
            version = "~> 2.9"
         }
      }
    }

    provider "proxmox" {
      pm_api_url      = "https://<PROXMOX_HOST>:8006/api2/json"
      pm_user         = "<USERNAME>@pam"
      pm_password     = "<PASSWORD>"
      pm_tls_insecure = true
    }

    resource "proxmox_vm_qemu" "example" {
      name        = "test-vm"
      target_node = "<PROXMOX_NODE>"
      clone       = "<TEMPLATE_NAME>"
      cores       = 2
      memory      = 2048
      disk {
         size = "32G"
      }
      network {
         model = "virtio"
         bridge = "vmbr0"
      }
    }
    ```

3. **Initialize and apply:**

    ```sh
    tofu init
    tofu plan
    tofu apply
    ```

## Notes

- Replace placeholders (`<...>`) with your actual values.
- For advanced options, see the [Proxmox provider documentation](https://registry.terraform.io/providers/Telmate/proxmox/latest/docs).

## 📋 Multiple VM Deployment

This project supports creating multiple VMs with sequential initialization for optimal resource usage:

- **[Deployment Flow Documentation](DEPLOYMENT_FLOW.md)** - Complete technical overview
- **[VM Creation Flow Diagram](vm_creation_flow.md)** - Visual deployment sequence

### Quick Start for Multiple VMs

1. **Configure VM count** in `terraform.tfvars`:
   ```hcl
   vm_count = 3  # Creates 3 VMs
   ```

2. **Deploy**:
   ```sh
   tofu plan
   tofu apply
   ```

3. **Monitor progress** - Scripts run sequentially to avoid overloading Proxmox

## References

- [OpenTofu Documentation](https://opentofu.org/docs/)
- [BPG Proxmox Provider](https://registry.terraform.io/providers/bpg/proxmox/latest) - Reliable and actively maintained
- [BPG Provider Documentation](https://registry.terraform.io/providers/bpg/proxmox/latest/docs)
