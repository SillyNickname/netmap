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
# Instala o Python, pip, módulos de venv e ferramentas de rede:
sudo apt install -y python3 python3-pip python3-venv python3-full iputils-ping curl
# Em algumas versões do Ubuntu (ex: 22.04 ou 24.04), garanta o pacote venv da sua versão específica:
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
sudo apt install -y "python${PY_VER}-venv"
```

### Passo 2: Copiar os Arquivos para o Diretório de Produção
```bash
sudo mkdir -p /opt/netmap/data
sudo cp -r netmap static templates run.py requirements.txt sample_hosts.csv netmap.cfg /opt/netmap/
cd /opt/netmap
```

### Passo 3: Criar o Ambiente Virtual e Instalar Bibliotecas
```bash
# Cria o ambiente virtual isolado:
sudo python3 -m venv /opt/netmap/.venv

# (Caso o pip não venha por padrão no venv do seu Ubuntu, inicialize com ensurepip):
sudo /opt/netmap/.venv/bin/python3 -m ensurepip --default-pip 2>/dev/null || true

# Instala as bibliotecas do NetMap usando o pip do ambiente virtual:
sudo /opt/netmap/.venv/bin/python3 -m pip install --upgrade pip
sudo /opt/netmap/.venv/bin/python3 -m pip install -r /opt/netmap/requirements.txt
```

> **💡 Como executar ou testar manualmente no terminal:**
> Sempre utilize o Python do ambiente virtual para não haver conflito com o Python do sistema operacional:
> ```bash
> # Opção A: Executar diretamente com o Python do venv:
> sudo /opt/netmap/.venv/bin/python3 /opt/netmap/run.py
>
> # Opção B: Ativar o venv na sessão do terminal antes de rodar:
> cd /opt/netmap
> source .venv/bin/activate
> python3 run.py
> ```
> *(Nota: O script `run.py` também detecta e ativa automaticamente o `.venv` local caso você o execute no diretório do projeto).*

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

## 🌐 Configuração com Nginx (Proxy Reverso & HTTPS)

O NetMap foi desenvolvido para funcionar tanto na raiz de um domínio (`https://netmap.exemplo.com/`) quanto em um **subdiretório compartilhado** (ex: `https://servidor.exemplo.com/netmap/`).

### Cenário A: Executar sob um Subdiretório (ex: `/netmap/`)

Para hospedar o NetMap sob um subcaminho como `https://<hostname>/netmap/` conectado a `http://<host_ip>:8080/`:

Adicione o bloco abaixo dentro do seu bloco `server { ... }` existente no Nginx:

```nginx
# Redireciona /netmap sem barra para /netmap/
location = /netmap {
    return 301 /netmap/;
}

# Proxy reverso para o NetMap sob /netmap/
location /netmap/ {
    # ATENÇÃO: A barra final em http://127.0.0.1:8080/ é fundamental para reescrever a URI
    proxy_pass http://127.0.0.1:8080/;

    # Cabeçalhos padrão de proxy reverso
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Informa ao NetMap o prefixo do subdiretório
    proxy_set_header X-Forwarded-Prefix /netmap;

    # Suporte a HTTP/1.1 e WebSockets
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    # Timeouts recomendados para sondagens de longa duração
    proxy_connect_timeout 60s;
    proxy_read_timeout 120s;
}
```

> **Como funciona:**
> 1. O cabeçalho `X-Forwarded-Prefix /netmap` faz com que o NetMap ajuste dinamicamente todos os links de páginas, APIs (`/netmap/api/...`), arquivos estáticos (`/netmap/static/...`), exportação CSV e cookies de autenticação (`Path=/netmap`).
> 2. Opcionalmente, você também pode configurar `url_prefix = /netmap` no arquivo `netmap.cfg` (ou na aba de Configurações no painel de administração).

---

### Cenário B: Executar na Raiz do Domínio (ex: `netmap.seu-dominio.com`)

Se desejar um domínio ou subdomínio dedicado:

Crie `/etc/nginx/sites-available/netmap`:
```nginx
server {
    listen 80;
    server_name netmap.seu-dominio.com; # ou o IP do servidor

    location / {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Suporte a HTTP/1.1 e WebSockets
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Ativar o Site e Recarregar o Nginx
```bash
sudo ln -s /etc/nginx/sites-available/netmap /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### (Opcional) Gerar Certificado SSL Gratuito com Certbot
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
