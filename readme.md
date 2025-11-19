[![Test Deploy.py](https://github.com/miciav/proxmox-stack-deployer/workflows/Test%20Deploy.py/badge.svg)](https://github.com/miciav/proxmox-stack-deployer/actions)
[![codecov](https://codecov.io/gh/miciav/proxmox-stack-deployer/branch/main/graph/badge.svg)](https://codecov.io/gh/miciav/proxmox-stack-deployer)
[![Latest Release](https://img.shields.io/github/v/release/miciav/proxmox-stack-deployer)](https://github.com/miciav/proxmox-stack-deployer/releases/latest)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenTofu](https://img.shields.io/badge/OpenTofu-1.6+-purple.svg)](https://opentofu.org/)
[![Ansible](https://img.shields.io/badge/Ansible-2.9+-red.svg)](https://www.ansible.com/)
[![Proxmox](https://img.shields.io/badge/Proxmox-VE-orange.svg)](https://www.proxmox.com/)

# 🚀 Proxmox VM Deployment Automation with OpenTofu and Ansible

This project provides a comprehensive solution for automating the deployment and configuration of virtual machines on a Proxmox VE cluster, using OpenTofu (an open-source fork of Terraform) for infrastructure management and Ansible for post-deployment configuration and NAT rule management.

## 📖 Documentation

- [Features](docs/features.md)
- [Technologies Used](docs/technologies.md)
- [Deployment Flow](docs/deployment_flow.md)
- [Project Structure](docs/project_structure.md)
- [Configuration](docs/configuration.md)
- [Usage](docs/usage.md)
- [Configuration File](docs/config_file.md)
- [Connecting to VMs](docs/connecting.md)
- [OpenFaaS Integration](docs/openfaas.md)
- [Testing](docs/testing.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Notes on Git History Rewriting](docs/git_history.md)
- [References](docs/references.md)

## 🖥️ Optional Web Dashboard

A lightweight dashboard is bundled in `webapp/` if you prefer to follow deployments from the browser:

1. Install requirements (ideally inside a virtualenv): `pip install -r requirements-test.txt`.
2. Start the server: `python webapp/app.py` (customise the port by exporting `DEPLOY_UI_PORT`).
3. Open `http://localhost:5000` to launch or destroy the stack.

The UI mirrors the Terraform/Ansible workflow, showing live logs and a card for each phase. Cards for Docker or K3s only appear when those roles are defined in `terraform.tfvars`, so the dashboard always matches the roles that will actually run.
