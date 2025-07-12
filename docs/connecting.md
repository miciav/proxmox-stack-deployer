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
