import argparse
import subprocess
import os
import sys


def run_command(command, check=True):
    print(f"Executing: {command}")
    result = subprocess.run(command, shell=True, check=check)
    return result


def parse_arguments():
    parser = argparse.ArgumentParser(description='Deploy and manage VMs on Proxmox')
    parser.add_argument('--force-redeploy', action='store_true', help='Force a new deployment even if one already exists')
    parser.add_argument('--continue-if-deployed', action='store_true', help='Continue execution even if the deployment already exists')
    parser.add_argument('--skip-nat', action='store_true', help='Skip NAT rule configuration')
    parser.add_argument('--skip-ansible', action='store_true', help='Skip Ansible configuration')
    parser.add_argument('--no-vm-update', action='store_true', help='Skip VM configuration playbook (configure-vms.yml)')
    parser.add_argument('--no-k3s', action='store_true', help='Skip K3s installation playbook (k3s_install.yml)')
    parser.add_argument('--no-docker', action='store_true', help='Skip Docker installation playbook (docker_install.yml)')
    parser.add_argument('--destroy', action='store_true', help='Destroy the created infrastructure')
    parser.add_argument('--workspace', help='Select a specific Terraform workspace')
    parser.add_argument('--auto-approve', action='store_true', help='Automatically approve Terraform changes')

    return parser.parse_args()


def main():
    args = parse_arguments()

    if args.destroy:
        print("Destroying infrastructure")
        run_ansible_destroy()
        run_terraform_destroy()
        os.system('rm -rf inventories/*')
        sys.exit(0)

    run_initial_setup_and_validation_tasks(args)
    run_terraform_deploy(args)

    if not args.skip_ansible:
        if not args.skip_nat:
            run_ansible_nat_configuration()
        if not args.no_vm_update:
            run_ansible_vm_configuration()
        if not args.no_k3s:
            run_ansible_k3s_installation()
        if not args.no_docker:
            run_ansible_docker_installation()

    print("Deployment completed")


def run_ansible_destroy():
    print("Running Ansible to remove NAT rules")
    run_command("ansible-playbook -i ./inventories/inventory-nat-rules.ini ./playbooks/remove_nat_rules.yml")


def run_terraform_destroy():
    print("Performing Terraform destroy")
    run_command("terraform destroy -auto-approve")


def run_initial_setup_and_validation_tasks(args):
    print("Running initial setup and validation tasks")
    run_command("./lib/prereq.sh")
    

def run_terraform_deploy(args):
    print("Running Terraform deployment")
    if args.workspace:
        run_command(f"terraform workspace select {args.workspace}")
    run_command("terraform apply -auto-approve")


def run_ansible_nat_configuration():
    print("Running Ansible NAT configuration")
    run_command("ansible-playbook -i ./inventories/inventory-nat-rules.ini ./playbooks/add_nat_rules.yml")


def run_ansible_vm_configuration():
    print("Running Ansible VM configuration")
    run_command("ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/configure-vms.yml")


def run_ansible_k3s_installation():
    print("Running Ansible K3s installation")
    run_command("ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/k3s_install.yml")


def run_ansible_docker_installation():
    print("Running Ansible Docker installation")
    run_command("ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/docker_install.yml")


if __name__ == '__main__':
    main()

