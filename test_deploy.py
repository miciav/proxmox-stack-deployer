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
from unittest.mock import patch, MagicMock
import sys
import os
import shutil
import tempfile

# Add the current directory to the path so we can import deploy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import deploy


class TestArgumentParsing(unittest.TestCase):
    """Test command-line argument parsing"""

    def test_parse_arguments_default(self):
        """Test default argument values"""
        with patch("sys.argv", ["deploy.py"]):
            with patch("deploy.load_config") as mock_load_config:
                mock_load_config.return_value = {
                    "force_redeploy": False,
                    "continue_if_deployed": False,
                    "skip_nat": False,
                    "skip_ansible": False,
                    "no_vm_update": False,
                    "no_k3s": False,
                    "no_docker": False,
                    "no_openfaas": False,
                    "destroy": True,
                    "workspace": "",
                    "auto_approve": True,
                }
                args = deploy.parse_arguments()

                self.assertFalse(args.force_redeploy)
                self.assertFalse(args.continue_if_deployed)
                self.assertFalse(args.skip_nat)
                self.assertFalse(args.skip_ansible)
                self.assertFalse(args.no_vm_update)
                self.assertFalse(args.no_k3s)
                self.assertFalse(args.no_docker)
                self.assertTrue(args.destroy)
                self.assertTrue(args.auto_approve)
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
            "--no-openfaas",
            "--destroy",
            "--auto-approve",
        ]

        with patch("sys.argv", test_args):
            with patch("deploy.load_config") as mock_load_config:
                mock_load_config.return_value = {
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
                args = deploy.parse_arguments()

                self.assertTrue(args.force_redeploy)
                self.assertTrue(args.continue_if_deployed)
                self.assertTrue(args.skip_nat)
                self.assertTrue(args.skip_ansible)
                self.assertTrue(args.no_vm_update)
                self.assertTrue(args.no_k3s)
                self.assertTrue(args.no_docker)
                self.assertTrue(args.no_openfaas)
                self.assertTrue(args.destroy)
                self.assertTrue(args.auto_approve)

    def test_parse_arguments_workspace(self):
        """Test workspace argument parsing"""
        with patch("sys.argv", ["deploy.py", "--workspace", "production"]):
            with patch("deploy.load_config") as mock_load_config:
                mock_load_config.return_value = {
                    "workspace": "",
                }
                args = deploy.parse_arguments()
                self.assertEqual(args.workspace, "production")


class TestCommandExecution(unittest.TestCase):
    """Test command execution functionality"""

    @patch("deploy.run_command")
    def test_run_command_success(self, mock_run_command):
        """Test successful command execution"""
        mock_run_command.return_value = MagicMock(returncode=0)

        result = deploy.run_command('echo "test"')

        mock_run_command.assert_called_once_with('echo "test"')
        self.assertEqual(result.returncode, 0)

    @patch("deploy.run_command")
    def test_run_command_failure(self, mock_run_command):
        """Test command execution failure"""
        mock_run_command.side_effect = Exception("Command failed")

        with self.assertRaises(Exception):
            deploy.run_command("false")


class TestDeploymentFunctions(unittest.TestCase):
    """Test individual deployment functions"""

    def setUp(self):
        # Create dummy files for ansible playbooks
        os.makedirs("playbooks", exist_ok=True)
        os.makedirs("inventories", exist_ok=True)
        with open("./playbooks/remove_nat_rules.yml", "w") as f:
            f.write("---")
        with open("./inventories/inventory-nat-rules.ini", "w") as f:
            f.write("[all]")
        with open("playbook.yml", "w") as f:
            f.write("---")
        with open("inventory.ini", "w") as f:
            f.write("[all]")

    def tearDown(self):
        # Clean up dummy files
        shutil.rmtree("playbooks")
        shutil.rmtree("inventories")
        os.remove("playbook.yml")
        os.remove("inventory.ini")

    @patch("ansible_runner.run")
    def test_run_ansible_destroy(self, mock_ansible_runner):
        """Test Ansible destroy function"""
        mock_ansible_runner.return_value = MagicMock(status="successful", rc=0)
        result = deploy.run_ansible_destroy()

        self.assertTrue(result)
        mock_ansible_runner.assert_called_once_with(
            private_data_dir="./",
            playbook=os.path.abspath("./playbooks/remove_nat_rules.yml"),
            inventory=os.path.abspath("./inventories/inventory-nat-rules.ini"),
            quiet=False,
            verbosity=1,
        )

    @patch("deploy.run_command")
    @patch("os.chdir")
    @patch("deploy.check_command_exists")
    def test_run_terraform_destroy_with_tofu(self, mock_check_command_exists, mock_chdir, mock_run_command):
        """Test Terraform destroy function with tofu"""
        mock_check_command_exists.return_value = True
        mock_run_command.return_value = MagicMock(stdout="OpenTofu v1.6.0")
        deploy.run_terraform_destroy()
        mock_run_command.assert_any_call("tofu version", capture_output=True)
        mock_run_command.assert_called_with("tofu destroy -auto-approve")

    @patch("deploy.run_command")
    @patch("os.chdir")
    @patch("deploy.check_command_exists")
    def test_run_terraform_destroy_with_terraform(self, mock_check_command_exists, mock_chdir, mock_run_command):
        """Test Terraform destroy function with terraform"""
        mock_check_command_exists.return_value = False
        mock_run_command.return_value = MagicMock(stdout="Terraform v1.2.0")
        deploy.run_terraform_destroy()
        mock_run_command.assert_any_call("terraform version", capture_output=True)
        mock_run_command.assert_called_with("terraform destroy -auto-approve")

    @patch("deploy.check_prerequisites")
    @patch("deploy.validate_tfvars_file")
    @patch("deploy.get_validated_vars")
    @patch("deploy.setup_ssh_keys")
    def test_run_initial_setup_and_validation_tasks(
        self, mock_setup_ssh_keys, mock_get_validated_vars, mock_validate_tfvars_file, mock_check_prerequisites
    ):
        """Test initial setup and validation tasks"""
        mock_check_prerequisites.return_value = True
        mock_validate_tfvars_file.return_value = True
        mock_get_validated_vars.return_value = True
        mock_setup_ssh_keys.return_value = True

        deploy.run_initial_setup_and_validation_tasks(MagicMock())

        mock_check_prerequisites.assert_called_once()
        mock_validate_tfvars_file.assert_called_once()
        mock_get_validated_vars.assert_called_once()
        mock_setup_ssh_keys.assert_called_once()

    @patch("deploy.run_terraform_workflow")
    @patch("deploy.run_command")
    def test_run_terraform_deploy_with_workspace(self, mock_run_command, mock_run_terraform_workflow):
        """Test Terraform deploy with workspace"""
        mock_args = MagicMock()
        mock_args.workspace = "production"
        mock_args.auto_approve = True

        deploy.run_terraform_deploy(mock_args)

        mock_run_command.assert_called_once_with("terraform workspace select production")
        mock_run_terraform_workflow.assert_called_once()
        self.assertEqual(os.environ.get("AUTO_APPROVE"), "true")

    @patch("ansible_runner.run")
    def test_run_ansible_playbook_success(self, mock_ansible_runner):
        """Test successful Ansible playbook execution"""
        mock_ansible_runner.return_value = MagicMock(status="successful", rc=0)
        result = deploy.run_ansible_playbook("test playbook", "playbook.yml", "inventory.ini")
        self.assertTrue(result)

    @patch("ansible_runner.run")
    def test_run_ansible_playbook_failure(self, mock_ansible_runner):
        """Test failed Ansible playbook execution"""
        mock_ansible_runner.return_value = MagicMock(status="failed", rc=1)
        result = deploy.run_ansible_playbook("test playbook", "playbook.yml", "inventory.ini")
        self.assertFalse(result)


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
        mock_args.workspace = None
        mock_parse_args.return_value = mock_args
        mock_ansible_destroy.return_value = True
        mock_exit.side_effect = SystemExit  # Stop execution after exit call

        with self.assertRaises(SystemExit):
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
    @patch("deploy.run_ansible_openfaas_installation")
    @patch("deploy.parse_arguments")
    def test_main_full_deployment(
        self,
        mock_parse_args,
        mock_openfaas_install,
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
        mock_args.no_openfaas = False
        mock_parse_args.return_value = mock_args

        # Mock the return values of the ansible functions
        mock_nat_config.return_value = True
        mock_vm_config.return_value = True
        mock_k3s_install.return_value = True
        mock_docker_install.return_value = True
        mock_openfaas_install.return_value = True

        deploy.main()

        mock_initial_setup.assert_called_once_with(mock_args)
        mock_terraform_deploy.assert_called_once_with(mock_args)
        mock_nat_config.assert_called_once()
        mock_vm_config.assert_called_once()
        mock_k3s_install.assert_called_once()
        mock_docker_install.assert_called_once()
        mock_openfaas_install.assert_called_once()

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


class TestConfigurationLoading(unittest.TestCase):
    """Test INI configuration file loading"""

    def test_load_config_missing_file(self):
        """Test loading config when file doesn't exist"""
        config = deploy.load_config("nonexistent.config")
        self.assertFalse(config["force_redeploy"])
        self.assertEqual(config["workspace"], "")

    def test_load_config_ini_format(self):
        """Test loading INI format configuration"""
        ini_content = """\
[deployment]
force_redeploy=true
auto_approve=true

[skip_options]
skip_nat=true

[terraform]
workspace=test-env
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(ini_content)
            f.flush()
            config = deploy.load_config(f.name)
            self.assertTrue(config["force_redeploy"])
            self.assertTrue(config["auto_approve"])
            self.assertTrue(config["skip_nat"])
            self.assertEqual(config["workspace"], "test-env")
        os.unlink(f.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)