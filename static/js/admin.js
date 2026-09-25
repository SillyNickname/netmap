// NetMap Administrative Interface JS
let currentHosts = [];
let currentGroups = [];
let currentUsers = [];
let editingHostId = null;

document.addEventListener("DOMContentLoaded", () => {
    checkAdminAuth();
});

async function checkAdminAuth() {
    try {
        const res = await fetch("/api/auth/me");
        const data = await res.json();
        if (!data.authenticated || data.user.role !== "admin") {
            window.location.href = "/?auth_required=true";
            return;
        }
        document.getElementById("admin-user-display").innerText = data.user.username;
        initAdminTabs();
        loadAllData();
    } catch (err) {
        console.error("Auth check failed:", err);
        window.location.href = "/";
    }
}

function initAdminTabs() {
    const tabs = document.querySelectorAll(".admin-tab-btn");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".admin-tab-panel").forEach(p => p.classList.remove("active"));
            
            tab.classList.add("active");
            const target = tab.getAttribute("data-tab");
            document.getElementById(target).classList.add("active");
        });
    });
}

async function loadAllData() {
    await Promise.all([
        loadHosts(),
        loadGroups(),
        loadSettings(),
        loadUsers(),
        loadStats()
    ]);
}

// ----------------- HOSTS MANAGEMENT -----------------

async function loadHosts() {
    try {
        const res = await fetch("/api/admin/hosts");
        const data = await res.json();
        currentHosts = data.hosts || [];
        renderHostsTable();
        populateParentDropdowns();
    } catch (err) {
        showToast("Error loading hosts", "error");
    }
}

function renderHostsTable() {
    const tbody = document.getElementById("hosts-table-body");
    if (!tbody) return;

    if (currentHosts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-dim); padding: 24px;">${t("no_hosts_title")}</td></tr>`;
        return;
    }

    tbody.innerHTML = currentHosts.map(h => `
        <tr>
            <td><strong>${escapeHtml(h.name)}</strong></td>
            <td><code>${escapeHtml(h.ip_address)}</code></td>
            <td>${escapeHtml(h.location)}</td>
            <td>${h.parent_name ? escapeHtml(h.parent_name) : `<span style="color: var(--text-dim);">${t("root_device")}</span>`}</td>
            <td>${h.grouping ? `<span class="group-badge">${escapeHtml(h.grouping)} (${h.group_mode || 'any'})</span>` : '—'}</td>
            <td>${h.is_active ? `<span style="color: var(--up-color);">${t("active_status")}</span>` : `<span style="color: var(--down-color);">${t("disabled_status")}</span>`}</td>
            <td style="text-align: right;">
                <button class="btn btn-outline" style="padding: 2px 8px; font-size: 0.75rem;" onclick="openEditHostModal(${h.id})">${t("btn_edit")}</button>
                <button class="btn btn-danger" style="padding: 2px 8px; font-size: 0.75rem;" onclick="deleteHost(${h.id}, '${escapeHtml(h.name)}')">${t("btn_delete")}</button>
            </td>
        </tr>
    `).join("");
}

function populateParentDropdowns() {
    const sel = document.getElementById("host-form-parent");
    if (!sel) return;
    sel.innerHTML = `<option value="">${t("field_parent_none")}</option>` + 
        currentHosts
            .filter(h => !editingHostId || h.id !== editingHostId)
            .map(h => `<option value="${h.id}">${escapeHtml(h.name)} (${escapeHtml(h.location)} - ${h.ip_address})</option>`)
            .join("");
}

function populateGroupDropdown() {
    const sel = document.getElementById("host-form-group");
    if (!sel) return;
    sel.innerHTML = `<option value="">${t("field_group_none")}</option>` + 
        currentGroups.map(g => `<option value="${escapeHtml(g.name)}">${escapeHtml(g.name)} (${g.aggregation_mode})</option>`).join("");
}

function openAddHostModal() {
    editingHostId = null;
    document.getElementById("host-modal-title").innerText = t("modal_add_host_title");
    document.getElementById("host-form").reset();
    document.getElementById("host-form-active").checked = true;
    populateParentDropdowns();
    populateGroupDropdown();
    document.getElementById("host-modal").classList.add("active");
}

function openEditHostModal(hostId) {
    const host = currentHosts.find(h => h.id === hostId);
    if (!host) return;

    editingHostId = hostId;
    document.getElementById("host-modal-title").innerText = t("modal_edit_host_title");
    populateParentDropdowns();
    populateGroupDropdown();

    document.getElementById("host-form-name").value = host.name;
    document.getElementById("host-form-ip").value = host.ip_address;
    document.getElementById("host-form-location").value = host.location;
    document.getElementById("host-form-parent").value = host.parent_id || "";
    document.getElementById("host-form-group").value = host.grouping || "";
    document.getElementById("host-form-desc").value = host.description || "";
    document.getElementById("host-form-active").checked = Boolean(host.is_active);

    document.getElementById("host-modal").classList.add("active");
}

function closeHostModal() {
    document.getElementById("host-modal").classList.remove("active");
    editingHostId = null;
}

async function handleHostSubmit(e) {
    e.preventDefault();
    const payload = {
        name: document.getElementById("host-form-name").value.trim(),
        ip_address: document.getElementById("host-form-ip").value.trim(),
        location: document.getElementById("host-form-location").value.trim(),
        parent_id: document.getElementById("host-form-parent").value ? parseInt(document.getElementById("host-form-parent").value) : null,
        grouping: document.getElementById("host-form-group").value || null,
        description: document.getElementById("host-form-desc").value.trim(),
        is_active: document.getElementById("host-form-active").checked
    };

    try {
        let res;
        if (editingHostId) {
            res = await fetch(`/api/admin/hosts/${editingHostId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        } else {
            res = await fetch("/api/admin/hosts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

        const data = await res.json();
        if (res.ok && data.success) {
            showToast(data.message, "success");
            closeHostModal();
            await loadHosts();
            await loadGroups();
        } else {
            showToast(data.detail || "Failed to save host", "error");
        }
    } catch (err) {
        showToast("Network error while saving host", "error");
    }
}

async function deleteHost(id, name) {
    if (!confirm(`${t("confirm_delete_host")} '${name}'?`)) {
        return;
    }
    try {
        const res = await fetch(`/api/admin/hosts/${id}`, { method: "DELETE" });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(`Deleted '${name}'`, "success");
            await loadHosts();
        } else {
            showToast(data.detail || "Failed to delete host", "error");
        }
    } catch (err) {
        showToast("Error deleting host", "error");
    }
}

// ----------------- GROUPS MANAGEMENT -----------------

async function loadGroups() {
    try {
        const res = await fetch("/api/admin/groups");
        const data = await res.json();
        currentGroups = data.groups || [];
        renderGroupsTable();
        populateGroupDropdown();
    } catch (err) {
        showToast("Error loading groups", "error");
    }
}

function renderGroupsTable() {
    const tbody = document.getElementById("groups-table-body");
    if (!tbody) return;

    if (currentGroups.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 24px;">No groups configured.</td></tr>`;
        return;
    }

    tbody.innerHTML = currentGroups.map(g => `
        <tr>
            <td><strong>${escapeHtml(g.name)}</strong></td>
            <td>
                <span class="group-badge" style="font-size: 0.8rem;">
                    ${g.aggregation_mode === 'any' ? t("mode_any") : t("mode_all")}
                </span>
            </td>
            <td>${g.host_count} ${t("hosts_count_suffix")}</td>
            <td>${escapeHtml(g.description || '—')}</td>
            <td style="text-align: right;">
                <button class="btn btn-outline" style="padding: 2px 8px; font-size: 0.75rem;" onclick="openEditGroupModal('${escapeHtml(g.name)}')">${t("btn_edit")}</button>
                <button class="btn btn-danger" style="padding: 2px 8px; font-size: 0.75rem;" onclick="deleteGroup('${escapeHtml(g.name)}')">${t("btn_delete")}</button>
            </td>
        </tr>
    `).join("");
}

function openAddGroupModal() {
    document.getElementById("group-modal-title").innerText = t("modal_add_group_title");
    document.getElementById("group-form").reset();
    document.getElementById("group-form-name").removeAttribute("readonly");
    document.getElementById("group-modal").classList.add("active");
}

function openEditGroupModal(groupName) {
    const grp = currentGroups.find(g => g.name === groupName);
    if (!grp) return;

    document.getElementById("group-modal-title").innerText = t("modal_edit_group_title");
    document.getElementById("group-form-name").value = grp.name;
    document.getElementById("group-form-name").setAttribute("readonly", "true");
    document.getElementById("group-form-mode").value = grp.aggregation_mode;
    document.getElementById("group-form-desc").value = grp.description || "";
    document.getElementById("group-modal").classList.add("active");
}

function closeGroupModal() {
    document.getElementById("group-modal").classList.remove("active");
}

async function handleGroupSubmit(e) {
    e.preventDefault();
    const name = document.getElementById("group-form-name").value.trim();
    const isEdit = document.getElementById("group-form-name").hasAttribute("readonly");
    const payload = {
        name: name,
        aggregation_mode: document.getElementById("group-form-mode").value,
        description: document.getElementById("group-form-desc").value.trim()
    };

    try {
        let res;
        if (isEdit) {
            res = await fetch(`/api/admin/groups/${encodeURIComponent(name)}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        } else {
            res = await fetch("/api/admin/groups", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

        const data = await res.json();
        if (res.ok && data.success) {
            showToast(data.message, "success");
            closeGroupModal();
            await loadGroups();
            await loadHosts();
        } else {
            showToast(data.detail || "Failed to save group", "error");
        }
    } catch (err) {
        showToast("Error saving group", "error");
    }
}

async function deleteGroup(name) {
    if (!confirm(t("confirm_delete_group"))) {
        return;
    }
    try {
        const res = await fetch(`/api/admin/groups/${encodeURIComponent(name)}`, { method: "DELETE" });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(`Deleted group '${name}'`, "success");
            await loadGroups();
            await loadHosts();
        } else {
            showToast(data.detail || "Failed to delete group", "error");
        }
    } catch (err) {
        showToast("Error deleting group", "error");
    }
}

// ----------------- SETTINGS MANAGEMENT -----------------

async function loadSettings() {
    try {
        const res = await fetch("/api/admin/settings");
        const data = await res.json();
        
        document.getElementById("set-interval").value = data.interval_seconds;
        document.getElementById("set-threads").value = data.ping_threads;
        document.getElementById("set-timeout").value = data.ping_timeout;
        document.getElementById("set-count").value = data.ping_count;
        document.getElementById("set-retention").value = data.retention_hours;
        document.getElementById("set-port").value = data.server_port;
        document.getElementById("set-host").value = data.server_host;
    } catch (err) {
        showToast("Error loading settings", "error");
    }
}

async function handleSettingsSubmit(e) {
    e.preventDefault();
    const payload = {
        interval_seconds: parseInt(document.getElementById("set-interval").value),
        ping_threads: parseInt(document.getElementById("set-threads").value),
        ping_timeout: parseInt(document.getElementById("set-timeout").value),
        ping_count: parseInt(document.getElementById("set-count").value),
        retention_hours: parseInt(document.getElementById("set-retention").value),
        server_port: parseInt(document.getElementById("set-port").value),
        server_host: document.getElementById("set-host").value.trim()
    };

    try {
        const res = await fetch("/api/admin/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(t("settings_saved_success"), "success");
        } else {
            showToast(data.detail || "Failed to update settings", "error");
        }
    } catch (err) {
        showToast("Error saving settings", "error");
    }
}

// ----------------- CSV IMPORT & EXPORT -----------------

async function handleCsvUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById("csv-file-input");
    const rawText = document.getElementById("csv-raw-text").value.trim();
    const purgeCheckbox = document.getElementById("csv-purge-checkbox");
    const purgeExisting = purgeCheckbox ? purgeCheckbox.checked : false;

    if (purgeExisting) {
        if (!confirm(t("csv_purge_confirm"))) {
            return;
        }
    }

    const formData = new FormData();
    if (fileInput.files.length > 0) {
        formData.append("file", fileInput.files[0]);
    } else if (rawText) {
        formData.append("csv_text", rawText);
    } else {
        showToast("Please select a file or paste CSV text.", "error");
        return;
    }

    formData.append("purge_existing", purgeExisting ? "true" : "false");

    const btn = document.getElementById("btn-csv-import");
    const origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Importing...`;

    try {
        const res = await fetch("/api/admin/csv/import", {
            method: "POST",
            body: formData
        });
        const data = await res.json();
        if (res.ok && data.success) {
            let msg = purgeExisting 
                ? t("csv_purge_success").replace("{count}", data.imported)
                : `Successfully imported ${data.imported} hosts!`;
            if (data.errors && data.errors.length > 0) {
                msg += ` (${data.errors.length} warnings/skipped)`;
            }
            showToast(msg, "success");
            document.getElementById("csv-import-form").reset();
            await loadHosts();
            await loadGroups();
            await loadStats();
        } else {
            showToast(data.detail || (data.errors ? data.errors.join("; ") : "Import failed"), "error");
        }
    } catch (err) {
        showToast("Failed to process CSV import", "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHtml;
    }
}

// ----------------- USER MANAGEMENT -----------------

async function loadUsers() {
    try {
        const res = await fetch("/api/admin/users");
        const data = await res.json();
        currentUsers = data.users || [];
        renderUsersTable();
    } catch (err) {
        showToast("Error loading users", "error");
    }
}

function renderUsersTable() {
    const tbody = document.getElementById("users-table-body");
    if (!tbody) return;

    tbody.innerHTML = currentUsers.map(u => `
        <tr>
            <td><strong>${escapeHtml(u.username)}</strong></td>
            <td>
                <span style="font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; background: rgba(59,130,246,0.15); color: #60a5fa; font-weight: 600;">
                    ${u.role}
                </span>
            </td>
            <td>${new Date(u.created_at).toLocaleDateString()}</td>
            <td style="text-align: right;">
                <button class="btn btn-danger" style="padding: 2px 8px; font-size: 0.75rem;" onclick="deleteUser(${u.id}, '${escapeHtml(u.username)}')">${t("btn_delete")}</button>
            </td>
        </tr>
    `).join("");
}

async function handleUserCreate(e) {
    e.preventDefault();
    const user = document.getElementById("new-user-name").value.trim();
    const pass = document.getElementById("new-user-pass").value;
    const role = document.getElementById("new-user-role").value;

    try {
        const res = await fetch("/api/admin/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: user, password: pass, role: role })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(`User '${user}' created successfully`, "success");
            document.getElementById("user-create-form").reset();
            await loadUsers();
        } else {
            showToast(data.detail || "Failed to create user", "error");
        }
    } catch (err) {
        showToast("Error creating user", "error");
    }
}

async function deleteUser(id, username) {
    if (!confirm(`${t("confirm_delete_user")} '${username}'?`)) return;
    try {
        const res = await fetch(`/api/admin/users/${id}`, { method: "DELETE" });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(`Deleted user '${username}'`, "success");
            await loadUsers();
        } else {
            showToast(data.detail || "Failed to delete user", "error");
        }
    } catch (err) {
        showToast("Error deleting user", "error");
    }
}

// ----------------- STATS & MAINTENANCE -----------------

async function loadStats() {
    try {
        const res = await fetch("/api/admin/maintenance/stats");
        const data = await res.json();

        document.getElementById("stat-db-hosts").innerText = `${data.hosts_count} ${t("hosts_count_suffix")}`;
        document.getElementById("stat-db-history").innerText = `${data.history_rows_count.toLocaleString()} ${t("db_records_label")} (${data.history_db_size_mb} MB)`;
        document.getElementById("stat-db-hosts-size").innerText = `${data.hosts_db_size_mb} MB`;
    } catch (err) {
        console.error("Failed to load maintenance stats:", err);
    }
}

async function triggerManualPrune() {
    try {
        const res = await fetch("/api/admin/maintenance/prune", { method: "POST" });
        const data = await res.json();
        if (res.ok && data.success) {
            showToast(data.message, "success");
            await loadStats();
        } else {
            showToast("Failed to prune history", "error");
        }
    } catch (err) {
        showToast("Error executing prune", "error");
    }
}

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerText = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
