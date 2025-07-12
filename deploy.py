#!/usr/bin/env python3
"""
Proxmox Stack Deployer

This script automates the deployment and management of a Proxmox-based infrastructure stack.
It orchestrates the creation and configuration of VMs using Terraform and Ansible,
with support for K3s, Docker, and OpenFaaS installations.

The script can be configured via command-line arguments or a configuration file (deploy.config).
"""

import argparse
import os
import sys
import configparser
from pathlib import Path
import ansible_runner

from lib.common import (
    run_command,
    print_status,
    print_header,
    print_error,
    print_ansible,
    check_command_exists,
    TERRAFORM_DIR,
)
from lib.prereq import (
    check_prerequisites,
    validate_tfvars_file,
    get_validated_vars,
    setup_ssh_keys,
)
from lib.terraform import run_terraform_workflow


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
        "force_redeploy": False,  # Force redeployment even if already deployed
        "continue_if_deployed": False,  # Continue if deployment already exists
        "skip_nat": False,  # Skip NAT configuration
        "skip_ansible": False,  # Skip all Ansible playbooks
        "no_vm_update": False,  # Skip VM configuration
        "no_k3s": False,  # Skip K3s installation
        "no_docker": False,  # Skip Docker installation
        "no_openfaas": False,  # Skip OpenFaaS installation
        "destroy": True,  # Destroy infrastructure
        "workspace": "",  # Terraform workspace
        "auto_approve": True,  # Auto-approve Terraform changes
    }

    if not os.path.exists(config_file):
        print_status(
            f"Configuration file '{config_file}' not found, using default values"
        )
        return config

    print_status(f"Loading configuration from '{config_file}'")

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
        print_error(f"Error reading configuration file: {e}")
        print_status("Using default values")
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
        print_header("INFRASTRUCTURE DESTRUCTION")
        # First remove NAT rules with Ansible
        if not run_ansible_destroy():
            print_error("NAT rule removal failed. Continuing with destruction...")
        # Then destroy all Terraform-managed resources
        run_terraform_destroy()
        # Clean up inventory files
        os.system("rm -rf inventories/*")
        # Exit after destruction is complete
        sys.exit(0)

    # Start deployment process
    print_header("STARTING DEPLOYMENT PROCESS")
    # 1. Run prerequisite checks and setup
    run_initial_setup_and_validation_tasks(args)
    # 2. Deploy infrastructure with Terraform
    run_terraform_deploy(args)

    # 3. Run Ansible playbooks for configuration if not skipped
    if not args.skip_ansible:
        print_header("ANSIBLE CONFIGURATION")
        # Configure NAT rules
        if not args.skip_nat:
            if not run_ansible_nat_configuration():
                print_error("NAT configuration failed. Continuing with deployment...")
        # Configure VMs (updates, packages, etc.)
        if not args.no_vm_update:
            if not run_ansible_vm_configuration():
                print_error("VM configuration failed. Continuing with deployment...")
        # Install K3s Kubernetes
        if not args.no_k3s:
            if not run_ansible_k3s_installation():
                print_error("K3s installation failed. Continuing with deployment...")
        # Install Docker
        if not args.no_docker:
            if not run_ansible_docker_installation():
                print_error("Docker installation failed. Continuing with deployment...")
        # Install OpenFaaS
        if not args.no_openfaas:
            if not run_ansible_openfaas_installation():
                print_error(
                    "OpenFaaS installation failed. Continuing with deployment..."
                )

    print_status("Deployment completed successfully")


def run_ansible_destroy():
    """
    Remove NAT rules using Ansible playbook.

    This is part of the infrastructure destruction process.
    Uses ansible_runner library for better integration with Python.
    """
    return run_ansible_playbook(
        "NAT rule removal",
        "./playbooks/remove_nat_rules.yml",
        "./inventories/inventory-nat-rules.ini",
    )


def run_terraform_destroy():
    """
    Destroy all Terraform-managed infrastructure.

    This removes all VMs and resources created by Terraform.
    """
    if check_command_exists("tofu"):
        tf_cmd = "tofu"
        tf_version_result = run_command(f"{tf_cmd} version", capture_output=True)
        tf_version = (
            tf_version_result.stdout.splitlines()[0]
            if tf_version_result.stdout
            else "Unknown version"
        )
        print_status(f"Using OpenTofu: {tf_version}")
    else:
        tf_cmd = "terraform"
        tf_version_result = run_command(f"{tf_cmd} version", capture_output=True)
        tf_version = (
            tf_version_result.stdout.splitlines()[0]
            if tf_version_result.stdout
            else "Unknown version"
        )
        print_status(f"Using Terraform: {tf_version}")

    print_status(f"Performing {tf_cmd} destroy")
    original_dir = os.getcwd()
    os.chdir(TERRAFORM_DIR)
    run_command(f"{tf_cmd} destroy -auto-approve")
    os.chdir(original_dir)


def run_initial_setup_and_validation_tasks(args):
    """
    Run prerequisite checks and setup tasks.

    This executes the prereq.py script which validates the environment
    and prepares it for deployment.

    Args:
        args: Command-line arguments
    """
    print_header("INITIAL SETUP AND VALIDATION")
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
    print_header("TERRAFORM DEPLOYMENT")
    if args.workspace:
        run_command(f"terraform workspace select {args.workspace}")

    # Set AUTO_APPROVE environment variable based on args
    if args.auto_approve:
        os.environ["AUTO_APPROVE"] = "true"
        print_status(
            "Auto-approve enabled: Terraform changes will be applied automatically"
        )

    run_terraform_workflow()


def run_ansible_playbook(operation_name, playbook_path, inventory_path):
    """
    Generic function to run Ansible playbooks with proper error handling.

    Args:
        operation_name: Name of the operation (for logging)
        playbook_path: Path to the playbook file
        inventory_path: Path to the inventory file

    Returns:
        bool: True if playbook execution was successful, False otherwise
    """
    print_status(f"Running Ansible {operation_name}")
    print_ansible(f"Using ansible_runner for {operation_name}")
    print_ansible(f"Current directory: {os.getcwd()}")

    # Save current directory and change to script directory
    original_cwd = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    try:
        os.chdir(script_dir)
        print_ansible(f"Changed to script directory: {script_dir}")

        # Check if files exist
        if not os.path.exists(playbook_path):
            print_error(f"Playbook not found: {playbook_path}")
            return False

        if not os.path.exists(inventory_path):
            print_error(f"Inventory not found: {inventory_path}")
            return False

        print_ansible("Files verified, starting playbook execution...")

        # Run the playbook using ansible_runner
        result = ansible_runner.run(
            private_data_dir="./",
            playbook=os.path.abspath(playbook_path),
            inventory=os.path.abspath(inventory_path),
            quiet=False,
            verbosity=1,
        )

        # Check result status (more robust than just checking rc)
        if result.status == "successful":
            print_status(f"Ansible {operation_name} completed successfully")
            print_ansible(f"Playbook executed with return code: {result.rc}")
            return True
        else:
            print_error(f"Ansible {operation_name} failed with status: {result.status}")
            print_error(f"Return code: {result.rc}")

            # Show error details if available
            if hasattr(result, "events"):
                for event in result.events:
                    if event.get("event") == "runner_on_failed":
                        task_name = event.get("event_data", {}).get(
                            "task", "Unknown task"
                        )
                        error_msg = (
                            event.get("event_data", {})
                            .get("res", {})
                            .get("msg", "Unknown error")
                        )
                        print_error(f"Failed task: {task_name}")
                        print_error(f"Error: {error_msg}")

            return False

    except FileNotFoundError as e:
        print_error(f"File not found during Ansible execution: {str(e)}")
        return False
    except PermissionError as e:
        print_error(f"Permission denied during Ansible execution: {str(e)}")
        return False
    except Exception as e:
        print_error(f"Unexpected exception during Ansible execution: {str(e)}")
        # Print full traceback for debugging
        import traceback

        print_error(f"Traceback: {traceback.format_exc()}")
        return False
    finally:
        # Always restore original directory
        os.chdir(original_cwd)
        print_ansible(f"Restored original directory: {original_cwd}")


def run_ansible_nat_configuration():
    """
    Configure NAT rules using Ansible.
    This allows VMs to access external networks through the Proxmox host.
    Uses ansible_runner library for better integration with Python.
    """
    return run_ansible_playbook(
        "NAT configuration",
        "./playbooks/add_nat_rules.yml",
        "./inventories/inventory-nat-rules.ini",
    )


def run_ansible_vm_configuration():
    """
    Configure VMs using Ansible.

    This performs basic VM setup and configuration tasks.
    Uses ansible_runner library for better integration with Python.
    """
    return run_ansible_playbook(
        "VM configuration",
        "./playbooks/configure-vms.yml",
        "./inventories/inventory_updates.ini",
    )


def run_ansible_k3s_installation():
    """
    Install K3s Kubernetes on VMs using Ansible.

    This sets up a lightweight Kubernetes cluster.
    Uses ansible_runner library for better integration with Python.
    """
    return run_ansible_playbook(
        "K3s installation",
        "./playbooks/k3s_install.yml",
        "./inventories/inventory_updates.ini",
    )


def run_ansible_docker_installation():
    """
    Install Docker on VMs using Ansible.

    This provides container runtime capabilities.
    Uses ansible_runner library for better integration with Python.
    """
    return run_ansible_playbook(
        "Docker installation",
        "./playbooks/docker_install.yml",
        "./inventories/inventory_updates.ini",
    )


def run_ansible_openfaas_installation():
    """
    Install OpenFaaS on the K3s cluster using Ansible.

    OpenFaaS provides serverless functions capabilities on Kubernetes.
    Uses ansible_runner library for better integration with Python.
    """
    return run_ansible_playbook(
        "OpenFaaS installation",
        "./playbooks/install_openfaas.yml",
        "./inventories/inventory_updates.ini",
    )


if __name__ == "__main__":
    main()
