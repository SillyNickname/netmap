/**
 * NetMap - Network Tree Status Monitor (i18n Module)
 * Developed by: Antigravity (Google DeepMind)
 * Requested and commissioned by: Andre Kajita <kajita@univap.br>
 * Default language: pt-BR (Brazilian Portuguese)
 */

const TRANSLATIONS = {
    "pt-BR": {
        // App header
        "brand_subtitle": "Admin",
        "stat_total": "Total:",
        "stat_up": "● ONLINE:",
        "stat_down": "● OFFLINE:",
        "stat_uptime": "Disponibilidade:",
        "btn_force_poll": "⚡ Forçar Sondagem",
        "btn_sign_in": "Entrar",
        "btn_logout": "Sair",
        "btn_admin": "⚙️ Administração",
        "back_to_tree": "← Voltar ao Mapa",

        // Toolbar
        "label_locations": "LOCAIS:",
        "all_sites": "Todos os Locais",
        "last_polled": "Última Sondagem:",
        "next_poll": "Próxima Sondagem:",
        "btn_refresh": "↻ Atualizar",
        "polling_now": "Sondando...",
        "density_label": "Modo:",
        "density_compact": "Compacto (20px)",
        "density_tall": "Expandido",
        "locations_collapse_label": "Locais:",
        "btn_collapse_all": "⇲ Recolher Todos",
        "btn_expand_all": "⇱ Expandir Todos",
        "pin_tooltip": "Fixar no topo",
        "unpin_tooltip": "Desafixar do topo",

        // Tree
        "loading_hierarchy": "Carregando topologia da rede...",
        "no_hosts_title": "Nenhum Dispositivo Cadastrado",
        "no_hosts_desc": "Comece entrando como administrador para cadastrar seus dispositivos ou carregar um arquivo CSV.",
        "btn_sign_in_admin": "Entrar como Administrador",
        "no_roots": "Nenhum dispositivo raiz neste local.",
        "hosts_count_suffix": "dispositivos",
        "click_timeline_tooltip": "Clique para ver histórico completo de 24h+",
        "status_up": "ONLINE",
        "status_down": "OFFLINE",
        "status_unknown": "DESCONHECIDO",
        "status_timeout": "Tempo Esgotado",
        "status_partially_up": "Parcialmente Ativo",
        "group_degraded": "Parcialmente Ativo",
        "click_group_tooltip": "Clique para ver membros e status do grupo",
        "modal_group_title": "Agrupamento de Dispositivos",
        "group_status_label": "Status do Grupo:",
        "aggregation_mode_label": "Modo de Agregação:",
        "member_hosts_title": "Dispositivos Membros",
        "th_latency": "Latência / RTT",
        "btn_view_timeline": "Ver Histórico",

        // Timeline Modal
        "modal_timeline_title": "Histórico do Dispositivo",
        "uptime_label": "Disponibilidade",
        "total_checks": "Total de Verificações:",
        "successful_checks": "Com Sucesso:",
        "failed_checks": "Falhas:",
        "hours_ago": "Horas Atrás",
        "now": "Agora",
        "incidents_title": "Incidentes de Indisponibilidade",
        "th_started": "Início",
        "th_resolved": "Fim",
        "th_duration": "Duração",
        "incident_ongoing": "Em andamento",
        "zero_incidents": "✓ 100% operacional sem incidentes de indisponibilidade neste período.",
        "no_records_window": "Nenhum registro de sondagem na janela selecionada.",
        "ip_label": "IP:",
        "location_label": "Local:",
        "group_label": "Grupo:",
        "parent_label": "Pai:",
        "time_earliest": "Início",
        "time_now": "Mais recente",
        "time_back_6h": "Voltar 6h",
        "time_fwd_6h": "Avançar 6h",
        "time_back_12h": "Voltar 12h",
        "time_fwd_12h": "Avançar 12h",
        "time_back_24h": "Voltar 24h",
        "time_fwd_24h": "Avançar 24h",
        "time_back_48h": "Voltar 48h",
        "time_fwd_48h": "Avançar 48h",
        "stable_period": "Período Estável (ONLINE)",
        "outage_period": "Período de Queda (OFFLINE)",
        "period_start": "Início:",
        "period_end": "Fim:",
        "period_duration": "Duração:",
        "period_checks": "Sondagens consecutivas:",
        "period_unchanging": "sem alteração de estado",
        "avg_latency": "Latência média:",
        "loc_warning_red_title": "Alerta Crítico: {down}/{total} dispositivos offline ({pct}%)",
        "loc_warning_yellow_title": "Alerta de Atenção: {down}/{total} dispositivos offline ({pct}%)",
        "loc_unstable_title": "Alerta de Instabilidade: {count} dispositivo(s) com >10% de queda nas últimas 6h",
        "instability_desc_lime": "Instável: {pct}% de queda nas últimas 6h",
        "instability_desc_yellow": "Alta Instabilidade: {pct}% de queda nas últimas 6h",
        "instability_desc_red": "Instabilidade Crítica: {pct}% de queda nas últimas 6h",

        // Login Modal
        "login_modal_title": "Acessar o NetMap",
        "username_label": "Nome de Usuário",
        "password_label": "Senha",
        "login_btn_submit": "Entrar no Sistema",
        "default_accounts_hint": "Contas padrão: <code>admin / admin123</code> ou <code>operator / operator123</code>",
        "login_error_generic": "Falha na autenticação",
        "login_error_network": "Erro de conexão com o servidor.",
        "welcome_user": "Bem-vindo de volta, ",
        "logged_out_success": "Sessão encerrada com sucesso",
        "auth_required_poll": "Autenticação necessária: Entre com sua conta para forçar a sondagem.",

        // Admin Tabs
        "tab_hosts": "🖥️ Dispositivos",
        "tab_groups": "👥 Grupos",
        "tab_csv": "📂 Importar / Exportar CSV",
        "tab_settings": "⚙️ Configurações (.cfg)",
        "tab_users": "👤 Usuários",
        "tab_maintenance": "🛠️ Manutenção",

        // Admin - Hosts Tab
        "admin_hosts_title": "Dispositivos de Rede & Topologia",
        "admin_hosts_desc": "Gerencie IPs, locais geográficos e a hierarquia pai-filho da topologia.",
        "btn_add_host": "+ Novo Dispositivo",
        "sort_by_label": "Ordenar por:",
        "sort_asc": "Ascendente",
        "sort_desc": "Descendente",
        "th_host_name": "Nome",
        "th_ip_target": "IP / Host",
        "th_location": "Localização (Macro)",
        "th_parent": "Dispositivo Pai (Hierarquia)",
        "th_grouping": "Agrupamento",
        "th_status": "Status",
        "th_actions": "Ações",
        "root_device": "Raiz",
        "active_status": "Ativo",
        "disabled_status": "Desativado",
        "btn_edit": "Editar",
        "btn_delete": "Excluir",
        "confirm_delete_host": "Tem certeza que deseja excluir o dispositivo",

        // Admin - Groups Tab
        "admin_groups_title": "Agrupamentos de Dispositivos",
        "admin_groups_desc": "Agregue múltiplos dispositivos em um único estado consolidado de ONLINE / OFFLINE.",
        "btn_add_group": "+ Novo Grupo",
        "th_group_name": "Nome do Grupo",
        "th_aggregation_mode": "Modo de Agregação",
        "th_assigned_hosts": "Dispositivos Atribuídos",
        "th_description": "Descrição",
        "mode_any": "Qualquer Host ONLINE = Grupo ONLINE (Redundância / HA)",
        "mode_all": "Todos os Hosts ONLINE = Grupo ONLINE (Cluster Estrito)",
        "confirm_delete_group": "Tem certeza que deseja excluir o grupo? Os dispositivos ficarão avulsos.",

        // Admin - CSV Tab
        "csv_import_title": "📥 Importação em Lote via CSV",
        "csv_import_desc": "Envie um arquivo CSV com o inventário da rede. O relacionamento hierárquico e grupos serão resolvidos automaticamente.",
        "csv_select_file": "Selecionar Arquivo CSV",
        "csv_paste_direct": "Ou Cole o Conteúdo CSV Diretamente",
        "csv_purge_label": "Purgar banco de dados antes de importar (substituição completa)",
        "csv_purge_warning": "⚠️ Se marcado, todos os dispositivos e históricos atuais serão apagados permanentemente antes da importação. As contas de usuários serão preservadas.",
        "csv_purge_confirm": "ATENÇÃO: Você marcou a opção de PURGAR o banco de dados. Todos os dispositivos e registros de histórico atuais serão excluídos permanentemente antes de importar o novo arquivo.\n\nDeseja realmente continuar?",
        "csv_purge_success": "Banco de dados purgado com sucesso e {count} novos dispositivos importados!",
        "btn_upload_csv": "🚀 Enviar & Importar Dispositivos",
        "csv_export_title": "📤 Exportação & Modelos",
        "csv_export_desc": "Baixe arquivos de exemplo ou exporte o banco de dados atual.",
        "csv_download_template": "Baixar Modelo de CSV",
        "csv_template_desc": "Arquivo CSV de exemplo pré-formatado com cabeçalhos, hierarquia e grupos.",
        "btn_download_template": "📄 Baixar CSV de Exemplo",
        "csv_export_db": "Exportar Banco de Dados",
        "csv_export_desc_2": "Exporta todos os dispositivos, grupos e relacionamentos cadastrados.",
        "btn_export_db": "💾 Exportar Dispositivos em CSV",

        // Admin - Settings Tab
        "settings_title": "Configuração do Sistema",
        "settings_desc": "As alterações são salvas automaticamente no arquivo <code>netmap.cfg</code> e aplicadas imediatamente ao motor de sondagem.",
        "set_interval_label": "Intervalo de Sondagem Automática (Segundos)",
        "set_threads_label": "Threads / Tarefas de Ping Paralelas",
        "set_timeout_label": "Tempo Limite de Resposta do Ping (Segundos)",
        "set_count_label": "Pacotes por Sondagem (por Host)",
        "set_retention_label": "Retenção de Histórico (Horas, mín 24h)",
        "set_host_label": "Endereço de Escuta (Bind IP)",
        "set_port_label": "Porta TCP do Servidor",
        "set_prefix_label": "Prefixo de URL / Subdiretório (Opcional, ex: /netmap)",
        "set_prefix_hint": "Necessário somente se não usar o cabeçalho X-Forwarded-Prefix no proxy reverso.",
        "btn_save_settings": "💾 Salvar Configurações no netmap.cfg",
        "settings_saved_success": "Configurações salvas no netmap.cfg e aplicadas com sucesso!",

        // Admin - Users Tab
        "users_title": "Gerenciamento de Usuários",
        "users_desc": "Administrador: acesso total ao sistema e banco de dados.<br>Operador: permissão para forçar sondagem na tela principal.",
        "users_create_title": "Cadastrar Nova Conta",
        "users_create_desc": "Adicione um novo operador ou administrador.",
        "th_username": "Usuário",
        "th_role": "Papel",
        "th_created": "Criado em",
        "btn_create_user": "+ Criar Conta",
        "role_operator": "Operador (Pode forçar sondagens)",
        "role_admin": "Administrador (Acesso Completo)",
        "confirm_delete_user": "Tem certeza que deseja excluir o usuário",

        // Admin - Maintenance Tab
        "maint_title": "Saúde dos Bancos de Dados & Armazenamento",
        "maint_desc": "Monitore os bancos <code>hosts.db</code> (inventário) e <code>history.db</code> (série temporal).",
        "db_hosts_label": "BANCO DE DISPOSITIVOS",
        "db_history_label": "BANCO DE HISTÓRICO",
        "db_records_label": "registros temporais indexados",
        "btn_run_prune": "🧹 Executar Limpeza de Histórico Agora",
        "btn_refresh_stats": "↻ Atualizar Estatísticas",

        // Modals - Host Form
        "modal_add_host_title": "Novo Dispositivo",
        "modal_edit_host_title": "Editar Dispositivo",
        "field_host_name": "Nome do Dispositivo *",
        "field_ip": "Endereço IP ou Hostname *",
        "field_location": "Localização (Macro) *",
        "field_parent": "Dispositivo Pai (Hierarquia)",
        "field_parent_none": "-- Nenhum (Dispositivo Raiz) --",
        "field_group": "Agrupamento (Opcional)",
        "field_group_none": "-- Avulso (Sem Grupo) --",
        "field_active": "Ativar Sondagem (Monitorar)",
        "field_desc": "Descrição / Observações",
        "btn_cancel": "Cancelar",
        "btn_save_host": "Salvar Dispositivo",

        // Modals - Group Form
        "modal_add_group_title": "Novo Grupo",
        "modal_edit_group_title": "Editar Grupo",
        "field_group_name": "Nome do Grupo *",
        "field_group_mode": "Modo de Agregação *",
        "field_group_mode_hint": "'Qualquer host ONLINE' é ideal para clusters balanceados ou com redundância (HA).",
        "btn_save_group": "Salvar Grupo",

        // Speedtest
        "nav_speedtest": "🚀 Teste de Velocidade",
        "tab_speedtest": "🚀 Testes de Velocidade",
        "st_cooldown_title": "Intervalo de Espera Ativo para Visitantes",
        "st_cooldown_desc": "Visitantes podem realizar um teste a cada 2 horas. Próximo teste em:",
        "st_cooldown_auth_hint": "(Operadores e Administradores podem entrar para testar sem intervalo).",
        "st_server_target": "Servidor de Teste:",
        "st_ready_msg": "Pronto para iniciar o teste de velocidade",
        "st_realtime_history": "Histórico do Teste em Tempo Real",
        "st_metric_latency": "Latência & Jitter",
        "st_metric_jitter": "Jitter:",
        "st_metric_download": "Download",
        "st_metric_upload": "Upload",
        "st_max": "Máx:",
        "st_btn_start": "🚀 Iniciar Teste de Velocidade",
        "st_phase_ping": "Testando Latência (Ping & Jitter)...",
        "st_phase_download": "Testando Download...",
        "st_phase_upload": "Testando Upload...",
        "st_phase_saving": "Salvando resultados...",
        "st_phase_done": "Teste Concluído com Sucesso!",
        "st_phase_error": "Erro ao executar o teste.",
        "st_cooldown_alert": "Aguarde o período de intervalo para executar um novo teste.",
        "st_your_ip": "Seu IP",
        "st_admin_title": "Histórico de Testes de Velocidade",
        "st_admin_desc": "Consulte e pesquise os testes executados pelos usuários da rede por endereço IP.",
        "st_search_ip_placeholder": "Pesquisar por IP (ex: 192.168.1.50)...",
        "st_filter_btn": "Filtrar",
        "st_clear_btn": "Limpar",
        "st_refresh_btn": "↻ Atualizar",
        "th_st_ip": "IP do Cliente",
        "th_st_timestamp": "Data / Hora",
        "th_st_ping": "Latência / Jitter",
        "th_st_download": "Download (Méd / Máx)",
        "th_st_upload": "Upload (Méd / Máx)",
        "th_st_role": "Tipo de Usuário",
        "th_st_actions": "Ações",
        "st_no_results": "Nenhum resultado de teste de velocidade encontrado.",
        "role_visitor": "Visitante",
        "nav_login": "🔐 Entrar"
    },
    "en": {
        // App header
        "brand_subtitle": "Admin",
        "stat_total": "Total:",
        "stat_up": "● UP:",
        "stat_down": "● DOWN:",
        "stat_uptime": "Uptime:",
        "btn_force_poll": "⚡ Force Poll",
        "btn_sign_in": "Sign In",
        "btn_logout": "Logout",
        "btn_admin": "⚙️ Admin",
        "back_to_tree": "← Back to Tree View",

        // Toolbar
        "label_locations": "LOCATIONS:",
        "all_sites": "All Sites",
        "last_polled": "Last Polled:",
        "next_poll": "Next Poll:",
        "btn_refresh": "↻ Refresh",
        "polling_now": "Polling...",
        "density_label": "View:",
        "density_compact": "Compact (20px)",
        "density_tall": "Comfortable",
        "locations_collapse_label": "Locations:",
        "btn_collapse_all": "⇲ Collapse All",
        "btn_expand_all": "⇱ Expand All",
        "pin_tooltip": "Pin to top",
        "unpin_tooltip": "Unpin from top",

        // Tree
        "loading_hierarchy": "Loading network hierarchy...",
        "no_hosts_title": "No Hosts Configured Yet",
        "no_hosts_desc": "Get started by logging in as an administrator to add your network hosts or upload a CSV file.",
        "btn_sign_in_admin": "Sign In as Admin",
        "no_roots": "No root devices in this location.",
        "hosts_count_suffix": "hosts",
        "click_timeline_tooltip": "Click to view full 24h+ timeline",
        "status_up": "UP",
        "status_down": "DOWN",
        "status_unknown": "UNKNOWN",
        "status_timeout": "Timeout",
        "status_partially_up": "Partially Up",
        "group_degraded": "Partially Up",
        "click_group_tooltip": "Click to view group members and status",
        "modal_group_title": "Device Grouping",
        "group_status_label": "Group Status:",
        "aggregation_mode_label": "Aggregation Mode:",
        "member_hosts_title": "Member Devices",
        "th_latency": "Latency / RTT",
        "btn_view_timeline": "View Timeline",

        // Timeline Modal
        "modal_timeline_title": "Host Timeline",
        "uptime_label": "Uptime",
        "total_checks": "Total Checks:",
        "successful_checks": "Successful:",
        "failed_checks": "Failed:",
        "hours_ago": "Hours Ago",
        "now": "Now",
        "incidents_title": "Downtime Incidents",
        "th_started": "Started",
        "th_resolved": "Resolved",
        "th_duration": "Duration",
        "incident_ongoing": "Ongoing",
        "zero_incidents": "✓ 100% operational with 0 downtime incidents in this period.",
        "no_records_window": "No poll records in selected window.",
        "ip_label": "IP:",
        "location_label": "Location:",
        "group_label": "Group:",
        "parent_label": "Parent:",
        "time_earliest": "Earliest",
        "time_now": "Latest",
        "time_back_6h": "Back 6h",
        "time_fwd_6h": "Forward 6h",
        "time_back_12h": "Back 12h",
        "time_fwd_12h": "Forward 12h",
        "time_back_24h": "Back 24h",
        "time_fwd_24h": "Forward 24h",
        "time_back_48h": "Back 48h",
        "time_fwd_48h": "Forward 48h",
        "stable_period": "Stable Period (ONLINE)",
        "outage_period": "Outage Period (OFFLINE)",
        "period_start": "Start:",
        "period_end": "End:",
        "period_duration": "Duration:",
        "period_checks": "Consecutive polls:",
        "period_unchanging": "without state changes",
        "avg_latency": "Avg latency:",
        "loc_warning_red_title": "Critical Alert: {down}/{total} devices offline ({pct}%)",
        "loc_warning_yellow_title": "Warning Alert: {down}/{total} devices offline ({pct}%)",
        "loc_unstable_title": "Instability Alert: {count} device(s) with >10% downtime in last 6h",
        "instability_desc_lime": "Unstable: {pct}% downtime in last 6h",
        "instability_desc_yellow": "High Instability: {pct}% downtime in last 6h",
        "instability_desc_red": "Critical Instability: {pct}% downtime in last 6h",

        // Login Modal
        "login_modal_title": "Sign In to NetMap",
        "username_label": "Username",
        "password_label": "Password",
        "login_btn_submit": "Sign In",
        "default_accounts_hint": "Default accounts: <code>admin / admin123</code> or <code>operator / operator123</code>",
        "login_error_generic": "Authentication failed",
        "login_error_network": "Network error. Could not connect to server.",
        "welcome_user": "Welcome back, ",
        "logged_out_success": "Logged out successfully",
        "auth_required_poll": "Authentication required: Please sign in to force a poll.",

        // Admin Tabs
        "tab_hosts": "🖥️ Hosts",
        "tab_groups": "👥 Groups",
        "tab_csv": "📂 CSV Import / Export",
        "tab_settings": "⚙️ Settings (.cfg)",
        "tab_users": "👤 Users",
        "tab_maintenance": "🛠️ Maintenance",

        // Admin - Hosts Tab
        "admin_hosts_title": "Network Hosts & Hierarchy",
        "admin_hosts_desc": "Manage host IPs, locations, and parent-child tree hierarchy.",
        "btn_add_host": "+ Add New Host",
        "sort_by_label": "Sort by:",
        "sort_asc": "Ascending",
        "sort_desc": "Descending",
        "th_host_name": "Host Name",
        "th_ip_target": "IP / Target",
        "th_location": "Location (Macro)",
        "th_parent": "Parent Host (Hierarchy)",
        "th_grouping": "Grouping",
        "th_status": "Status",
        "th_actions": "Actions",
        "root_device": "Root",
        "active_status": "Active",
        "disabled_status": "Disabled",
        "btn_edit": "Edit",
        "btn_delete": "Delete",
        "confirm_delete_host": "Are you sure you want to delete host",

        // Admin - Groups Tab
        "admin_groups_title": "Host Groupings",
        "admin_groups_desc": "Aggregate multiple host responses into a single combined up/down state.",
        "btn_add_group": "+ Add Group",
        "th_group_name": "Group Name",
        "th_aggregation_mode": "Aggregation Mode",
        "th_assigned_hosts": "Assigned Hosts",
        "th_description": "Description",
        "mode_any": "Any Host UP = Group UP (Redundancy / HA)",
        "mode_all": "All Hosts UP = Group UP (Strict Cluster Health)",
        "confirm_delete_group": "Are you sure you want to delete group? Hosts in this group will become standalone.",

        // Admin - CSV Tab
        "csv_import_title": "📥 Bulk Import from CSV",
        "csv_import_desc": "Upload a CSV file containing your network inventory. Parent devices and groups will be automatically resolved.",
        "csv_select_file": "Select CSV File",
        "csv_paste_direct": "Or Paste CSV Content Directly",
        "csv_purge_label": "Purge database before importing (full replacement)",
        "csv_purge_warning": "⚠️ If checked, all existing hosts and history records will be permanently deleted before import. User accounts will be preserved.",
        "csv_purge_confirm": "WARNING: You have selected to PURGE the database. All existing hosts and history will be permanently deleted before importing the new file.\n\nAre you sure you want to proceed?",
        "csv_purge_success": "Database successfully purged and {count} new hosts imported!",
        "btn_upload_csv": "🚀 Upload & Import Hosts",
        "csv_export_title": "📤 Export & Templates",
        "csv_export_desc": "Download templates or export current database contents.",
        "csv_download_template": "Download CSV Template",
        "csv_template_desc": "Pre-formatted CSV sample file with proper headers, hierarchy, and groups.",
        "btn_download_template": "📄 Download Template CSV",
        "csv_export_db": "Export Database to CSV",
        "csv_export_desc_2": "Export all currently configured hosts, groups, and hierarchy relationships.",
        "btn_export_db": "💾 Export Current Hosts CSV",

        // Admin - Settings Tab
        "settings_title": "System Configuration",
        "settings_desc": "Changes are automatically written to <code>netmap.cfg</code> and applied immediately to the background engine.",
        "set_interval_label": "Auto-Polling Interval (Seconds)",
        "set_threads_label": "Parallel Ping Threads / Workers",
        "set_timeout_label": "Ping Timeout (Seconds)",
        "set_count_label": "Ping Count (Packets per Host)",
        "set_retention_label": "History Retention (Hours, min 24h)",
        "set_host_label": "Server Bind Address",
        "set_port_label": "Server TCP Port",
        "set_prefix_label": "URL Prefix / Subdirectory (Optional, e.g. /netmap)",
        "set_prefix_hint": "Only required if not passing X-Forwarded-Prefix header in reverse proxy.",
        "btn_save_settings": "💾 Save Configuration to netmap.cfg",
        "settings_saved_success": "Settings successfully saved to netmap.cfg and live engine!",

        // Admin - Users Tab
        "users_title": "Manage Users",
        "users_desc": "Admin: full configuration and database access.<br>Operator: can force poll from the public dashboard.",
        "users_create_title": "Create User Account",
        "users_create_desc": "Add a new administrator or operator.",
        "th_username": "Username",
        "th_role": "Role",
        "th_created": "Created",
        "btn_create_user": "+ Create Account",
        "role_operator": "Operator (Can trigger force poll)",
        "role_admin": "Administrator (Full Access)",
        "confirm_delete_user": "Are you sure you want to delete user",

        // Admin - Maintenance Tab
        "maint_title": "Dual Database Health & Storage",
        "maint_desc": "Monitor <code>hosts.db</code> (inventory) and <code>history.db</code> (time-series status).",
        "db_hosts_label": "HOSTS DATABASE",
        "db_history_label": "HISTORY DATABASE",
        "db_records_label": "indexed time-series records",
        "btn_run_prune": "🧹 Run Retention Prune Now",
        "btn_refresh_stats": "↻ Refresh Stats",

        // Modals - Host Form
        "modal_add_host_title": "Add New Host",
        "modal_edit_host_title": "Edit Host",
        "field_host_name": "Host Name *",
        "field_ip": "IP Address or Hostname *",
        "field_location": "Location (Macro Hierarchy) *",
        "field_parent": "Parent Device (Tree Hierarchy)",
        "field_parent_none": "-- None (Root Device) --",
        "field_group": "Grouping (Optional)",
        "field_group_none": "-- Standalone (No Group) --",
        "field_active": "Enable Polling (Active)",
        "field_desc": "Description / Notes",
        "btn_cancel": "Cancel",
        "btn_save_host": "Save Host",

        // Modals - Group Form
        "modal_add_group_title": "Add New Group",
        "modal_edit_group_title": "Edit Group",
        "field_group_name": "Group Name *",
        "field_group_mode": "Aggregation Mode *",
        "field_group_mode_hint": "'Any Host UP' is ideal for load-balanced or redundant clusters where 1 working node keeps service up.",
        "btn_save_group": "Save Group",

        // Speedtest
        "nav_speedtest": "🚀 Speedtest",
        "tab_speedtest": "🚀 Speedtest Results",
        "st_cooldown_title": "Visitor Cooldown Period Active",
        "st_cooldown_desc": "Visitors may run a speed test once every 2 hours. Next available test in:",
        "st_cooldown_auth_hint": "(Operators and Administrators can log in to test without delay).",
        "st_server_target": "Test Server Target:",
        "st_ready_msg": "Ready to start network speed test",
        "st_realtime_history": "Real-time Speed History",
        "st_metric_latency": "Latency & Jitter",
        "st_metric_jitter": "Jitter:",
        "st_metric_download": "Download",
        "st_metric_upload": "Upload",
        "st_max": "Max:",
        "st_btn_start": "🚀 Start Speed Test",
        "st_phase_ping": "Testing Latency (Ping & Jitter)...",
        "st_phase_download": "Testing Download Throughput...",
        "st_phase_upload": "Testing Upload Throughput...",
        "st_phase_saving": "Persisting results...",
        "st_phase_done": "Speed Test Completed Successfully!",
        "st_phase_error": "Error during speed test execution.",
        "st_cooldown_alert": "Please wait for cooldown interval before running another test.",
        "st_your_ip": "Your IP",
        "st_admin_title": "Speedtest Run History",
        "st_admin_desc": "Inspect and search throughput tests performed by network clients by IP address.",
        "st_search_ip_placeholder": "Search by IP (e.g. 192.168.1.50)...",
        "st_filter_btn": "Filter",
        "st_clear_btn": "Clear",
        "st_refresh_btn": "↻ Refresh",
        "th_st_ip": "Client IP",
        "th_st_timestamp": "Date / Time",
        "th_st_ping": "Latency / Jitter",
        "th_st_download": "Download (Avg / Max)",
        "th_st_upload": "Upload (Avg / Max)",
        "th_st_role": "User Role",
        "th_st_actions": "Actions",
        "st_no_results": "No speedtest results found.",
        "role_visitor": "Visitor",
        "nav_login": "🔐 Login"
    }
};

let currentLang = localStorage.getItem("netmap_lang") || "pt-BR";

function t(key) {
    if (TRANSLATIONS[currentLang] && TRANSLATIONS[currentLang][key]) {
        return TRANSLATIONS[currentLang][key];
    }
    if (TRANSLATIONS["en"] && TRANSLATIONS["en"][key]) {
        return TRANSLATIONS["en"][key];
    }
    return key;
}

function setLanguage(lang) {
    if (TRANSLATIONS[lang]) {
        currentLang = lang;
        localStorage.setItem("netmap_lang", lang);
        document.documentElement.lang = lang;
        applyTranslations();
        
        // Trigger dashboard re-render if loaded
        if (typeof renderTree === "function") renderTree();
        if (typeof renderLocationFilters === "function") renderLocationFilters();
        if (typeof renderAuthUI === "function") renderAuthUI();
        if (typeof renderHostsTable === "function") renderHostsTable();
        if (typeof renderGroupsTable === "function") renderGroupsTable();
        if (typeof renderUsersTable === "function") renderUsersTable();
        if (typeof loadSpeedtestResults === "function") loadSpeedtestResults();
    }
}

function applyTranslations() {
    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        const translation = t(key);
        if (translation && translation !== key) {
            el.innerHTML = translation;
        }
    });

    document.querySelectorAll("[data-i18n-title]").forEach(el => {
        const key = el.getAttribute("data-i18n-title");
        const translation = t(key);
        if (translation && translation !== key) {
            el.setAttribute("title", translation);
        }
    });

    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
        const key = el.getAttribute("data-i18n-placeholder");
        const translation = t(key);
        if (translation && translation !== key) {
            el.setAttribute("placeholder", translation);
        }
    });

    const langBtnPt = document.getElementById("lang-btn-pt");
    const langBtnEn = document.getElementById("lang-btn-en");
    if (langBtnPt && langBtnEn) {
        if (currentLang === "pt-BR") {
            langBtnPt.classList.add("active");
            langBtnEn.classList.remove("active");
        } else {
            langBtnPt.classList.remove("active");
            langBtnEn.classList.add("active");
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    document.documentElement.lang = currentLang;
    applyTranslations();
});
