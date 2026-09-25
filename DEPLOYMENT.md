# NetMap - Guia de Implantação no Ubuntu Server / Deployment Guide

Este guia detalha o processo de instalação e implantação do **NetMap** em servidores **Ubuntu** (Ubuntu 20.04 LTS, 22.04 LTS, 24.04 LTS e superiores), utilizando o gerenciador de pacotes nativo **`apt`**, ambientes virtuais do **Python (`venv`)** e **`systemd`** para execução em segundo plano com inicialização automática.

---

## ⚡ Método 1: Instalação Automática (Recomendado)

O script [`install.sh`](file:///home/kajita/git/netmap/install.sh) automatiza 100% da instalação: instala os pacotes do sistema via `apt`, cria o ambiente virtual isolado, instala as bibliotecas via `pip` e registra o serviço no `systemd`.

### 1. Clonar ou Transferir os Arquivos para o Servidor Ubuntu
```bash
# Exemplo via git ou scp
git clone <URL_DO_REPOSITORIO> netmap
cd netmap
```

### 2. Executar o Instalador
```bash
sudo ./install.sh
```

> **Opção de instalação no diretório atual:**
> Se preferir rodar a partir do diretório onde os arquivos já estão em vez de `/opt/netmap`, execute:
> ```bash
> sudo ./install.sh --in-place
> ```

O instalador irá:
1. Executar `apt-get update` e instalar `python3`, `python3-pip`, `python3-venv` e `iputils-ping`.
2. Criar a estrutura em `/opt/netmap`.
3. Criar o ambiente virtual Python em `/opt/netmap/.venv`.
4. Instalar todas as dependências (`fastapi`, `uvicorn`, `aiosqlite`, `bcrypt`, etc.).
5. Criar e iniciar o serviço de sistema `netmap.service`.

---

## 🛠️ Método 2: Instalação Manual Passo a Passo

Caso prefira executar cada etapa manualmente:

### Passo 1: Atualizar o Sistema e Instalar Pacotes com `apt`
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv iputils-ping curl
```

### Passo 2: Copiar os Arquivos para o Diretório de Produção
```bash
sudo mkdir -p /opt/netmap/data
sudo cp -r netmap static templates run.py requirements.txt sample_hosts.csv netmap.cfg /opt/netmap/
cd /opt/netmap
```

### Passo 3: Criar o Ambiente Virtual e Instalar Bibliotecas com `pip`
```bash
sudo python3 -m venv /opt/netmap/.venv
sudo /opt/netmap/.venv/bin/pip install --upgrade pip
sudo /opt/netmap/.venv/bin/pip install -r /opt/netmap/requirements.txt
```

### Passo 4: Registrar o Serviço no `systemd`
Crie o arquivo de serviço `/etc/systemd/system/netmap.service`:
```bash
sudo tee /etc/systemd/system/netmap.service > /dev/null << 'EOF'
[Unit]
Description=NetMap - Network Tree Status Monitor
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/netmap
ExecStart=/opt/netmap/.venv/bin/python3 /opt/netmap/run.py
Restart=always
RestartSec=5s

LimitNOFILE=65536
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
SyslogIdentifier=netmap

[Install]
WantedBy=multi-user.target
EOF
```

### Passo 5: Iniciar e Habilitar o Serviço
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now netmap
```

---

## 🛡️ Configuração de Firewall (UFW)

Para permitir acesso à porta do NetMap (padrão `8080`):
```bash
sudo ufw allow 8080/tcp comment "NetMap Web Monitor"
sudo ufw reload
```

---

## 🌐 Configuração Opcional com Nginx (Proxy Reverso & HTTPS)

Se desejar disponibilizar o NetMap na porta padrão `80`/`443` com domínio e certificado SSL (Let's Encrypt):

### 1. Instalar o Nginx
```bash
sudo apt install -y nginx
```

### 2. Criar Configuração de Site no Nginx
Crie `/etc/nginx/sites-available/netmap`:
```nginx
server {
    listen 80;
    server_name netmap.seu-dominio.com; # ou o IP do servidor

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Suporte a WebSockets / SSE
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3. Ativar o Site e Recarregar o Nginx
```bash
sudo ln -s /etc/nginx/sites-available/netmap /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4. (Opcional) Gerar Certificado SSL Gratuito com Certbot
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d netmap.seu-dominio.com
```

---

## 📋 Comandos de Gerenciamento do Serviço

| Ação | Comando |
|---|---|
| **Verificar Status** | `sudo systemctl status netmap` |
| **Reiniciar Serviço** | `sudo systemctl restart netmap` |
| **Parar Serviço** | `sudo systemctl stop netmap` |
| **Iniciar Serviço** | `sudo systemctl start netmap` |
| **Ver Logs em Tempo Real** | `sudo journalctl -u netmap -f` |

---

## 💾 Backup e Restauração

Todos os dados persistentes ficam contidos em dois arquivos:
1. `data/hosts.db` (Inventário, topologia, grupos e usuários)
2. `data/history.db` (Série temporal de histórico de pings)
3. `netmap.cfg` (Configurações do sistema)

Para fazer backup:
```bash
sudo tar -czvf netmap-backup-$(date +%F).tar.gz /opt/netmap/data /opt/netmap/netmap.cfg
```

---

## 🗑️ Desinstalação

Para remover o serviço do servidor:
```bash
sudo /opt/netmap/uninstall.sh
```
Ou manualmente:
```bash
sudo systemctl stop netmap
sudo systemctl disable netmap
sudo rm -f /etc/systemd/system/netmap.service
sudo systemctl daemon-reload
```
