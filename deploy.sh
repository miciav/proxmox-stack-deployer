#!/bin/bash

set -e # Exit script on any error

# export DEBUG=true

# Import all libraries
source "$(dirname "$0")/lib/common.sh"     # Base functions and output
source "$(dirname "$0")/lib/prereq.sh"    # Prerequisite checks
source "$(dirname "$0")/lib/ssh.sh"       # SSH management
source "$(dirname "$0")/lib/terraform.sh" # Terraform/OpenTofu management

# Ensure cleanup is called on exit
trap cleanup EXIT

# Function to load configuration from file
load_config() {
    local config_file="${1:-deploy.config}"
    
    if [[ -f "$config_file" ]]; then
        print_status "Loading configuration from '$config_file'"
        
        # Source the config file, but only process valid variable assignments
        while IFS= read -r line; do
            # Skip comments and empty lines
            if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "${line// }" ]]; then
                continue
            fi
            
            # Process valid variable assignments
            if [[ "$line" =~ ^[[:space:]]*([A-Z_]+)[[:space:]]*=[[:space:]]*(.*)$ ]]; then
                local var_name="${BASH_REMATCH[1]}"
                local var_value="${BASH_REMATCH[2]}"
                
                # Remove quotes from value
                var_value="${var_value//\"/}"
                var_value="${var_value//\'/}"
                
                # Set the variable if it's not already set by command line
                case "$var_name" in
                    FORCE_REDEPLOY|CONTINUE_IF_DEPLOYED|SKIP_NAT|SKIP_ANSIBLE|NO_VM_UPDATE|NO_K3S|NO_DOCKER|NO_OPENFAAS|AUTO_APPROVE|DESTROY)
                        if [[ "${!var_name}" == "false" ]] && [[ "$var_value" == "true" ]]; then
                            declare -g "$var_name"="true"
                        fi
                        ;;
                    WORKSPACE)
                        if [[ -z "${!var_name}" ]] && [[ -n "$var_value" ]]; then
                            declare -g "$var_name"="$var_value"
                        fi
                        ;;
                esac
            fi
        done < "$config_file"
    else
        print_status "Configuration file '$config_file' not found, using default values"
    fi
}

# Function to parse arguments
parse_arguments() {
    # Initialize global variables with default values
    FORCE_REDEPLOY="false"
    CONTINUE_IF_DEPLOYED="false"
    SKIP_NAT="false"
    SKIP_ANSIBLE="false"
    NO_VM_UPDATE="false"
    NO_K3S="false"
    NO_DOCKER="false"
    NO_OPENFAAS="false"
    WORKSPACE=""
    AUTO_APPROVE="false"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force-redeploy)
                FORCE_REDEPLOY="true"
                shift
                ;;
            --continue-if-deployed)
                CONTINUE_IF_DEPLOYED="true"
                shift
                ;;
            --skip-nat)
                SKIP_NAT="true"
                shift
                ;;
            --skip-ansible)
                SKIP_ANSIBLE="true"
                shift
                ;;
            --workspace)
                WORKSPACE="$2"
                shift 2
                ;;
            --auto-approve)
                AUTO_APPROVE="true"
                shift
                ;;
            --no-vm-update)
                NO_VM_UPDATE="true"
                shift
                ;;
            --no-k3s)
                NO_K3S="true"
                shift
                ;;
            --no-docker)
                NO_DOCKER="true"
                shift
                ;;
            --no-openfaas)
                NO_OPENFAAS="true"
                shift
                ;;
            --destroy)
                DESTROY="true"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown argument: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Load configuration file (this will only set variables that weren't set by command line)
    load_config "deploy.config"
    
    # Export variables to make them available to other scripts
    export FORCE_REDEPLOY CONTINUE_IF_DEPLOYED SKIP_NAT SKIP_ANSIBLE NO_VM_UPDATE NO_K3S NO_DOCKER NO_OPENFAAS WORKSPACE AUTO_APPROVE
}

# Function to show help
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

OPTIONS:
    --force-redeploy       Force a new deployment even if one already exists
    --continue-if-deployed Continue execution even if the deployment already exists
    --skip-nat             Skip NAT rule configuration
    --skip-ansible         Skip Ansible configuration
    --workspace NAME       Select a specific Terraform workspace
    --auto-approve         Automatically approve Terraform changes
    --no-vm-update         Skip VM configuration playbook (configure-vms.yml)
    --no-k3s               Skip K3s installation playbook (k3s_install.yml)
    --no-docker            Skip Docker installation playbook (docker_install.yml)
    --no-openfaas          Skip OpenFaaS installation playbook (install_openfaas.yml)
    --destroy              Destroy the created infrastructure
    -h, --help             Show this help

CONFIGURATION:
    Configuration file: deploy.config (command line flags override file settings)
    Place this file in the same directory as the deployment script.

EXAMPLES:
    $0 --auto-approve --continue-if-deployed
    $0 --force-redeploy --skip-nat
    $0 --workspace production --auto-approve
    $0 --destroy

EOF
}

run_ansible_destroy(){
  print_status "Removing NAT rules..."
  NAT_INVENTORY_FILE="./inventories/inventory-nat-rules.ini"
  NAT_PLAYBOOK_FILE="./playbooks/remove_nat_rules.yml"
  if ! ansible-playbook -i "$NAT_INVENTORY_FILE" "$NAT_PLAYBOOK_FILE"; then
    print_error "Error removing NAT rules"
    exit 1
  fi
  print_success "NAT rules removed successfully"
}


run_initial_setup_and_validation_tasks(){
    # Check prerequisites
    check_prerequisites
    # Validate the terraform.tfvars file and read ci_user and proxmox_host
    validate_tfvars_file
    get_validated_vars
    # Setup SSH keys
    setup_ssh_keys
   # test_proxmox_connection "$PROXMOX_HOST" "$PROXMOX_USER"
}

run_terraform_deploy(){
      # Select workspace if specified
      select_terraform_workspace "$WORKSPACE"
      # Execute Terraform/OpenTofu workflow
      if run_terraform_workflow; then
          print_status "No changes to the infrastructure, checking if the VM already exists"
      fi

      # Get information of all VMs
      local vm_summary
      if ! vm_summary=$(get_vm_summary_from_terraform); then
          exit 1
      fi

      print_status "VM information obtained:"
      echo "$vm_summary" | jq .

      # Get array of VM IPs
      local vm_ips
      if ! vm_ips=$(get_vm_ips_from_terraform); then
          print_error "Failed to get VM IPs from Terraform output."
          exit 1
      fi

      print_status "VM IPs: $(echo "$vm_ips" | jq -r 'values | join(", ")')"
}


# Main deployment function
main() {
    # Parse arguments
    parse_arguments "$@"

    # Initial header
    print_header "🚀 STARTING WORKFLOW AT $(date)"

    # If destroy is requested, execute and exit
    if [[ "$DESTROY" == "true" ]]; then
        run_ansible_destroy
        run_terraform_destroy
        rm inventories/*
        exit 0
    fi

    # First task, it is a shell-based task
    run_initial_setup_and_validation_tasks

    # Second Task, execute terraform/opentofu

    # Check if the deployment already exists
    cd "$TERRAFORM_DIR" || exit 1
    if [[ "$FORCE_REDEPLOY" != "true" ]] && [[ -f "terraform.tfstate" ]] && [[ $(jq '.resources | length' terraform.tfstate) -gt 0 ]]; then
        print_warning "The deployment seems to have been already executed."
        if [[ "$CONTINUE_IF_DEPLOYED" != "true" ]]; then
            print_warning "Use --force-redeploy to force a new deployment or --continue-if-deployed to continue."
            exit 0
        else
            cd ..
            print_status "Flag --continue-if-deployed detected, execution continues."
            run_terraform_deploy
        fi
    else
      cd ..
      print_status "Flag --continue-if-deployed detected, execution continues."
      run_terraform_deploy
    fi
    cd ..

    #Ansible task 1
    # Configure NAT rules using Ansible
    if [[ "${SKIP_ANSIBLE:-false}" != "true" ]]; then
        if [[ "$SKIP_NAT" != "true" ]]; then
            print_status "Configuring NAT rules for SSH and K3s API via Ansible..."
            NAT_INVENTORY_FILE="./inventories/inventory-nat-rules.ini"
            NAT_PLAYBOOK_FILE="./playbooks/add_nat_rules.yml"
            ansible-playbook -i "$NAT_INVENTORY_FILE" "$NAT_PLAYBOOK_FILE"
            echo "$ANSIBLE_OUTPUT" # Print the full output for debugging
            print_success "NAT rules configured successfully"
        fi
    fi
    
    #Ansible task 2
    if [[ "${SKIP_ANSIBLE:-false}" != "true" ]]; then
        print_status "Starting Ansible configuration for ${#vm_ips[@]} VMs..."
        UPDATE_INVENTORY_FILE="./inventories/inventory_updates.ini"
        if [[ "${NO_VM_UPDATE}" != "true" ]]; then
            UPDATE_PLAYBOOK_FILE="./playbooks/configure-vms.yml"
            if ! ansible-playbook -i "$UPDATE_INVENTORY_FILE" "$UPDATE_PLAYBOOK_FILE"; then
                print_error "Ansible configuration failed for some VMs"
            else
                print_success "Ansible configuration completed successfully"
            fi
        else
            print_status "Skipping VM configuration (NO_VM_UPDATE=true)"
        fi
    fi

    #Ansible task 3 - K3s installation
    if [[ "${SKIP_ANSIBLE:-false}" != "true" ]]; then
        if [[ "${NO_K3S}" != "true" ]]; then
            print_status "Executing K3s playbook..."
            K3S_PLAYBOOK_FILE="./playbooks/k3s_install.yml"
            if ! ansible-playbook -i "$UPDATE_INVENTORY_FILE" "$K3S_PLAYBOOK_FILE"; then
                print_error "Error executing K3s playbook"
                return 1
            fi
            print_success "✓ K3s playbook completed successfully"
        else
            print_status "Skipping K3s installation (NO_K3S=true)"
        fi
    else
        print_status "Ansible configuration skipped (SKIP_ANSIBLE=true)"
    fi
    
    #Ansible task 4 - Docker installation
    if [[ "${SKIP_ANSIBLE:-false}" != "true" ]]; then
        if [[ "${NO_DOCKER}" != "true" ]]; then
            print_status "Executing Docker playbook..."
            DOCKER_PLAYBOOK_FILE="./playbooks/docker_install.yml"
            if ! ansible-playbook -i "$UPDATE_INVENTORY_FILE" "$DOCKER_PLAYBOOK_FILE"; then
                print_error "Error executing Docker playbook"
                return 1
            fi
            print_success "✓ Docker playbook completed successfully"
        else
            print_status "Skipping Docker installation (NO_DOCKER=true)"
        fi
    else
        print_status "Ansible configuration skipped (SKIP_ANSIBLE=true)"
    fi
    
    #Ansible task 5 - OpenFaaS installation
    if [[ "${SKIP_ANSIBLE:-false}" != "true" ]]; then
        if [[ "${NO_OPENFAAS}" != "true" ]]; then
            print_status "Executing OpenFaaS playbook..."
            OPENFAAS_PLAYBOOK_FILE="./playbooks/install_openfaas.yml"
            if ! ansible-playbook -i "$UPDATE_INVENTORY_FILE" "$OPENFAAS_PLAYBOOK_FILE"; then
                print_error "Error executing OpenFaaS playbook"
                return 1
            fi
            print_success "✓ OpenFaaS playbook completed successfully"
        else
            print_status "Skipping OpenFaaS installation (NO_OPENFAAS=true)"
        fi
    else
        print_status "Ansible configuration skipped (SKIP_ANSIBLE=true)"
    fi
    
    print_status "Deployment completed at $(date)"
}

# Execute main if script is called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
