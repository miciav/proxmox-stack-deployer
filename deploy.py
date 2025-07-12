#!/usr/bin/env python3
"""
Proxmox Stack Deployer

This script automates the deployment and management of a Proxmox-based infrastructure stack.
It orchestrates the creation and configuration of VMs using Terraform and Ansible,
with support for K3s, Docker, and OpenFaaS installations.

The script can be configured via command-line arguments or a configuration file (deploy.config).
"""

import argparse
import subprocess
import os
import sys
import configparser
from pathlib import Path

from lib.prereq import check_prerequisites, validate_tfvars_file, get_validated_vars, setup_ssh_keys
from lib.terraform import run_terraform_workflow


def run_command(command, check=True):
    """
    Execute a shell command and return the result.

    Args:
        command (str): The shell command to execute
        check (bool): If True, raises an exception if the command returns a non-zero exit code

    Returns:
        subprocess.CompletedProcess: The result of the command execution
    """
    print(f"Executing: {command}")
    result = subprocess.run(command, shell=True, check=check)
    return result


def load_config(config_file="deploy.config"):
    """
    Load configuration from INI file, return default values if file doesn't exist.

    This function reads deployment configuration from an INI file and converts
    the values to appropriate types. If the file doesn't exist or has errors,
    default values are used.

    Args:
        config_file (str): Path to the configuration file (default: "deploy.config")

    Returns:
        dict: Configuration dictionary with all settings
    """
    # Default configuration values
    config = {
        "force_redeploy": False,      # Force redeployment even if already deployed
        "continue_if_deployed": False, # Continue if deployment already exists
        "skip_nat": False,            # Skip NAT configuration
        "skip_ansible": False,        # Skip all Ansible playbooks
        "no_vm_update": False,        # Skip VM configuration
        "no_k3s": False,              # Skip K3s installation
        "no_docker": False,           # Skip Docker installation
        "no_openfaas": False,         # Skip OpenFaaS installation
        "destroy": False,             # Destroy infrastructure
        "workspace": "",              # Terraform workspace
        "auto_approve": False,        # Auto-approve Terraform changes
    }

    if not os.path.exists(config_file):
        print(f"Configuration file '{config_file}' not found, using default values")
        return config

    print(f"Loading configuration from '{config_file}'")

    try:
        # Initialize the config parser
        parser = configparser.ConfigParser()
        parser.read(config_file)

        # Define mapping of config sections to their respective keys
        # This allows organizing related settings in different sections of the config file
        sections_mapping = {
            "deployment": ["force_redeploy", "continue_if_deployed", "auto_approve"],
            "skip_options": [
                "skip_nat",
                "skip_ansible",
                "no_vm_update",
                "no_k3s",
                "no_docker",
                "no_openfaas",
            ],
            "terraform": ["workspace"],
            "destruction": ["destroy"],
        }

        # Process each section and its keys
        for section_name, keys in sections_mapping.items():
            if parser.has_section(section_name):
                for key in keys:
                    if parser.has_option(section_name, key):
                        # Get the raw value from the config file
                        value = parser.get(section_name, key)
                        # Remove quotes if present for cleaner values
                        value = value.strip().strip('"').strip("'")

                        # Convert string values to appropriate types:
                        # - "true"/"false" to boolean
                        # - Empty strings remain empty
                        # - Other values remain as strings
                        if value.lower() in ["true", "false"]:
                            config[key] = value.lower() == "true"
                        elif value == "":
                            config[key] = ""
                        else:
                            config[key] = value

        return config

    except Exception as e:
        print(f"Error reading configuration file: {e}")
        print("Using default values")
        return config


def parse_arguments():
    """
    Parse command-line arguments and apply configuration defaults from the config file.

    Command-line arguments take precedence over configuration file settings.

    Returns:
        argparse.Namespace: Parsed arguments with defaults applied
    """
    # Load the configuration file first
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

    # Apply config defaults for any arguments not explicitly set on the command line
    # For each option, if it wasn't specified in command line args but exists in the config,
    # use the value from the config file

    # Deployment options
    if not args.force_redeploy and config.get("force_redeploy"):
        args.force_redeploy = True
    if not args.continue_if_deployed and config.get("continue_if_deployed"):
        args.continue_if_deployed = True
    if not args.auto_approve and config.get("auto_approve"):
        args.auto_approve = True

    # Skip options
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

    # Terraform and destruction options
    if not args.destroy and config.get("destroy"):
        args.destroy = True
    if not args.workspace and config.get("workspace"):
        args.workspace = config.get("workspace")

    return args


def main():
    """
    Main entry point for the Proxmox stack deployment script.

    This function orchestrates the entire deployment or destruction process based on 
    the provided arguments. It handles:
    1. Infrastructure destruction if --destroy is specified
    2. Initial setup and validation
    3. Terraform deployment
    4. Ansible configuration (NAT, VM updates, K3s, Docker, OpenFaaS)
    """
    args = parse_arguments()

    # Handle destruction mode if --destroy flag is set
    if args.destroy:
        print("Destroying infrastructure")
        # First remove NAT rules with Ansible
        run_ansible_destroy()
        # Then destroy all Terraform-managed resources
        run_terraform_destroy()
        # Clean up inventory files
        os.system("rm -rf inventories/*")
        # Exit after destruction is complete
        sys.exit(0)

    # Start deployment process
    # 1. Run prerequisite checks and setup
    run_initial_setup_and_validation_tasks(args)
    # 2. Deploy infrastructure with Terraform
    run_terraform_deploy(args)

    # 3. Run Ansible playbooks for configuration if not skipped
    if not args.skip_ansible:
        # Configure NAT rules
        if not args.skip_nat:
            run_ansible_nat_configuration()
        # Configure VMs (updates, packages, etc.)
        if not args.no_vm_update:
            run_ansible_vm_configuration()
        # Install K3s Kubernetes
        if not args.no_k3s:
            run_ansible_k3s_installation()
        # Install Docker
        if not args.no_docker:
            run_ansible_docker_installation()
        # Install OpenFaaS
        if not args.no_openfaas:
            run_ansible_openfaas_installation()

    print("Deployment completed")


def run_ansible_destroy():
    """
    Remove NAT rules using Ansible playbook.

    This is part of the infrastructure destruction process.
    """
    print("Running Ansible to remove NAT rules")
    run_command(
        "ansible-playbook -i ./inventories/inventory-nat-rules.ini ./playbooks/remove_nat_rules.yml"
    )


def run_terraform_destroy():
    """
    Destroy all Terraform-managed infrastructure.

    This removes all VMs and resources created by Terraform.
    """
    print("Performing Terraform destroy")
    run_command("terraform destroy -auto-approve")


def run_initial_setup_and_validation_tasks(args):
    """
    Run prerequisite checks and setup tasks.

    This executes the prereq.py script which validates the environment
    and prepares it for deployment.

    Args:
        args: Command-line arguments
    """
    print("Running initial setup and validation tasks")
    check_prerequisites()
    if not validate_tfvars_file():
        sys.exit(1)
    if not get_validated_vars():
        sys.exit(1)
    if not setup_ssh_keys():
        sys.exit(1)


def run_terraform_deploy(args):
    """
    Deploy infrastructure using Terraform.

    This creates VMs and other resources defined in Terraform configuration.

    Args:
        args: Command-line arguments containing workspace information
    """
    print("Running Terraform deployment")
    if args.workspace:
        run_command(f"terraform workspace select {args.workspace}")
    run_terraform_workflow()


def run_ansible_nat_configuration():
    """
    Configure NAT rules using Ansible.

    This allows VMs to access external networks through the Proxmox host.
    """
    print("Running Ansible NAT configuration")
    run_command(
        "ansible-playbook -i ./inventories/inventory-nat-rules.ini ./playbooks/add_nat_rules.yml"
    )


def run_ansible_vm_configuration():
    """
    Configure VMs using Ansible.

    This performs basic VM setup and configuration tasks.
    """
    print("Running Ansible VM configuration")
    run_command(
        "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/configure-vms.yml"
    )


def run_ansible_k3s_installation():
    """
    Install K3s Kubernetes on VMs using Ansible.

    This sets up a lightweight Kubernetes cluster.
    """
    print("Running Ansible K3s installation")
    run_command(
        "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/k3s_install.yml"
    )


def run_ansible_docker_installation():
    """
    Install Docker on VMs using Ansible.

    This provides container runtime capabilities.
    """
    print("Running Ansible Docker installation")
    run_command(
        "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/docker_install.yml"
    )


def run_ansible_openfaas_installation():
    """
    Install OpenFaaS on the K3s cluster using Ansible.

    OpenFaaS provides serverless functions capabilities on Kubernetes.
    """
    print("Running Ansible OpenFaaS installation")
    run_command(
        "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/install_openfaas.yml"
    )


if __name__ == "__main__":
    main()
