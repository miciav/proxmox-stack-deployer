#!/usr/bin/env python3
"""
Comprehensive test suite for deploy.py

This test suite covers:
- Unit tests for individual functions
- Integration tests for deployment workflows
- Edge cases and error handling
- Command-line argument parsing
- Mock subprocess calls
"""

import unittest
from unittest.mock import patch, MagicMock, call
import pytest
import sys
import os
from io import StringIO

# Add the current directory to the path so we can import deploy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import deploy


class TestArgumentParsing(unittest.TestCase):
    """Test command-line argument parsing"""

    def test_parse_arguments_default(self):
        """Test default argument values"""
        with patch("sys.argv", ["deploy.py"]):
            args = deploy.parse_arguments()

            self.assertFalse(args.force_redeploy)
            self.assertFalse(args.continue_if_deployed)
            self.assertFalse(args.skip_nat)
            self.assertFalse(args.skip_ansible)
            self.assertFalse(args.no_vm_update)
            self.assertFalse(args.no_k3s)
            self.assertFalse(args.no_docker)
            self.assertFalse(args.destroy)
            self.assertFalse(args.auto_approve)
            self.assertIsNone(args.workspace)

    def test_parse_arguments_all_flags(self):
        """Test parsing all boolean flags"""
        test_args = [
            "deploy.py",
            "--force-redeploy",
            "--continue-if-deployed",
            "--skip-nat",
            "--skip-ansible",
            "--no-vm-update",
            "--no-k3s",
            "--no-docker",
            "--destroy",
            "--auto-approve",
        ]

        with patch("sys.argv", test_args):
            args = deploy.parse_arguments()

            self.assertTrue(args.force_redeploy)
            self.assertTrue(args.continue_if_deployed)
            self.assertTrue(args.skip_nat)
            self.assertTrue(args.skip_ansible)
            self.assertTrue(args.no_vm_update)
            self.assertTrue(args.no_k3s)
            self.assertTrue(args.no_docker)
            self.assertTrue(args.destroy)
            self.assertTrue(args.auto_approve)

    def test_parse_arguments_workspace(self):
        """Test workspace argument parsing"""
        with patch("sys.argv", ["deploy.py", "--workspace", "production"]):
            args = deploy.parse_arguments()
            self.assertEqual(args.workspace, "production")


class TestCommandExecution(unittest.TestCase):
    """Test command execution functionality"""

    @patch("subprocess.run")
    def test_run_command_success(self, mock_run):
        """Test successful command execution"""
        mock_run.return_value = MagicMock(returncode=0)

        result = deploy.run_command('echo "test"')

        mock_run.assert_called_once_with('echo "test"', shell=True, check=True)
        self.assertEqual(result.returncode, 0)

    @patch("subprocess.run")
    def test_run_command_failure(self, mock_run):
        """Test command execution failure"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

        with self.assertRaises(subprocess.CalledProcessError):
            deploy.run_command("false")

    @patch("subprocess.run")
    def test_run_command_no_check(self, mock_run):
        """Test command execution with check=False"""
        mock_run.return_value = MagicMock(returncode=1)

        result = deploy.run_command("false", check=False)

        mock_run.assert_called_once_with("false", shell=True, check=False)


class TestDeploymentFunctions(unittest.TestCase):
    """Test individual deployment functions"""

    @patch("deploy.run_command")
    def test_run_ansible_destroy(self, mock_run_command):
        """Test Ansible destroy function"""
        deploy.run_ansible_destroy()

        mock_run_command.assert_called_once_with(
            "ansible-playbook -i ./inventories/inventory-nat-rules.ini ./playbooks/remove_nat_rules.yml"
        )

    @patch("deploy.run_command")
    def test_run_terraform_destroy(self, mock_run_command):
        """Test Terraform destroy function"""
        deploy.run_terraform_destroy()

        mock_run_command.assert_called_once_with("terraform destroy -auto-approve")

    @patch("deploy.run_command")
    def test_run_initial_setup_and_validation_tasks(self, mock_run_command):
        """Test initial setup and validation tasks"""
        mock_args = MagicMock()
        deploy.run_initial_setup_and_validation_tasks(mock_args)

        mock_run_command.assert_called_once_with("./lib/prereq.sh")

    @patch("deploy.run_command")
    def test_run_terraform_deploy_no_workspace(self, mock_run_command):
        """Test Terraform deploy without workspace"""
        mock_args = MagicMock()
        mock_args.workspace = None

        deploy.run_terraform_deploy(mock_args)

        mock_run_command.assert_called_once_with("terraform apply -auto-approve")

    @patch("deploy.run_command")
    def test_run_terraform_deploy_with_workspace(self, mock_run_command):
        """Test Terraform deploy with workspace"""
        mock_args = MagicMock()
        mock_args.workspace = "production"

        deploy.run_terraform_deploy(mock_args)

        expected_calls = [
            call("terraform workspace select production"),
            call("terraform apply -auto-approve"),
        ]
        mock_run_command.assert_has_calls(expected_calls)

    @patch("deploy.run_command")
    def test_run_ansible_nat_configuration(self, mock_run_command):
        """Test Ansible NAT configuration"""
        deploy.run_ansible_nat_configuration()

        mock_run_command.assert_called_once_with(
            "ansible-playbook -i ./inventories/inventory-nat-rules.ini ./playbooks/add_nat_rules.yml"
        )

    @patch("deploy.run_command")
    def test_run_ansible_vm_configuration(self, mock_run_command):
        """Test Ansible VM configuration"""
        deploy.run_ansible_vm_configuration()

        mock_run_command.assert_called_once_with(
            "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/configure-vms.yml"
        )

    @patch("deploy.run_command")
    def test_run_ansible_k3s_installation(self, mock_run_command):
        """Test Ansible K3s installation"""
        deploy.run_ansible_k3s_installation()

        mock_run_command.assert_called_once_with(
            "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/k3s_install.yml"
        )

    @patch("deploy.run_command")
    def test_run_ansible_docker_installation(self, mock_run_command):
        """Test Ansible Docker installation"""
        deploy.run_ansible_docker_installation()

        mock_run_command.assert_called_once_with(
            "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/docker_install.yml"
        )


class TestMainFunction(unittest.TestCase):
    """Test the main function and workflow"""

    @patch("deploy.run_ansible_destroy")
    @patch("deploy.run_terraform_destroy")
    @patch("os.system")
    @patch("sys.exit")
    @patch("deploy.parse_arguments")
    def test_main_destroy_workflow(
        self,
        mock_parse_args,
        mock_exit,
        mock_os_system,
        mock_terraform_destroy,
        mock_ansible_destroy,
    ):
        """Test destroy workflow"""
        mock_args = MagicMock()
        mock_args.destroy = True
        mock_parse_args.return_value = mock_args

        deploy.main()

        mock_ansible_destroy.assert_called_once()
        mock_terraform_destroy.assert_called_once()
        mock_os_system.assert_called_once_with("rm -rf inventories/*")
        mock_exit.assert_called_once_with(0)

    @patch("deploy.run_initial_setup_and_validation_tasks")
    @patch("deploy.run_terraform_deploy")
    @patch("deploy.run_ansible_nat_configuration")
    @patch("deploy.run_ansible_vm_configuration")
    @patch("deploy.run_ansible_k3s_installation")
    @patch("deploy.run_ansible_docker_installation")
    @patch("deploy.parse_arguments")
    def test_main_full_deployment(
        self,
        mock_parse_args,
        mock_docker_install,
        mock_k3s_install,
        mock_vm_config,
        mock_nat_config,
        mock_terraform_deploy,
        mock_initial_setup,
    ):
        """Test full deployment workflow"""
        mock_args = MagicMock()
        mock_args.destroy = False
        mock_args.skip_ansible = False
        mock_args.skip_nat = False
        mock_args.no_vm_update = False
        mock_args.no_k3s = False
        mock_args.no_docker = False
        mock_parse_args.return_value = mock_args

        deploy.main()

        mock_initial_setup.assert_called_once_with(mock_args)
        mock_terraform_deploy.assert_called_once_with(mock_args)
        mock_nat_config.assert_called_once()
        mock_vm_config.assert_called_once()
        mock_k3s_install.assert_called_once()
        mock_docker_install.assert_called_once()

    @patch("deploy.run_initial_setup_and_validation_tasks")
    @patch("deploy.run_terraform_deploy")
    @patch("deploy.run_ansible_nat_configuration")
    @patch("deploy.run_ansible_vm_configuration")
    @patch("deploy.run_ansible_k3s_installation")
    @patch("deploy.run_ansible_docker_installation")
    @patch("deploy.parse_arguments")
    def test_main_skip_ansible(
        self,
        mock_parse_args,
        mock_docker_install,
        mock_k3s_install,
        mock_vm_config,
        mock_nat_config,
        mock_terraform_deploy,
        mock_initial_setup,
    ):
        """Test deployment with skip ansible"""
        mock_args = MagicMock()
        mock_args.destroy = False
        mock_args.skip_ansible = True
        mock_parse_args.return_value = mock_args

        deploy.main()

        mock_initial_setup.assert_called_once_with(mock_args)
        mock_terraform_deploy.assert_called_once_with(mock_args)
        mock_nat_config.assert_not_called()
        mock_vm_config.assert_not_called()
        mock_k3s_install.assert_not_called()
        mock_docker_install.assert_not_called()

    @patch("deploy.run_initial_setup_and_validation_tasks")
    @patch("deploy.run_terraform_deploy")
    @patch("deploy.run_ansible_nat_configuration")
    @patch("deploy.run_ansible_vm_configuration")
    @patch("deploy.run_ansible_k3s_installation")
    @patch("deploy.run_ansible_docker_installation")
    @patch("deploy.parse_arguments")
    def test_main_selective_skips(
        self,
        mock_parse_args,
        mock_docker_install,
        mock_k3s_install,
        mock_vm_config,
        mock_nat_config,
        mock_terraform_deploy,
        mock_initial_setup,
    ):
        """Test deployment with selective skips"""
        mock_args = MagicMock()
        mock_args.destroy = False
        mock_args.skip_ansible = False
        mock_args.skip_nat = True
        mock_args.no_vm_update = True
        mock_args.no_k3s = False
        mock_args.no_docker = True
        mock_parse_args.return_value = mock_args

        deploy.main()

        mock_initial_setup.assert_called_once_with(mock_args)
        mock_terraform_deploy.assert_called_once_with(mock_args)
        mock_nat_config.assert_not_called()
        mock_vm_config.assert_not_called()
        mock_k3s_install.assert_called_once()
        mock_docker_install.assert_not_called()


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""

    @patch("deploy.run_command")
    def test_command_failure_propagation(self, mock_run_command):
        """Test that command failures are properly propagated"""
        mock_run_command.side_effect = subprocess.CalledProcessError(1, "cmd")

        with self.assertRaises(subprocess.CalledProcessError):
            deploy.run_ansible_destroy()

    @patch("deploy.run_command")
    def test_terraform_workspace_selection_failure(self, mock_run_command):
        """Test failure in terraform workspace selection"""
        mock_run_command.side_effect = [
            subprocess.CalledProcessError(1, "terraform workspace select"),
            MagicMock(),
        ]

        mock_args = MagicMock()
        mock_args.workspace = "nonexistent"

        with self.assertRaises(subprocess.CalledProcessError):
            deploy.run_terraform_deploy(mock_args)

    @patch("sys.argv", ["deploy.py", "--invalid-arg"])
    def test_invalid_argument_handling(self):
        """Test handling of invalid arguments"""
        with self.assertRaises(SystemExit):
            deploy.parse_arguments()


class TestIntegration(unittest.TestCase):
    """Integration tests for the deployment workflow"""

    @patch("subprocess.run")
    @patch("os.system")
    @patch("sys.exit")
    def test_end_to_end_destroy(self, mock_exit, mock_os_system, mock_subprocess):
        """Test end-to-end destroy workflow"""
        mock_subprocess.return_value = MagicMock(returncode=0)

        test_args = ["deploy.py", "--destroy"]

        with patch("sys.argv", test_args):
            deploy.main()

        # Verify that both destroy commands were called
        expected_calls = [
            call(
                "ansible-playbook -i ./inventories/inventory-nat-rules.ini ./playbooks/remove_nat_rules.yml",
                shell=True,
                check=True,
            ),
            call("terraform destroy -auto-approve", shell=True, check=True),
        ]
        mock_subprocess.assert_has_calls(expected_calls, any_order=True)
        mock_os_system.assert_called_once_with("rm -rf inventories/*")
        mock_exit.assert_called_once_with(0)

    @patch("subprocess.run")
    def test_end_to_end_deployment(self, mock_subprocess):
        """Test end-to-end deployment workflow"""
        mock_subprocess.return_value = MagicMock(returncode=0)

        test_args = ["deploy.py", "--auto-approve"]

        with patch("sys.argv", test_args):
            deploy.main()

        # Verify that all deployment commands were called
        expected_commands = [
            "./lib/prereq.sh",
            "terraform apply -auto-approve",
            "ansible-playbook -i ./inventories/inventory-nat-rules.ini ./playbooks/add_nat_rules.yml",
            "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/configure-vms.yml",
            "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/k3s_install.yml",
            "ansible-playbook -i ./inventories/inventory_updates.ini ./playbooks/docker_install.yml",
        ]

        for cmd in expected_commands:
            mock_subprocess.assert_any_call(cmd, shell=True, check=True)


class TestUtilities(unittest.TestCase):
    """Test utility functions and helpers"""

    @patch("builtins.print")
    @patch("subprocess.run")
    def test_command_output_logging(self, mock_subprocess, mock_print):
        """Test that commands are logged before execution"""
        mock_subprocess.return_value = MagicMock(returncode=0)

        deploy.run_command('echo "test"')

        mock_print.assert_called_with('Executing: echo "test"')
        mock_subprocess.assert_called_once_with('echo "test"', shell=True, check=True)


if __name__ == "__main__":
    # Import subprocess after setting up the test environment
    import subprocess

    # Run the tests
    unittest.main(verbosity=2)
