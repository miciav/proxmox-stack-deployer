## 🛠️ Technologies Used

- **[OpenTofu](https://opentofu.org/)**: For infrastructure provisioning (VMs on Proxmox).
- **[Ansible](https://www.ansible.com/)**: For VM configuration, K3s/Docker installation, and NAT rule management on the Proxmox host.
- **[Helm](https://helm.sh/)**: For deploying OpenFaaS on Kubernetes (K3s) clusters.
- **[Proxmox VE](https://www.proxmox.com/en/)**: The virtualization platform.
- **Bash Scripting**: Orchestration of the entire deployment process via `deploy.sh`.
- **Python**: Alternative deployment script (`deploy.py`) with comprehensive testing suite.
- **`jq`**: For parsing and manipulating OpenTofu's JSON output.
