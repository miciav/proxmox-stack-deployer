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

The project provides two deployment options:

**Option 1: Bash Script (Traditional)**
```bash
./deploy.sh [OPTIONS]
```

**Option 2: Python Script (Modern with Testing)**
```bash
python deploy.py [OPTIONS]
```

Both scripts provide the same functionality and command-line options.
