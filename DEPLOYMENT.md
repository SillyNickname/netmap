# NetMap - Guia de Implantação no Ubuntu e Linux / Deployment Guide

> **Desenvolvido por / Developed by:** Antigravity (Google DeepMind)  
> **Requisitado e comissionado por / Requested and commissioned by:** Andre Kajita (<kajita@univap.br>)

Este guia detalha o processo de instalação, configuração de portas/IP binding, serviços de inicialização/parada/reinicialização e implantação em produção do **NetMap** em servidores **Ubuntu** e nas principais distribuições Linux (Debian, RHEL, CentOS, Rocky Linux, AlmaLinux, Fedora, openSUSE, Alpine, Arch), utilizando ambientes nativos **sem Docker**.

---

## ⚡ Método 1: Instalação Automática e Interativa (Recomendado)

O script [`install.sh`](file:///Extra/git/netmap/install.sh) automatiza 100% da instalação: instala os pacotes do sistema pelo gerenciador nativo da distribuição (`apt`, `dnf`, `yum`, `zypper`, `pacman`, `apk`), cria o ambiente virtual Python isolado, configura o endereço IP de escuta, porta e prefixo de URL para proxy reverso, e registra o serviço de inicialização automática.

### 1. Clonar ou Transferir os Arquivos para o Servidor
```bash
git clone https://git.fve.edu.br/kajita/netmap.git
cd netmap
```

### 2. Executar o Instalador

#### Modo Interativo (Padrão)
Se executado diretamente no terminal, o instalador perguntará interativamente os parâmetros de rede com valores padrão sugeridos:
```bash
sudo ./install.sh
```
Perguntas interativas:
- **IP Binding address** [padrão: `0.0.0.0`]: Defina `0.0.0.0` para escutar em todas as interfaces de rede, ou `127.0.0.1` para escutar apenas localmente para o proxy reverso.
- **Port number** [padrão: `8080`]: Porta TCP onde o NetMap irá operar.
- **URL subpath prefix** [padrão: `/netmap`]: Prefixo de URL do proxy reverso (ex: `/netmap` para acessar via `https://<seu-dominio>/netmap`).

#### Modo Não-Interativo via Linha de Comando (Flags)
Você pode passar todos os parâmetros diretamente via argumentos:
```bash
# Exemplo 1: Escutar em 0.0.0.0 na porta 8080 sob /netmap (Padrão):
sudo ./install.sh --host 0.0.0.0 --port 8080 --prefix /netmap -y

# Exemplo 2: Escutar apenas em localhost (127.0.0.1) na porta 8080 sob /netmap:
sudo ./install.sh --host 127.0.0.1 --port 8080 --prefix /netmap -y

# Exemplo 3: Instalação no diretório atual (in-place):
sudo ./install.sh --in-place --port 8080 --prefix /netmap -y
```

### Opções Disponíveis do Instalador:
| Parâmetro | Descrição | Valor Padrão |
|---|---|---|
| `--host <IP>` | Endereço IP de escuta (bind IP) | `0.0.0.0` |
| `--port <PORT>` | Porta TCP de escuta | `8080` |
| `--prefix <PATH>` | Prefixo de subdiretório para Nginx | `/netmap` |
| `--dir <PATH>` | Diretório de instalação | `/opt/netmap` |
| `--in-place` | Instala no diretório atual | Desativado |
| `-y`, `--yes` | Modo não interativo (não faz perguntas) | Desativado |
| `-h`, `--help` | Exibe a ajuda com todas as opções | — |

---

## 🕹️ Controle de Serviço: Inicialização, Parada e Reinicialização

O NetMap disponibiliza comandos convenientes que funcionam a partir de qualquer diretório do terminal, além da integração com `systemd`:

### 1. Comando Unificado `netmap` (CLI Global)
Durante a instalação, o utilitário `/usr/local/bin/netmap` é registrado no sistema:

```bash
# Iniciar o servidor NetMap
sudo netmap start

# Parar o servidor NetMap
sudo netmap stop

# Reiniciar o servidor NetMap
sudo netmap restart

# Verificar status detalhado e teste de resposta da API
sudo netmap status

# Visualizar logs em tempo real
sudo netmap logs

# Exibir a configuração exata recomendada para o Nginx
netmap nginx
```

### 2. Comandos Nativos do `systemd` (Ubuntu, Debian, RHEL, CentOS, Rocky, Fedora, openSUSE)
```bash
sudo systemctl start netmap
sudo systemctl stop netmap
sudo systemctl restart netmap
sudo systemctl status netmap
sudo journalctl -u netmap -f
```

### 3. Scripts Autônomos (Diretório `scripts/`)
Para ambientes sem systemd (containers, chroots, etc.):
```bash
/opt/netmap/scripts/start.sh    # Inicia como daemon em segundo plano
/opt/netmap/scripts/stop.sh     # Encerra o processo de forma graciosa
/opt/netmap/scripts/restart.sh  # Reinicia o processo
/opt/netmap/scripts/status.sh   # Verifica PID e porta de escuta
```

---

## 🌐 Configuração do Proxy Reverso com Nginx

O NetMap foi projetado especificamente para rodar sob domínios genéricos com um subdiretório (ex: `https://<seu-dominio>/netmap`).

### 1. Gerar o Bloco de Configuração do Nginx Automaticamente
Você pode gerar o bloco de configuração sob medida para a sua instalação a qualquer momento com:
```bash
netmap nginx
```

### 2. Adicionar ao Bloco `server { ... }` do seu Nginx
Abra o arquivo de configuração do seu site no Nginx (ex: `/etc/nginx/sites-available/default` ou `/etc/nginx/sites-available/seu-site`):

```nginx
# Redireciona /netmap sem barra final para /netmap/
location = /netmap {
    return 301 /netmap/;
}

# Proxy reverso para o NetMap sob /netmap/
location /netmap/ {
    # ATENÇÃO: A barra final em http://127.0.0.1:8080/ é essencial para reescrever a URI
    proxy_pass http://127.0.0.1:8080/;

    # Cabeçalhos padrão de encaminhamento
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Informa ao NetMap seu prefixo para montagem correta de rotas, assets e cookies
    proxy_set_header X-Forwarded-Prefix /netmap;

    # Suporte a WebSockets e HTTP/1.1
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    # Timeouts recomendados para sondagens de rede
    proxy_connect_timeout 60s;
    proxy_read_timeout 120s;
}

# Bloco Opcional para Daemon Remoto de Speedtest:
# Se você estiver executando o daemon de speedtest em um servidor remoto dedicado (ex: 192.168.10.50:8081):
location /netmap/speedtest/target/ {
    proxy_pass http://192.168.10.50:8081/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Essencial para medição precisa de taxa de transferência:
    gzip off;
    proxy_buffering off;
    proxy_request_buffering off;
    client_max_body_size 100M;
}
```

> **Por que a barra final em `proxy_pass http://127.0.0.1:8080/;` é fundamental?**
> No Nginx, adicionar a barra final (`/`) no `proxy_pass` faz com que o prefixo `/netmap/` seja removido antes do envio ao backend local. Combinado com o cabeçalho `X-Forwarded-Prefix /netmap` e o middleware ASGI do NetMap, todas as rotas da API (`/netmap/api/...`), arquivos estáticos (`/netmap/static/...`), exportação CSV e cookies de sessão (`Path=/netmap`) funcionam com 100% de compatibilidade e sem conflitos.

### 3. Testar e Recarregar o Nginx
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🛠️ Método 2: Instalação Manual Passo a Passo

Caso prefira executar cada etapa manualmente:

### Passo 1: Instalar Dependências do Sistema
- **Ubuntu / Debian**:
  ```bash
  sudo apt update
  sudo apt install -y python3 python3-pip python3-venv python3-full iputils-ping curl
  ```
- **RHEL / Rocky Linux / AlmaLinux / CentOS**:
  ```bash
  sudo dnf install -y python3 python3-pip iputils curl
  ```

### Passo 2: Copiar os Arquivos
```bash
sudo mkdir -p /opt/netmap/data
sudo cp -r netmap static templates scripts run.py requirements.txt sample_hosts.csv netmap.cfg /opt/netmap/
sudo chmod -R 755 /opt/netmap
sudo chmod +x /opt/netmap/scripts/*
sudo ln -sf /opt/netmap/scripts/netmap-ctl /usr/local/bin/netmap
```

### Passo 3: Configurar o Ambiente Virtual Python
```bash
sudo python3 -m venv /opt/netmap/.venv
sudo /opt/netmap/.venv/bin/python3 -m pip install --upgrade pip
sudo /opt/netmap/.venv/bin/python3 -m pip install -r /opt/netmap/requirements.txt
```

### Passo 4: Registrar o Serviço no `systemd`
Crie o arquivo `/etc/systemd/system/netmap.service`:
```ini
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
```

### Passo 5: Ativar e Iniciar o Serviço
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now netmap
```

---

## 🛰️ Daemon Autônomo de Teste de Velocidade / Standalone Speedtest Daemon

O NetMap inclui um daemon assíncrono ultraleve (`netmap.speedtest_daemon`) que pode ser executado em um servidor remoto dedicado para medição de throughput (Download/Upload de 5 segundos e Latência/Jitter) sem compressão e sem overhead de banco de dados.

### 1. Iniciar Manualmente no Servidor Remoto
```bash
# Execução direta com o launcher incluído:
/opt/netmap/scripts/netmap-speedtest-daemon --host 0.0.0.0 --port 8081

# Ou invocando diretamente o módulo Python:
python3 -m netmap.speedtest_daemon --host 0.0.0.0 --port 8081
```

### 2. Configurar como Serviço `systemd` no Servidor Remoto
Crie o arquivo `/etc/systemd/system/netmap-speedtest.service` no servidor remoto:
```ini
[Unit]
Description=NetMap Speedtest Standalone Daemon
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/netmap
ExecStart=/opt/netmap/.venv/bin/python3 -m netmap.speedtest_daemon --host 0.0.0.0 --port 8081
Restart=always
RestartSec=3s
LimitNOFILE=65536
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
SyslogIdentifier=netmap-speedtest

[Install]
WantedBy=multi-user.target
```

Ative e inicie o serviço no servidor remoto:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now netmap-speedtest
sudo systemctl status netmap-speedtest
```

### 3. Configurar no Servidor Principal NetMap
No servidor principal do NetMap onde está o Nginx:
1. No arquivo `/etc/nginx/sites-available/...`, adicione o bloco de proxy apontando para o IP do servidor remoto:
   ```nginx
   location /netmap/speedtest/target/ {
       proxy_pass http://<IP_DO_SERVIDOR_REMOTO>:8081/;
       proxy_http_version 1.1;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       gzip off;
       proxy_buffering off;
       proxy_request_buffering off;
       client_max_body_size 100M;
   }
   ```
2. Recarregue o Nginx: `sudo nginx -t && sudo systemctl reload nginx`
3. No arquivo `/opt/netmap/netmap.cfg` (ou na aba **Configurações / Settings** do painel de administração):
   ```ini
   [speedtest]
   enabled = true
   server_url = /netmap/speedtest/target
   duration_seconds = 5
   visitor_cooldown_hours = 2
   ```

---

## 🛡️ Firewall (UFW / Firewalld)

Se o Nginx e o NetMap estiverem no mesmo servidor e você configurou o bind para `127.0.0.1`, você só precisa abrir as portas HTTP/HTTPS no firewall:
```bash
# Ubuntu (UFW)
sudo ufw allow 80/tcp comment "HTTP Nginx"
sudo ufw allow 443/tcp comment "HTTPS Nginx"
sudo ufw reload
```

Se o NetMap estiver em um servidor interno dedicado e escutando em `0.0.0.0:8080`:
```bash
# Permitir apenas tráfego vindo do IP do servidor de Proxy Reverso:
sudo ufw allow from <IP_DO_NGINX> to any port 8080 proto tcp comment "NetMap from Reverse Proxy"
sudo ufw reload
```

---

## 🔒 Credenciais Padrão e Segurança em Produção

1. **Acesso Inicial**:
   - URL: `https://<seu-dominio>/netmap/`
   - Painel Admin: `https://<seu-dominio>/netmap/admin`
   - Usuário Administrador: `admin` / Senha: `admin123`
   - Usuário Operador: `operator` / Senha: `operator123`

2. **Alteração de Senha**:
   - Faça login no painel de administração (`/admin`), vá até a aba **Usuários** e altere as senhas das contas padrão.
   - O NetMap possui proteção integrada contra bloqueio acidental: impede a exclusão ou rebaixamento da última conta de administrador.

3. **Chave Secreta**:
   - Altere o parâmetro `secret_key` no arquivo `netmap.cfg` para uma sequência alfanumérica aleatória longa.

---

## 💾 Backup e Restauração

Todos os dados persistentes ficam contidos em:
1. `data/hosts.db` (Inventário, hierarquia e contas)
2. `data/history.db` (Histórico de disponibilidade e latência)
3. `netmap.cfg` (Configurações)

### Criar Backup:
```bash
sudo tar -czvf /backup/netmap-backup-$(date +%F).tar.gz -C /opt/netmap data netmap.cfg
```

### Restaurar Backup:
```bash
sudo netmap stop
sudo tar -xzvf /backup/netmap-backup-YYYY-MM-DD.tar.gz -C /opt/netmap/
sudo netmap start
```

---

## 🗑️ Desinstalação

Para desinstalar o serviço e remover os arquivos:
```bash
sudo /opt/netmap/uninstall.sh
```

---

## 👥 Créditos e Autoria / Authorship & Credits

- **Desenvolvedor / Developer**: Antigravity (Google DeepMind)
- **Requisitado e comissionado por / Requested & Commissioned by**: Andre Kajita (<kajita@univap.br>)
- **Instituição / Institution**: Universidade do Vale do Paraíba (UNIVAP)

