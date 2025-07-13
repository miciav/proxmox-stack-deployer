## 🚀 OpenFaaS Integration

The project includes automatic OpenFaaS installation and configuration on K3s nodes using Helm.

### What Gets Installed

- **OpenFaaS Gateway**: Main API gateway for function management
- **OpenFaaS Controller**: Manages function deployments in Kubernetes
- **Prometheus**: Monitoring and metrics collection
- **Alertmanager**: Alert management system
- **Basic Authentication**: Secure access to the OpenFaaS UI

### Configuration Details

- **Namespace**: `openfaas` (system components)
- **Function Namespace**: `openfaas-fn` (deployed functions)
- **Gateway Port**: 31112 (NodePort service)
- **Authentication**: Basic auth enabled with auto-generated password

### Accessing OpenFaaS

After deployment, OpenFaaS will be accessible via:

```bash
# Direct access (if NAT rules are configured)
http://<proxmox_host>:<k3s_nat_port>/

# Or via port-forwarding
kubectl port-forward -n openfaas svc/gateway 8080:8080
# Then visit: http://localhost:8080
```

**Login Credentials:**
- **Username**: `admin`
- **Password**: Displayed in deployment output or retrieve with:
  ```bash
  kubectl get secret -n openfaas basic-auth -o jsonpath="{.data.basic-auth-password}" | base64 --decode
  ```

### Managing OpenFaaS

**Install OpenFaaS CLI:**
```bash
curl -sSL https://cli.openfaas.com | sudo sh
```

**Login to OpenFaaS:**
```bash
echo -n <password> | faas-cli login --username admin --password-stdin
```

**Deploy a test function:**
```bash
faas-cli deploy --image functions/figlet --name figlet
```

### Skipping OpenFaaS Installation

If you don't want OpenFaaS installed, use the `--no-openfaas` flag:

```bash
./deploy.sh --no-openfaas
# or
python deploy.py --no-openfaas
```
