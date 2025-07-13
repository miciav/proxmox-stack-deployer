## ✨ Key Features

- **Scalable Multi-VM Deployment**: Efficiently create and configure an arbitrary number of VMs.
- **Role-Based VM Configuration**: Distinguish between VMs for different purposes (K3s, Docker, OpenFaaS) using role-based deployment.
- **Staggered Creation**: VMs are created in parallel but with a configurable delay to optimize Proxmox host resource usage.
- **Sequential Initialization**: VM waiting and configuration scripts are executed sequentially to ensure stability and predictability.
- **Automatic NAT Configuration**: Dynamically configures NAT rules (for SSH, K3s API, and Docker) on the Proxmox host.
- **K3s Provisioning**: Includes automatic installation of K3s (lightweight Kubernetes) on designated VMs.
- **Docker Provisioning**: Includes automatic installation of Docker on designated VMs.
- **OpenFaaS Deployment**: Automatical installation and configuration of OpenFaaS on K3s nodes using Helm.
- **SSH Key Management**: Setup and management of SSH keys for secure access to VMs.
- **Detailed Output**: Generates inventory files and connection summaries to facilitate VM access and management.
- **OpenTofu Workspace Support**: Allows managing different deployment environments (e.g., `dev`, `prod`).
- **Dual Deployment Options**: Both Bash (`deploy.sh`) and Python (`deploy.py`) deployment scripts available.
- **Comprehensive Testing**: Full test suite with unit tests, integration tests, and CI/CD pipeline.
