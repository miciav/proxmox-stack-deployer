#!/bin/bash

# Script per generare l'inventory Ansible da Terraform output

# Ottieni l'IP della VM da Terraform
VM_IP=$(terraform output -raw vm_ip)

# Crea il file inventory per Ansible
cat > inventory.ini << EOF
[terraform_vms]
terraform-vm ansible_host=$VM_IP ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa

[terraform_vms:vars]
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
EOF

echo "Inventory generato con IP: $VM_IP"