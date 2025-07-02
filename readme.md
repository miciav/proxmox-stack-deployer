# 🚀 Proxmox VM Deployment Automation with OpenTofu and Ansible

Questo progetto fornisce una soluzione completa per l'automazione del deployment e della configurazione di macchine virtuali su un cluster Proxmox VE, utilizzando OpenTofu (un fork open-source di Terraform) per la gestione dell'infrastruttura e Ansible per la configurazione post-deployment e la gestione delle regole NAT.

## ✨ Caratteristiche Principali

- **Deployment Multi-VM Scalabile**: Crea e configura un numero arbitrario di VM in modo efficiente.
- **Creazione Staggered**: Le VM vengono create in parallelo ma con un ritardo configurabile per ottimizzare l'uso delle risorse del Proxmox host.
- **Inizializzazione Sequenziale**: Gli script di attesa e configurazione delle VM vengono eseguiti in sequenza per garantire stabilità e prevedibilità.
- **Configurazione Automatica NAT**: Configura dinamicamente le regole NAT (per SSH e K3s API) sul Proxmox host.
- **Provisioning K3s**: Include l'installazione automatica di K3s (Kubernetes leggero) sulle VM.
- **Gestione Chiavi SSH**: Setup e gestione delle chiavi SSH per l'accesso sicuro alle VM.
- **Output Dettagliato**: Genera file di inventory e riepiloghi di connessione per facilitare l'accesso e la gestione delle VM.
- **Supporto Workspace OpenTofu**: Permette di gestire diversi ambienti di deployment (es. `dev`, `prod`).

## 🛠️ Tecnologie Utilizzate

- **[OpenTofu](https://opentofu.org/)**: Per il provisioning dell'infrastruttura (VM su Proxmox).
- **[Ansible](https://www.ansible.com/)**: Per la configurazione delle VM, l'installazione di K3s e la gestione delle regole NAT sul Proxmox host.
- **[Proxmox VE](https://www.proxmox.com/en/)**: La piattaforma di virtualizzazione.
- **Bash Scripting**: Orchestrazione dell'intero processo di deployment tramite `deploy_main.sh`.
- **`jq`**: Per il parsing e la manipolazione dell'output JSON di OpenTofu.

## 🚀 Flusso di Deployment

Il processo di deployment è orchestrato dallo script `deploy_main.sh` e segue le seguenti fasi:

1.  **Parsing Argomenti**: Analizza gli argomenti passati allo script (es. `--force-redeploy`, `--skip-nat`).
2.  **Verifica Prerequisiti**: Controlla la presenza degli strumenti necessari (OpenTofu, Ansible, `jq`).
3.  **Validazione `terraform.tfvars`**: Assicura che il file di configurazione delle variabili sia corretto.
4.  **Setup Chiavi SSH**: Configura le chiavi SSH per l'accesso al Proxmox host e alle VM.
5.  **Selezione Workspace OpenTofu**: Seleziona o crea un workspace OpenTofu per isolare gli stati di deployment.
6.  **Workflow OpenTofu**: Esegue `tofu init`, `tofu plan`, `tofu apply` per creare le VM su Proxmox.
    - Le VM vengono create in modo scaglionato (`deployment_delay`).
    - Per ogni VM, viene eseguito lo script `wait_for_vm.sh` che attende l'assegnazione dell'IP, verifica il guest agent e lo stato del sistema.
7.  **Configurazione Regole NAT (Ansible)**:
    - Genera un file di inventory (`inventories/inventory-nat-rules.ini`) basato sull'output di OpenTofu.
    - Esegue il playbook Ansible `add_ssh_nat_rules2.yml` per configurare le regole NAT (SSH e K3s API) sul Proxmox host.
    - Genera un file di inventory specifico per le connessioni SSH (`ssh_connections.ini`).
8.  **Configurazione VM (Ansible)**:
    - Esegue il playbook Ansible `configure-vm.yml` per la configurazione iniziale delle VM.
    - Esegue il playbook Ansible `k3s_install.yml` per installare K3s sulle VM.
9.  **Visualizzazione Informazioni Finali**: Mostra un riepilogo dettagliato delle VM create, delle mappature NAT e dei comandi di connessione SSH.

Per una descrizione più dettagliata del flusso di creazione delle VM e del deployment, consultare:
- **[Deployment Flow Documentation](DEPLOYMENT_FLOW.md)**
- **[VM Creation Flow Diagram](terraform-opentofu/vm_creation_flow.md)**

## 📂 Struttura del Progetto

```
.gitignore
add_ssh_nat_rules2.yml
configure-vm.yml
deploy_main.sh
DEPLOYMENT_FLOW.md
k3s_install.yml
main.tf
readme.md
requirements.yml
tofu-workflow.sh
variables.tf
vm_creation_flow.md
wait_for_vm.sh

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
├── inventory-nat-rules.ini  # Generato dinamicamente
└── ssh_connections.ini      # Generato dinamicamente

templates/
├── inventory-nat-rules.ini.j2
└── ssh_inventory.ini.j2

# Altri file generati/ignorati:
.terraform/
*.tfstate*
logs/
```

## ⚙️ Configurazione

Le variabili di configurazione principali sono definite in `variables.tf` e possono essere sovrascritte in `terraform.tfvars`.

### `variables.tf`

Questo file definisce tutte le variabili che possono essere utilizzate nel progetto OpenTofu, inclusi i loro tipi, descrizioni e valori di default. È la fonte della verità per le configurazioni disponibili.

### `terraform.tfvars`

Questo file è il luogo dove si specificano i valori effettivi per le variabili definite in `variables.tf`. **Non dovrebbe essere committato nel controllo versione** (è già ignorato dal `.gitignore`) in quanto contiene configurazioni specifiche dell'ambiente o credenziali sensibili.

Esempi di variabili chiave che puoi configurare:

-   `vm_count`: Numero di VM da creare. (es. `vm_count = 3`)
-   `deployment_delay`: Ritardo in secondi tra la creazione di VM consecutive per evitare sovraccarichi sul Proxmox host. (es. `deployment_delay = 30`)
-   `vm_name_prefix`: Prefisso utilizzato per nominare le VM. (es. `vm_name_prefix = "ubuntu-opentofu"`)
-   `vm_configs`: Una mappa complessa per personalizzare le risorse (CPU, RAM, disco) di singole VM. Utile per creare VM con specifiche diverse all'interno dello stesso deployment.

Esempio `terraform.tfvars`:

```hcl
vm_count = 2
deployment_delay = 30
vm_name_prefix = "ubuntu-opentofu"

vm_configs = {
  "web-server-1" = {
    cores     = 4
    memory    = 16384
    disk_size = "128G"
  }
  "db-server-1" = {
    cores     = 2
    memory    = 8192
    disk_size = "256G"
  }
}
```

## 🚀 Utilizzo

### Prerequisiti

Prima di eseguire il deployment, assicurati di avere i seguenti strumenti installati e configurati correttamente:

-   **Proxmox VE server**: Un server Proxmox VE funzionante con l'API abilitata. Assicurati di avere un utente Proxmox con permessi API sufficienti per creare e gestire VM e configurare le regole di rete.
-   **OpenTofu**: Installato e configurato sul tuo sistema locale. Puoi trovare la guida all'installazione ufficiale [qui](https://opentofu.org/docs/cli/install/).
    -   Verifica l'installazione: `tofu --version`
-   **Ansible**: Installato sul tuo sistema locale. Puoi installarlo tramite pip: `pip install ansible`.
    -   Verifica l'installazione: `ansible --version`
-   **`jq`**: Un parser JSON da riga di comando, utilizzato per elaborare l'output di OpenTofu. Installalo tramite il tuo gestore di pacchetti (es. `brew install jq` su macOS, `sudo apt-get install jq` su Debian/Ubuntu).
    -   Verifica l'installazione: `jq --version`
-   **Chiave SSH**: Una chiave SSH privata (`id_rsa` o simile) configurata per l'accesso al Proxmox host e, successivamente, alle VM create. Il percorso della chiave deve essere specificato nel file di inventory principale.

### Esecuzione del Deployment

Per avviare il processo di deployment, esegui lo script principale dalla directory radice del progetto:

```bash
./deploy_main.sh [OPZIONI]
```

**Opzioni della Riga di Comando:**

-   `--force-redeploy`: Forza un nuovo deployment anche se un `terraform.tfstate` esistente indica che le risorse sono già state create. Utile per ricreare l'ambiente da zero.
-   `--continue-if-deployed`: Permette allo script di continuare l'esecuzione anche se il deployment sembra essere già stato eseguito. Utile per riprendere un'esecuzione interrotta o per applicare solo le fasi di configurazione.
-   `--skip-nat`: Salta la fase di configurazione delle regole NAT sul Proxmox host. Le VM verranno create ma non saranno accessibili tramite port forwarding.
-   `--skip-ansible`: Salta tutte le fasi di configurazione Ansible. Le VM verranno create e inizializzate, ma non verrà eseguita alcuna configurazione post-deployment (es. installazione K3s).
-   `--workspace NOME`: Specifica un nome per il workspace OpenTofu. Questo permette di isolare gli stati di deployment per diversi ambienti (es. `dev`, `staging`, `production`). Se il workspace non esiste, verrà creato.
-   `--auto-approve`: Approva automaticamente le modifiche proposte da OpenTofu (`tofu apply -auto-approve`), evitando la richiesta di conferma manuale.
-   `-h`, `--help`: Mostra un messaggio di aiuto con tutte le opzioni disponibili e gli esempi di utilizzo.

**Esempi di Utilizzo:**

```bash
# Esegue un deployment completo, approvando automaticamente le modifiche e continuando se già deployato
./deploy_main.sh --auto-approve --continue-if-deployed

# Forza un nuovo deployment da zero, saltando la configurazione NAT
./deploy_main.sh --force-redeploy --skip-nat

# Esegue il deployment in un workspace specifico chiamato 'production', con approvazione automatica
./deploy_main.sh --workspace production --auto-approve
```

### Output Generati

Durante e dopo il deployment, il progetto genera diversi file utili per la gestione e il debug:

-   `inventories/inventory-nat-rules.ini`: Un file di inventory Ansible che viene aggiornato dinamicamente con le mappature delle porte NAT assegnate alle VM. Contiene dettagli come `vm_id`, `vm_name`, `vm_ip`, `vm_port`, `service` e `host_port`.
-   `ssh_connections.ini`: Un file di inventory Ansible dedicato specificamente alle connessioni SSH alle VM. Include le porte NATtate per SSH, il nome utente, l'host e il percorso della chiave SSH privata, oltre alla porta esterna per l'API K3s (se applicabile).
-   `/tmp/vm_<VMID>_ip.txt`: Per ogni VM creata, questo file temporaneo contiene l'indirizzo IP privato scoperto dopo l'avvio.
-   `/tmp/vm_<VMID>_summary.txt`: Contiene un riepilogo del deployment e informazioni di debug dettagliate per ogni VM, generate dallo script `wait_for_vm.sh`.

## 🔗 Connessione alle VM

Dopo un deployment riuscito, la sezione finale dell'output di `deploy_main.sh` fornirà un riepilogo dettagliato delle VM, inclusi i comandi SSH diretti per connettersi a ciascuna di esse. È anche possibile utilizzare il file `ssh_connections.ini` con Ansible per gestire le VM:

```bash
# Esempio di connessione SSH diretta (dall'output dello script):
ssh -i /path/to/your/key -p <host_port_ssh> <user>@<proxmox_host_ip>

# Esempio di utilizzo con Ansible per testare la connettività:
ansible -i ssh_connections.ini <nome_vm> -m ping

# Esempio di esecuzione di un comando remoto con Ansible:
ansible -i ssh_connections.ini <nome_vm> -a "hostname" # Esegue 'hostname' sulla VM
```

##  troubleshooting

### `sudo: a password is required` durante la configurazione NAT

**Problema**: L'esecuzione del playbook Ansible per le regole NAT fallisce con un errore `sudo: a password is required`.

**Causa**: Questo accade perché il playbook Ansible tenta di eseguire operazioni con privilegi di root (`become: true`) sul `localhost` (la macchina da cui stai eseguendo lo script), ma non ha una password per `sudo`.

**Soluzione**: Assicurati che il task Ansible che modifica i file locali (come `inventory-nat-rules.ini` o `ssh_connections.ini`) abbia `become: false` esplicitamente impostato. Questo indica ad Ansible di non usare `sudo` per quel task specifico, poiché non sono necessari privilegi di root per modificare file nella tua directory utente.

### `git filter-repo` fallisce o non è trovato

**Problema**: Il comando `git filter-repo` non viene riconosciuto o fallisce durante la riscrittura della cronologia.

**Causa**: `git filter-repo` potrebbe non essere installato o non essere nel PATH del tuo sistema.

**Soluzione**: Installa `git filter-repo` utilizzando il tuo gestore di pacchetti preferito. Ad esempio:
-   **Python pip**: `pip install git-filter-repo`
-   **macOS Homebrew**: `brew install git-filter-repo`

### Problemi di Connettività SSH alle VM

**Problema**: Non riesci a connetterti via SSH alle VM dopo il deployment.

**Causa Possibile**: Le regole NAT potrebbero non essere state applicate correttamente, il firewall del Proxmox host potrebbe bloccare le connessioni, o la VM potrebbe non aver avviato correttamente il servizio SSH.

**Soluzione**: 
1.  **Verifica le Regole NAT**: Controlla l'output del deployment per assicurarti che le regole NAT siano state configurate con successo. Puoi anche accedere al Proxmox host e verificare manualmente le regole `iptables` (`iptables -t nat -L PREROUTING`).
2.  **Firewall Proxmox**: Assicurati che il firewall del Proxmox host non stia bloccando le porte che hai mappato. Potrebbe essere necessario aggiungere regole per consentire il traffico in ingresso sulle porte NATtate.
3.  **Stato VM**: Verifica lo stato della VM sul Proxmox VE UI. Assicurati che sia in esecuzione e che il servizio SSH sia attivo all'interno della VM.
4.  **Chiave SSH**: Controlla che la chiave SSH specificata sia corretta e che tu stia usando il percorso completo e i permessi corretti (`chmod 400 your_key_file`).

## ⚠️ Note sulla Riscrittura della Cronologia Git

Questo progetto ha subito una riscrittura della cronologia Git per rimuovere tutti i file `.ini` dai commit passati. Questa è un'operazione **distruttiva** e **irreversibile**.

-   Se hai clonato il repository prima di questa modifica, potresti dover **eliminare la tua copia locale e clonare nuovamente** il repository.
-   Se stai collaborando, assicurati che tutti i membri del team siano a conoscenza di questa modifica e aggiornino i loro repository di conseguenza.
-   Dopo la riscrittura, dovrai **riaggiungere il tuo remote `origin`** (se rimosso da `git filter-repo`) e poi eseguire un `git push --force` per aggiornare il repository remoto.

## 📚 Riferimenti

-   [OpenTofu Documentation](https://opentofu.org/docs/)
-   [BPG Proxmox Provider](https://registry.terraform.io/providers/bpg/proxmox/latest) - Provider OpenTofu/Terraform per Proxmox.
-   [Ansible Documentation](https://docs.ansible.com/)
