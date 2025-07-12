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
