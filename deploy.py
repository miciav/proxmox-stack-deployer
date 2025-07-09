import argparse
import subprocess
import os
import sys
import configparser
from pathlib import Path


def run_command(command, check=True):
    print(f"Executing: {command}")
    result = subprocess.run(command, shell=True, check=check)
    return result


def load_config(config_file="deploy.config"):
    """Load configuration from file, return default values if file doesn't exist"""
    config = {
        "force_redeploy": False,
        "continue_if_deployed": False,
        "skip_nat": False,
        "skip_ansible": False,
        "no_vm_update": False,
        "no_k3s": False,
        "no_docker": False,
        "no_openfaas": False,
        "destroy": False,
        "workspace": "",
        "auto_approve": False,
    }

    if not os.path.exists(config_file):
        print(f"Configuration file '{config_file}' not found, using default values")
        return config

    print(f"Loading configuration from '{config_file}'")

    try:
        with open(config_file, "r") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip().lower()
                    value = value.strip().strip('"').strip("'")

                    # Convert string values to appropriate types
                    if value.lower() in ["true", "false"]:
                        value = value.lower() == "true"
                    elif value == "":
                        value = ""

                    # Map config keys to argument names
                    if key in config:
                        config[key] = value

        return config

    except Exception as e:
        print(f"Error reading configuration file: {e}")
        print("Using default values")
        return config


def parse_arguments():
    # Load configuration file first
    config = load_config()

    parser = argparse.ArgumentParser(
        description="Deploy and manage VMs on Proxmox",
        epilog="Configuration file: deploy.config (command line flags override file settings)",
    )
    parser.add_argument(
        "--force-redeploy",
        action="store_true",
        help="Force a new deployment even if one already exists",
    )
    parser.add_argument(
        "--continue-if-deployed",
        action="store_true",
        help="Continue execution even if the deployment already exists",
    )
    parser.add_argument(
        "--skip-nat", action="store_true", help="Skip NAT rule configuration"
    )
    parser.add_argument(
        "--skip-ansible", action="store_true", help="Skip Ansible configuration"
    )
    parser.add_argument(
        "--no-vm-update",
        action="store_true",
        help="Skip VM configuration playbook (configure-vms.yml)",
    )
    parser.add_argument(
        "--no-k3s",
        action="store_true",
        help="Skip K3s installation playbook (k3s_install.yml)",
    )
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Skip Docker installation playbook (docker_install.yml)",
    )
    parser.add_argument(
        "--no-openfaas",
        action="store_true",
        help="Skip OpenFaaS installation playbook (install_openfaas.yml)",
    )
    parser.add_argument(
        "--destroy", action="store_true", help="Destroy the created infrastructure"
    )
    parser.add_argument("--workspace", help="Select a specific Terraform workspace")
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Automatically approve Terraform changes",
    )

    args = parser.parse_args()

    # Apply config defaults for any arguments not explicitly set
    if not args.force_redeploy and config.get("force_redeploy"):
        args.force_redeploy = True
    if not args.continue_if_deployed and config.get("continue_if_deployed"):
        args.continue_if_deployed = True
    if not args.skip_nat and config.get("skip_nat"):
        args.skip_nat = True
    if not args.skip_ansible and config.get("skip_ansible"):
        args.skip_ansible = True
    if not args.no_vm_update and config.get("no_vm_update"):
        args.no_vm_update = True
    if not args.no_k3s and config.get("no_k3s"):
        args.no_k3s = True
    if not args.no_docker and config.get("no_docker"):
        args.no_docker = True
    if not args.no_openfaas and config.get("no_openfaas"):
        args.no_openfaas = True
    if not args.destroy and config.get("destroy"):
        args.destroy = True
    if not args.workspace and config.get("workspace"):
        args.workspace = config.get("workspace")
    if not args.auto_approve and config.get("auto_approve"):
        args.auto_approve = True

    return args


def main():
    args = parse_arguments()

    if args.destroy:
        print("Destroying infrastructure")
        run_ansible_destroy()
        run_terraform_destroy()
        os.system("rm -rf inventories/*")
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
        if not args.no_openfaas:
            run_ansible_openfaas_installation()

    print("Deployment completed")


def run_ansible_destroy():
    print("Running Ansible to remove NAT rules")
    run_command(
        "ansible-playbook -i ./inventories/inventory-nat-rules.ini ./playbooks/remove_nat_rules.yml"
    )


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
    run_command(
        "ansible-playbook -i ./inventories/inventory-nat-rules.ini ./playbooks/add_nat_rules.yml"
    )


def run_ansible_vm_configuration():
    print("Running Ansible VM configuration")
    run_command(
        "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/configure-vms.yml"
    )


def run_ansible_k3s_installation():
    print("Running Ansible K3s installation")
    run_command(
        "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/k3s_install.yml"
    )


def run_ansible_docker_installation():
    print("Running Ansible Docker installation")
    run_command(
        "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/docker_install.yml"
    )


def run_ansible_openfaas_installation():
    print("Running Ansible OpenFaaS installation")
    run_command(
        "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/install_openfaas.yml"
    )


if __name__ == "__main__":
    main()
