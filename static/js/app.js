// NetMap Main Application JS
const APP_BASE = (function() {
    if (typeof window.NETMAP_BASE === "string" && window.NETMAP_BASE.length > 0) {
        return window.NETMAP_BASE.replace(/\/$/, "");
    }
    let p = window.location.pathname || "";
    p = p.replace(/\/admin(\/.*)?$/, "");
    p = p.replace(/\/$/, "");
    return p;
})();

function getInitialLocationFilter() {
    const params = new URLSearchParams(window.location.search);
    const locParam = params.get("location") || params.get("loc");
    if (locParam) {
        return locParam;
    }
    const saved = localStorage.getItem("netmap_location_filter");
    if (saved && saved !== "all") {
        return saved;
    }
    return "all";
}

let currentUser = null;
let currentLocations = [];
let activeLocationFilter = getInitialLocationFilter();
let countdownInterval = null;
let secondsUntilNextPoll = 0;
let currentTimelineHostId = null;
let currentTimelineHours = 48;
let currentTimelineEndTime = null;
let currentDensity = localStorage.getItem("netmap_density") || "compact";

document.addEventListener("DOMContentLoaded", () => {
    initDensity();
    initLocationFilter();
    initAuth();
    loadDashboard();
    setupEventListeners();
    
    // Auto refresh status and tree periodically
    setInterval(refreshData, 10000);
});

function initLocationFilter() {
    const params = new URLSearchParams(window.location.search);
    const urlLoc = params.get("location") || params.get("loc");
    if (urlLoc) {
        activeLocationFilter = urlLoc;
        localStorage.setItem("netmap_location_filter", urlLoc);
    } else {
        const saved = localStorage.getItem("netmap_location_filter");
        if (saved && saved !== "all") {
            activeLocationFilter = saved;
            const url = new URL(window.location.href);
            url.searchParams.set("location", saved);
            window.history.replaceState({ location: saved }, "", url.toString());
        } else {
            activeLocationFilter = "all";
        }
    }
}

window.addEventListener("popstate", () => {
    const params = new URLSearchParams(window.location.search);
    const loc = params.get("location") || params.get("loc") || "all";
    if (loc !== activeLocationFilter) {
        filterLocation(loc, false);
    }
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
        const res = await fetch(`${APP_BASE}/api/auth/me`);
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
            adminLink = `<a href="${APP_BASE}/admin" class="btn btn-outline" style="padding: 5px 10px; font-size: 0.8rem;">${t("btn_admin")}</a>`;
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
        await fetch(`${APP_BASE}/api/auth/logout`, { method: "POST" });
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
        const res = await fetch(`${APP_BASE}/api/auth/login`, {
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
        const res = await fetch(`${APP_BASE}/api/status`);
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
            ? `${APP_BASE}/api/tree` 
            : `${APP_BASE}/api/tree?location_filter=${encodeURIComponent(activeLocationFilter)}`;
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

    fetch(`${APP_BASE}/api/tree`).then(r => r.json()).then(fullData => {
        const locs = fullData.locations || [];
        const devSummary = fullData.device_summary || null;
        
        let allAlertBadge = "";
        let allAlertClass = "";
        if (devSummary && devSummary.alert_level) {
            allAlertClass = `alert-${devSummary.alert_level}`;
            const warnTitle = (devSummary.alert_level === "red" ? t("loc_warning_red_title") : t("loc_warning_yellow_title"))
                .replace("{down}", devSummary.down)
                .replace("{total}", devSummary.total)
                .replace("{pct}", devSummary.down_pct);
            allAlertBadge = `
                <span class="loc-warning-badge badge-${devSummary.alert_level}" title="${escapeHtml(warnTitle)}">
                    <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor">
                        <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
                    </svg>
                </span>
            `;
        }

        const allHref = `${APP_BASE}/`;
        const totalAllCount = locs.reduce((acc, l) => acc + (l.device_total !== undefined ? l.device_total : l.total_count), 0);
        let html = `
            <a href="${allHref}" class="pill-tab ${activeLocationFilter === 'all' ? 'active' : ''} ${allAlertClass}" 
               data-location="all"
               onclick="event.preventDefault(); filterLocation('all');">
                ${t("all_sites")} (${totalAllCount})${allAlertBadge}
            </a>
        `;
        locs.forEach(l => {
            const isActive = activeLocationFilter === l.name;
            const locHref = `${APP_BASE}/?location=${encodeURIComponent(l.name)}`;
            
            let locAlertBadge = "";
            let locAlertClass = "";
            const devTotal = l.device_total !== undefined ? l.device_total : l.total_count;
            const devDown = l.device_down !== undefined ? l.device_down : l.down_count;
            const downPct = l.device_down_pct !== undefined ? l.device_down_pct : (devTotal > 0 ? (devDown / devTotal) * 100 : 0);
            
            let alertLevel = l.alert_level;
            if (!alertLevel && devTotal > 0 && devDown > 0) {
                if (downPct >= 75) alertLevel = "red";
                else if (downPct >= 50) alertLevel = "yellow";
            }

            if (alertLevel) {
                locAlertClass = `alert-${alertLevel}`;
                const warnTitle = (alertLevel === "red" ? t("loc_warning_red_title") : t("loc_warning_yellow_title"))
                    .replace("{down}", devDown)
                    .replace("{total}", devTotal)
                    .replace("{pct}", downPct);
                locAlertBadge = `
                    <span class="loc-warning-badge badge-${alertLevel}" title="${escapeHtml(warnTitle)}">
                        <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor">
                            <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
                        </svg>
                    </span>
                `;
            }

            html += `
                <a href="${locHref}" class="pill-tab ${isActive ? 'active' : ''} ${locAlertClass}" 
                   data-location="${escapeHtml(l.name)}"
                   onclick="event.preventDefault(); filterLocation(this.getAttribute('data-location'));">
                    ${escapeHtml(l.name)} (${devTotal})${locAlertBadge}
                </a>
            `;
        });
        tabsContainer.innerHTML = html;
    });
}

function filterLocation(locName, updateHistory = true) {
    activeLocationFilter = locName || "all";
    localStorage.setItem("netmap_location_filter", activeLocationFilter);

    if (updateHistory) {
        const url = new URL(window.location.href);
        if (activeLocationFilter === "all") {
            url.searchParams.delete("location");
            url.searchParams.delete("loc");
        } else {
            url.searchParams.set("location", activeLocationFilter);
        }
        window.history.pushState({ location: activeLocationFilter }, "", url.toString());
    }

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
        const locHref = `${APP_BASE}/?location=${encodeURIComponent(loc.name)}`;
        html += `
            <div class="location-section">
                <div class="location-header">
                    <div class="location-title">
                        <a href="${locHref}" data-location="${escapeHtml(loc.name)}" onclick="event.preventDefault(); filterLocation(this.getAttribute('data-location'));" style="color: inherit; text-decoration: none; cursor: pointer;">📍 ${escapeHtml(loc.name)}</a>
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
        // Ultra-Compact 20px (IP and latency removed for visual uniformity & compactness; visible on hover & click)
        return `
            <div class="host-card ${statusClass}" onclick="${clickAction}" title="${cardTitle}">
                <span class="status-dot ${statusBadgeClass}"></span>
                <span class="host-name" title="${escapeHtml(node.name)}">${escapeHtml(node.name)}</span>
                ${groupBadgeHtml}
                ${sparklineHtml}
            </div>
        `;
    }
}

function renderSparkline30m(records) {
    const slotCount = currentDensity === "tall" ? 20 : 4;
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

function formatDurationSeconds(sec) {
    if (sec < 60) return `${sec}s`;
    const mins = Math.floor(sec / 60);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    const remMins = mins % 60;
    if (hrs < 24) return remMins > 0 ? `${hrs}h ${remMins}m` : `${hrs}h`;
    const days = Math.floor(hrs / 24);
    const remHrs = hrs % 24;
    return remHrs > 0 ? `${days}d ${remHrs}h` : `${days}d`;
}

async function openTimelineModal(hostId, hours = 48, endTime = null) {
    currentTimelineHostId = hostId;
    currentTimelineHours = Math.min(48, Math.max(1, hours || 48));
    currentTimelineEndTime = endTime;

    const modal = document.getElementById("timeline-modal");
    modal.classList.add("active");

    const contentDiv = document.getElementById("timeline-modal-content");
    contentDiv.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--text-dim);">
            <div class="spinner"></div> ${t("loading_hierarchy")}
        </div>
    `;

    try {
        const queryParams = new URLSearchParams({ hours: currentTimelineHours });
        if (endTime !== null && endTime !== undefined) {
            queryParams.set("end_time", endTime);
        }
        const res = await fetch(`${APP_BASE}/api/hosts/${hostId}/timeline?${queryParams.toString()}`);
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

    const startTs = timeline.start_time || (timeline.end_time - currentTimelineHours * 3600);
    const endTs = timeline.end_time || Math.floor(Date.now() / 1000);
    const earliestTs = timeline.earliest_time;
    const hasEarlier = !!timeline.has_earlier;
    const hasLater = !!timeline.has_later;

    const startDt = new Date(startTs * 1000);
    const endDt = new Date(endTs * 1000);

    const pad = n => String(n).padStart(2, '0');
    const formatDt = dt => `${pad(dt.getDate())}/${pad(dt.getMonth() + 1)}/${dt.getFullYear()} ${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
    const rangeDisplay = `${formatDt(startDt)} ➔ ${formatDt(endDt)}`;

    // Time Navigation Handlers
    const nowTs = Math.floor(Date.now() / 1000);
    const earliestTarget = earliestTs ? (earliestTs + currentTimelineHours * 3600) : null;
    const back12hTarget = endTs - (12 * 3600);
    const back6hTarget = endTs - (6 * 3600);
    const fwd6hTarget = (endTs + (6 * 3600) >= nowTs) ? null : (endTs + (6 * 3600));
    const fwd12hTarget = (endTs + (12 * 3600) >= nowTs) ? null : (endTs + (12 * 3600));

    // 1. Time Navigation Toolbar
    const navToolbarHtml = `
        <div class="timeline-nav-toolbar">
            <div class="timeline-nav-group">
                <button class="btn btn-outline btn-xs" ${!hasEarlier || !earliestTarget ? 'disabled' : ''} 
                    onclick="openTimelineModal(${host.id}, ${currentTimelineHours}, ${earliestTarget})"
                    title="${t("time_earliest")}">
                    ⏮ ${t("time_earliest")}
                </button>
                <button class="btn btn-outline btn-xs" ${!hasEarlier ? 'disabled' : ''} 
                    onclick="openTimelineModal(${host.id}, ${currentTimelineHours}, ${back12hTarget})"
                    title="${t("time_back_12h")}">
                    ◀ -12h
                </button>
                <button class="btn btn-outline btn-xs" ${!hasEarlier ? 'disabled' : ''} 
                    onclick="openTimelineModal(${host.id}, ${currentTimelineHours}, ${back6hTarget})"
                    title="${t("time_back_6h")}">
                    ◀ -6h
                </button>
            </div>
            <div class="timeline-nav-range">
                <span>📅 ${rangeDisplay}</span>
            </div>
            <div class="timeline-nav-group">
                <button class="btn btn-outline btn-xs" ${!hasLater ? 'disabled' : ''} 
                    onclick="openTimelineModal(${host.id}, ${currentTimelineHours}, ${fwd6hTarget})"
                    title="${t("time_fwd_6h")}">
                    +6h ▶
                </button>
                <button class="btn btn-outline btn-xs" ${!hasLater ? 'disabled' : ''} 
                    onclick="openTimelineModal(${host.id}, ${currentTimelineHours}, ${fwd12hTarget})"
                    title="${t("time_fwd_12h")}">
                    +12h ▶
                </button>
                <button class="btn btn-outline btn-xs" ${!hasLater ? 'disabled' : ''} 
                    onclick="openTimelineModal(${host.id}, ${currentTimelineHours}, null)"
                    title="${t("time_now")}">
                    ⏭ ${t("time_now")}
                </button>
            </div>
        </div>
    `;

    // 2. Time Bar (Ruler) above poll history
    const totalDurationSec = Math.max(1, endTs - startTs);
    const tickCount = 5;
    let ticksHtml = "";
    for (let i = 0; i < tickCount; i++) {
        const pct = (i / (tickCount - 1)) * 100;
        const tickTs = startTs + Math.round(totalDurationSec * (i / (tickCount - 1)));
        const tickDt = new Date(tickTs * 1000);
        const tickText = `${pad(tickDt.getDate())}/${pad(tickDt.getMonth() + 1)} ${pad(tickDt.getHours())}:${pad(tickDt.getMinutes())}`;
        let cls = "time-bar-tick";
        if (i === 0) cls += " tick-start";
        else if (i === tickCount - 1) cls += " tick-end";
        ticksHtml += `<div class="${cls}" style="left: ${pct}%;"><span>${tickText}</span></div>`;
    }

    const timeBarHtml = `
        <div class="timeline-time-bar">
            <div class="time-bar-track"></div>
            <div class="time-bar-ticks">${ticksHtml}</div>
        </div>
    `;

    // 3. Poll History Bar: Condensed or Standard Slices
    let slicesHtml = "";
    const isDense = records.length > 120;

    if (records.length > 0) {
        if (isDense) {
            // Group consecutive polls of unchanging state
            const runs = [];
            let currentRun = null;
            records.forEach(r => {
                if (!currentRun || currentRun.is_up !== r.is_up) {
                    if (currentRun) runs.push(currentRun);
                    currentRun = {
                        is_up: r.is_up,
                        start_ts: r.timestamp,
                        end_ts: r.timestamp,
                        count: 1,
                        rtts: (r.rtt_ms !== null && r.rtt_ms !== undefined) ? [r.rtt_ms] : [],
                        errors: r.error_msg ? [r.error_msg] : []
                    };
                } else {
                    currentRun.end_ts = r.timestamp;
                    currentRun.count++;
                    if (r.rtt_ms !== null && r.rtt_ms !== undefined) currentRun.rtts.push(r.rtt_ms);
                    if (r.error_msg) currentRun.errors.push(r.error_msg);
                }
            });
            if (currentRun) runs.push(currentRun);

            runs.forEach(run => {
                const runDurSec = Math.max(60, run.end_ts - run.start_ts + 60);
                const sDt = new Date(run.start_ts * 1000);
                const eDt = new Date(run.end_ts * 1000);
                const startStr = `${formatDt(sDt)}`;
                const endStr = `${formatDt(eDt)}`;
                const durStr = formatDurationSeconds(Math.max(60, run.end_ts - run.start_ts));
                const isCondensed = run.count > 1;
                const stateCls = run.is_up ? "up" : "down";
                const typeCls = isCondensed ? "condensed" : "single";

                let avgRttStr = "";
                if (run.is_up && run.rtts.length > 0) {
                    const avg = (run.rtts.reduce((a, b) => a + b, 0) / run.rtts.length).toFixed(1);
                    avgRttStr = `${avg}ms`;
                }
                const errStr = run.errors[0] || (run.is_up ? "" : t("status_timeout"));

                const nativeTitle = isCondensed
                    ? `${run.is_up ? t("stable_period") : t("outage_period")}\n${t("period_start")} ${startStr}\n${t("period_end")} ${endStr}\n${t("period_duration")} ${durStr}\n${t("period_checks")} ${run.count} (${t("period_unchanging")})${avgRttStr ? `\n${t("avg_latency")} ${avgRttStr}` : ''}`
                    : `${startStr} - ${run.is_up ? t("status_up") : t("status_down")} (${avgRttStr || errStr})`;

                slicesHtml += `
                    <div class="timeline-slice ${typeCls} ${stateCls}"
                         style="flex: ${runDurSec}; min-width: ${isCondensed ? '4px' : '2px'};"
                         data-type="${typeCls}"
                         data-is-up="${run.is_up ? '1' : '0'}"
                         data-start="${escapeHtml(startStr)}"
                         data-end="${escapeHtml(endStr)}"
                         data-dur="${escapeHtml(durStr)}"
                         data-count="${run.count}"
                         data-rtt="${escapeHtml(avgRttStr)}"
                         data-err="${escapeHtml(errStr)}"
                         title="${escapeHtml(nativeTitle)}"></div>
                `;
            });
        } else {
            // Standard discrete bars for non-dense history
            records.forEach(r => {
                const dt = new Date(r.timestamp * 1000);
                const dtStr = formatDt(dt);
                const rttStr = (r.rtt_ms !== null && r.rtt_ms !== undefined) ? `${r.rtt_ms.toFixed(1)}ms` : "";
                const errStr = r.error_msg || (r.is_up ? "" : t("status_timeout"));
                const cls = r.is_up ? "up" : "down";
                const nativeTitle = `${dtStr} - ${r.is_up ? t("status_up") : t("status_down")} (${rttStr || errStr})`;

                slicesHtml += `
                    <div class="timeline-slice single ${cls}"
                         style="flex: 1; min-width: 2px;"
                         data-type="single"
                         data-is-up="${r.is_up ? '1' : '0'}"
                         data-start="${escapeHtml(dtStr)}"
                         data-end="${escapeHtml(dtStr)}"
                         data-dur="1m"
                         data-count="1"
                         data-rtt="${escapeHtml(rttStr)}"
                         data-err="${escapeHtml(errStr)}"
                         title="${escapeHtml(nativeTitle)}"></div>
                `;
            });
        }
    } else {
        slicesHtml = `<div style="padding: 4px; color: var(--text-dim); font-size: 0.8rem; width: 100%; text-align: center;">${t("no_records_window")}</div>`;
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
                            const startStr = new Date(inc.start * 1000).toLocaleString();
                            const endStr = inc.end ? new Date(inc.end * 1000).toLocaleString() : `<span style="color: var(--down-color); font-weight: 700;">${t("incident_ongoing")}</span>`;
                            const durStr = formatDurationSeconds(inc.duration_seconds);
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
                <button class="pill-tab ${currentTimelineHours === 6 ? 'active' : ''}" onclick="openTimelineModal(${host.id}, 6, currentTimelineEndTime)">6h</button>
                <button class="pill-tab ${currentTimelineHours === 12 ? 'active' : ''}" onclick="openTimelineModal(${host.id}, 12, currentTimelineEndTime)">12h</button>
                <button class="pill-tab ${currentTimelineHours === 24 ? 'active' : ''}" onclick="openTimelineModal(${host.id}, 24, currentTimelineEndTime)">24h</button>
                <button class="pill-tab ${currentTimelineHours === 48 ? 'active' : ''}" onclick="openTimelineModal(${host.id}, 48, currentTimelineEndTime)">48h</button>
            </div>
        </div>

        ${navToolbarHtml}

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
            ${timeBarHtml}
            <div class="timeline-chart-bar" id="timeline-chart-bar-el">
                ${slicesHtml}
            </div>
        </div>

        ${incidentsHtml}
    `;

    setupTimelineTooltip();
}

function setupTimelineTooltip() {
    let tooltip = document.getElementById("timeline-floating-tooltip");
    if (!tooltip) {
        tooltip = document.createElement("div");
        tooltip.id = "timeline-floating-tooltip";
        tooltip.className = "timeline-floating-tooltip";
        document.body.appendChild(tooltip);
    }

    const slices = document.querySelectorAll(".timeline-slice");
    slices.forEach(slice => {
        slice.addEventListener("mouseenter", (e) => {
            const isUp = slice.getAttribute("data-is-up") === "1";
            const type = slice.getAttribute("data-type");
            const start = slice.getAttribute("data-start");
            const end = slice.getAttribute("data-end");
            const dur = slice.getAttribute("data-dur");
            const count = slice.getAttribute("data-count");
            const rtt = slice.getAttribute("data-rtt");
            const err = slice.getAttribute("data-err");

            let html = "";
            if (type === "condensed") {
                const headerColor = isUp ? "var(--up-color)" : "var(--down-color)";
                const headerText = isUp ? t("stable_period") : t("outage_period");
                html = `
                    <div class="tt-title" style="color: ${headerColor};">
                        <span>●</span> ${headerText}
                    </div>
                    <div class="tt-row"><span>${t("period_start")}</span><span class="tt-val">${start}</span></div>
                    <div class="tt-row"><span>${t("period_end")}</span><span class="tt-val">${end}</span></div>
                    <div class="tt-row"><span>${t("period_duration")}</span><span class="tt-val">${dur}</span></div>
                    <div class="tt-row"><span>${t("period_checks")}</span><span class="tt-val">${count}</span></div>
                    ${rtt ? `<div class="tt-row"><span>${t("avg_latency")}</span><span class="tt-val">${rtt}</span></div>` : ''}
                    ${err ? `<div class="tt-row"><span>Status:</span><span class="tt-val" style="color:var(--down-color);">${err}</span></div>` : ''}
                `;
            } else {
                const headerColor = isUp ? "var(--up-color)" : "var(--down-color)";
                const headerText = isUp ? t("status_up") : t("status_down");
                html = `
                    <div class="tt-title" style="color: ${headerColor};">
                        <span>●</span> ${headerText}
                    </div>
                    <div class="tt-row"><span>Data/Hora:</span><span class="tt-val">${start}</span></div>
                    ${rtt ? `<div class="tt-row"><span>${t("th_latency")}:</span><span class="tt-val">${rtt}</span></div>` : ''}
                    ${err ? `<div class="tt-row"><span>Status:</span><span class="tt-val" style="color:var(--down-color);">${err}</span></div>` : ''}
                `;
            }

            tooltip.innerHTML = html;
            tooltip.style.display = "block";
            positionTooltip(e, tooltip);
        });

        slice.addEventListener("mousemove", (e) => {
            positionTooltip(e, tooltip);
        });

        slice.addEventListener("mouseleave", () => {
            tooltip.style.display = "none";
        });
    });
}

function positionTooltip(e, tooltip) {
    const pad = 14;
    let left = e.clientX + pad;
    let top = e.clientY + pad;

    const width = 280;
    if (left + width > window.innerWidth - 20) {
        left = e.clientX - width - pad;
    }
    if (top + 160 > window.innerHeight) {
        top = e.clientY - 160;
    }
    tooltip.style.left = `${Math.max(10, left)}px`;
    tooltip.style.top = `${Math.max(10, top)}px`;
}

function closeTimelineModal() {
    document.getElementById("timeline-modal").classList.remove("active");
    const tooltip = document.getElementById("timeline-floating-tooltip");
    if (tooltip) tooltip.style.display = "none";
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
        const res = await fetch(`${APP_BASE}/api/groups/${encodeURIComponent(groupName)}/timeline`);
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
        const res = await fetch(`${APP_BASE}/api/poll/force`, { method: "POST" });
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
