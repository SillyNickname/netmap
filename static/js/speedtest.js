/**
 * NetMap - Standalone Speedtest Engine JS
 * Developed by: Antigravity (Google DeepMind)
 * Requested and commissioned by: Andre Kajita <kajita@univap.br>
 */

const APP_BASE = (function() {
    if (typeof window.NETMAP_BASE === "string" && window.NETMAP_BASE.length > 0) {
        return window.NETMAP_BASE.replace(/\/$/, "");
    }
    let p = window.location.pathname || "";
    p = p.replace(/\/speedtest(\/.*)?$/, "");
    p = p.replace(/\/$/, "");
    return p;
})();

let speedtestConfig = {
    enabled: true,
    server_url: "",
    duration_seconds: 5,
    can_test: true,
    cooldown_remaining_seconds: 0,
    client_ip: "127.0.0.1",
    user_role: "visitor"
};

let isRunning = false;
let cooldownTimerId = null;

// Helper: Speed to Gauge Angle (-140 to +140 deg)
function speedToGauge(mbps) {
    if (mbps <= 0) return { angle: -140, fraction: 0 };
    // Non-linear scale benchmarks:
    // 0 -> -140 deg (frac 0.0)
    // 0 -> -130 deg (frac 0.00)
    // 10 -> -91 deg (frac 0.15)
    // 50 -> -49.4 deg (frac 0.31)
    // 100 -> 0 deg (frac 0.50)
    // 250 -> +46.8 deg (frac 0.68)
    // 500 -> +88.4 deg (frac 0.84)
    // 1000+ -> +130 deg (frac 1.0)
    let frac = 0;
    if (mbps <= 0) {
        frac = 0;
    } else if (mbps <= 10) {
        frac = (mbps / 10) * 0.15;
    } else if (mbps <= 50) {
        frac = 0.15 + ((mbps - 10) / 40) * 0.16;
    } else if (mbps <= 100) {
        frac = 0.31 + ((mbps - 50) / 50) * 0.19;
    } else if (mbps <= 250) {
        frac = 0.50 + ((mbps - 100) / 150) * 0.18;
    } else if (mbps <= 500) {
        frac = 0.68 + ((mbps - 250) / 250) * 0.16;
    } else if (mbps <= 1000) {
        frac = 0.84 + ((mbps - 500) / 500) * 0.16;
    } else {
        frac = 1.0;
    }
    frac = Math.min(1.0, Math.max(0.0, frac));
    const angle = -130 + frac * 260;
    return { angle, fraction: frac };
}

function updateGauge(mbps) {
    const valEl = document.getElementById("speed-val-mbps");
    const mbsEl = document.getElementById("speed-val-mbs");
    const needleEl = document.getElementById("gauge-needle");
    const arcEl = document.getElementById("gauge-val-arc");

    const safeMbps = Math.max(0, mbps);
    const mbs = safeMbps / 8;

    if (valEl) valEl.textContent = safeMbps.toFixed(2);
    if (mbsEl) mbsEl.textContent = mbs.toFixed(2);

    const { angle, fraction } = speedToGauge(safeMbps);
    if (needleEl) {
        needleEl.setAttribute("transform", `translate(180, 155) rotate(${angle.toFixed(1)})`);
    }
    if (arcEl) {
        const totalLen = 499.2;
        const offset = totalLen * (1 - fraction);
        arcEl.style.strokeDashoffset = offset.toFixed(1);
    }
}

function addChartBar(mbps, isUpload, maxScale) {
    const chart = document.getElementById("bar-chart");
    if (!chart) return;
    const bar = document.createElement("div");
    bar.className = "chart-bar" + (isUpload ? " upload" : "");
    const scale = Math.max(10, maxScale);
    const pct = Math.min(100, Math.max(4, (mbps / scale) * 100));
    bar.style.height = `${pct.toFixed(1)}%`;
    bar.title = `${mbps.toFixed(2)} Mbps (${(mbps / 8).toFixed(2)} MB/s)`;
    chart.appendChild(bar);

    // Keep at most 35 bars
    while (chart.children.length > 35) {
        chart.removeChild(chart.firstChild);
    }
}

function clearChart() {
    const chart = document.getElementById("bar-chart");
    if (chart) chart.innerHTML = "";
}

function setPhaseTitle(msg, isPulsing = true) {
    const el = document.getElementById("phase-title");
    if (!el) return;
    if (isPulsing) {
        el.className = "phase-title active";
        el.innerHTML = `<span class="pulse-dot"></span> <span>${msg}</span>`;
    } else {
        el.className = "phase-title";
        el.innerHTML = `<span>${msg}</span>`;
    }
}

function formatRemainingSeconds(sec) {
    if (sec <= 0) return "00:00:00";
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function updateCooldownUI() {
    const banner = document.getElementById("cooldown-banner");
    const timer = document.getElementById("cooldown-timer");
    const btn = document.getElementById("btn-start-test");

    if (speedtestConfig.cooldown_remaining_seconds > 0) {
        if (banner) banner.className = "cooldown-banner visible";
        if (timer) timer.textContent = formatRemainingSeconds(speedtestConfig.cooldown_remaining_seconds);
        if (btn) btn.disabled = true;
    } else {
        if (banner) banner.className = "cooldown-banner";
        if (btn && !isRunning) btn.disabled = false;
    }
}

function startCooldownCountdown() {
    if (cooldownTimerId) clearInterval(cooldownTimerId);
    updateCooldownUI();
    if (speedtestConfig.cooldown_remaining_seconds <= 0) return;

    cooldownTimerId = setInterval(() => {
        speedtestConfig.cooldown_remaining_seconds--;
        if (speedtestConfig.cooldown_remaining_seconds <= 0) {
            speedtestConfig.cooldown_remaining_seconds = 0;
            speedtestConfig.can_test = true;
            clearInterval(cooldownTimerId);
            cooldownTimerId = null;
        }
        updateCooldownUI();
    }, 1000);
}

// Resolve effective speedtest server endpoint
function getTargetBase() {
    const raw = (speedtestConfig.server_url || "").trim();
    if (!raw) {
        return `${APP_BASE}/api/speedtest`;
    }
    let u = raw.replace(/\/+$/, "");
    // Scheme-qualified URLs
    if (/^https?:\/\//i.test(u)) {
        return u;
    }
    // IP:port or hostname:port without scheme (e.g. 192.168.1.50:8081)
    if (/^(\d{1,3}\.){3}\d{1,3}(:\d+)?(\/.*)?$/i.test(u) || /^[a-zA-Z0-9.-]+:\d+(\/.*)?$/i.test(u)) {
        const scheme = window.location.protocol === "https:" ? "https://" : "http://";
        return `${scheme}${u}`;
    }
    // Path starting with /
    if (u.startsWith("/")) {
        if (APP_BASE && !u.startsWith(APP_BASE + "/") && u !== APP_BASE) {
            return `${APP_BASE}${u}`;
        }
        return u;
    }
    // Relative path
    return APP_BASE ? `${APP_BASE}/${u}` : `/${u}`;
}

// 1. Latency & Jitter Test
async function runPingTest(targetBase) {
    setPhaseTitle(t("st_phase_ping", "Testando Latência (Ping & Jitter)..."));
    document.getElementById("chart-phase-indicator").textContent = "PING";

    const pingTimes = [];
    const iterations = 5;

    for (let i = 0; i < iterations; i++) {
        const start = performance.now();
        try {
            const resp = await fetch(`${targetBase}/ping?t=${Date.now()}_${i}`, {
                cache: "no-store",
                headers: { "Pragma": "no-cache", "Cache-Control": "no-cache" }
            });
            if (!resp.ok) {
                console.warn(`[Speedtest Ping] HTTP error ${resp.status} from ${targetBase}/ping`);
            } else {
                await resp.json();
                const rtt = performance.now() - start;
                pingTimes.push(rtt);
            }
        } catch (e) {
            console.error(`[Speedtest Ping] Error reaching ${targetBase}/ping:`, e);
        }
        await new Promise(r => setTimeout(r, 80));
    }

    if (pingTimes.length === 0) {
        return { ping: 0, jitter: 0, pingCount: 0 };
    }

    const avgPing = pingTimes.reduce((a, b) => a + b, 0) / pingTimes.length;
    let jitter = 0;
    if (pingTimes.length > 1) {
        let diffs = 0;
        for (let i = 1; i < pingTimes.length; i++) {
            diffs += Math.abs(pingTimes[i] - pingTimes[i - 1]);
        }
        jitter = diffs / (pingTimes.length - 1);
    }

    document.getElementById("metric-ping").textContent = avgPing.toFixed(1);
    document.getElementById("metric-jitter").textContent = jitter.toFixed(1);

    return { ping: avgPing, jitter, pingCount: pingTimes.length };
}

// 2. Download Test (5 seconds)
async function runDownloadTest(targetBase, durationSeconds) {
    setPhaseTitle(t("st_phase_download", "Testando Download..."));
    document.getElementById("chart-phase-indicator").textContent = "DOWNLOAD";
    clearChart();

    const startTime = performance.now();
    const durationMs = durationSeconds * 1000;
    let totalBytes = 0;
    let maxMbps = 0;
    const samples = [];

    // Controller for aborting streams when timer ends
    const abortController = new AbortController();

    // Launch 3 parallel download streams
    const streamCount = 3;
    const streamPromises = [];

    for (let s = 0; s < streamCount; s++) {
        streamPromises.push((async () => {
            while (performance.now() - startTime < durationMs && !abortController.signal.aborted) {
                try {
                    const resp = await fetch(`${targetBase}/download?bytes=30000000&stream=${s}&t=${Date.now()}`, {
                        cache: "no-store",
                        signal: abortController.signal
                    });
                    if (!resp.ok) {
                        console.error(`[Speedtest Download] HTTP ${resp.status} from ${targetBase}/download`);
                        break;
                    }
                    if (!resp.body) break;
                    const reader = resp.body.getReader();
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        if (value) {
                            totalBytes += value.length;
                        }
                        if (performance.now() - startTime >= durationMs) {
                            reader.cancel();
                            break;
                        }
                    }
                } catch (e) {
                    if (e.name === "AbortError") break;
                    console.error(`[Speedtest Download] Error streaming from ${targetBase}/download:`, e);
                    break;
                }
            }
        })());
    }

    // Sampler loop every 180ms
    let lastBytes = 0;
    let lastTime = performance.now();

    const samplerInterval = setInterval(() => {
        const now = performance.now();
        const deltaSec = (now - lastTime) / 1000;
        const deltaBytes = totalBytes - lastBytes;

        if (deltaSec > 0.05) {
            const instantMbps = (deltaBytes * 8) / (deltaSec * 1_000_000);
            if (instantMbps > maxMbps) maxMbps = instantMbps;
            samples.push(instantMbps);
            updateGauge(instantMbps);
            addChartBar(instantMbps, false, Math.max(maxMbps, 50));
            lastBytes = totalBytes;
            lastTime = now;
        }
    }, 180);

    // Wait until duration completes
    await new Promise(r => setTimeout(r, durationMs));
    abortController.abort();
    clearInterval(samplerInterval);

    try { await Promise.allSettled(streamPromises); } catch (_) {}

    const totalElapsedSec = Math.max(0.001, (performance.now() - startTime) / 1000);
    const avgMbps = (totalBytes * 8) / (totalElapsedSec * 1_000_000);

    // Update Download UI
    document.getElementById("metric-dl-avg").textContent = avgMbps.toFixed(2);
    document.getElementById("metric-dl-max").textContent = maxMbps.toFixed(2);
    document.getElementById("metric-dl-mbs").textContent = (avgMbps / 8).toFixed(2);

    updateGauge(avgMbps);
    return { avgMbps, maxMbps, totalBytes };
}

// 3. Upload Test (5 seconds)
async function runUploadTest(targetBase, durationSeconds) {
    setPhaseTitle(t("st_phase_upload", "Testando Upload..."));
    document.getElementById("chart-phase-indicator").textContent = "UPLOAD";
    clearChart();

    // Prepare 1MB pseudo-random binary payload to upload in chunks
    const chunkSizeBytes = 1024 * 1024; // 1 MB
    const uploadPayload = new Uint8Array(chunkSizeBytes);
    for (let i = 0; i < chunkSizeBytes; i++) {
        uploadPayload[i] = (i * 31 + 17) & 0xFF;
    }

    const startTime = performance.now();
    const durationMs = durationSeconds * 1000;
    let totalBytesUploaded = 0;
    let maxMbps = 0;
    const samples = [];
    const abortController = new AbortController();

    const streamCount = 2;
    const streamPromises = [];

    for (let s = 0; s < streamCount; s++) {
        streamPromises.push((async () => {
            while (performance.now() - startTime < durationMs && !abortController.signal.aborted) {
                try {
                    const postStart = performance.now();
                    const resp = await fetch(`${targetBase}/upload`, {
                        method: "POST",
                        body: uploadPayload,
                        cache: "no-store",
                        signal: abortController.signal
                    });
                    if (resp.ok) {
                        totalBytesUploaded += chunkSizeBytes;
                    } else {
                        console.error(`[Speedtest Upload] HTTP ${resp.status} from ${targetBase}/upload`);
                    }
                } catch (e) {
                    if (e.name === "AbortError") break;
                    console.error(`[Speedtest Upload] Error uploading to ${targetBase}/upload:`, e);
                    break;
                }
            }
        })());
    }

    // Sampler loop every 180ms
    let lastBytes = 0;
    let lastTime = performance.now();

    const samplerInterval = setInterval(() => {
        const now = performance.now();
        const deltaSec = (now - lastTime) / 1000;
        const deltaBytes = totalBytesUploaded - lastBytes;

        if (deltaSec > 0.05) {
            const instantMbps = (deltaBytes * 8) / (deltaSec * 1_000_000);
            if (instantMbps > maxMbps) maxMbps = instantMbps;
            samples.push(instantMbps);
            updateGauge(instantMbps);
            addChartBar(instantMbps, true, Math.max(maxMbps, 50));
            lastBytes = totalBytesUploaded;
            lastTime = now;
        }
    }, 180);

    await new Promise(r => setTimeout(r, durationMs));
    abortController.abort();
    clearInterval(samplerInterval);

    try { await Promise.allSettled(streamPromises); } catch (_) {}

    const totalElapsedSec = Math.max(0.001, (performance.now() - startTime) / 1000);
    const avgMbps = (totalBytesUploaded * 8) / (totalElapsedSec * 1_000_000);

    // Update Upload UI
    document.getElementById("metric-ul-avg").textContent = avgMbps.toFixed(2);
    document.getElementById("metric-ul-max").textContent = maxMbps.toFixed(2);
    document.getElementById("metric-ul-mbs").textContent = (avgMbps / 8).toFixed(2);

    updateGauge(avgMbps);
    return { avgMbps, maxMbps, totalBytesUploaded };
}

// Main Test Orchestrator
async function startSpeedTest() {
    if (isRunning) return;
    if (speedtestConfig.cooldown_remaining_seconds > 0) {
        alert(t("st_cooldown_alert", "Aguarde o período de intervalo para executar um novo teste."));
        return;
    }

    isRunning = true;
    const btn = document.getElementById("btn-start-test");
    if (btn) btn.disabled = true;

    // Reset UI metrics
    document.getElementById("metric-ping").textContent = "--";
    document.getElementById("metric-jitter").textContent = "--";
    document.getElementById("metric-dl-avg").textContent = "--";
    document.getElementById("metric-dl-max").textContent = "--";
    document.getElementById("metric-dl-mbs").textContent = "--";
    document.getElementById("metric-ul-avg").textContent = "--";
    document.getElementById("metric-ul-max").textContent = "--";
    document.getElementById("metric-ul-mbs").textContent = "--";
    updateGauge(0);
    clearChart();

    const targetBase = getTargetBase();
    const duration = speedtestConfig.duration_seconds || 5;
    console.log(`[NetMap Speedtest] Starting test against probe target: "${targetBase}" (Configured: "${speedtestConfig.server_url || ''}")`);

    try {
        // Step 1: Latency & Jitter
        const { ping, jitter, pingCount } = await runPingTest(targetBase);

        // Step 2: Download Test
        const { avgMbps: dlAvg, maxMbps: dlMax, totalBytes: dlBytes } = await runDownloadTest(targetBase, duration);

        // Step 3: Upload Test
        const { avgMbps: ulAvg, maxMbps: ulMax, totalBytesUploaded: ulBytes } = await runUploadTest(targetBase, duration);

        // Connection failure guard: check if any bytes transferred or pings succeeded
        if ((!dlBytes || dlBytes === 0) && (!ulBytes || ulBytes === 0) && (!pingCount || pingCount === 0)) {
            setPhaseTitle(`❌ ${t("st_phase_failed_conn", "Falha de conexão com o servidor de teste.")} (${targetBase})`, false);
            console.error(`[NetMap Speedtest] Could not connect or transfer data with target "${targetBase}". Please check network/proxy.`);
            return;
        }

        // Step 4: Submit Results to NetMap server
        setPhaseTitle(t("st_phase_saving", "Salvando resultados..."), false);
        try {
            const pingVal = Number.isFinite(ping) ? parseFloat(ping.toFixed(1)) : 0.0;
            const jitterVal = Number.isFinite(jitter) ? parseFloat(jitter.toFixed(1)) : 0.0;
            const dlMaxVal = Number.isFinite(dlMax) ? parseFloat(dlMax.toFixed(2)) : 0.0;
            const dlAvgVal = Number.isFinite(dlAvg) ? parseFloat(dlAvg.toFixed(2)) : 0.0;
            const ulMaxVal = Number.isFinite(ulMax) ? parseFloat(ulMax.toFixed(2)) : 0.0;
            const ulAvgVal = Number.isFinite(ulAvg) ? parseFloat(ulAvg.toFixed(2)) : 0.0;

            const saveResp = await fetch(`${APP_BASE}/api/speedtest/results`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ping_ms: pingVal,
                    jitter_ms: jitterVal,
                    download_max_mbps: dlMaxVal,
                    download_avg_mbps: dlAvgVal,
                    upload_max_mbps: ulMaxVal,
                    upload_avg_mbps: ulAvgVal
                })
            });

            if (saveResp.ok) {
                const resData = await saveResp.json();
                console.log("Speedtest result saved successfully, ID:", resData.id);
                if (resData.role === "visitor" && speedtestConfig.visitor_cooldown_hours > 0) {
                    speedtestConfig.cooldown_remaining_seconds = speedtestConfig.visitor_cooldown_hours * 3600;
                    speedtestConfig.can_test = false;
                    startCooldownCountdown();
                }
            } else if (saveResp.status === 429) {
                const errData = await saveResp.json();
                console.warn("Cooldown enforced on save:", errData);
            } else {
                const errTxt = await saveResp.text();
                console.error("Failed to save speedtest results:", saveResp.status, errTxt);
            }
        } catch (saveErr) {
            console.error("Failed to persist speedtest results:", saveErr);
        }

        setPhaseTitle(`✅ ${t("st_phase_done", "Teste Concluído com Sucesso!")}`, false);
        document.getElementById("chart-phase-indicator").textContent = "CONCLUÍDO";
    } catch (err) {
        console.error("Speedtest error:", err);
        setPhaseTitle(`❌ ${t("st_phase_error", "Erro ao executar o teste.")}`, false);
    } finally {
        isRunning = false;
        if (btn && speedtestConfig.cooldown_remaining_seconds <= 0) {
            btn.disabled = false;
        }
    }
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// Initial configuration loader
async function initSpeedtest() {
    try {
        const resp = await fetch(`${APP_BASE}/api/speedtest/config`, { cache: "no-store" });
        if (resp.ok) {
            const data = await resp.json();
            speedtestConfig = Object.assign(speedtestConfig, data);

            // Display server target
            const targetEl = document.getElementById("server-target-display");
            const ipEl = document.getElementById("client-ip-badge");
            const targetBase = getTargetBase();
            console.log(`[NetMap Speedtest] Initialized config:`, speedtestConfig);
            console.log(`[NetMap Speedtest] Resolved probe target endpoint: "${targetBase}"`);

            if (targetEl) {
                if (speedtestConfig.server_url && speedtestConfig.server_url.trim().length > 0) {
                    targetEl.innerHTML = `🛰️ <span style="color: #22d3ee;" title="${escapeHtml(targetBase)}">${escapeHtml(speedtestConfig.server_url)}</span>`;
                } else {
                    targetEl.innerHTML = `🎯 <span style="color: #94a3b8;">${escapeHtml(t("st_local_engine", "NetMap Local Engine (Servidor Local)"))}</span>`;
                }
            }
            if (ipEl && speedtestConfig.client_ip) {
                ipEl.textContent = `(${t("st_your_ip", "Seu IP")}: ${speedtestConfig.client_ip})`;
            }

            // Check Mixed Content warning
            if (window.location.protocol === "https:" && targetBase.startsWith("http://")) {
                console.warn(`[NetMap Speedtest] Mixed Content Warning: Site is HTTPS but probe target is HTTP ("${targetBase}").`);
                const phaseEl = document.getElementById("phase-title");
                if (phaseEl) {
                    phaseEl.innerHTML = `<span style="color: #f59e0b; font-size: 0.85rem;">⚠️ Atenção: Página HTTPS acessando probe HTTP (${escapeHtml(targetBase)}). Se o navegador bloquear, utilize o proxy Nginx (/netmap/speedtest/target) ou HTTPS.</span>`;
                }
            }

            if (speedtestConfig.cooldown_remaining_seconds > 0) {
                startCooldownCountdown();
            } else {
                updateCooldownUI();
            }
        }
    } catch (e) {
        console.warn("Could not load speedtest config:", e);
    }

    // Check user auth session for navigation slot
    try {
        const authResp = await fetch(`${APP_BASE}/api/auth/me`, { cache: "no-store" });
        const slot = document.getElementById("nav-auth-slot");
        if (authResp.ok && slot) {
            const authData = await authResp.json();
            if (authData.authenticated && authData.user) {
                const u = authData.user;
                const roleLabel = u.role === "admin" ? "Admin" : (u.role === "operator" ? (currentLang === "en" ? "Operator" : "Operador") : u.role);
                slot.innerHTML = `
                    <a href="${APP_BASE}/admin" class="btn btn-primary" style="padding: 4px 10px; font-size: 0.8rem;">⚙️ Admin</a>
                    <span style="font-size: 0.8rem; color: var(--text-muted); display: inline-flex; align-items: center; gap: 4px;">👤 <strong>${escapeHtml(u.username)}</strong> (${escapeHtml(roleLabel)})</span>
                `;
            } else {
                slot.innerHTML = `
                    <a href="${APP_BASE}/admin" class="btn btn-outline" style="padding: 4px 10px; font-size: 0.8rem;">🔐 Login</a>
                `;
            }
        }
    } catch (_) {}
}

document.addEventListener("DOMContentLoaded", () => {
    initSpeedtest();
});
