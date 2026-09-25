// NetMap Main Application JS
let currentUser = null;
let currentLocations = [];
let activeLocationFilter = 'all';
let countdownInterval = null;
let secondsUntilNextPoll = 0;
let currentTimelineHostId = null;
let currentTimelineHours = 24;

document.addEventListener("DOMContentLoaded", () => {
    initAuth();
    loadDashboard();
    setupEventListeners();
    
    // Auto refresh status and tree periodically
    setInterval(refreshData, 10000);
});

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
            adminLink = `<a href="/admin" class="btn btn-outline" style="padding: 5px 10px; font-size: 0.8rem;">⚙️ Admin</a>`;
        }
        authContainer.innerHTML = `
            ${adminLink}
            <span style="font-size: 0.82rem; color: var(--text-muted); display: flex; align-items: center; gap: 5px;">
                👤 <strong>${escapeHtml(currentUser.username)}</strong>
                <span style="font-size: 0.7rem; padding: 1px 5px; background: rgba(59,130,246,0.2); border-radius: 3px; color: #60a5fa;">${currentUser.role}</span>
            </span>
            <button onclick="handleLogout()" class="btn btn-outline" style="padding: 4px 8px; font-size: 0.78rem;">Logout</button>
        `;
        forcePollBtn.removeAttribute("title");
        forcePollBtn.classList.remove("disabled");
    } else {
        authContainer.innerHTML = `
            <button onclick="openLoginModal()" class="btn btn-primary" style="padding: 6px 14px; font-size: 0.82rem;">Sign In</button>
        `;
        forcePollBtn.setAttribute("title", "Only logged-in users can force a poll");
    }
}

async function handleLogout() {
    try {
        await fetch("/api/auth/logout", { method: "POST" });
        currentUser = null;
        renderAuthUI();
        showToast("Logged out successfully", "success");
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
            showToast(`Welcome back, ${data.user.username}!`, "success");
        } else {
            errDiv.innerText = data.detail || "Authentication failed";
        }
    } catch (err) {
        errDiv.innerText = "Network error. Could not connect to server.";
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
            document.getElementById("last-poll-time").innerText = "Never";
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
            elem.innerText = "Polling...";
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

    // Fetch all locations if currently filtered to populate full tabs
    fetch("/api/tree").then(r => r.json()).then(fullData => {
        const locs = fullData.locations || [];
        let html = `
            <button class="pill-tab ${activeLocationFilter === 'all' ? 'active' : ''}" 
                    onclick="filterLocation('all')">
                All Sites (${locs.reduce((acc, l) => acc + l.total_count, 0)})
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
                <h3 style="color: var(--text-muted); margin-bottom: 8px;">No Hosts Configured Yet</h3>
                <p style="font-size: 0.9rem; max-width: 480px; margin: 0 auto 16px;">
                    Get started by logging in as an administrator to add your network hosts or upload a CSV file.
                </p>
                <button onclick="openLoginModal()" class="btn btn-primary">Sign In as Admin</button>
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
                        <span class="location-badge">${loc.total_count} hosts</span>
                    </div>
                    <div style="display: flex; gap: 14px; font-size: 0.8rem; font-family: var(--font-mono);">
                        <span style="color: var(--up-color);">● ${loc.up_count} UP</span>
                        <span style="color: var(--down-color);">● ${loc.down_count} DOWN</span>
                    </div>
                </div>
                <div class="tree-container">
        `;

        if (loc.roots.length === 0) {
            html += `<div style="color: var(--text-dim); font-size: 0.85rem; padding: 12px;">No root devices in this location.</div>`;
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
    let statusText = "UNKNOWN";
    let statusBadgeClass = "unpolled";

    if (node.is_up === true) {
        statusClass = "status-up";
        statusText = "UP";
        statusBadgeClass = "up";
    } else if (node.is_up === false) {
        statusClass = "status-down";
        statusText = "DOWN";
        statusBadgeClass = "down";
    }

    // Grouping check
    let groupHtml = "";
    if (node.grouping) {
        let grpStatus = node.group_status;
        let grpInfo = `${escapeHtml(node.grouping)}`;
        if (grpStatus && grpStatus.is_degraded) {
            statusClass = "status-degraded";
            grpInfo += ` (${grpStatus.hosts_up}/${grpStatus.hosts_total})`;
        }
        groupHtml = `<span class="group-badge" title="Group: ${escapeHtml(node.grouping)} (${node.group_mode})">${grpInfo}</span>`;
    }

    let rttDisplay = "—";
    if (node.rtt_ms !== null && node.rtt_ms !== undefined) {
        rttDisplay = `${node.rtt_ms.toFixed(1)}ms`;
    } else if (node.is_up === false) {
        rttDisplay = "Down";
    }

    // Abbreviated 30-minute sparkline without label line
    let sparklineHtml = renderSparkline30m(node.sparkline_30m);

    return `
        <div class="host-card ${statusClass}" onclick="openTimelineModal(${node.id})" title="${escapeHtml(node.name)} (${escapeHtml(node.ip_address)}) - ${statusText} - Click for 24h timeline">
            <span class="status-dot ${statusBadgeClass}"></span>
            <span class="host-name" title="${escapeHtml(node.name)}">${escapeHtml(node.name)}</span>
            <span class="ip-badge">${escapeHtml(node.ip_address)}</span>
            ${groupHtml}
            <span class="rtt-val">${rttDisplay}</span>
            ${sparklineHtml}
        </div>
    `;
}

function renderSparkline30m(records) {
    const slotCount = 16;
    let slots = [];
    
    if (records && records.length > 0) {
        const recent = records.slice(-slotCount);
        recent.forEach(r => {
            const cls = r.up ? "up" : "down";
            const dateStr = new Date(r.t * 1000).toLocaleTimeString();
            const rttStr = r.rtt !== null ? `${r.rtt}ms` : "Down";
            slots.push(`<div class="spark-dot ${cls}" title="${dateStr} - ${r.up ? 'UP' : 'DOWN'} (${rttStr})"></div>`);
        });
        while (slots.length < slotCount) {
            slots.unshift(`<div class="spark-dot empty" title="No check data"></div>`);
        }
    } else {
        for (let i = 0; i < slotCount; i++) {
            slots.push(`<div class="spark-dot empty" title="No check data"></div>`);
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
            <div class="spinner"></div> Loading host timeline...
        </div>
    `;

    try {
        const res = await fetch(`/api/hosts/${hostId}/timeline?hours=${hours}`);
        if (!res.ok) throw new Error("Host not found");
        const data = await res.json();
        renderTimelineData(data);
    } catch (err) {
        contentDiv.innerHTML = `<div style="color: var(--down-color); text-align: center; padding: 20px;">Failed to load host history.</div>`;
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
            const rttStr = r.rtt_ms ? `${r.rtt_ms.toFixed(1)}ms` : "Down";
            const cls = r.is_up ? "up" : "down";
            slicesHtml += `<div class="timeline-slice ${cls}" title="${dt} - ${r.is_up ? 'UP' : 'DOWN'} (${rttStr})"></div>`;
        });
    } else {
        slicesHtml = `<div style="padding: 4px; color: var(--text-dim); font-size: 0.8rem;">No poll records in selected window.</div>`;
    }

    let incidentsHtml = "";
    if (incidents.length > 0) {
        incidentsHtml = `
            <div style="margin-top: 14px;">
                <h4 style="font-size: 0.95rem; margin-bottom: 8px;">Downtime Incidents (${incidents.length})</h4>
                <table class="incident-table">
                    <thead>
                        <tr>
                            <th>Started</th>
                            <th>Resolved</th>
                            <th>Duration</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${incidents.map(inc => {
                            const startStr = new Date(inc.start * 1000).toLocaleTimeString();
                            const endStr = inc.end ? new Date(inc.end * 1000).toLocaleTimeString() : '<span style="color: var(--down-color); font-weight: 700;">Ongoing</span>';
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
                ✓ 100% operational with 0 downtime incidents in this period.
            </div>
        `;
    }

    const contentDiv = document.getElementById("timeline-modal-content");
    contentDiv.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
            <div>
                <div style="font-size: 0.85rem; color: var(--text-muted);">
                    <strong>IP:</strong> ${escapeHtml(host.ip_address)} &nbsp;|&nbsp; 
                    <strong>Location:</strong> ${escapeHtml(host.location)}
                    ${host.grouping ? `&nbsp;|&nbsp; <strong>Group:</strong> ${escapeHtml(host.grouping)}` : ""}
                    ${host.parent_name ? `&nbsp;|&nbsp; <strong>Parent:</strong> ${escapeHtml(host.parent_name)}` : ""}
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
                <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase;">Uptime (${currentTimelineHours}h)</div>
                <div class="uptime-stat" style="color: ${timeline.uptime_pct >= 99 ? 'var(--up-color)' : (timeline.uptime_pct >= 90 ? 'var(--degraded-color)' : 'var(--down-color)')}">
                    ${timeline.uptime_pct}%
                </div>
            </div>
            <div style="text-align: right; font-size: 0.82rem; color: var(--text-muted);">
                <div>Total Checks: <strong>${timeline.total_checks}</strong></div>
                <div>Successful: <strong style="color: var(--up-color);">${timeline.up_checks}</strong></div>
                <div>Failed: <strong style="color: var(--down-color);">${timeline.total_checks - timeline.up_checks}</strong></div>
            </div>
        </div>

        <div>
            <div style="font-size: 0.82rem; color: var(--text-dim); margin-bottom: 6px; display: flex; justify-content: space-between;">
                <span>${currentTimelineHours} Hours Ago</span>
                <span>Now</span>
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

// ----------------- Force Poll -----------------

async function handleForcePoll() {
    if (!currentUser) {
        showToast("Authentication required: Please sign in to force a poll.", "error");
        openLoginModal();
        return;
    }

    const btn = document.getElementById("btn-force-poll");
    const origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Polling...`;

    try {
        const res = await fetch("/api/poll/force", { method: "POST" });
        const data = await res.json();
        
        if (res.ok && data.success) {
            showToast(`Poll complete: ${data.result ? data.result.polled_count : ''} hosts checked in ${data.result ? data.result.duration : ''}s!`, "success");
            await loadDashboard();
        } else {
            showToast(data.detail || data.message || "Failed to trigger poll", "error");
        }
    } catch (err) {
        showToast("Error executing force poll", "error");
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
