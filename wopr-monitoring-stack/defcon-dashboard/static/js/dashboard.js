/**
 * WOPR DEFCON ONE Dashboard - Frontend JavaScript
 * Real-time monitoring with Server-Sent Events
 */

// ═══════════════════════════════════════════════════════════════
// STATE & CONFIGURATION
// ═══════════════════════════════════════════════════════════════
const state = {
    currentTab: 'system',
    currentLogTab: 'fail2ban',
    eventSource: null,
    charts: {},
    blockedData: [],
    idsData: [],
};

const DEFCON_MESSAGES = {
    1: 'CRITICAL - IMMEDIATE ACTION REQUIRED',
    2: 'ELEVATED THREAT LEVEL',
    3: 'INCREASED READINESS',
    4: 'ABOVE NORMAL READINESS',
    5: 'ALL SYSTEMS NOMINAL',
};

const DEFCON_COLORS = {
    1: 'red',
    2: 'orange',
    3: 'orange',
    4: 'green',
    5: 'green',
};

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initTabs();
    initLogTabs();
    initCharts();
    initEventSource();
    fetchInitialData();
});

// ═══════════════════════════════════════════════════════════════
// CLOCK
// ═══════════════════════════════════════════════════════════════
function initClock() {
    function updateClock() {
        const now = new Date();
        const time = now.toLocaleTimeString('en-US', { hour12: false });
        document.getElementById('clock').textContent = time;
    }
    updateClock();
    setInterval(updateClock, 1000);
}

// ═══════════════════════════════════════════════════════════════
// TAB NAVIGATION
// ═══════════════════════════════════════════════════════════════
function initTabs() {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Update nav tabs
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.nav-tab[data-tab="${tabName}"]`).classList.add('active');

    // Update content
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');

    state.currentTab = tabName;

    // Load tab-specific data
    if (tabName === 'security') {
        loadSecurityLogs();
    }
}

function initLogTabs() {
    document.querySelectorAll('.log-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const logType = tab.dataset.log;
            switchLogTab(logType);
        });
    });
}

function switchLogTab(logType) {
    document.querySelectorAll('.log-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.log-tab[data-log="${logType}"]`).classList.add('active');
    state.currentLogTab = logType;
    loadSecurityLogs();
}

// ═══════════════════════════════════════════════════════════════
// MINI CHARTS (Simple canvas-based)
// ═══════════════════════════════════════════════════════════════
function initCharts() {
    // Initialize chart data arrays
    for (let i = 0; i < 30; i++) {
        state.blockedData.push(0);
        state.idsData.push(0);
    }
}

function drawChart(canvasId, data, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.offsetWidth;
    const height = canvas.offsetHeight;

    // Set actual canvas size
    canvas.width = width;
    canvas.height = height;

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Draw grid lines
    ctx.strokeStyle = 'rgba(0, 255, 65, 0.1)';
    ctx.lineWidth = 1;
    for (let i = 0; i < 5; i++) {
        const y = (height / 5) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }

    // Draw data line
    const max = Math.max(...data, 1);
    const step = width / (data.length - 1);

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.shadowColor = color;
    ctx.shadowBlur = 10;

    ctx.beginPath();
    data.forEach((value, index) => {
        const x = index * step;
        const y = height - (value / max) * (height - 10);
        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    ctx.stroke();

    // Draw current value
    ctx.shadowBlur = 0;
    ctx.fillStyle = color;
    ctx.font = 'bold 14px "Share Tech Mono"';
    ctx.textAlign = 'right';
    ctx.fillText(data[data.length - 1].toString(), width - 5, 20);
}

function updateCharts(blocked, idsAlerts) {
    // Shift data and add new values
    state.blockedData.shift();
    state.blockedData.push(blocked || 0);

    state.idsData.shift();
    state.idsData.push(idsAlerts || 0);

    // Redraw
    drawChart('blocked-canvas', state.blockedData, '#ff4444');
    drawChart('ids-canvas', state.idsData, '#ff8844');
}

// ═══════════════════════════════════════════════════════════════
// DATA FETCHING
// ═══════════════════════════════════════════════════════════════
async function fetchInitialData() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.error('Failed to fetch initial data:', error);
    }
}

function initEventSource() {
    if (state.eventSource) {
        state.eventSource.close();
    }

    state.eventSource = new EventSource('/api/stream');

    state.eventSource.addEventListener('status', (event) => {
        const data = JSON.parse(event.data);
        updateDashboard(data);
    });

    state.eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        // Reconnect after 5 seconds
        setTimeout(initEventSource, 5000);
    };
}

// ═══════════════════════════════════════════════════════════════
// DASHBOARD UPDATES
// ═══════════════════════════════════════════════════════════════
function updateDashboard(data) {
    if (!data) return;

    // Update timestamp
    document.getElementById('last-update').textContent =
        `Last update: ${new Date().toLocaleTimeString()}`;

    // Update DEFCON level
    updateDefconLevel(data.defcon_level);

    // Update system metrics
    if (data.metrics) {
        updateMetric('cpu', data.metrics.cpu);
        updateMetric('memory', data.metrics.memory);
        updateMetric('disk', data.metrics.disk);
    }

    // Update security metrics
    if (data.security) {
        document.getElementById('fail2ban-bans').textContent =
            data.security.fail2ban_bans || '0';
        document.getElementById('suricata-alerts').textContent =
            data.security.suricata_alerts || '0';
    }

    // Update alerts
    if (data.alerts) {
        updateAlerts(data.alerts);
    }

    // Update charts
    updateCharts(
        data.security?.firewall_blocks || 0,
        data.security?.suricata_alerts || 0
    );
}

function updateDefconLevel(level) {
    const levelEl = document.getElementById('defcon-level');
    const statusEl = document.getElementById('defcon-status');

    levelEl.textContent = level;
    statusEl.textContent = DEFCON_MESSAGES[level] || 'UNKNOWN';

    // Update color class
    levelEl.classList.remove('green', 'orange', 'red');
    levelEl.classList.add(DEFCON_COLORS[level]);
}

function updateMetric(name, value) {
    const valueEl = document.getElementById(`${name}-value`);
    const barEl = document.getElementById(`${name}-bar`);

    if (valueEl && value !== null && value !== undefined) {
        const numValue = parseFloat(value).toFixed(1);
        valueEl.textContent = numValue;

        if (barEl) {
            barEl.style.width = `${Math.min(numValue, 100)}%`;

            // Color based on threshold
            if (numValue > 90) {
                barEl.style.background = '#ff4444';
                barEl.style.boxShadow = '0 0 10px #ff4444';
            } else if (numValue > 75) {
                barEl.style.background = '#ff8844';
                barEl.style.boxShadow = '0 0 10px #ff8844';
            } else {
                barEl.style.background = '#00ff41';
                barEl.style.boxShadow = '0 0 10px #00ff41';
            }
        }
    }
}

function updateAlerts(alerts) {
    const container = document.getElementById('alerts-container');
    if (!container) return;

    if (!alerts.items || alerts.items.length === 0) {
        container.innerHTML = `
            <div class="alert-item info">
                <span class="alert-icon">&#9432;</span>
                <span class="alert-message">No active alerts - All systems operational</span>
            </div>
        `;
        return;
    }

    container.innerHTML = alerts.items.map(alert => {
        const severity = alert.labels?.severity || 'info';
        const name = alert.labels?.alertname || 'Unknown Alert';
        const instance = alert.labels?.instance || '';
        const description = alert.annotations?.description || '';

        return `
            <div class="alert-item ${severity}">
                <span class="alert-icon">${severity === 'critical' ? '&#9888;' : '&#9888;'}</span>
                <span class="alert-message">
                    <strong>${name}</strong> ${instance ? `on ${instance}` : ''}<br>
                    <small>${description}</small>
                </span>
                <span class="alert-time">${new Date(alert.startsAt).toLocaleTimeString()}</span>
            </div>
        `;
    }).join('');
}

// ═══════════════════════════════════════════════════════════════
// SECURITY LOGS
// ═══════════════════════════════════════════════════════════════
async function loadSecurityLogs() {
    const container = document.getElementById('security-logs');
    if (!container) return;

    container.innerHTML = '<div class="log-line">Loading logs...</div>';

    try {
        const response = await fetch(`/api/logs/${state.currentLogTab}`);
        const data = await response.json();

        if (!data.logs || data.logs.length === 0) {
            container.innerHTML = '<div class="log-line">No logs available</div>';
            return;
        }

        container.innerHTML = data.logs.map(log => {
            const action = log.labels?.action || log.labels?.event_type || 'INFO';
            const ip = log.labels?.ip || log.labels?.src_ip || '';

            return `
                <div class="log-line">
                    <span class="log-time">${log.timestamp}</span>
                    <span class="log-action ${action.toLowerCase()}">${action.toUpperCase()}</span>
                    ${ip ? `<span class="log-ip">${ip}</span>` : ''}
                    <span class="log-details">${escapeHtml(log.message.substring(0, 100))}</span>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Failed to load logs:', error);
        container.innerHTML = '<div class="log-line">Error loading logs</div>';
    }
}

// ═══════════════════════════════════════════════════════════════
// TOP BLOCKED IPs
// ═══════════════════════════════════════════════════════════════
function updateTopBlockedIPs(ips) {
    const container = document.getElementById('top-blocked-ips');
    if (!container || !ips) return;

    container.innerHTML = ips.slice(0, 5).map((ip, index) => `
        <div class="ip-item">
            <span class="ip-rank r${index + 1}">${index + 1}</span>
            <span class="ip-address">${ip.address}</span>
            <span class="ip-count">? ${ip.count}</span>
        </div>
    `).join('');
}

// ═══════════════════════════════════════════════════════════════
// SUPPORT PLANE ACTIONS
// ═══════════════════════════════════════════════════════════════
function runDiagnostics() {
    alert('Running diagnostics across all nodes...\n\nThis would connect to the Support Plane API.');
}

function showRemediation() {
    alert('Remediation actions panel\n\nThis would show available remediation options from the Support Plane.');
}

function breakGlass() {
    if (confirm('BREAK GLASS - Emergency Access\n\nThis will initiate emergency access procedures. Continue?')) {
        alert('Break glass procedure initiated.\n\nThis would trigger the Support Plane break glass flow.');
    }
}

function showAuditLog() {
    alert('Audit Log\n\nThis would display the Support Plane audit trail.');
}

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (state.eventSource) {
        state.eventSource.close();
    }
});