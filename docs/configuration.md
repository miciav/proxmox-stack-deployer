## ⚙️ Configuration

Main configuration variables are defined in `variables.tf` and can be overridden in `terraform.tfvars`.

### `variables.tf`

This file defines all variables that can be used in the OpenTofu project, including their types, descriptions, and default values. It is the single source of truth for available configurations.

### `terraform.tfvars`

This file is where you specify the actual values for the variables defined in `variables.tf`. **It should not be committed to version control** (it's already ignored by `.gitignore`) as it contains environment-specific configurations or sensitive credentials.

Examples of key variables you can configure:

-   `vm_count`: Number of VMs to create. (e.g., `vm_count = 3`)
-   `deployment_delay`: Delay in seconds between consecutive VM creations to avoid overloading the Proxmox host. (e.g., `deployment_delay = 30`)
-   `vm_name_prefix`: Prefix used to name the VMs. (e.g., `vm_name_prefix = "my-cluster"`)
-   `vm_roles`: A map specifying the role for each VM ("k3s" or "docker"). (e.g., `vm_roles = {"my-cluster-1" = "k3s", "my-cluster-2" = "docker"}`)
-   `default_vm_role`: Default role for VMs not explicitly specified in vm_roles. (e.g., `default_vm_role = "k3s"`)
-   `vm_configs`: A complex map to customize resources (CPU, RAM, disk) of individual VMs. Useful for creating VMs with different specifications within the same deployment.

Example `terraform.tfvars`:

```hcl
vm_count = 4
deployment_delay = 30
vm_name_prefix = "my-cluster"

# VM Role Configuration
vm_roles = {
  "my-cluster-1" = "k3s"
  "my-cluster-2" = "k3s"
  "my-cluster-3" = "docker"
  "my-cluster-4" = "docker"
}

# Default role for VMs not explicitly specified
default_vm_role = "k3s"

vm_configs = {
  "web-server-1" = {
    cores     = 4
    memory    = 16384
    disk_size = "128G"
  }
  "db-server-1" = {
    cores     = 2
    memory    = 8192
    disk_size = "256G"
  }
}
```