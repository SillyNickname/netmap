// NetMap Main Application JS
let currentUser = null;
let currentLocations = [];
let activeLocationFilter = 'all';
let countdownInterval = null;
let secondsUntilNextPoll = 0;
let currentTimelineHostId = null;
let currentTimelineHours = 24;
let currentDensity = localStorage.getItem("netmap_density") || "compact";

document.addEventListener("DOMContentLoaded", () => {
    initDensity();
    initAuth();
    loadDashboard();
    setupEventListeners();
    
    // Auto refresh status and tree periodically
    setInterval(refreshData, 10000);
});

// ----------------- Density (Compact / Tall) -----------------

function initDensity() {
    setDensity(currentDensity, false);
}

function setDensity(mode, shouldRerender = true) {
    currentDensity = mode;
    localStorage.setItem("netmap_density", mode);
    
    if (mode === "tall") {
        document.body.classList.add("density-tall");
        document.body.classList.remove("density-compact");
    } else {
        document.body.classList.add("density-compact");
        document.body.classList.remove("density-tall");
    }

    const btnCompact = document.getElementById("density-btn-compact");
    const btnTall = document.getElementById("density-btn-tall");
    if (btnCompact && btnTall) {
        if (mode === "tall") {
            btnTall.classList.add("active");
            btnCompact.classList.remove("active");
        } else {
            btnCompact.classList.add("active");
            btnTall.classList.remove("active");
        }
    }

    if (shouldRerender) {
        renderTree();
    }
}

// ----------------- Auth State -----------------

async function initAuth() {
    try {
        const res = await fetch("/api/auth/me");
        const data = await res.json();
        if (data.authenticated && data.user) {
            currentUser = data.user;
            renderAuthUI();
        } else {
            currentUser = null;
            renderAuthUI();
        }
    } catch (err) {
        console.error("Failed to check auth state:", err);
    }
}

function renderAuthUI() {
    const authContainer = document.getElementById("nav-auth-container");
    const forcePollBtn = document.getElementById("btn-force-poll");
    
    if (currentUser) {
        let adminLink = "";
        if (currentUser.role === "admin") {
            adminLink = `<a href="/admin" class="btn btn-outline" style="padding: 5px 10px; font-size: 0.8rem;">${t("btn_admin")}</a>`;
        }
        authContainer.innerHTML = `
            ${adminLink}
            <span style="font-size: 0.82rem; color: var(--text-muted); display: flex; align-items: center; gap: 5px;">
                👤 <strong>${escapeHtml(currentUser.username)}</strong>
                <span style="font-size: 0.7rem; padding: 1px 5px; background: rgba(59,130,246,0.2); border-radius: 3px; color: #60a5fa;">${currentUser.role}</span>
            </span>
            <button onclick="handleLogout()" class="btn btn-outline" style="padding: 4px 8px; font-size: 0.78rem;">${t("btn_logout")}</button>
        `;
        forcePollBtn.removeAttribute("title");
        forcePollBtn.classList.remove("disabled");
    } else {
        authContainer.innerHTML = `
            <button onclick="openLoginModal()" class="btn btn-primary" style="padding: 6px 14px; font-size: 0.82rem;">${t("btn_sign_in")}</button>
        `;
        forcePollBtn.setAttribute("title", t("auth_required_poll"));
    }
}

async function handleLogout() {
    try {
        await fetch("/api/auth/logout", { method: "POST" });
        currentUser = null;
        renderAuthUI();
        showToast(t("logged_out_success"), "success");
    } catch (err) {
        console.error("Logout failed:", err);
    }
}

function openLoginModal() {
    document.getElementById("login-modal").classList.add("active");
    document.getElementById("login-username").focus();
}

function closeLoginModal() {
    document.getElementById("login-modal").classList.remove("active");
    document.getElementById("login-form").reset();
    document.getElementById("login-error").innerText = "";
}

async function handleLoginSubmit(e) {
    e.preventDefault();
    const user = document.getElementById("login-username").value.trim();
    const pass = document.getElementById("login-password").value;
    const errDiv = document.getElementById("login-error");
    errDiv.innerText = "";

    try {
        const res = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: user, password: pass })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            currentUser = data.user;
            closeLoginModal();
            renderAuthUI();
            showToast(`${t("welcome_user")} ${data.user.username}!`, "success");
        } else {
            errDiv.innerText = data.detail || t("login_error_generic");
        }
    } catch (err) {
        errDiv.innerText = t("login_error_network");
    }
}

// ----------------- Data Loading -----------------

async function loadDashboard() {
    await Promise.all([loadStatus(), loadTree()]);
}

async function refreshData() {
    await Promise.all([loadStatus(), loadTree(false)]);
}

async function loadStatus() {
    try {
        const res = await fetch("/api/status");
        const data = await res.json();
        
        document.getElementById("stat-total").innerText = data.total_hosts || 0;
        document.getElementById("stat-up").innerText = data.hosts_up || 0;
        document.getElementById("stat-down").innerText = data.hosts_down || 0;
        
        const uptimePct = data.total_hosts > 0 
            ? ((data.hosts_up / data.total_hosts) * 100).toFixed(1) + "%" 
            : "100%";
        document.getElementById("stat-uptime").innerText = uptimePct;

        if (data.last_poll_time) {
            const dt = new Date(data.last_poll_time * 1000);
            document.getElementById("last-poll-time").innerText = dt.toLocaleTimeString();
        } else {
            document.getElementById("last-poll-time").innerText = "—";
        }

        if (data.next_poll_in_seconds !== null && data.next_poll_in_seconds !== undefined) {
            secondsUntilNextPoll = data.next_poll_in_seconds;
            startCountdown();
        }
    } catch (err) {
        console.error("Error loading status:", err);
    }
}

function startCountdown() {
    if (countdownInterval) clearInterval(countdownInterval);
    const elem = document.getElementById("next-poll-countdown");
    if (!elem) return;

    elem.innerText = `${secondsUntilNextPoll}s`;
    countdownInterval = setInterval(() => {
        if (secondsUntilNextPoll > 0) {
            secondsUntilNextPoll--;
            elem.innerText = `${secondsUntilNextPoll}s`;
        } else {
            elem.innerText = t("polling_now");
        }
    }, 1000);
}

async function loadTree(renderFilters = true) {
    try {
        const url = activeLocationFilter === 'all' 
            ? "/api/tree" 
            : `/api/tree?location_filter=${encodeURIComponent(activeLocationFilter)}`;
        const res = await fetch(url);
        const data = await res.json();
        
        currentLocations = data.locations || [];
        if (renderFilters) {
            renderLocationFilters();
        }
        renderTree();
    } catch (err) {
        console.error("Error loading tree data:", err);
    }
}

function renderLocationFilters() {
    const tabsContainer = document.getElementById("location-tabs");
    if (!tabsContainer) return;

    fetch("/api/tree").then(r => r.json()).then(fullData => {
        const locs = fullData.locations || [];
        let html = `
            <button class="pill-tab ${activeLocationFilter === 'all' ? 'active' : ''}" 
                    onclick="filterLocation('all')">
                ${t("all_sites")} (${locs.reduce((acc, l) => acc + l.total_count, 0)})
            </button>
        `;
        locs.forEach(l => {
            const isActive = activeLocationFilter === l.name;
            html += `
                <button class="pill-tab ${isActive ? 'active' : ''}" 
                        onclick="filterLocation('${escapeHtml(l.name)}')">
                    ${escapeHtml(l.name)} (${l.total_count})
                </button>
            `;
        });
        tabsContainer.innerHTML = html;
    });
}

function filterLocation(locName) {
    activeLocationFilter = locName;
    loadTree(true);
}

// ----------------- Left-to-Right Tree Rendering -----------------

function renderTree() {
    const container = document.getElementById("tree-root-container");
    if (!container) return;

    if (!currentLocations || currentLocations.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 60px 20px; color: var(--text-dim);">
                <div style="font-size: 2.5rem; margin-bottom: 12px;">📡</div>
                <h3 style="color: var(--text-muted); margin-bottom: 8px;">${t("no_hosts_title")}</h3>
                <p style="font-size: 0.9rem; max-width: 480px; margin: 0 auto 16px;">
                    ${t("no_hosts_desc")}
                </p>
                <button onclick="openLoginModal()" class="btn btn-primary">${t("btn_sign_in_admin")}</button>
            </div>
        `;
        return;
    }

    let html = "";
    currentLocations.forEach(loc => {
        html += `
            <div class="location-section">
                <div class="location-header">
                    <div class="location-title">
                        <span>📍 ${escapeHtml(loc.name)}</span>
                        <span class="location-badge">${loc.total_count} ${t("hosts_count_suffix")}</span>
                    </div>
                    <div style="display: flex; gap: 14px; font-size: 0.8rem; font-family: var(--font-mono);">
                        <span style="color: var(--up-color);">● ${loc.up_count} ${t("status_up")}</span>
                        ${loc.degraded_count > 0 ? `<span style="color: var(--degraded-color);">● ${loc.degraded_count} ${t("status_partially_up")}</span>` : ''}
                        <span style="color: var(--down-color);">● ${loc.down_count} ${t("status_down")}</span>
                    </div>
                </div>
                <div class="tree-container">
        `;

        if (loc.roots.length === 0) {
            html += `<div style="color: var(--text-dim); font-size: 0.85rem; padding: 12px;">${t("no_roots")}</div>`;
        } else {
            loc.roots.forEach(rootNode => {
                html += `
                    <div class="tree-row">
                        ${renderTreeNodeBranch(rootNode)}
                    </div>
                `;
            });
        }

        html += `
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function renderTreeNodeBranch(node) {
    let cardHtml = renderHostCard(node);
    let childrenHtml = "";

    if (node.children && node.children.length > 0) {
        childrenHtml = `
            <div class="tree-children">
                ${node.children.map(child => renderTreeNodeBranch(child)).join("")}
            </div>
        `;
    }

    return `
        <div class="tree-branch">
            ${cardHtml}
            ${childrenHtml}
        </div>
    `;
}

function renderHostCard(node) {
    let statusClass = "status-unpolled";
    let statusText = t("status_unknown");
    let statusBadgeClass = "unpolled";

    // Degradado / Parcialmente Ativo: use a yellow box
    if (node.is_degraded) {
        statusClass = "status-degraded";
        statusText = t("status_partially_up");
        statusBadgeClass = "degraded";
    } else if (node.is_up === true) {
        statusClass = "status-up";
        statusText = t("status_up");
        statusBadgeClass = "up";
    } else if (node.is_up === false) {
        statusClass = "status-down";
        statusText = t("status_down");
        statusBadgeClass = "down";
    }

    // Ping time / RTT:
    // If the ping requests time out, instead of stating so replace the time with a little red X emoji.
    let rttDisplay = "—";
    if (node.rtt_ms !== null && node.rtt_ms !== undefined) {
        rttDisplay = `${node.rtt_ms.toFixed(1)}ms`;
    } else if (node.is_up === false) {
        rttDisplay = `<span class="timeout-emoji" title="${node.error_msg || t("status_timeout")}">❌</span>`;
    }

    // Grouping indicator
    let groupBadgeHtml = "";
    if (node.is_group) {
        const degradedCls = node.is_degraded ? "group-degraded" : "";
        groupBadgeHtml = `<span class="group-badge ${degradedCls}" title="${node.hosts_up}/${node.hosts_total} ${t("hosts_count_suffix")} ${node.group_mode ? '(' + node.group_mode + ')' : ''}">👥 ${node.hosts_up}/${node.hosts_total}</span>`;
    }

    const clickAction = node.is_group 
        ? `openGroupModal('${encodeURIComponent(node.grouping)}')` 
        : `openTimelineModal(${node.id})`;

    const cardTitle = node.is_group
        ? `${escapeHtml(node.name)} (${node.hosts_up}/${node.hosts_total}) - ${statusText} - ${t("click_group_tooltip")}`
        : `${escapeHtml(node.name)} (${escapeHtml(node.ip_address)}) - ${statusText} - ${t("click_timeline_tooltip")}`;

    let sparklineHtml = renderSparkline30m(node.sparkline_30m);

    // Render Compact (20px) vs Tall (Comfortable)
    if (currentDensity === "tall") {
        return `
            <div class="host-card ${statusClass}" onclick="${clickAction}" title="${cardTitle}">
                <div class="card-row-top">
                    <div style="display: flex; align-items: center; gap: 6px; overflow: hidden;">
                        <span class="status-dot ${statusBadgeClass}"></span>
                        <span class="host-name" title="${escapeHtml(node.name)}">${escapeHtml(node.name)}</span>
                    </div>
                    ${groupBadgeHtml}
                </div>
                <div class="card-row-bottom">
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span class="ip-badge">${escapeHtml(node.ip_address)}</span>
                        <span class="rtt-val">${rttDisplay}</span>
                    </div>
                    ${sparklineHtml}
                </div>
            </div>
        `;
    } else {
        // Ultra-Compact 20px (IP removed for maximum horizontal compactness; visible on hover & click)
        return `
            <div class="host-card ${statusClass}" onclick="${clickAction}" title="${cardTitle}">
                <span class="status-dot ${statusBadgeClass}"></span>
                <span class="host-name" title="${escapeHtml(node.name)}">${escapeHtml(node.name)}</span>
                ${groupBadgeHtml}
                <span class="rtt-val">${rttDisplay}</span>
                ${sparklineHtml}
            </div>
        `;
    }
}

function renderSparkline30m(records) {
    const slotCount = currentDensity === "tall" ? 20 : 8;
    let slots = [];
    
    if (records && records.length > 0) {
        const recent = records.slice(-slotCount);
        recent.forEach(r => {
            const cls = r.degraded ? "degraded" : (r.up ? "up" : "down");
            const dateStr = new Date(r.t * 1000).toLocaleTimeString();
            const rttStr = (r.rtt !== null && r.rtt !== undefined) ? `${r.rtt}ms` : "❌";
            let statusLabel = r.degraded ? t("status_partially_up") : (r.up ? t("status_up") : t("status_down"));
            if (r.hosts_total && r.hosts_total > 1) {
                statusLabel += ` (${r.hosts_up}/${r.hosts_total})`;
            }
            slots.push(`<div class="spark-dot ${cls}" title="${dateStr} - ${statusLabel} (${rttStr})"></div>`);
        });
        while (slots.length < slotCount) {
            slots.unshift(`<div class="spark-dot empty" title="${t("no_records_window")}"></div>`);
        }
    } else {
        for (let i = 0; i < slotCount; i++) {
            slots.push(`<div class="spark-dot empty" title="${t("no_records_window")}"></div>`);
        }
    }

    return `<div class="sparkline-bar">${slots.join("")}</div>`;
}

// ----------------- Host Timeline Modal -----------------

async function openTimelineModal(hostId, hours = 24) {
    currentTimelineHostId = hostId;
    currentTimelineHours = hours;

    const modal = document.getElementById("timeline-modal");
    modal.classList.add("active");

    const contentDiv = document.getElementById("timeline-modal-content");
    contentDiv.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--text-dim);">
            <div class="spinner"></div> ${t("loading_hierarchy")}
        </div>
    `;

    try {
        const res = await fetch(`/api/hosts/${hostId}/timeline?hours=${hours}`);
        if (!res.ok) throw new Error("Host not found");
        const data = await res.json();
        renderTimelineData(data);
    } catch (err) {
        contentDiv.innerHTML = `<div style="color: var(--down-color); text-align: center; padding: 20px;">${t("login_error_network")}</div>`;
    }
}

function renderTimelineData(data) {
    const host = data.host;
    const timeline = data.timeline;
    const records = timeline.records || [];
    const incidents = timeline.incidents || [];

    document.getElementById("timeline-host-title").innerText = host.name;

    let slicesHtml = "";
    if (records.length > 0) {
        records.forEach(r => {
            const dt = new Date(r.timestamp * 1000).toLocaleString();
            const rttStr = r.rtt_ms ? `${r.rtt_ms.toFixed(1)}ms` : "❌";
            const cls = r.is_up ? "up" : "down";
            slicesHtml += `<div class="timeline-slice ${cls}" title="${dt} - ${r.is_up ? t("status_up") : t("status_down")} (${rttStr})"></div>`;
        });
    } else {
        slicesHtml = `<div style="padding: 4px; color: var(--text-dim); font-size: 0.8rem;">${t("no_records_window")}</div>`;
    }

    let incidentsHtml = "";
    if (incidents.length > 0) {
        incidentsHtml = `
            <div style="margin-top: 14px;">
                <h4 style="font-size: 0.95rem; margin-bottom: 8px;">${t("incidents_title")} (${incidents.length})</h4>
                <table class="incident-table">
                    <thead>
                        <tr>
                            <th>${t("th_started")}</th>
                            <th>${t("th_resolved")}</th>
                            <th>${t("th_duration")}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${incidents.map(inc => {
                            const startStr = new Date(inc.start * 1000).toLocaleTimeString();
                            const endStr = inc.end ? new Date(inc.end * 1000).toLocaleTimeString() : `<span style="color: var(--down-color); font-weight: 700;">${t("incident_ongoing")}</span>`;
                            const mins = Math.round(inc.duration_seconds / 60);
                            const durStr = mins >= 60 ? `${(mins/60).toFixed(1)}h` : `${mins}m (${inc.duration_seconds}s)`;
                            return `
                                <tr>
                                    <td>${startStr}</td>
                                    <td>${endStr}</td>
                                    <td>${durStr}</td>
                                </tr>
                            `;
                        }).join("")}
                    </tbody>
                </table>
            </div>
        `;
    } else {
        incidentsHtml = `
            <div style="color: var(--up-color); font-size: 0.85rem; padding: 10px 0;">
                ${t("zero_incidents")}
            </div>
        `;
    }

    const contentDiv = document.getElementById("timeline-modal-content");
    contentDiv.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
            <div>
                <div style="font-size: 0.85rem; color: var(--text-muted);">
                    <strong>${t("ip_label")}</strong> ${escapeHtml(host.ip_address)} &nbsp;|&nbsp; 
                    <strong>${t("location_label")}</strong> ${escapeHtml(host.location)}
                    ${host.grouping ? `&nbsp;|&nbsp; <strong>${t("group_label")}</strong> ${escapeHtml(host.grouping)}` : ""}
                    ${host.parent_name ? `&nbsp;|&nbsp; <strong>${t("parent_label")}</strong> ${escapeHtml(host.parent_name)}` : ""}
                </div>
                ${host.description ? `<div style="font-size: 0.82rem; color: var(--text-dim); margin-top: 4px;">${escapeHtml(host.description)}</div>` : ""}
            </div>
            <div class="pill-tabs">
                <button class="pill-tab ${currentTimelineHours === 6 ? 'active' : ''}" onclick="openTimelineModal(${host.id}, 6)">6h</button>
                <button class="pill-tab ${currentTimelineHours === 12 ? 'active' : ''}" onclick="openTimelineModal(${host.id}, 12)">12h</button>
                <button class="pill-tab ${currentTimelineHours === 24 ? 'active' : ''}" onclick="openTimelineModal(${host.id}, 24)">24h</button>
                <button class="pill-tab ${currentTimelineHours === 48 ? 'active' : ''}" onclick="openTimelineModal(${host.id}, 48)">48h</button>
            </div>
        </div>

        <div class="timeline-banner">
            <div>
                <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase;">${t("uptime_label")} (${currentTimelineHours}h)</div>
                <div class="uptime-stat" style="color: ${timeline.uptime_pct >= 99 ? 'var(--up-color)' : (timeline.uptime_pct >= 90 ? 'var(--degraded-color)' : 'var(--down-color)')}">
                    ${timeline.uptime_pct}%
                </div>
            </div>
            <div style="text-align: right; font-size: 0.82rem; color: var(--text-muted);">
                <div>${t("total_checks")} <strong>${timeline.total_checks}</strong></div>
                <div>${t("successful_checks")} <strong style="color: var(--up-color);">${timeline.up_checks}</strong></div>
                <div>${t("failed_checks")} <strong style="color: var(--down-color);">${timeline.total_checks - timeline.up_checks}</strong></div>
            </div>
        </div>

        <div>
            <div style="font-size: 0.82rem; color: var(--text-dim); margin-bottom: 6px; display: flex; justify-content: space-between;">
                <span>${currentTimelineHours} ${t("hours_ago")}</span>
                <span>${t("now")}</span>
            </div>
            <div class="timeline-chart-bar">
                ${slicesHtml}
            </div>
        </div>

        ${incidentsHtml}
    `;
}

function closeTimelineModal() {
    document.getElementById("timeline-modal").classList.remove("active");
}

// ----------------- Group Details Modal -----------------

async function openGroupModal(encodedGroupName) {
    const groupName = decodeURIComponent(encodedGroupName);
    const modal = document.getElementById("timeline-modal");
    modal.classList.add("active");

    document.getElementById("timeline-host-title").innerText = `👥 ${groupName}`;

    const contentDiv = document.getElementById("timeline-modal-content");
    contentDiv.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--text-dim);">
            <div class="spinner"></div> ${t("loading_hierarchy")}
        </div>
    `;

    try {
        const res = await fetch(`/api/groups/${encodeURIComponent(groupName)}/timeline`);
        if (!res.ok) throw new Error("Group not found");
        const data = await res.json();
        renderGroupModalData(data.group);
    } catch (err) {
        contentDiv.innerHTML = `<div style="color: var(--down-color); text-align: center; padding: 20px;">${t("login_error_network")}</div>`;
    }
}

function renderGroupModalData(group) {
    let statusBadge = "";
    if (group.is_degraded) {
        statusBadge = `<span style="background: rgba(245, 158, 11, 0.25); border: 1px solid rgba(245, 158, 11, 0.7); color: #fbbf24; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 700;">⚠️ ${t("status_partially_up")} (${group.hosts_up}/${group.hosts_total})</span>`;
    } else if (group.is_up === true) {
        statusBadge = `<span style="background: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.6); color: #34d399; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 700;">● ${t("status_up")} (${group.hosts_up}/${group.hosts_total})</span>`;
    } else if (group.is_up === false) {
        statusBadge = `<span style="background: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.6); color: #f87171; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 700;">● ${t("status_down")} (0/${group.hosts_total})</span>`;
    } else {
        statusBadge = `<span style="background: rgba(100, 116, 139, 0.2); color: #94a3b8; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem;">● ${t("status_unknown")}</span>`;
    }

    const modeText = group.aggregation_mode === "all" ? t("mode_all") : t("mode_any");

    let membersRowsHtml = "";
    if (group.members && group.members.length > 0) {
        membersRowsHtml = group.members.map(m => {
            let mStatus = "";
            let mRtt = "—";
            if (m.is_up === true) {
                mStatus = `<span style="color: var(--up-color); font-weight: 600;">● ${t("status_up")}</span>`;
                mRtt = m.rtt_ms !== null && m.rtt_ms !== undefined ? `${m.rtt_ms.toFixed(1)}ms` : "—";
            } else if (m.is_up === false) {
                mStatus = `<span style="color: var(--down-color); font-weight: 600;">● ${t("status_down")}</span>`;
                mRtt = `<span class="timeout-emoji" style="font-size: 1rem;" title="${t("status_timeout")}">❌</span>`;
            } else {
                mStatus = `<span style="color: var(--unpolled-color);">● ${t("status_unknown")}</span>`;
            }

            return `
                <tr>
                    <td style="font-weight: 600; color: #fff;">${escapeHtml(m.name)}</td>
                    <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(m.ip_address)}</td>
                    <td style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(m.location)}</td>
                    <td>${mStatus}</td>
                    <td style="font-family: var(--font-mono); font-size: 0.85rem;">${mRtt}</td>
                    <td>
                        <button class="btn btn-outline" style="padding: 2px 8px; font-size: 0.75rem;" onclick="openTimelineModal(${m.id})">
                            📊 ${t("btn_view_timeline")}
                        </button>
                    </td>
                </tr>
            `;
        }).join("");
    } else {
        membersRowsHtml = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 16px;">${t("no_hosts_desc")}</td></tr>`;
    }

    const contentDiv = document.getElementById("timeline-modal-content");
    contentDiv.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                ${statusBadge}
                <span style="font-size: 0.85rem; color: var(--text-muted);">
                    <strong>${t("aggregation_mode_label")}</strong> ${modeText}
                </span>
            </div>
        </div>
        ${group.description ? `<div style="font-size: 0.85rem; color: var(--text-dim); margin-bottom: 16px;">${escapeHtml(group.description)}</div>` : ""}

        <div style="margin-top: 10px;">
            <h4 style="font-size: 0.95rem; margin-bottom: 8px; color: var(--text-main);">${t("member_hosts_title")} (${group.hosts_total})</h4>
            <table class="incident-table">
                <thead>
                    <tr>
                        <th>${t("th_host_name")}</th>
                        <th>${t("th_ip_target")}</th>
                        <th>${t("th_location")}</th>
                        <th>${t("th_status")}</th>
                        <th>${t("th_latency")}</th>
                        <th>${t("th_actions")}</th>
                    </tr>
                </thead>
                <tbody>
                    ${membersRowsHtml}
                </tbody>
            </table>
        </div>
    `;
}

// ----------------- Force Poll -----------------

async function handleForcePoll() {
    if (!currentUser) {
        showToast(t("auth_required_poll"), "error");
        openLoginModal();
        return;
    }

    const btn = document.getElementById("btn-force-poll");
    const origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> ${t("polling_now")}`;

    try {
        const res = await fetch("/api/poll/force", { method: "POST" });
        const data = await res.json();
        
        if (res.ok && data.success) {
            const count = data.result ? data.result.polled_count : 0;
            const dur = data.result ? data.result.duration : 0;
            showToast(`${count} ${t("hosts_count_suffix")} (${dur}s)`, "success");
            await loadDashboard();
        } else {
            showToast(data.detail || data.message || "Failed", "error");
        }
    } catch (err) {
        showToast(t("login_error_network"), "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHtml;
    }
}

// ----------------- Event Listeners & Helpers -----------------

function setupEventListeners() {
    document.getElementById("btn-force-poll").addEventListener("click", handleForcePoll);
    document.getElementById("login-form").addEventListener("submit", handleLoginSubmit);

    // Escape key closes modals
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeLoginModal();
            closeTimelineModal();
        }
    });
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
