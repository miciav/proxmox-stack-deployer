## 📂 Project Structure

```
.gitignore
deploy.py
deploy.sh
DEPLOYMENT_FLOW.md
readme.md
requirements-test.txt
run_tests.py
test_deploy.py

playbooks/
├── add_nat_rules.yml
├── configure-vms.yml
├── docker_install.yml
├── install_openfaas.yml
├── k3s_install.yml
└── remove_nat_rules.yml

terraform-opentofu/
├── main.tf
├── variables.tf
├── vm_creation_flow.md
└── wait_for_vm.sh

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
