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
    - Executes the Ansible playbook `install_openfaas.yml` to deploy OpenFaaS using Helm.
9.  **Display Final Information**: Shows a detailed summary of created VMs, NAT mappings, and SSH connection commands.

For a more detailed description of the VM creation and deployment flow, refer to:
- **[Deployment Flow Documentation](DEPLOYMENT_FLOW.md)**
- **[VM Creation Flow Diagram](terraform-opentofu/vm_creation_flow.md)**
