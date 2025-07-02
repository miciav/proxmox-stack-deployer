# 🚀 Proxmox VM Deployment Automation with OpenTofu and Ansible

This project provides a comprehensive solution for automating the deployment and configuration of virtual machines on a Proxmox VE cluster, using OpenTofu (an open-source fork of Terraform) for infrastructure management and Ansible for post-deployment configuration and NAT rule management.

## ✨ Key Features

- **Scalable Multi-VM Deployment**: Efficiently create and configure an arbitrary number of VMs.
- **Staggered Creation**: VMs are created in parallel but with a configurable delay to optimize Proxmox host resource usage.
- **Sequential Initialization**: VM waiting and configuration scripts are executed sequentially to ensure stability and predictability.
- **Automatic NAT Configuration**: Dynamically configures NAT rules (for SSH and K3s API) on the Proxmox host.
- **K3s Provisioning**: Includes automatic installation of K3s (lightweight Kubernetes) on the VMs.
- **SSH Key Management**: Setup and management of SSH keys for secure access to VMs.
- **Detailed Output**: Generates inventory files and connection summaries to facilitate VM access and management.
- **OpenTofu Workspace Support**: Allows managing different deployment environments (e.g., `dev`, `prod`).

## 🛠️ Technologies Used

- **[OpenTofu](https://opentofu.org/)**: For infrastructure provisioning (VMs on Proxmox).
- **[Ansible](https://www.ansible.com/)**: For VM configuration, K3s installation, and NAT rule management on the Proxmox host.
- **[Proxmox VE](https://www.proxmox.com/en/)**: The virtualization platform.
- **Bash Scripting**: Orchestration of the entire deployment process via `deploy_main.sh`.
- **`jq`**: For parsing and manipulating OpenTofu's JSON output.

## 🚀 Deployment Flow

 The deployment process is orchestrated by the `deploy_main.sh` script and follows these phases:

1.  **Argument Parsing**: Analyzes arguments passed to the script (e.g., `--force-redeploy`, `--skip-nat`).
2.  **Prerequisite Check**: Verifies the presence of necessary tools (OpenTofu, Ansible, `jq`).
3.  **`terraform.tfvars` Validation**: Ensures the variable configuration file is correct.
4.  **SSH Key Setup**: Configures SSH keys for access to the Proxmox host and VMs.
5.  **OpenTofu Workspace Selection**: Selects or creates an OpenTofu workspace to isolate deployment states.
6.  **OpenTofu Workflow**: Executes `tofu init`, `tofu plan`, `tofu apply` to create VMs on Proxmox.
    - VMs are created in a staggered manner (`deployment_delay`).
    - For each VM, the `wait_for_vm.sh` script is executed, which waits for IP assignment, verifies the guest agent, and system status.
7.  **NAT Rules Configuration (Ansible)**:
    - Generates an Ansible inventory file (`inventories/inventory-nat-rules.ini`) based on OpenTofu's output.
    - Executes the Ansible playbook `add_ssh_nat_rules2.yml` to configure NAT rules (SSH and K3s API) on the Proxmox host.
    - Generates a specific inventory file for SSH connections (`ssh_connections.ini`).
8.  **VM Configuration (Ansible)**:
    - Executes the Ansible playbook `configure-vm.yml` for initial VM configuration.
    - Executes the Ansible playbook `k3s_install.yml` to install K3s on the VMs.
9.  **Display Final Information**: Shows a detailed summary of created VMs, NAT mappings, and SSH connection commands.

For a more detailed description of the VM creation and deployment flow, refer to:
- **[Deployment Flow Documentation](DEPLOYMENT_FLOW.md)**
- **[VM Creation Flow Diagram](terraform-opentofu/vm_creation_flow.md)**

## 📂 Project Structure

```
.gitignore
add_ssh_nat_rules2.yml
configure-vm.yml
deploy_main.sh
DEPLOYMENT_FLOW.md
k3s_install.yml
main.tf
readme.md
requirements.yml
tofu-workflow.sh
variables.tf
vm_creation_flow.md
wait_for_vm.sh

lib/
├── ansible.sh
├── common.sh
├── networking.sh
├── prereq.sh
├── proxmox.sh
├── ssh.sh
├── terraform.sh
└── utils.sh

inventories/
├── inventory-nat-rules.ini  # Dynamically generated
└── ssh_connections.ini      # Dynamically generated

templates/
├── inventory-nat-rules.ini.j2
└── ssh_inventory.ini.j2

# Other generated/ignored files:
.terraform/
*.tfstate*
logs/
```

## ⚙️ Configuration

Main configuration variables are defined in `variables.tf` and can be overridden in `terraform.tfvars`.

### `variables.tf`

This file defines all variables that can be used in the OpenTofu project, including their types, descriptions, and default values. It is the single source of truth for available configurations.

### `terraform.tfvars`

This file is where you specify the actual values for the variables defined in `variables.tf`. **It should not be committed to version control** (it's already ignored by `.gitignore`) as it contains environment-specific configurations or sensitive credentials.

Examples of key variables you can configure:

-   `vm_count`: Number of VMs to create. (e.g., `vm_count = 3`)
-   `deployment_delay`: Delay in seconds between consecutive VM creations to avoid overloading the Proxmox host. (e.g., `deployment_delay = 30`)
-   `vm_name_prefix`: Prefix used to name the VMs. (e.g., `vm_name_prefix = "ubuntu-opentofu"`)
-   `vm_configs`: A complex map to customize resources (CPU, RAM, disk) of individual VMs. Useful for creating VMs with different specifications within the same deployment.

Example `terraform.tfvars`:

```hcl
vm_count = 2
deployment_delay = 30
vm_name_prefix = "ubuntu-opentofu"

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

## 🚀 Usage

### Prerequisites

Before running the deployment, ensure you have the following tools installed and configured correctly:

-   **Proxmox VE server**: A functional Proxmox VE server with API enabled. Ensure you have a Proxmox user with sufficient API permissions to create and manage VMs and configure network rules.
-   **OpenTofu**: Installed and configured on your local system. You can find the official installation guide [here](https://opentofu.org/docs/cli/install/).
    -   Verify installation: `tofu --version`
-   **Ansible**: Installed on your local system. You can install it via pip: `pip install ansible`.
    -   Verify installation: `ansible --version`
-   **`jq`**: A command-line JSON parser, used to process OpenTofu's output. Install it via your preferred package manager (e.g., `brew install jq` on macOS, `sudo apt-get install jq` on Debian/Ubuntu).
    -   Verify installation: `jq --version`
-   **SSH Key**: A private SSH key (`id_rsa` or similar) configured for access to the Proxmox host and, subsequently, to the created VMs. The key path must be specified in the main inventory file.

### Running the Deployment

To start the deployment process, run the main script from the project root directory:

```bash
./deploy.sh [OPTIONS]
```

**Command Line Options:**

-   `--force-redeploy`: Forces a new deployment even if an existing `terraform.tfstate` indicates that resources have already been created. Useful for recreating the environment from scratch.
-   `--continue-if-deployed`: Allows the script to continue execution even if the deployment appears to have already run. Useful for resuming an interrupted execution or applying only the configuration phases.
-   `--skip-nat`: Skips the NAT rule configuration phase on the Proxmox host. VMs will be created but will not be accessible via port forwarding.
-   `--skip-ansible`: Skips all Ansible configuration phases. VMs will be created and initialized, but no post-deployment configuration (e.g., K3s installation) will be performed.
-   `--workspace NAME`: Specifies a name for the OpenTofu workspace. This allows isolating deployment states for different environments (e.g., `dev`, `staging`, `production`). If the workspace does not exist, it will be created.
-   `--auto-approve`: Automatically approves changes proposed by OpenTofu (`tofu apply -auto-approve`), avoiding manual confirmation prompts.
-   `--no-vm-update`: Skips the VM configuration playbook (`configure-vms.yml`).
-   `--no-k3s`: Skips the K3s installation playbook (`k3s_install.yml`).
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

## 🔗 Connecting to VMs

After a successful deployment, the final section of the `deploy_main.sh` output will provide a detailed summary of the VMs, including direct SSH commands to connect to each of them. You can also use the `ssh_connections.ini` file with Ansible to manage the VMs:

```bash
# Example of direct SSH connection (from script output):
ssh -i /path/to/your/key -p <host_port_ssh> <user>@<proxmox_host_ip>

# Example of use with Ansible to test connectivity:
ansible -i ssh_connections.ini <vm_name> -m ping

# Example of running a remote command with Ansible:
ansible -i ssh_connections.ini <vm_name> -a "hostname" # Executes 'hostname' on the VM
```

##  Troubleshooting

### `sudo: a password is required` during NAT configuration

**Problem**: The Ansible playbook for NAT rules fails with a `sudo: a password is required` error.

**Cause**: This happens because the Ansible playbook attempts to perform operations with root privileges (`become: true`) on `localhost` (the machine from which you are running the script), but it does not have a password for `sudo`.

**Solution**: Ensure that the Ansible task modifying local files (like `inventory-nat-rules.ini` or `ssh_connections.ini`) has `become: false` explicitly set. This tells Ansible not to use `sudo` for that specific task, as root privileges are not required to modify files in your user directory.

### `git filter-repo` fails or is not found

**Problem**: The `git filter-repo` command is not recognized or fails during history rewriting.

**Cause**: `git filter-repo` might not be installed or not be in your system's PATH.

**Solution**: Install `git filter-repo` using your preferred package manager. For example:
-   **Python pip**: `pip install git-filter-repo`
-   **macOS Homebrew**: `brew install git-filter-repo`

### SSH Connectivity Issues to VMs

**Problem**: You cannot connect via SSH to VMs after deployment.

**Possible Cause**: NAT rules might not have been applied correctly, the Proxmox host's firewall might be blocking connections, or the VM might not have started the SSH service correctly.

**Solution**: 
1.  **Verify NAT Rules**: Check the deployment output to ensure that NAT rules were successfully configured. You can also access the Proxmox host and manually verify `iptables` rules (`iptables -t nat -L PREROUTING`).
2.  **Proxmox Firewall**: Ensure that the Proxmox host's firewall is not blocking the ports you have mapped. You might need to add rules to allow incoming traffic on the NATted ports.
3.  **VM Status**: Check the VM status on the Proxmox VE UI. Ensure it is running and that the SSH service is active within the VM.
4.  **SSH Key**: Verify that the specified SSH key is correct and that you are using the full path and correct permissions (`chmod 400 your_key_file`).

## ⚠️ Notes on Git History Rewriting

This project has undergone a Git history rewrite to remove all `.ini` files from past commits. This is a **destructive** and **irreversible** operation.

-   If you cloned the repository before this change, you might need to **delete your local copy and re-clone** the repository.
-   If you are collaborating, ensure all team members are aware of this change and update their repositories accordingly.
-   After rewriting, you will need to **re-add your `origin` remote** (if removed by `git filter-repo`) and then perform a `git push --force` to update the remote repository.

## 📚 References

-   [OpenTofu Documentation](https://opentofu.org/docs/)
-   [BPG Proxmox Provider](https://registry.terraform.io/providers/bpg/proxmox/latest) - OpenTofu/Terraform Provider for Proxmox.
-   [Ansible Documentation](https://docs.ansible.com/)
