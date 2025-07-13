## 📋 Configuration File

The deployment scripts support a configuration file (`deploy.config`) that allows you to set default values for all command-line options. This eliminates the need to specify commonly used flags repeatedly.

### Configuration File Format

The configuration file uses INI format with sections and key-value pairs:

```ini
; Deployment Configuration File
; This file allows you to set default values for deployment options
; Command line flags will override these settings if provided
; 
; Format: INI format with sections [section_name] and key=value pairs
; Boolean values: true/false
; String values: can be quoted or unquoted
; Comments: lines starting with ;

[deployment]
; Force a new deployment even if one already exists
force_redeploy=false

; Continue execution even if deployment already exists
continue_if_deployed=false

; Automatically approve Terraform changes (no manual confirmation)
auto_approve=false

[skip_options]
; Skip NAT rule configuration
skip_nat=false

; Skip all Ansible configuration phases
skip_ansible=false

; Skip VM configuration playbook (configure-vms.yml)
no_vm_update=false

; Skip K3s installation playbook (k3s_install.yml)
no_k3s=false

; Skip Docker installation playbook (docker_install.yml)
no_docker=false

; Skip OpenFaaS installation playbook (install_openfaas.yml)
no_openfaas=false

[terraform]
; Terraform workspace to use (leave empty for default)
workspace=""

[destruction]
; Destroy the created infrastructure
destroy=false
```

### INI Format Benefits

- **Organized Structure**: Related settings are grouped into logical sections
- **Better Readability**: Clear separation between different configuration areas
- **Standard Format**: Uses widely recognized INI conventions
- **Tool Compatibility**: Works with standard configuration parsers
- **Flexible Comments**: Both `;` and `#` comment styles supported

**File Location:** Place the `deploy.config` file in the same directory as your deployment scripts (`deploy.sh` or `deploy.py`). The scripts will automatically detect and load it.

### Using Configuration Files

```bash
# The scripts automatically look for 'deploy.config' in the current directory
./deploy.sh
python deploy.py

# Override config file settings with flags
./deploy.sh --force-redeploy  # Overrides FORCE_REDEPLOY in config
```

**Priority Order:**
1. Command line flags (highest priority)
2. Configuration file settings
3. Default values (lowest priority)

**Command Line Options:**

-   `--force-redeploy`: Forces a new deployment even if an existing `terraform.tfstate` indicates that resources have already been created. Useful for recreating the environment from scratch.
-   `--continue-if-deployed`: Allows the script to continue execution even if the deployment appears to have already run. Useful for resuming an interrupted execution or applying only the configuration phases.
-   `--skip-nat`: Skips the NAT rule configuration phase on the Proxmox host. VMs will be created but will not be accessible via port forwarding.
-   `--skip-ansible`: Skips all Ansible configuration phases. VMs will be created and initialized, but no post-deployment configuration (e.g., K3s installation) will be performed.
-   `--workspace NAME`: Specifies a name for the OpenTofu workspace. This allows isolating deployment states for different environments (e.g., `dev`, `staging`, `production`). If the workspace does not exist, it will be created.
-   `--auto-approve`: Automatically approves changes proposed by OpenTofu (`tofu apply -auto-approve`), avoiding manual confirmation prompts.
-   `--no-vm-update`: Skips the VM configuration playbook (`configure-vms.yml`).
-   `--no-k3s`: Skips the K3s installation playbook (`k3s_install.yml`).
-   `--no-docker`: Skips the Docker installation playbook (`docker_install.yml`).
-   `--no-openfaas`: Skips the OpenFaaS installation playbook (`install_openfaas.yml`).
-   `--destroy`: Destroys the infrastructure created by OpenTofu. If used with `--auto-approve`, it will not prompt for confirmation.
-   `-h`, `--help`: Shows a help message with all available options and usage examples.

**Usage Examples:**

```bash
# Performs a full deployment, automatically approving changes and continuing if already deployed
./deploy.sh --auto-approve --continue-if-deployed

# Forces a new deployment from scratch, skipping NAT configuration
./deploy.sh --force-redeploy --skip-nat

# Deploys to a specific workspace named 'production', with automatic approval
./deploy.sh --workspace production --auto-approve

# Deploys VMs but skips the VM configuration playbook
./deploy.sh --no-vm-update

# Deploys VMs but skips the K3s installation playbook
./deploy.sh --no-k3s

# Deploys VMs but skips the OpenFaaS installation playbook
./deploy.sh --no-openfaas

# Destroys the infrastructure, requiring manual confirmation
./deploy.sh --destroy

# Destroys the infrastructure without prompting for confirmation
./deploy.sh --destroy --auto-approve
```

### Generated Outputs

During and after deployment, the project generates several useful files for management and debugging:

-   `inventories/inventory-nat-rules.ini`: An Ansible inventory file that is dynamically updated with NAT port mappings assigned to VMs. Contains details such as `vm_id`, `vm_name`, `vm_ip`, `vm_port`, `service`, and `host_port`.
-   `ssh_connections.ini`: An Ansible inventory file specifically dedicated to SSH connections to VMs. Includes NATted ports for SSH, username, host, and the path to the private SSH key, as well as the external port for the K3s API (if applicable).
-   `/tmp/vm_<VMID>_ip.txt`: For each VM created, this temporary file contains the private IP address discovered after startup.
-   `/tmp/vm_<VMID>_summary.txt`: Contains a deployment summary and detailed debug information for each VM, generated by the `wait_for_vm.sh` script.
