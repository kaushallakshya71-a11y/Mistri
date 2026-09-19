/**
 * Mistri Admin Views
 * Dashboard, Repairs Management, Inventory, Reports, Staff Management
 */

/** Admin Dashboard */
async function renderAdminDashboard() {
    showLoading();
    try {
        const stats = await api.get('/repairs/stats/dashboard');
        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="page-title">📊 Admin Dashboard</div>
                            <div class="page-subtitle">Overview of your repair shop performance</div>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="api.download('/reports/export/csv?type=repairs', 'mistri_repairs.csv')" class="btn btn-outline btn-sm">⬇ Export CSV</button>
                            <button onclick="logout()" class="btn btn-outline btn-sm" style="color:var(--danger);border-color:rgba(239,68,68,0.4)">🚪 Logout</button>
                        </div>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card animate-scale-in stagger-1">
                        <div class="stat-icon">🔧</div>
                        <div class="stat-value">${stats.total}</div>
                        <div class="stat-label">Total Repairs</div>
                    </div>
                    <div class="stat-card animate-scale-in stagger-2">
                        <div class="stat-icon">⏳</div>
                        <div class="stat-value">${stats.pending}</div>
                        <div class="stat-label">Pending</div>
                    </div>
                    <div class="stat-card animate-scale-in stagger-3">
                        <div class="stat-icon">✅</div>
                        <div class="stat-value">${stats.completed}</div>
                        <div class="stat-label">Completed</div>
                    </div>
                    <div class="stat-card animate-scale-in stagger-4">
                        <div class="stat-icon">💰</div>
                        <div class="stat-value">${formatCurrency(stats.revenue)}</div>
                        <div class="stat-label">Total Revenue</div>
                    </div>
                    ${stats.low_stock_alerts > 0 ? `
                        <div class="stat-card animate-scale-in stagger-5" style="border-color:rgba(255,77,77,0.4)">
                            <div class="stat-icon">⚠️</div>
                            <div class="stat-value text-danger">${stats.low_stock_alerts}</div>
                            <div class="stat-label">Low Stock Alerts</div>
                            <div class="stat-change down">Action required</div>
                        </div>
                    ` : ''}
                </div>

                <div class="charts-grid">
                    <div class="chart-card">
                        <div class="chart-header">
                            <div class="chart-title">📈 Revenue Analytics</div>
                            <div class="chart-time-pills">
                                <button class="chart-pill-btn active" id="btn-rev-7" onclick="filterRevenueDays(7, this)">7D</button>
                                <button class="chart-pill-btn" id="btn-rev-14" onclick="filterRevenueDays(14, this)">14D</button>
                                <button class="chart-pill-btn" id="btn-rev-30" onclick="filterRevenueDays(30, this)">30D</button>
                            </div>
                        </div>
                        <div class="chart-kpi-row">
                            <div>
                                <div class="chart-kpi-amount" id="chart-rev-amount">${formatCurrency((stats.daily_revenue || []).reduce((s, d) => s + (d.revenue || 0), 0))}</div>
                                <div class="chart-kpi-sub">
                                    <span class="kpi-trend-pill positive">↑ 14.2%</span>
                                    <span>vs previous period • Daily avg: <b>${formatCurrency(Math.round(((stats.daily_revenue || []).reduce((s, d) => s + (d.revenue || 0), 0)) / Math.max(1, (stats.daily_revenue || []).length)))}</b></span>
                                </div>
                            </div>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="revenue-chart"></canvas>
                        </div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header">
                            <div class="chart-title">🔄 Repair Pipeline Distribution</div>
                            <span class="chart-badge">Live Status</span>
                        </div>
                        <div class="chart-split">
                            <div class="chart-wrapper" style="height:210px;position:relative">
                                <canvas id="status-chart"></canvas>
                            </div>
                            <div class="chart-breakdown-list" id="status-breakdown-container">
                                <!-- Populated dynamically by renderStatusChart -->
                            </div>
                        </div>
                    </div>
                </div>

                <div class="table-container">
                    <div class="table-header-row">
                        <div class="table-title">🕒 Recent Jobs</div>
                        <button class="btn btn-outline btn-sm" onclick="router.navigate('/admin/repairs')">View All</button>
                    </div>
                    <table>
                        <thead><tr><th>Repair ID</th><th>Customer</th><th>Device</th><th>Status</th><th>Date</th></tr></thead>
                        <tbody>
                            ${stats.recent_jobs.map(j => `
                                <tr onclick="renderAdminRepairDetail(${j.id})" style="cursor:pointer">
                                    <td class="font-mono text-primary-color">${j.repair_id}</td>
                                    <td>${j.customer_name}</td>
                                    <td>${j.device_type} — ${j.brand}</td>
                                    <td>${statusBadge(j.status)}</td>
                                    <td style="color:var(--text-muted);font-size:0.8rem">${formatDate(j.created_at)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `);

        // Cache stats for reactive theme changes
        window._cachedDashboardStats = stats;

        // Render charts
        renderRevenueChart(stats.daily_revenue);
        renderStatusChart(stats.status_distribution);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** Professional Chart Theme Helper */
function getChartTheme() {
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    return {
        isLight,
        textColor: isLight ? '#475569' : '#94A3B8',
        textMuted: isLight ? '#94A3B8' : '#64748B',
        titleColor: isLight ? '#0F172A' : '#F8FAFC',
        gridColor: isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.06)',
        borderColor: isLight ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.1)',
        tooltipBg: isLight ? '#FFFFFF' : '#13151F',
        tooltipBorder: isLight ? 'rgba(0,0,0,0.12)' : 'rgba(249, 115, 22, 0.35)',
        tooltipTitle: isLight ? '#0F172A' : '#FFFFFF',
        tooltipBody: isLight ? '#334155' : '#E2E8F0',
        primary: '#F97316',
        primaryDark: '#EA580C',
        accent: '#FBBF24',
        success: '#22C55E',
        info: '#38BDF8',
        purple: '#A855F7',
        pink: '#EC4899',
        danger: '#EF4444'
    };
}

// Interactive Revenue Filter Helper
window.filterRevenueDays = function(days, btn) {
    if (!window._cachedDashboardStats || !window._cachedDashboardStats.daily_revenue) return;
    const parent = btn.closest('.chart-time-pills');
    if (parent) {
        parent.querySelectorAll('.chart-pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }
    const all = window._cachedDashboardStats.daily_revenue;
    const sliced = all.slice(-days);
    const total = sliced.reduce((s, d) => s + (d.revenue || 0), 0);
    const amountEl = document.getElementById('chart-rev-amount');
    if (amountEl) {
        amountEl.textContent = formatCurrency(total);
    }
    renderRevenueChart(sliced);
};

let _revenueChartInstance = null;
function renderRevenueChart(data = []) {
    const canvas = document.getElementById('revenue-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (_revenueChartInstance) {
        _revenueChartInstance.destroy();
        _revenueChartInstance = null;
    }

    const theme = getChartTheme();
    const gradient = ctx.createLinearGradient(0, 0, 0, 240);
    gradient.addColorStop(0, 'rgba(249, 115, 22, 0.40)');
    gradient.addColorStop(0.55, 'rgba(249, 115, 22, 0.12)');
    gradient.addColorStop(1, 'rgba(249, 115, 22, 0.00)');

    const labels = (data || []).map(d => {
        const raw = d.day || d.period || '';
        if (raw.includes('-')) {
            const parts = raw.split('-');
            if (parts.length === 3) {
                const dt = new Date(parts[0], parts[1] - 1, parts[2]);
                if (!isNaN(dt.getTime())) {
                    return dt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
                }
            }
        }
        return raw;
    });

    const values = (data || []).map(d => d.revenue || 0);

    // Neon Line Glow & Crosshair plugin
    const neonGlowPlugin = {
        id: 'neonGlowPlugin',
        beforeDatasetDraw(chart, args) {
            const { ctx } = chart;
            ctx.save();
            ctx.shadowColor = 'rgba(249, 115, 22, 0.65)';
            ctx.shadowBlur = 18;
            ctx.shadowOffsetY = 6;
        },
        afterDatasetDraw(chart, args) {
            chart.ctx.restore();
        },
        afterDraw(chart) {
            if (chart.tooltip && chart.tooltip._active && chart.tooltip._active.length) {
                const activePoint = chart.tooltip._active[0];
                const { ctx, chartArea: { top, bottom } } = chart;
                const x = activePoint.element.x;
                ctx.save();
                ctx.beginPath();
                ctx.moveTo(x, top);
                ctx.lineTo(x, bottom);
                ctx.lineWidth = 1.5;
                ctx.strokeStyle = 'rgba(249, 115, 22, 0.35)';
                ctx.setLineDash([4, 4]);
                ctx.stroke();
                ctx.restore();
            }
        }
    };

    _revenueChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.length ? labels : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [{
                label: 'Revenue',
                data: values.length ? values : [0, 0, 0, 0, 0, 0, 0],
                borderColor: theme.primary,
                borderWidth: 2.8,
                backgroundColor: gradient,
                fill: true,
                tension: 0.38,
                pointBackgroundColor: theme.primary,
                pointBorderColor: theme.isLight ? '#FFFFFF' : '#13151F',
                pointBorderWidth: 2.5,
                pointRadius: 4.5,
                pointHoverRadius: 7.5,
                pointHoverBackgroundColor: theme.primaryDark,
                pointHoverBorderColor: '#FFFFFF',
                pointHoverBorderWidth: 3,
            }]
        },
        plugins: [neonGlowPlugin],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 750,
                easing: 'easeOutQuart'
            },
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: theme.tooltipBg,
                    titleColor: theme.tooltipTitle,
                    bodyColor: theme.tooltipBody,
                    borderColor: theme.tooltipBorder,
                    borderWidth: 1.5,
                    padding: 12,
                    boxPadding: 6,
                    usePointStyle: true,
                    cornerRadius: 10,
                    displayColors: true,
                    titleFont: { family: 'Inter', size: 12, weight: '600' },
                    bodyFont: { family: 'Inter', size: 13, weight: '700' },
                    callbacks: {
                        label: (context) => ' Daily Revenue: ' + formatCurrency(context.parsed.y)
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    border: { display: false },
                    ticks: {
                        color: theme.textColor,
                        font: { family: 'Inter', size: 11, weight: '500' }
                    }
                },
                y: {
                    border: { display: false },
                    grid: {
                        color: theme.gridColor,
                        borderDash: [4, 4]
                    },
                    ticks: {
                        color: theme.textColor,
                        font: { family: 'Inter', size: 11 },
                        callback: (v) => v >= 1000 ? '₹' + (v / 1000).toFixed(1) + 'k' : '₹' + v
                    }
                }
            }
        }
    });
}

let _statusChartInstance = null;
function renderStatusChart(data = []) {
    const canvas = document.getElementById('status-chart');
    if (!canvas || !data.length) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (_statusChartInstance) {
        _statusChartInstance.destroy();
        _statusChartInstance = null;
    }

    const theme = getChartTheme();
    const colors = {
        Requested: '#38BDF8',
        Received: '#38BDF8',
        Assigned: '#6366F1',
        Diagnosing: '#FBBF24',
        Approved: '#06B6D4',
        Repairing: '#F97316',
        Ready: '#A855F7',
        Completed: '#22C55E',
        Delivered: '#16A34A',
        'On Hold': '#EAB308',
        Cancelled: '#EF4444',
        Rejected: '#EF4444'
    };

    const totalJobs = data.reduce((sum, d) => sum + (d.count || 0), 0);

    // Populate Status Breakdown Progress Track List
    const breakdownContainer = document.getElementById('status-breakdown-container');
    if (breakdownContainer) {
        // Sort descending by count
        const sorted = [...data].sort((a, b) => (b.count || 0) - (a.count || 0)).slice(0, 5);
        breakdownContainer.innerHTML = sorted.map(d => {
            const count = d.count || 0;
            const pct = totalJobs > 0 ? Math.round((count / totalJobs) * 100) : 0;
            const color = colors[d.status] || '#94A3B8';
            return `
                <div class="chart-breakdown-row">
                    <div class="chart-breakdown-meta">
                        <div class="chart-breakdown-label">
                            <span class="chart-breakdown-dot" style="background:${color}"></span>
                            <span>${d.status}</span>
                        </div>
                        <div class="chart-breakdown-values">
                            <b>${count}</b> <span style="color:var(--text-muted);font-size:0.72rem">(${pct}%)</span>
                        </div>
                    </div>
                    <div class="chart-progress-track">
                        <div class="chart-progress-fill" style="width:${pct}%;background:${color}"></div>
                    </div>
                </div>
            `;
        }).join('');
    }

    const centerTextPlugin = {
        id: 'statusCenterText',
        beforeDraw(chart) {
            const { width, height, ctx } = chart;
            ctx.save();
            ctx.font = '800 1.7rem "Space Grotesk", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = theme.titleColor;
            ctx.fillText(totalJobs, width / 2, height / 2 - 10);

            ctx.font = '600 0.68rem "Inter", sans-serif';
            ctx.letterSpacing = '0.08em';
            ctx.fillStyle = theme.textMuted;
            ctx.fillText('TOTAL JOBS', width / 2, height / 2 + 12);
            ctx.restore();
        }
    };

    _statusChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.map(d => d.status),
            datasets: [{
                data: data.map(d => d.count),
                backgroundColor: data.map(d => colors[d.status] || '#94A3B8'),
                borderWidth: 0,
                spacing: 3,
                borderRadius: 5,
                hoverOffset: 8,
            }]
        },
        plugins: [centerTextPlugin],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '72%',
            animation: {
                animateRotate: true,
                animateScale: true,
                duration: 750,
                easing: 'easeOutQuart'
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: theme.tooltipBg,
                    titleColor: theme.tooltipTitle,
                    bodyColor: theme.tooltipBody,
                    borderColor: theme.tooltipBorder,
                    borderWidth: 1.5,
                    padding: 12,
                    boxPadding: 6,
                    usePointStyle: true,
                    cornerRadius: 10,
                    titleFont: { family: 'Inter', size: 12, weight: '600' },
                    bodyFont: { family: 'Inter', size: 12, weight: '500' },
                    callbacks: {
                        label: (ctx) => {
                            const val = ctx.raw || 0;
                            const pct = totalJobs > 0 ? Math.round((val / totalJobs) * 100) : 0;
                            return ` ${ctx.label}: ${val} (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
}

/** Admin Repairs Management */
async function renderAdminRepairs() {
    showLoading();
    try {
        const [jobs, users, workloads] = await Promise.all([
            api.get('/repairs/'),
            api.get('/auth/users'),
            api.get('/repairs/technicians/workload').catch(() => [])
        ]);
        const workloadMap = {};
        workloads.forEach(w => { workloadMap[w.id] = w.active_repairs_count; });

        const technicians = users.filter(u => u.role === 'staff').map(t => ({
            id: t.id,
            name: t.name,
            active_jobs: workloadMap[t.id] || 0
        }));

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="page-title">🔧 Manage Repairs</div>
                    <div class="page-subtitle">${jobs.length} total repair jobs · Smart assignment & lifecycle tracking</div>
                </div>

                <div class="filter-row" style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">
                    <div class="search-bar" style="flex:1;min-width:240px;max-width:380px">
                        <span class="search-icon">🔍</span>
                        <input type="text" placeholder="Search by name, device, repair ID..." id="repair-search" oninput="filterRepairs()" >
                    </div>
                    <select class="form-control" id="status-filter" onchange="filterRepairs()" style="width:auto">
                        <option value="">All Statuses</option>
                        <option value="Requested">Requested (New)</option>
                        <option value="Assigned">Assigned</option>
                        <option value="Diagnosing">Diagnosing</option>
                        <option value="Approved">Approved</option>
                        <option value="Repairing">Repairing</option>
                        <option value="Ready">Ready for Pickup</option>
                        <option value="Delivered">Delivered</option>
                        <option value="Completed">Completed</option>
                        <option value="On Hold">On Hold</option>
                        <option value="Cancelled">Cancelled</option>
                        <option value="Rejected">Rejected</option>
                    </select>
                </div>

                <div class="table-container">
                    <table id="repairs-table">
                        <thead><tr>
                            <th>Repair ID</th><th>Customer</th><th>Device</th>
                            <th>Problem</th><th>Status</th><th>Technician</th><th>Cost</th><th>Date</th><th>Action</th>
                        </tr></thead>
                        <tbody id="repairs-tbody">
                            ${jobs.map(j => `
                                <tr data-search="${[j.repair_id, j.customer_name, j.brand, j.model, j.device_type].join(' ').toLowerCase()}" data-status="${j.status}">
                                    <td class="font-mono text-primary-color" style="cursor:pointer;font-weight:600" onclick="renderAdminRepairDetail(${j.id})">${j.repair_id}</td>
                                    <td>
                                        <div style="font-weight:500">${j.customer_name}</div>
                                        <div style="font-size:0.75rem;color:var(--text-muted)">${j.customer_phone || ''}</div>
                                        <span class="badge" style="font-size:0.65rem;padding:2px 5px;background:${j.service_type === 'Home Pickup' ? '#8b5cf622' : '#0ea5e922'};color:${j.service_type === 'Home Pickup' ? '#a78bfa' : '#38bdf8'}">
                                            ${j.service_type === 'Home Pickup' ? '🏠 Home Visit' : '🏪 Store'}
                                        </span>
                                    </td>
                                    <td>${j.device_type}<br><span style="font-size:0.8rem;color:var(--text-muted)">${j.brand} ${j.model}</span></td>
                                    <td style="max-width:180px;font-size:0.8rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${j.problem_description}</td>
                                    <td>${statusBadge(j.status)}</td>
                                    <td style="font-size:0.85rem">
                                        ${j.technician_name ? `
                                            <span style="font-weight:500">👨‍🔧 ${j.technician_name}</span>
                                        ` : `
                                            <button class="btn btn-sm btn-outline" style="border-color:#6C63FF;color:#6C63FF;padding:3px 8px;font-size:0.75rem" onclick="openAiTechnicianModal(${j.id}, '${j.device_type}')">
                                                🤖 AI Match
                                            </button>
                                        `}
                                    </td>
                                    <td style="font-weight:500">${j.actual_cost ? formatCurrency(j.actual_cost) : j.estimated_cost ? formatCurrency(j.estimated_cost) : '—'}</td>
                                    <td style="font-size:0.78rem;color:var(--text-muted)">${formatDate(j.created_at)}</td>
                                    <td>
                                        <div class="flex gap-1">
                                            <button class="btn btn-outline btn-sm" onclick='openUpdateStatusModal(${j.id}, "${j.status}", ${JSON.stringify(technicians)})' title="Update Status">🔄 Status</button>
                                            <button class="btn btn-outline btn-sm" onclick='openAdminEditRepairModal(${JSON.stringify(j).replace(/'/g, "&apos;")})' title="Edit Full Repair">✏️</button>
                                            <button class="btn btn-danger btn-sm" onclick="deleteRepairJob(${j.id}, '${j.repair_id}')" title="Delete Repair">🗑️</button>
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function filterRepairs() {
    const search = document.getElementById('repair-search').value.toLowerCase();
    const status = document.getElementById('status-filter').value;
    document.querySelectorAll('#repairs-tbody tr').forEach(row => {
        const matchSearch = !search || row.dataset.search.includes(search);
        const matchStatus = !status || row.dataset.status === status;
        row.style.display = (matchSearch && matchStatus) ? '' : 'none';
    });
}

async function openAiTechnicianModal(jobId, deviceType) {
    const overlay = showModal(`
        <div class="modal-header">
            <span class="modal-title">🤖 AI Smart Technician Match</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="font-size:0.85rem;color:var(--text-muted);margin-bottom:12px">
            Analyzing technician skill profiles, past completed repairs for <b>${deviceType || 'device'}</b>, customer ratings, and current workload.
        </div>
        <div id="ai-tech-content" style="text-align:center;padding:24px 0">
            <div class="spinner" style="width:36px;height:36px;border-width:3px;margin:0 auto 12px"></div>
            <div style="font-size:0.85rem;color:var(--text-muted)">Matching best available technician...</div>
        </div>
    `);

    try {
        const res = await api.get(`/ai/recommend-technician/${jobId}`);
        const container = document.getElementById('ai-tech-content');
        if (!container) return;

        if (!res.recommendations || res.recommendations.length === 0) {
            container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">👨‍🔧</div><div>No technicians registered yet</div></div>`;
            return;
        }

        container.style.textAlign = 'left';
        container.innerHTML = `
            <div style="display:flex;flex-direction:column;gap:12px">
                ${res.recommendations.map((rec, idx) => `
                    <div style="border:1px solid ${idx === 0 ? 'var(--primary)' : 'var(--border)'};background:${idx === 0 ? 'rgba(108,99,255,0.08)' : 'var(--card-bg)'};border-radius:var(--radius-md);padding:14px">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                            <div style="font-weight:600;font-size:1rem;display:flex;align-items:center;gap:6px">
                                ${idx === 0 ? '🏆' : '👨‍🔧'} ${rec.name}
                                ${idx === 0 ? '<span class="badge badge-completed" style="font-size:0.65rem">Top Match</span>' : ''}
                            </div>
                            <span class="badge" style="background:#6C63FF22;color:#6C63FF;font-weight:700;font-size:0.85rem">${rec.match_score}% Match</span>
                        </div>
                        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;font-size:0.75rem;color:var(--text-muted);margin:8px 0;background:rgba(255,255,255,0.03);padding:6px 10px;border-radius:var(--radius-sm)">
                            <div>🛠️ Past Done: <b>${rec.completed_same_device}</b></div>
                            <div>⭐ Rating: <b>${rec.avg_rating || '5.0'}</b></div>
                            <div>⏳ Active Jobs: <b>${rec.current_workload}</b></div>
                        </div>
                        <div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:10px;font-style:italic">
                            💡 ${rec.rationale}
                        </div>
                        <button class="btn ${idx === 0 ? 'btn-primary' : 'btn-outline'} btn-sm w-full" onclick="quickAssignTechnician(${jobId}, ${rec.technician_id}, '${rec.name}')">
                            ✓ Assign to ${rec.name}
                        </button>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (e) {
        const container = document.getElementById('ai-tech-content');
        if (container) container.innerHTML = `<div class="text-danger" style="padding:16px">${e.message}</div>`;
    }
}

async function quickAssignTechnician(jobId, techId, techName) {
    try {
        await api.post(`/repairs/${jobId}/assign`, { technician_id: techId });
        showToast(`Job assigned to ${techName}!`, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminRepairs();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function openUpdateStatusModal(jobId, currentStatus, technicians) {
    const statuses = [
        'Requested', 'Assigned', 'Diagnosing', 'Approved',
        'Repairing', 'Ready', 'Delivered', 'Completed',
        'On Hold', 'Cancelled', 'Rejected'
    ];
    const overlay = showModal(`
        <div class="modal-header">
            <span class="modal-title">✏️ Update Repair #${jobId}</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-group">
            <label class="form-label">Status</label>
            <select class="form-control" id="modal-status">
                ${statuses.map(s => `<option value="${s}" ${s === currentStatus ? 'selected' : ''}>${s}</option>`).join('')}
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Assign Technician</label>
            <select class="form-control" id="modal-tech">
                <option value="">No change</option>
                ${technicians.map(t => `<option value="${t.id}">${t.name} (${t.active_jobs} active)</option>`).join('')}
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Actual Cost (₹)</label>
            <input type="number" class="form-control" id="modal-cost" placeholder="0">
        </div>
        <div class="form-group">
            <label class="form-label">Technician Notes</label>
            <textarea class="form-control" id="modal-notes" rows="3" placeholder="Optional notes..."></textarea>
        </div>
        <button class="btn btn-primary w-full" onclick="submitStatusUpdate(${jobId})">Save Changes</button>
    `);
}

async function submitStatusUpdate(jobId) {
    const status = document.getElementById('modal-status').value;
    const techId = document.getElementById('modal-tech').value;
    const cost = document.getElementById('modal-cost').value;
    const notes = document.getElementById('modal-notes').value;
    try {
        await api.put(`/repairs/${jobId}/status`, {
            status,
            technician_id: techId ? parseInt(techId) : null,
            actual_cost: cost ? parseFloat(cost) : null,
            technician_notes: notes || null
        });
        showToast('Status updated!', 'success');
        document.querySelector('.modal-overlay').remove();
        renderAdminRepairs();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function renderAdminRepairDetail(jobId) {
    showLoading();
    try {
        const [job, history, photos, warranty] = await Promise.all([
            api.get(`/repairs/${jobId}`),
            api.get(`/repairs/${jobId}/history`).catch(() => []),
            api.get(`/repairs/${jobId}/photos`).catch(() => []),
            api.get(`/warranties/repair/${jobId}`).catch(() => null)
        ]);

        setContent(`
            <div class="page" style="max-width:850px;margin:0 auto">
                <div style="margin-bottom:20px;display:flex;justify-content:space-between;align-items:center">
                    <button class="btn btn-outline btn-sm" onclick="router.navigate('/admin/repairs')">← Back to Repairs</button>
                    ${warranty && warranty.status === 'Active' ? `
                        <span class="badge badge-completed" style="padding:6px 12px;font-size:0.85rem">🛡️ ${warranty.days_remaining} Days Warranty Active</span>
                    ` : ''}
                </div>
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="font-mono text-primary-color" style="font-size:1.2rem;font-weight:700">${job.repair_id}</div>
                            <div class="page-title">${job.brand} ${job.model} (${job.device_type})</div>
                        </div>
                        ${statusBadge(job.status)}
                    </div>
                </div>

                <!-- Lifecycle Visual Timeline & Logs -->
                <div class="card" style="margin-bottom:16px">
                    ${renderTimeline(job.status, history)}
                </div>

                <!-- Rejection Banner if Rejected by Staff -->
                ${job.rejection_reason ? `
                    <div style="padding:12px 16px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:var(--radius-sm);margin-bottom:16px">
                        <div style="font-weight:700;color:var(--danger)">⚠️ Technician Rejection Notice:</div>
                        <div style="font-size:0.85rem;margin-top:2px">Assigned technician rejected this job. Reason: <b>${job.rejection_reason}</b></div>
                        ${job.rejection_notes ? `<div style="font-size:0.8rem;color:var(--text-muted);margin-top:2px">Notes: ${job.rejection_notes}</div>` : ''}
                        <div style="margin-top:8px">
                            <button class="btn btn-danger btn-sm" onclick="openReassignModal(${jobId}, '${job.technician_name || ''}')">🔄 Reassign to Another Technician</button>
                        </div>
                    </div>
                ` : ''}

                <!-- Customer and Technician info -->
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
                    <div class="card">
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:8px;font-weight:700">CUSTOMER & SERVICE MODE</div>
                        <div style="font-weight:600">${job.customer_name}</div>
                        <div style="font-size:0.85rem">${job.customer_phone || 'No phone'} · ${job.customer_email || ''}</div>
                        <div style="margin-top:6px">
                            <span class="badge" style="background:${job.service_type === 'Home Pickup' ? '#8b5cf622' : '#0ea5e922'};color:${job.service_type === 'Home Pickup' ? '#a78bfa' : '#38bdf8'}">
                                ${job.service_type === 'Home Pickup' ? '🏠 Home Pickup / Visit' : '🏪 Store Drop-off'}
                            </span>
                        </div>
                        ${job.pickup_address ? `
                            <div style="font-size:0.82rem;margin-top:6px;color:var(--text-secondary)">
                                📍 <b>Address:</b> ${job.pickup_address}
                                <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(job.pickup_address)}" target="_blank" style="margin-left:6px;color:var(--primary);text-decoration:none;font-weight:600">🗺️ Maps</a>
                            </div>
                        ` : ''}
                    </div>
                    <div class="card">
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:8px;font-weight:700">ASSIGNED TECHNICIAN</div>
                        <div style="font-weight:600">${job.technician_name || '<span class="text-muted">Unassigned</span>'}</div>
                        ${job.assigned_at ? `<div style="font-size:0.75rem;color:var(--text-muted)">Assigned: ${formatDate(job.assigned_at)}</div>` : ''}
                        <div style="margin-top:8px">
                            <button class="btn btn-outline btn-sm" onclick="openReassignModal(${jobId}, '${job.technician_name || ''}')">🔄 Reassign Technician</button>
                        </div>
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:8px;font-weight:700">COST</div>
                        <div style="font-weight:600;color:var(--primary)">${formatCurrency(job.actual_cost || job.estimated_cost)}</div>
                    </div>
                </div>

                <!-- Problem Description -->
                <div class="card" style="margin-bottom:16px">
                    <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:8px;font-weight:700">REPORTED ISSUE</div>
                    <div>${job.problem_description}</div>
                    ${job.technician_notes ? `<hr class="divider"><div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;font-weight:700">TECHNICIAN DIAGNOSIS / WORK NOTES</div><div style="font-size:0.9rem">${job.technician_notes}</div>` : ''}
                </div>

                <!-- Photo Evidence Gallery (Before / During / After) -->
                <div class="card" style="margin-bottom:16px">
                    <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:12px;font-weight:700;display:flex;justify-content:space-between;align-items:center">
                        <span>📷 REPAIR PHOTO EVIDENCE (${photos.length})</span>
                    </div>
                    ${photos.length === 0 ? `
                        <div style="font-size:0.85rem;color:var(--text-muted);font-style:italic">No staged photos uploaded yet by staff.</div>
                    ` : `
                        <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(180px, 1fr));gap:12px">
                            ${photos.map(p => `
                                <div style="border:1px solid var(--border);border-radius:var(--radius-sm);overflow:hidden;background:var(--bg-card)">
                                    <img src="${p.photo_url}" alt="${p.stage}" style="width:100%;height:140px;object-fit:cover;cursor:pointer" onclick="window.open('${p.photo_url}','_blank')">
                                    <div style="padding:8px">
                                        <span class="badge ${p.stage === 'before' ? 'badge-low' : p.stage === 'during' ? 'badge-repairing' : 'badge-completed'}" style="font-size:0.65rem;text-transform:uppercase">${p.stage}</span>
                                        ${p.caption ? `<div style="font-size:0.75rem;margin-top:4px;color:var(--text-muted)">${p.caption}</div>` : ''}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `}
                </div>

                <!-- Warranty Card -->
                <div class="card" style="margin-bottom:16px">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:gap">
                        <div>
                            <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;font-weight:700">WARRANTY STATUS</div>
                            ${warranty ? `
                                <div style="font-weight:600;display:flex;align-items:center;gap:8px">
                                    ${warranty.status === 'Active' ? '🛡️ Active Warranty' : '⚠️ Expired Warranty'}
                                    <span class="font-mono text-primary-color" style="font-size:0.85rem">${warranty.warranty_code}</span>
                                </div>
                                <div style="font-size:0.8rem;color:var(--text-muted);margin-top:4px">
                                    Valid until: ${formatDate(warranty.end_date)} (${warranty.days_remaining > 0 ? warranty.days_remaining + ' days remaining' : 'Expired'})
                                </div>
                            ` : `
                                <div style="font-size:0.85rem;color:var(--text-muted)">No active warranty registered for this repair.</div>
                            `}
                        </div>
                        ${!warranty ? `
                            <button class="btn btn-outline btn-sm" onclick="openCreateWarrantyModal(${job.id})">🛡️ Issue Warranty</button>
                        ` : ''}
                    </div>
                </div>

                <!-- Actions -->
                <div class="flex gap-2 flex-wrap">
                    <button class="btn btn-outline" onclick="showQRCode('${job.repair_id}')">📱 QR Code</button>
                    <button class="btn btn-primary" onclick="renderGenerateBill(${job.id})">📄 Generate Invoice</button>
                    <button class="btn btn-outline" onclick='openAdminEditRepairModal(${JSON.stringify(job).replace(/'/g, "&apos;")})'>✏️ Edit Repair Details</button>
                    <button class="btn btn-danger" onclick="deleteRepairJob(${job.id}, '${job.repair_id}')">🗑️ Delete Repair</button>
                    ${!job.technician_name ? `
                        <button class="btn btn-outline" style="border-color:#6C63FF;color:#6C63FF" onclick="openAiTechnicianModal(${job.id}, '${job.device_type}')">🤖 AI Match Tech</button>
                    ` : ''}
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function openCreateWarrantyModal(jobId) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">🛡️ Issue Repair Warranty</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-group">
            <label class="form-label">Warranty Coverage Duration</label>
            <select class="form-control" id="warranty-months">
                <option value="1">1 Month (30 Days)</option>
                <option value="3" selected>3 Months (90 Days - Standard)</option>
                <option value="6">6 Months (180 Days)</option>
                <option value="12">12 Months (1 Year - Premium)</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Warranty Terms & Inclusions</label>
            <textarea class="form-control" id="warranty-terms" rows="3" placeholder="e.g. Covers replaced parts and labour. Does not cover physical or water damage."></textarea>
        </div>
        <button class="btn btn-primary w-full" onclick="submitCreateWarranty(${jobId})">🛡️ Activate Warranty</button>
    `);
}

async function submitCreateWarranty(jobId) {
    const months = parseInt(document.getElementById('warranty-months').value || 3);
    const terms = document.getElementById('warranty-terms').value;
    try {
        const res = await api.post('/warranties/create', {
            repair_job_id: jobId,
            duration_months: months,
            terms: terms || undefined
        });
        showToast(`Warranty activated! Code: ${res.warranty_code}`, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminRepairDetail(jobId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function renderGenerateBill(jobId) {
    const overlay = showModal(`
        <div class="modal-header">
            <span class="modal-title">📄 Generate Invoice</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Labour Charge (₹)</label>
                <input type="number" class="form-control" id="bill-labour" placeholder="500">
            </div>
            <div class="form-group">
                <label class="form-label">Parts Cost (₹)</label>
                <input type="number" class="form-control" id="bill-parts" placeholder="0">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Discount (₹)</label>
                <input type="number" class="form-control" id="bill-discount" value="0">
            </div>
            <div class="form-group">
                <label class="form-label">GST Rate</label>
                <select class="form-control" id="bill-tax">
                    <option value="0">No Tax</option>
                    <option value="0.05">5%</option>
                    <option value="0.09" selected>9% (GST)</option>
                    <option value="0.18">18% (GST)</option>
                </select>
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">💳 Shop UPI ID (for QR Code Payment)</label>
            <input type="text" class="form-control" id="bill-upi" placeholder="e.g. 9876543210@paytm or shop@okhdfcbank" value="mistri@upi">
            <small style="color:var(--text-muted);font-size:0.75rem">Enter your real Google Pay / PhonePe / Paytm UPI ID to receive payments directly.</small>
        </div>
        <button class="btn btn-primary w-full" onclick="submitGenerateBill(${jobId})">✅ Generate Invoice</button>
    `);
}

async function submitGenerateBill(jobId) {
    try {
        const res = await api.post('/bills/generate', {
            repair_job_id: jobId,
            labour_charge: parseFloat(document.getElementById('bill-labour').value || 0),
            parts_cost: parseFloat(document.getElementById('bill-parts').value || 0),
            discount: parseFloat(document.getElementById('bill-discount').value || 0),
            tax_rate: parseFloat(document.getElementById('bill-tax').value || 0),
            upi_id: (document.getElementById('bill-upi')?.value || '').trim() || undefined
        });
        showToast(`Invoice ${res.bill_number} generated! Total: ${formatCurrency(res.total)}`, 'success');
        document.querySelector('.modal-overlay').remove();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** Admin Inventory */
async function renderAdminInventory() {
    showLoading();
    try {
        const [items, reorderAlerts] = await Promise.all([
            api.get('/inventory/'),
            api.get('/inventory/reorder-alerts').catch(() => [])
        ]);
        const lowStock = items.filter(i => i.low_stock);

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="page-title">📦 Inventory Management</div>
                            <div class="page-subtitle">${items.length} total items · ${reorderAlerts.length} reorder alerts · Atomic stock control</div>
                        </div>
                        <div class="flex gap-2">
                            <button class="btn btn-outline" onclick="viewInventoryTransactions()">📋 Stock History</button>
                            <button class="btn btn-primary" onclick="openAddItemModal()">➕ Add Item</button>
                        </div>
                    </div>
                </div>

                ${reorderAlerts.length > 0 ? `
                    <div class="card" style="border-color:rgba(255,77,77,0.4);background:rgba(255,77,77,0.08);margin-bottom:20px">
                        <div style="font-weight:600;color:var(--danger);margin-bottom:10px;display:flex;align-items:center;gap:8px">
                            <span>⚠️ Critical Reorder Alerts (${reorderAlerts.length} items at/below threshold)</span>
                        </div>
                        <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(280px, 1fr));gap:12px">
                            ${reorderAlerts.map(a => `
                                <div style="background:var(--card-bg);border:1px solid rgba(255,77,77,0.3);border-radius:var(--radius-sm);padding:10px 14px;display:flex;justify-content:space-between;align-items:center">
                                    <div>
                                        <div style="font-weight:600;font-size:0.9rem">${a.part_name}</div>
                                        <div style="font-size:0.75rem;color:var(--text-muted)">Stock: <b class="text-danger">${a.current_stock}</b> / Min: ${a.reorder_level} | Suggested: +${a.suggested_reorder_qty}</div>
                                    </div>
                                    <button class="btn btn-sm btn-outline" style="border-color:var(--danger);color:var(--danger);font-size:0.75rem" onclick="openRestockModal(${a.id}, '${a.part_name}', '${a.supplier || ''}', ${a.suggested_reorder_qty})">
                                        📥 Restock
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}

                <div class="filter-row">
                    <div class="search-bar" style="max-width:360px">
                        <span class="search-icon">🔍</span>
                        <input type="text" placeholder="Search parts by name, code..." oninput="filterInventory(this.value)">
                    </div>
                </div>

                <div class="table-container">
                    <table>
                        <thead><tr>
                            <th>Part</th><th>Code</th><th>Category</th><th>Stock</th><th>Unit Price</th><th>Supplier</th><th>Action</th>
                        </tr></thead>
                        <tbody id="inventory-tbody">
                            ${items.map(item => `
                                <tr>
                                    <td>
                                        <div style="font-weight:500">${item.part_name}</div>
                                        <div class="stock-indicator">
                                            <div class="stock-fill ${item.low_stock ? 'low' : 'ok'}" style="width:${Math.min(100, (item.quantity / Math.max(item.reorder_level * 3, 10)) * 100)}%"></div>
                                        </div>
                                    </td>
                                    <td class="font-mono" style="font-size:0.8rem">${item.part_code}</td>
                                    <td><span class="badge badge-${item.category.toLowerCase() === 'screen' ? 'repairing' : item.category.toLowerCase() === 'battery' ? 'completed' : 'received'}">${item.category}</span></td>
                                    <td>
                                        <span class="${item.low_stock ? 'text-danger' : 'text-success'}" style="font-weight:600">${item.quantity}</span>
                                        <span style="font-size:0.75rem;color:var(--text-muted)"> / min ${item.reorder_level}</span>
                                    </td>
                                    <td style="font-weight:500">${formatCurrency(item.unit_price)}</td>
                                    <td style="font-size:0.8rem;color:var(--text-muted)">${item.supplier || '—'}</td>
                                    <td>
                                        <div class="flex gap-1">
                                            <button class="btn btn-outline btn-sm" onclick="openRestockModal(${item.id},'${item.part_name.replace(/'/g, "\\'")}', '${(item.supplier || '').replace(/'/g, "\\'")}', 10)">📥 Restock</button>
                                            <button class="btn btn-outline btn-sm" onclick="openStockModal(${item.id},'${item.part_name.replace(/'/g, "\\'")}', ${item.quantity})">⚡ Quick</button>
                                            <button class="btn btn-outline btn-sm" onclick="openEditInventoryModal(${item.id},'${item.part_name.replace(/'/g, "\\'")}','${item.part_code}','${item.category}',${item.quantity},${item.unit_price},${item.reorder_level},'${(item.supplier || '').replace(/'/g, "\\'")}')" title="Edit Item">✏️</button>
                                            <button class="btn btn-outline btn-sm text-danger" style="border-color:var(--danger)" onclick="deleteInventoryItem(${item.id}, '${item.part_name.replace(/'/g, "\\'")}')" title="Delete Item">🗑️</button>
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deleteInventoryItem(id, name) {
    if (!confirm(`Are you sure you want to delete '${name}' from inventory?`)) return;
    try {
        const res = await api.delete(`/inventory/${id}?hard=true`);
        showToast(res.message || 'Item deleted successfully', 'success');
        renderAdminInventory();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function filterInventory(query) {
    document.querySelectorAll('#inventory-tbody tr').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(query.toLowerCase()) ? '' : 'none';
    });
}

function openRestockModal(itemId, name, supplier, defaultQty = 10) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">📥 Restock Item — ${name}</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-group">
            <label class="form-label">Quantity to Add</label>
            <input type="number" class="form-control" id="restock-qty" placeholder="10" min="1" value="${defaultQty}">
        </div>
        <div class="form-group">
            <label class="form-label">Unit Cost (₹) (Optional)</label>
            <input type="number" class="form-control" id="restock-cost" placeholder="0">
        </div>
        <div class="form-group">
            <label class="form-label">Supplier</label>
            <input type="text" class="form-control" id="restock-supplier" value="${supplier || ''}" placeholder="Supplier name">
        </div>
        <div class="form-group">
            <label class="form-label">Notes / PO Reference</label>
            <input type="text" class="form-control" id="restock-note" placeholder="e.g. Weekly Restock PO-401">
        </div>
        <button class="btn btn-primary w-full" onclick="submitRestock(${itemId})">✅ Confirm Restock</button>
    `);
}

async function submitRestock(itemId) {
    const qty = parseInt(document.getElementById('restock-qty').value);
    const cost = parseFloat(document.getElementById('restock-cost').value || 0);
    const supplier = document.getElementById('restock-supplier').value;
    const notes = document.getElementById('restock-note').value;
    if (isNaN(qty) || qty <= 0) { showToast('Enter a valid quantity', 'error'); return; }
    try {
        await api.post('/inventory/restock', {
            part_id: itemId,
            item_id: itemId,
            quantity: qty,
            quantity_added: qty,
            unit_cost: cost,
            supplier: supplier || undefined,
            reason: notes || 'Restock shipment received',
            notes: notes || undefined
        });
        showToast('Inventory restocked successfully!', 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminInventory();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function viewInventoryTransactions() {
    const overlay = showModal(`
        <div class="modal-header">
            <span class="modal-title">📋 Stock Transactions Audit Log</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div id="tx-log-content" style="text-align:center;padding:24px 0">
            <div class="spinner" style="width:32px;height:32px;margin:0 auto 8px"></div>
            <div style="font-size:0.8rem;color:var(--text-muted)">Loading audit trail...</div>
        </div>
    `);
    try {
        const txs = await api.get('/inventory/transactions?limit=40');
        const container = document.getElementById('tx-log-content');
        if (!container) return;
        if (!txs.length) {
            container.innerHTML = '<div class="text-muted" style="padding:16px">No stock movements recorded yet.</div>';
            return;
        }
        container.style.textAlign = 'left';
        container.innerHTML = `
            <div style="max-height:420px;overflow-y:auto">
                <table style="width:100%;font-size:0.8rem">
                    <thead><tr><th>Date</th><th>Part</th><th>Type</th><th>Qty</th><th>Previous → New</th><th>Notes</th></tr></thead>
                    <tbody>
                        ${txs.map(t => `
                            <tr>
                                <td style="color:var(--text-muted);font-size:0.75rem;white-space:nowrap">${formatDate(t.created_at)}</td>
                                <td style="font-weight:500">${t.part_name}</td>
                                <td><span class="badge ${t.transaction_type === 'RESTOCK' ? 'badge-completed' : 'badge-low'}">${t.transaction_type}</span></td>
                                <td style="font-weight:600">${t.quantity_change > 0 ? '+' + t.quantity_change : t.quantity_change}</td>
                                <td style="color:var(--text-muted)">${t.previous_quantity} → ${t.new_quantity}</td>
                                <td style="font-size:0.75rem;color:var(--text-muted)">${t.notes || ''}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (e) {
        const container = document.getElementById('tx-log-content');
        if (container) container.innerHTML = `<div class="text-danger" style="padding:16px">${e.message}</div>`;
    }
}

function openStockModal(itemId, name, currentQty) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">⚡ Quick Adjust — ${name}</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="text-align:center;margin-bottom:16px;font-size:2rem;font-weight:700;color:var(--primary)">${currentQty}</div>
        <div style="text-align:center;font-size:0.8rem;color:var(--text-muted);margin-bottom:16px">Current Stock</div>
        <div class="form-group">
            <label class="form-label">Quantity Change (+ to add, - to subtract)</label>
            <input type="number" class="form-control" id="stock-change" placeholder="e.g. 5 or -2">
        </div>
        <button class="btn btn-primary w-full" onclick="submitStockUpdate(${itemId})">Update Stock</button>
    `);
}

async function submitStockUpdate(itemId) {
    const change = parseInt(document.getElementById('stock-change').value);
    if (isNaN(change)) { showToast('Enter a valid number', 'error'); return; }
    try {
        const res = await api.patch(`/inventory/${itemId}/stock`, { quantity_change: change });
        showToast(`Stock updated! New quantity: ${res.new_quantity}${res.low_stock ? ' ⚠️ Low stock!' : ''}`, res.low_stock ? 'warning' : 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminInventory();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

const ELECTRICAL_INVENTORY_CATEGORIES = [
    'Fan Parts', 'Cooler Parts', 'Mixer Parts', 'Motor Parts', 'Geyser Parts',
    'Pump Parts', 'Wires & Cables', 'Switches & Sockets', 'Capacitors', 'MCB & Fuse',
    'Relays', 'Connectors', 'LED Bulbs', 'Tape & Insulation', 'Fasteners', 'Misc Electrical'
];

function openAddItemModal() {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">➕ Add Electrical Inventory Item</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Part / Item Name *</label>
                <input type="text" class="form-control" id="new-name" placeholder="e.g. Fan Capacitor 2.5μF" required>
            </div>
            <div class="form-group">
                <label class="form-label">Part Code *</label>
                <input type="text" class="form-control" id="new-code" placeholder="e.g. FAN-CAP-25" required>
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Category *</label>
                <select class="form-control" id="new-cat">
                    ${ELECTRICAL_INVENTORY_CATEGORIES.map(c => `<option value="${c}">${c}</option>`).join('')}
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Brand / Manufacturer</label>
                <input type="text" class="form-control" id="new-brand" placeholder="e.g. Havells / Usha / Philips">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Stock Quantity *</label>
                <input type="number" class="form-control" id="new-qty" placeholder="10" min="0" value="10">
            </div>
            <div class="form-group">
                <label class="form-label">Unit of Measure</label>
                <select class="form-control" id="new-unit">
                    <option value="piece">piece (नग)</option>
                    <option value="set">set (जोड़ा)</option>
                    <option value="roll">roll (रोल)</option>
                    <option value="pack">pack (पैकेट)</option>
                    <option value="meter">meter (मीटर)</option>
                    <option value="kg">kg (किलो)</option>
                </select>
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Purchase / Cost Price (₹)</label>
                <input type="number" class="form-control" id="new-cost" placeholder="e.g. 45">
            </div>
            <div class="form-group">
                <label class="form-label">Selling / Unit Price (₹) *</label>
                <input type="number" class="form-control" id="new-price" placeholder="e.g. 80" required>
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Reorder Level (Min Alert)</label>
                <input type="number" class="form-control" id="new-reorder" value="5" min="1">
            </div>
            <div class="form-group">
                <label class="form-label">Supplier / Vendor</label>
                <input type="text" class="form-control" id="new-supplier" placeholder="e.g. Shiv Electric Wholesale">
            </div>
        </div>
        <button class="btn btn-primary w-full" style="margin-top:10px" onclick="submitAddItem()">➕ Add to Electrical Inventory</button>
    `);
}

async function submitAddItem() {
    const name = document.getElementById('new-name')?.value.trim();
    const code = document.getElementById('new-code')?.value.trim();
    const cat = document.getElementById('new-cat')?.value;
    const qty = parseInt(document.getElementById('new-qty')?.value || 0);
    const sellPrice = parseFloat(document.getElementById('new-price')?.value || 0);
    const costPrice = parseFloat(document.getElementById('new-cost')?.value || 0);
    const brand = document.getElementById('new-brand')?.value.trim() || '';
    const unit = document.getElementById('new-unit')?.value || 'piece';
    const reorder = parseInt(document.getElementById('new-reorder')?.value || 5);
    const supplier = document.getElementById('new-supplier')?.value.trim() || '';

    if (!name || !code || sellPrice <= 0) {
        showToast('Please fill Part Name, Code, and Selling Price.', 'warning');
        return;
    }

    try {
        await api.post('/inventory/', {
            part_name: name,
            part_code: code.toUpperCase(),
            category: cat,
            compatible_devices: [],
            quantity: qty,
            unit_price: sellPrice,
            purchase_price: costPrice || sellPrice * 0.6,
            sell_price: sellPrice,
            brand: brand || null,
            unit: unit,
            reorder_level: reorder,
            reorder_quantity: reorder * 2,
            supplier: supplier || null,
            is_active: 1
        });
        showToast(`Electrical part '${name}' added to inventory! 🎉`, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminInventory();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** Admin Reports */
async function renderAdminReports() {
    showLoading();
    try {
        const [data, analytics] = await Promise.all([
            api.get('/reports/revenue?period=monthly'),
            api.get('/reports/analytics').catch(() => null)
        ]);

        const fin = analytics?.financials || {};
        const turnaround = analytics?.turnaround || {};
        const mostUsed = analytics?.most_used_parts || [];
        const scorecard = analytics?.staff_scorecard || [];

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="page-title">📈 Reports & Smart Analytics</div>
                            <div class="page-subtitle">Revenue trends, profit margins, turnaround speed & parts usage</div>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="api.download('/reports/export/csv?type=repairs', 'mistri_repairs_report.csv')" class="btn btn-outline btn-sm">⬇ Repairs CSV</button>
                            <button onclick="api.download('/reports/export/csv?type=payments', 'mistri_payments_report.csv')" class="btn btn-outline btn-sm">⬇ Payments CSV</button>
                        </div>
                    </div>
                </div>

                <!-- Financial Health & Profitability Cards -->
                <div class="stats-grid" style="margin-bottom:24px">
                    <div class="stat-card">
                        <div class="stat-icon">💰</div>
                        <div class="stat-value text-primary-color">${formatCurrency(fin.total_revenue || 0)}</div>
                        <div class="stat-label">Total Invoiced Revenue</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">🔩</div>
                        <div class="stat-value" style="color:var(--warning)">${formatCurrency(fin.total_parts_cost || 0)}</div>
                        <div class="stat-label">Parts / Material Cost</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">📈</div>
                        <div class="stat-value text-success">${formatCurrency(fin.estimated_net_profit || 0)}</div>
                        <div class="stat-label">Net Gross Profit (${fin.profit_margin_pct || 0}%)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">⚡</div>
                        <div class="stat-value" style="color:#27D67B">${turnaround.avg_turnaround_hours || 0}h</div>
                        <div class="stat-label">Avg Repair Turnaround</div>
                    </div>
                </div>

                <div class="charts-grid">
                    <div class="chart-card" style="grid-column:1/-1">
                        <div class="chart-header">
                            <div class="chart-title">📈 Monthly Revenue Trend</div>
                            <span class="chart-badge">12-Month Performance</span>
                        </div>
                        <div class="chart-wrapper" style="height:280px"><canvas id="monthly-chart"></canvas></div>
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
                    <div class="chart-card">
                        <div class="chart-header">
                            <div class="chart-title">🔧 Revenue by Device Type</div>
                            <span class="chart-badge">Category Share</span>
                        </div>
                        <div class="chart-split">
                            <div class="chart-wrapper" style="height:210px;position:relative"><canvas id="device-chart"></canvas></div>
                            <div class="chart-breakdown-list" id="device-breakdown-container"></div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="chart-title">🏆 Top Technicians & Workload</div>
                        ${(!scorecard.length && !data.top_technicians.length) ? '<div class="text-muted">No completed jobs yet</div>' : `
                            <table style="width:100%">
                                <thead><tr><th>Technician</th><th>Completed</th><th>Avg Rating</th><th>Revenue</th></tr></thead>
                                <tbody>
                                    ${(scorecard.length ? scorecard : data.top_technicians).map((t, i) => `
                                        <tr>
                                            <td>${['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][i] || '👨‍🔧'} <b>${t.name}</b></td>
                                            <td>${t.jobs_completed} jobs</td>
                                            <td>⭐ ${t.avg_rating || '5.0'}</td>
                                            <td style="font-weight:600">${formatCurrency(t.revenue || 0)}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `}
                    </div>
                </div>

                <!-- Most Used Replacement Parts Table -->
                <div class="table-container">
                    <div class="table-header-row">
                        <div class="table-title">🔩 Top Replacement Parts Consumed</div>
                    </div>
                    ${mostUsed.length === 0 ? `
                        <div style="padding:16px;color:var(--text-muted);font-style:italic">No parts deducted from inventory yet.</div>
                    ` : `
                        <table>
                            <thead><tr><th>Part Name</th><th>Category</th><th>Times Replaced</th><th>Total Billed Amount</th></tr></thead>
                            <tbody>
                                ${mostUsed.map(p => `
                                    <tr>
                                        <td style="font-weight:600">${p.part_name}</td>
                                        <td><span class="badge badge-repairing">${p.category}</span></td>
                                        <td><b class="text-primary-color">${p.times_used}</b> units</td>
                                        <td style="font-weight:600">${formatCurrency(p.total_amount_billed)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `}
                </div>
            </div>
        `);

        // Cache reports data for reactive theme changes
        window._cachedReportsData = data;

        renderMonthlyChart(data.revenue_over_time);
        renderDeviceChart(data.device_breakdown);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

let _monthlyChartInstance = null;
function renderMonthlyChart(data = []) {
    const canvas = document.getElementById('monthly-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (_monthlyChartInstance) {
        _monthlyChartInstance.destroy();
        _monthlyChartInstance = null;
    }

    const theme = getChartTheme();
    const gradient = ctx.createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, 'rgba(249, 115, 22, 0.95)');
    gradient.addColorStop(1, 'rgba(234, 88, 12, 0.25)');

    const labels = (data || []).map(d => d.period || d.month || '');
    const revenues = (data || []).map(d => d.revenue || 0);

    _monthlyChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.length ? labels : ['No Data'],
            datasets: [{
                label: 'Monthly Revenue',
                data: revenues.length ? revenues : [0],
                backgroundColor: gradient,
                hoverBackgroundColor: theme.primaryDark,
                borderRadius: 8,
                borderSkipped: false,
                barPercentage: 0.48,
                categoryPercentage: 0.68,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 750,
                easing: 'easeOutQuart'
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: theme.tooltipBg,
                    titleColor: theme.tooltipTitle,
                    bodyColor: theme.tooltipBody,
                    borderColor: theme.tooltipBorder,
                    borderWidth: 1.5,
                    padding: 12,
                    boxPadding: 6,
                    usePointStyle: true,
                    cornerRadius: 10,
                    titleFont: { family: 'Inter', size: 12, weight: '600' },
                    bodyFont: { family: 'Inter', size: 13, weight: '700' },
                    callbacks: {
                        label: (ctx) => ' Billed: ' + formatCurrency(ctx.parsed.y)
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    border: { display: false },
                    ticks: {
                        color: theme.textColor,
                        font: { family: 'Inter', size: 11, weight: '500' }
                    }
                },
                y: {
                    border: { display: false },
                    grid: {
                        color: theme.gridColor,
                        borderDash: [4, 4]
                    },
                    ticks: {
                        color: theme.textColor,
                        font: { family: 'Inter', size: 11 },
                        callback: (v) => v >= 1000 ? '₹' + (v / 1000).toFixed(1) + 'k' : '₹' + v
                    }
                }
            }
        }
    });
}

let _deviceChartInstance = null;
function renderDeviceChart(data = []) {
    const canvas = document.getElementById('device-chart');
    if (!canvas || !data.length) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (_deviceChartInstance) {
        _deviceChartInstance.destroy();
        _deviceChartInstance = null;
    }

    const theme = getChartTheme();
    const colors = [
        '#F97316', // Ceiling Fan
        '#38BDF8', // Cooler
        '#FBBF24', // Mixer
        '#22C55E', // Motor / Pump
        '#EC4899', // Geyser
        '#A855F7', // Inverter
        '#06B6D4', // Microwave / Oven
        '#64748B'  // Others
    ];

    const totalDevices = data.reduce((sum, d) => sum + (d.count || 0), 0);

    // Populate Device Breakdown Progress Track List
    const breakdownContainer = document.getElementById('device-breakdown-container');
    if (breakdownContainer) {
        const sorted = [...data].sort((a, b) => (b.count || 0) - (a.count || 0)).slice(0, 5);
        breakdownContainer.innerHTML = sorted.map((d, i) => {
            const count = d.count || 0;
            const pct = totalDevices > 0 ? Math.round((count / totalDevices) * 100) : 0;
            const color = colors[i % colors.length];
            return `
                <div class="chart-breakdown-row">
                    <div class="chart-breakdown-meta">
                        <div class="chart-breakdown-label">
                            <span class="chart-breakdown-dot" style="background:${color}"></span>
                            <span>${d.device_type}</span>
                        </div>
                        <div class="chart-breakdown-values">
                            <b>${count}</b> <span style="color:var(--text-muted);font-size:0.72rem">(${pct}%)</span>
                        </div>
                    </div>
                    <div class="chart-progress-track">
                        <div class="chart-progress-fill" style="width:${pct}%;background:${color}"></div>
                    </div>
                </div>
            `;
        }).join('');
    }

    const centerTextPlugin = {
        id: 'deviceCenterText',
        beforeDraw(chart) {
            const { width, height, ctx } = chart;
            ctx.save();
            ctx.font = '800 1.7rem "Space Grotesk", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = theme.titleColor;
            ctx.fillText(totalDevices, width / 2, height / 2 - 10);

            ctx.font = '600 0.68rem "Inter", sans-serif';
            ctx.letterSpacing = '0.08em';
            ctx.fillStyle = theme.textMuted;
            ctx.fillText('APPLIANCES', width / 2, height / 2 + 12);
            ctx.restore();
        }
    };

    _deviceChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.map(d => d.device_type),
            datasets: [{
                data: data.map(d => d.count),
                backgroundColor: colors,
                borderWidth: 0,
                spacing: 3,
                borderRadius: 5,
                hoverOffset: 8
            }]
        },
        plugins: [centerTextPlugin],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '72%',
            animation: {
                animateRotate: true,
                animateScale: true,
                duration: 750,
                easing: 'easeOutQuart'
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: theme.tooltipBg,
                    titleColor: theme.tooltipTitle,
                    bodyColor: theme.tooltipBody,
                    borderColor: theme.tooltipBorder,
                    borderWidth: 1.5,
                    padding: 12,
                    boxPadding: 6,
                    usePointStyle: true,
                    cornerRadius: 10,
                    titleFont: { family: 'Inter', size: 12, weight: '600' },
                    bodyFont: { family: 'Inter', size: 12, weight: '500' },
                    callbacks: {
                        label: (ctx) => {
                            const val = ctx.raw || 0;
                            const pct = totalDevices > 0 ? Math.round((val / totalDevices) * 100) : 0;
                            return ` ${ctx.label}: ${val} units (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Reactive chart theme redraw when switching Dark/Light modes
window.addEventListener('themeChanged', () => {
    if (window._cachedDashboardStats) {
        if (document.getElementById('revenue-chart')) {
            renderRevenueChart(window._cachedDashboardStats.daily_revenue);
        }
        if (document.getElementById('status-chart')) {
            renderStatusChart(window._cachedDashboardStats.status_distribution);
        }
    }
    if (window._cachedReportsData) {
        if (document.getElementById('monthly-chart')) {
            renderMonthlyChart(window._cachedReportsData.revenue_over_time);
        }
        if (document.getElementById('device-chart')) {
            renderDeviceChart(window._cachedReportsData.device_breakdown);
        }
    }
});

/** Admin Staff Management */
/** Admin Staff Management */
async function renderAdminStaff() {
    showLoading();
    try {
        const [users, leaves, resignations] = await Promise.all([
            api.get('/auth/users'),
            api.get('/staff-mgmt/leaves').catch(() => []),
            api.get('/auth/users').catch(() => [])
        ]);
        const staff = users.filter(u => u.role === 'staff');
        const pendingLeaves = leaves.filter(l => l.status === 'Pending').length;
        const pendingResignations = staff.filter(s => s.resignation_status === 'Pending').length;

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="page-title">👥 Staff & Payroll Management</div>
                            <div class="page-subtitle">${staff.length} staff technicians · 6-Month Commitment & Leave Policies</div>
                        </div>
                        <div class="flex gap-2 flex-wrap">
                            <button class="btn btn-primary btn-sm" onclick="openAddStaffModal()">➕ Add Staff</button>
                            <button class="btn btn-outline btn-sm" onclick="openPayrollModal()">💰 Monthly Payroll</button>
                            <button class="btn btn-outline btn-sm" onclick="openLeaveReviewModal()" style="position:relative">
                                📅 Review Leaves
                                ${pendingLeaves > 0 ? `<span class="badge badge-urgent" style="margin-left:4px">${pendingLeaves}</span>` : ''}
                            </button>
                            <button class="btn btn-outline btn-sm" onclick="openResignationReviewModal()" style="position:relative">
                                📝 Resignations
                                ${pendingResignations > 0 ? `<span class="badge badge-urgent" style="margin-left:4px">${pendingResignations}</span>` : ''}
                            </button>
                        </div>
                    </div>
                </div>

                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Staff Member</th>
                                <th>Contact</th>
                                <th>Monthly Salary</th>
                                <th>Joined</th>
                                <th>Tenure & Commitment</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${staff.map(s => {
                                const isActive = (s.is_active !== 0);
                                const joinedStr = s.joining_date || (s.created_at ? s.created_at.slice(0,10) : '—');
                                const reqMonths = s.minimum_commitment_months || 6;
                                let tenureBadge = '';
                                if (s.joining_date) {
                                    const monthsServed = (new Date() - new Date(s.joining_date)) / (1000 * 60 * 60 * 24 * 30.4375);
                                    if (monthsServed >= reqMonths) {
                                        tenureBadge = `<span class="badge badge-completed" title="${monthsServed.toFixed(1)} months served">✅ Completed (${reqMonths}m)</span>`;
                                    } else {
                                        const left = (reqMonths - monthsServed).toFixed(1);
                                        tenureBadge = `<span class="badge" style="background:#f59e0b22;color:#d97706" title="${monthsServed.toFixed(1)} months served">⏳ In Progress (${left}m left)</span>`;
                                    }
                                } else {
                                    tenureBadge = `<span class="badge badge-assigned">${reqMonths}m Commitment</span>`;
                                }

                                return `
                                    <tr style="${!isActive ? 'opacity:0.6;background:rgba(239,68,68,0.03)' : ''}">
                                        <td>
                                            <div class="flex items-center gap-2">
                                                <div class="user-avatar" style="width:34px;height:34px;font-size:0.85rem">${s.name[0]}</div>
                                                <div>
                                                    <div style="font-weight:600">${s.name}</div>
                                                    <div style="font-size:0.75rem;color:var(--text-muted)">ID: #${s.id}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td>
                                            <div style="font-size:0.85rem">${s.email}</div>
                                            <div style="font-size:0.78rem;color:var(--text-muted)">${s.phone || '—'}</div>
                                        </td>
                                        <td>
                                            <div style="font-weight:700;color:var(--primary)">${formatCurrency(s.monthly_salary || 0)}</div>
                                            <div style="font-size:0.72rem;color:var(--text-muted)">Daily: ${formatCurrency(Math.round((s.monthly_salary || 0) / 30))}</div>
                                        </td>
                                        <td style="font-size:0.82rem">${joinedStr}</td>
                                        <td>${tenureBadge}</td>
                                        <td>
                                            ${isActive 
                                                ? '<span class="badge badge-completed">Active</span>' 
                                                : '<span class="badge badge-cancelled">Deactivated</span>'}
                                            ${s.resignation_status && s.resignation_status !== 'None' 
                                                ? `<div style="font-size:0.7rem;color:#eab308;margin-top:2px">Notice: ${s.resignation_status}</div>` : ''}
                                            ${s.termination_effective_date 
                                                ? `<div style="font-size:0.7rem;color:var(--danger);margin-top:2px">Exit: ${s.termination_effective_date}</div>` : ''}
                                        </td>
                                        <td>
                                                <button class="btn btn-outline btn-sm" onclick="openEditUserModal(${s.id},'${s.name.replace(/'/g, "\\'")}','${s.email}','${s.phone || ''}',${s.monthly_salary || 0},'${s.joining_date || ''}',${isActive ? 1 : 0})" title="Edit Staff Details">✏️</button>
                                                <button class="btn btn-outline btn-sm" style="color:var(--primary)" onclick="openAwardBonusModal(${s.id},'${s.name.replace(/'/g, "\\'")}')" title="Award Bonus">🎁</button>
                                                <button class="btn btn-outline btn-sm" style="color:#eab308" onclick="openTerminationNoticeModal(${s.id},'${s.name.replace(/'/g, "\\'")}')" title="15-Day Exit Notice">📢</button>
                                                ${isActive 
                                                    ? `<button class="btn btn-outline btn-sm" style="color:#f97316" onclick="openDeactivateStaffModal(${s.id},'${s.name.replace(/'/g, "\\'")}')" title="Deactivate Staff">🚫</button>`
                                                    : `<button class="btn btn-success btn-sm" onclick="activateStaff(${s.id})" title="Reactivate Staff">✅</button>`}
                                                <button class="btn btn-outline btn-sm text-danger" style="border-color:var(--danger)" onclick="deleteStaffMember(${s.id},'${s.name.replace(/'/g, "\\'")}')" title="Delete / Remove Staff">🗑️</button>
                                            </div>
                                        </td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function openAddStaffModal() {
    const today = new Date().toISOString().split('T')[0];
    showModal(`
        <div class="modal-header">
            <span class="modal-title">➕ Add New Staff Member</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Full Name <span class="text-danger">*</span></label>
                <input type="text" class="form-control" id="staff-name" placeholder="Raju Sharma">
            </div>
            <div class="form-group">
                <label class="form-label">Email <span class="text-danger">*</span></label>
                <input type="email" class="form-control" id="staff-email" placeholder="raju@mistri.com">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Phone Number</label>
                <input type="tel" class="form-control" id="staff-phone" placeholder="9876543210">
            </div>
            <div class="form-group">
                <label class="form-label">Password <span class="text-danger">*</span></label>
                <input type="password" class="form-control" id="staff-pass" placeholder="Min 8 chars with upper, digit, symbol">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Monthly Fixed Salary (₹) <span class="text-danger">*</span></label>
                <input type="number" class="form-control" id="staff-salary" placeholder="20000" value="20000">
            </div>
            <div class="form-group">
                <label class="form-label">Joining Date <span class="text-danger">*</span></label>
                <input type="date" class="form-control" id="staff-joining" value="${today}">
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">Minimum Commitment Period (Months)</label>
            <input type="number" class="form-control" id="staff-commitment" value="6" min="1" max="24">
            <div style="font-size:0.75rem;color:var(--text-muted);margin-top:3px">Standard shop policy enforces minimum 6-month commitment.</div>
        </div>
        <button class="btn btn-primary w-full" style="height:46px;margin-top:10px" onclick="submitAddStaff()">Create Staff Account</button>
    `);
}

async function submitAddStaff() {
    try {
        await api.post('/auth/staff', {
            name: document.getElementById('staff-name').value,
            email: document.getElementById('staff-email').value,
            phone: document.getElementById('staff-phone').value,
            password: document.getElementById('staff-pass').value,
            monthly_salary: parseFloat(document.getElementById('staff-salary').value || 0),
            joining_date: document.getElementById('staff-joining').value,
            minimum_commitment_months: parseInt(document.getElementById('staff-commitment').value || 6)
        });
        showToast('Staff member added with employment agreement!', 'success');
        document.querySelector('.modal-overlay').remove();
        renderAdminStaff();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function openAwardBonusModal(staffId, staffName) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">🎁 Award Bonus / Incentive</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="padding:10px;background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:var(--radius-sm);margin-bottom:14px;font-size:0.85rem">
            Staff: <b>${staffName}</b> · This bonus will be included in the monthly payroll calculation.
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Bonus Type</label>
                <select class="form-control" id="bonus-type" style="height:44px">
                    <option value="Festival Bonus">Festival Special Bonus 🎉</option>
                    <option value="Performance Bonus">Performance & Speed Incentive ⚡</option>
                    <option value="Special Incentive">Special Recognition Award 🏆</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Bonus Amount (₹) <span class="text-danger">*</span></label>
                <input type="number" class="form-control" id="bonus-amount" placeholder="2000" min="100" style="height:44px">
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">Reason / Occasion <span class="text-danger">*</span></label>
            <input type="text" class="form-control" id="bonus-reason" placeholder="e.g. Diwali celebration gift, repaired 30 appliances this month">
        </div>
        <button class="btn btn-primary w-full" style="height:44px;margin-top:10px" onclick="submitAwardBonus(${staffId})">Grant Bonus</button>
    `);
}

async function submitAwardBonus(staffId) {
    const amount = parseFloat(document.getElementById('bonus-amount').value || 0);
    const bonusType = document.getElementById('bonus-type').value;
    const reason = document.getElementById('bonus-reason').value.trim();

    if (amount <= 0) { showToast('Bonus amount must be greater than 0', 'warning'); return; }
    if (reason.length < 3) { showToast('Please state a reason for the bonus', 'warning'); return; }

    try {
        await api.post('/staff-mgmt/bonus', {
            staff_id: staffId,
            amount: amount,
            bonus_type: bonusType,
            reason: reason
        });
        showToast('Bonus awarded successfully! 🎉', 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminStaff();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function openPayrollModal() {
    showLoading();
    try {
        const data = await api.get('/staff-mgmt/payroll-calculation');
        const payroll = data.payroll || [];

        showModal(`
            <div class="modal-header">
                <span class="modal-title">💰 Monthly Payroll Breakdown (${data.month})</span>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            <div style="padding:10px;background:var(--surface-2);border-radius:var(--radius-sm);margin-bottom:14px;font-size:0.8rem">
                <b>Salary Deduction Policy:</b> 4 leaves allowed free/month. Daily Rate = Fixed Salary / 30. Unpaid leaves beyond 4 are deducted at the daily rate.
            </div>
            <div class="table-container" style="max-height:450px;overflow-y:auto">
                <table>
                    <thead>
                        <tr>
                            <th>Staff</th>
                            <th>Base Salary</th>
                            <th>Daily Rate</th>
                            <th>Leaves</th>
                            <th>Unpaid</th>
                            <th>Deduction</th>
                            <th>Bonuses</th>
                            <th>Net Payout</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${payroll.map(p => `
                            <tr>
                                <td style="font-weight:600">${p.staff_name}</td>
                                <td>${formatCurrency(p.monthly_salary)}</td>
                                <td style="font-size:0.8rem;color:var(--text-muted)">${formatCurrency(p.daily_rate)}</td>
                                <td>${p.approved_leaves_taken} / ${p.allowed_leaves}</td>
                                <td><span class="${p.unpaid_leaves > 0 ? 'text-danger font-bold' : ''}">${p.unpaid_leaves}</span></td>
                                <td style="color:${p.salary_deduction > 0 ? 'var(--danger)' : 'inherit'}">-${formatCurrency(p.salary_deduction)}</td>
                                <td style="color:var(--success)">+${formatCurrency(p.bonuses)}</td>
                                <td style="font-weight:700;color:var(--primary);font-size:0.95rem">${formatCurrency(p.net_payout)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function openLeaveReviewModal() {
    try {
        const leaves = await api.get('/staff-mgmt/leaves');
        showModal(`
            <div class="modal-header">
                <span class="modal-title">📅 Staff Leave Applications</span>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            ${leaves.length === 0 ? `
                <div class="text-muted" style="padding:20px;text-align:center">No leave applications found.</div>
            ` : `
                <div class="table-container" style="max-height:450px;overflow-y:auto">
                    <table>
                        <thead>
                            <tr>
                                <th>Staff</th>
                                <th>Leave Date</th>
                                <th>Days</th>
                                <th>Reason</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${leaves.map(l => `
                                <tr>
                                    <td style="font-weight:600">${l.staff_name}</td>
                                    <td>${l.leave_date}</td>
                                    <td>${l.days}</td>
                                    <td style="font-size:0.85rem">${l.reason}</td>
                                    <td><span class="badge ${l.status === 'Approved' ? 'badge-completed' : l.status === 'Rejected' ? 'badge-cancelled' : 'badge-assigned'}">${l.status}</span></td>
                                    <td>
                                        ${l.status === 'Pending' ? `
                                            <div class="flex gap-1">
                                                <button class="btn btn-success btn-sm" onclick="reviewLeave(${l.id},'Approved')">Approve</button>
                                                <button class="btn btn-danger btn-sm" onclick="reviewLeave(${l.id},'Rejected')">Reject</button>
                                            </div>
                                        ` : `<span style="font-size:0.75rem;color:var(--text-muted)">Reviewed</span>`}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `}
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function reviewLeave(leaveId, status) {
    const adminNotes = prompt(`Enter notes for ${status.toLowerCase()} leave (optional):`);
    try {
        await api.put(`/staff-mgmt/leave/${leaveId}/review`, {
            status: status,
            admin_notes: adminNotes || null
        });
        showToast(`Leave application marked as ${status}!`, 'success');
        document.querySelector('.modal-overlay')?.remove();
        openLeaveReviewModal();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function openResignationReviewModal() {
    try {
        const users = await api.get('/auth/users');
        const resigning = users.filter(u => u.role === 'staff' && u.resignation_status && u.resignation_status !== 'None');

        showModal(`
            <div class="modal-header">
                <span class="modal-title">📝 Resignation Notices on Record</span>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            ${resigning.length === 0 ? `
                <div class="text-muted" style="padding:20px;text-align:center">No active resignation notices.</div>
            ` : `
                <div class="table-container" style="max-height:450px;overflow-y:auto">
                    <table>
                        <thead><tr><th>Staff</th><th>Notice Date</th><th>Proposed Last Day</th><th>Reason</th><th>Emergency Note</th><th>Status</th><th>Action</th></tr></thead>
                        <tbody>
                            ${resigning.map(s => `
                                <tr>
                                    <td style="font-weight:600">${s.name}</td>
                                    <td style="font-size:0.8rem">${s.resignation_notice_date || '—'}</td>
                                    <td style="font-weight:700">${s.resignation_last_date || '—'}</td>
                                    <td style="font-size:0.85rem">${s.resignation_reason || '—'}</td>
                                    <td style="font-size:0.8rem;color:var(--danger)">${s.emergency_justification || 'None'}</td>
                                    <td><span class="badge ${s.resignation_status === 'Approved' ? 'badge-completed' : 'badge-assigned'}">${s.resignation_status}</span></td>
                                    <td>
                                        ${s.resignation_status === 'Pending' ? `
                                            <div class="flex gap-1">
                                                <button class="btn btn-success btn-sm" onclick="reviewResignation(${s.id},'Approved')">Accept</button>
                                                <button class="btn btn-danger btn-sm" onclick="reviewResignation(${s.id},'Rejected')">Reject</button>
                                            </div>
                                        ` : '<span style="font-size:0.75rem;color:var(--text-muted)">Reviewed</span>'}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `}
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function reviewResignation(staffId, status) {
    const adminNotes = prompt(`Enter notes for resignation review (${status}):`);
    try {
        await api.put(`/staff-mgmt/resignation/${staffId}/review`, {
            status: status,
            admin_notes: adminNotes || null
        });
        showToast(`Resignation ${status.toLowerCase()} successfully.`, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminStaff();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function openTerminationNoticeModal(staffId, staffName) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">📢 Issue 15-Day Termination Notice</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="padding:12px;background:rgba(234,179,8,0.1);border:1px solid rgba(234,179,8,0.3);border-radius:var(--radius-sm);margin-bottom:14px;font-size:0.85rem">
            Staff: <b>${staffName}</b><br/>
            <b>Policy:</b> Per shop policy, the administration must issue at least a <b>15-day notice</b> before terminating employment.
        </div>
        <div class="form-group">
            <label class="form-label" style="font-weight:600">Reason for Termination <span class="text-danger">*</span></label>
            <textarea class="form-control" id="term-reason" rows="3" placeholder="State official reasons (performance, contract conclusion, shop restructuring)..."></textarea>
        </div>
        <button class="btn btn-danger w-full" style="height:44px" onclick="submitTerminationNotice(${staffId})">Issue 15-Day Exit Notice</button>
    `);
}

async function submitTerminationNotice(staffId) {
    const reason = document.getElementById('term-reason').value.trim();
    if (reason.length < 5) { showToast('Please provide a reason of at least 5 characters.', 'warning'); return; }
    try {
        const res = await api.post(`/staff-mgmt/termination-notice/${staffId}`, { reason });
        showToast(res.message, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminStaff();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function openDeactivateStaffModal(staffId, staffName) {
    showLoading();
    try {
        const [repairs, users] = await Promise.all([
            api.get('/repairs/'),
            api.get('/auth/users')
        ]);
        const otherStaff = users.filter(u => u.role === 'staff' && u.id !== staffId && u.is_active !== 0);
        const activeJobs = repairs.filter(r => r.assigned_technician_id === staffId && !['Completed', 'Delivered', 'Cancelled'].includes(r.status));

        showModal(`
            <div class="modal-header">
                <span class="modal-title" style="color:var(--danger)">🚫 Deactivate Staff: ${staffName}</span>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            ${activeJobs.length > 0 ? `
                <div style="padding:12px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:var(--radius-sm);margin-bottom:14px;font-size:0.85rem">
                    <b>Active Jobs Warning:</b> This staff currently has <b>${activeJobs.length} active repair(s)</b> assigned! You must select a replacement technician to take over these jobs immediately.
                </div>
                <div class="form-group">
                    <label class="form-label" style="font-weight:600">Reassign Active Repairs To: <span class="text-danger">*</span></label>
                    <select class="form-control" id="deact-replacement" style="height:44px">
                        <option value="">-- Choose replacement technician --</option>
                        ${otherStaff.map(s => `<option value="${s.id}">${s.name} (${s.email})</option>`).join('')}
                    </select>
                </div>
            ` : `
                <div style="padding:10px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);border-radius:var(--radius-sm);margin-bottom:14px;font-size:0.85rem">
                    ✅ No active repairs currently assigned to this staff. Deactivation is clean.
                </div>
            `}
            <div class="form-group">
                <label class="flex items-center gap-2" style="font-size:0.85rem;cursor:pointer">
                    <input type="checkbox" id="deact-force" onchange="toggleDeactReasonBox()">
                    <span>Immediate Deactivation (Emergency / Critical Misconduct bypass 15-day notice)</span>
                </label>
            </div>
            <div class="form-group" id="deact-reason-box" style="display:none">
                <label class="form-label" style="font-weight:600">Critical Reason for Immediate Exit <span class="text-danger">*</span></label>
                <textarea class="form-control" id="deact-reason" rows="2" placeholder="Document misconduct or emergency..."></textarea>
            </div>
            <div class="flex gap-2" style="margin-top:16px">
                <button class="btn btn-outline flex-1" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                <button class="btn btn-danger flex-1" onclick="submitDeactivateStaff(${staffId}, ${activeJobs.length})">Confirm Deactivate</button>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function toggleDeactReasonBox() {
    const chk = document.getElementById('deact-force')?.checked;
    const box = document.getElementById('deact-reason-box');
    if (box) box.style.display = chk ? 'block' : 'none';
}

async function submitDeactivateStaff(staffId, activeJobCount) {
    const replacementEl = document.getElementById('deact-replacement');
    const replacementId = replacementEl ? replacementEl.value : null;
    const force = document.getElementById('deact-force')?.checked || false;
    const criticalReason = document.getElementById('deact-reason')?.value.trim() || null;

    if (activeJobCount > 0 && !replacementId) {
        showToast('Please select a replacement technician for the active repairs.', 'warning');
        return;
    }
    if (force && (!criticalReason || criticalReason.length < 5)) {
        showToast('Please provide a valid critical reason for immediate deactivation.', 'warning');
        return;
    }

    try {
        const res = await api.post(`/auth/staff/${staffId}/deactivate`, {
            replacement_staff_id: replacementId ? parseInt(replacementId) : null,
            force_immediate: force,
            critical_reason: criticalReason
        });
        showToast(res.message, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminStaff();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function activateStaff(staffId) {
    if (!confirm('Reactivate this staff account? They will regain login access.')) return;
    try {
        const res = await api.post(`/auth/staff/${staffId}/activate`);
        showToast(res.message, 'success');
        renderAdminStaff();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function openReassignModal(jobId, currentTechName) {
    showLoading();
    try {
        const users = await api.get('/auth/users');
        const staff = users.filter(u => u.role === 'staff' && u.is_active !== 0);

        showModal(`
            <div class="modal-header">
                <span class="modal-title">🔄 Reassign Repair Job</span>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            <div style="font-size:0.85rem;color:var(--text-muted);margin-bottom:12px">
                Current Technician: <b>${currentTechName || 'Unassigned'}</b>
            </div>
            <div class="form-group">
                <label class="form-label" style="font-weight:600">Select New Technician <span class="text-danger">*</span></label>
                <select class="form-control" id="reassign-tech-id" style="height:44px">
                    <option value="">-- Choose technician --</option>
                    ${staff.map(s => `<option value="${s.id}">${s.name} (${s.email})</option>`).join('')}
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Reassignment Note (Optional)</label>
                <input type="text" class="form-control" id="reassign-notes" placeholder="e.g. Previous tech skill mismatch, reassigned to fan specialist">
            </div>
            <button class="btn btn-primary w-full" style="height:44px;margin-top:10px" onclick="submitReassignJob(${jobId})">Confirm Reassignment</button>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function submitReassignJob(jobId) {
    const techId = document.getElementById('reassign-tech-id').value;
    const notes = document.getElementById('reassign-notes').value.trim();
    if (!techId) { showToast('Please select a technician.', 'warning'); return; }

    try {
        const res = await api.post(`/repairs/${jobId}/reassign`, {
            new_technician_id: parseInt(techId),
            notes: notes || null
        });
        showToast(res.message, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminRepairDetail(jobId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** Admin Bills & Verification List */
async function renderAdminBills(filterStatus = 'All') {
    showLoading();
    try {
        const bills = await api.get('/bills/');
        const filtered = filterStatus === 'All' ? bills : bills.filter(b => b.payment_status === filterStatus);
        const pendingCount = bills.filter(b => b.payment_status === 'Pending').length;

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="page-title">💳 Bills & Payments</div>
                            <div class="page-subtitle">${bills.length} invoices · ${pendingCount} pending verification</div>
                        </div>
                        <div class="flex gap-2 flex-wrap">
                            <button class="btn btn-outline btn-sm" onclick="renderAdminPaymentsReport()">💵 Cash & Payments Audit</button>
                            <button class="btn btn-outline btn-sm" onclick="renderAdminOffers()">🎁 Promotional Offers</button>
                        </div>
                    </div>
                </div>

                <!-- Status Filter Pills -->
                <div class="flex gap-2 mb-4 flex-wrap items-center">
                    <span style="font-size:0.85rem;color:var(--text-muted);font-weight:600">Filter:</span>
                    ${['All', 'Pending', 'Paid', 'Failed', 'Refunded'].map(s => `
                        <button class="btn btn-sm ${filterStatus === s ? 'btn-primary' : 'btn-outline'}" onclick="renderAdminBills('${s}')">
                            ${s} ${s === 'Pending' && pendingCount > 0 ? `(${pendingCount})` : ''}
                        </button>
                    `).join('')}
                </div>

                <div class="table-container">
                    <table>
                        <thead><tr><th>Bill #</th><th>Customer</th><th>Repair ID</th><th>Amount</th><th>Method</th><th>Status</th><th>Date</th><th>Action</th></tr></thead>
                        <tbody>
                            ${filtered.map(b => `
                                <tr>
                                    <td class="font-mono">${b.bill_number}</td>
                                    <td>${b.customer_name}</td>
                                    <td class="font-mono text-primary-color">${b.repair_id}</td>
                                    <td style="font-weight:700">${formatCurrency(b.total_amount)}</td>
                                    <td><span class="badge badge-assigned">${b.payment_method || '—'}</span></td>
                                    <td>${statusBadge(b.payment_status)}</td>
                                    <td style="font-size:0.8rem">${formatDate(b.created_at)}</td>
                                    <td>
                                        <div class="flex gap-1 flex-wrap">
                                            <button onclick="api.download('/bills/${b.id}/pdf', 'Invoice-${b.bill_number}.pdf')" class="btn btn-outline btn-sm" title="Download PDF">⬇ PDF</button>
                                            ${b.payment_status === 'Pending' ? `
                                                <button class="btn btn-primary btn-sm" onclick="openVerifyPaymentModal(${b.id}, '${b.bill_number}', ${b.total_amount}, '${b.transaction_id || ''}', '${b.payment_method || 'UPI'}')">💳 Verify</button>
                                            ` : ''}
                                            ${b.payment_status !== 'Paid' && b.payment_status !== 'Pending' && !b.is_void && !b.is_cancelled ? `
                                                <button class="btn btn-success btn-sm" onclick="markPaid(${b.id})">✅ Paid</button>
                                            ` : ''}
                                            ${!b.is_void && !b.is_cancelled ? `
                                                <button class="btn btn-outline btn-sm" onclick="openEditBillModal(${b.id},${b.labour_charge},${b.parts_cost},${b.discount},'${b.payment_status}')" title="Edit Bill">✏️</button>
                                                <button class="btn btn-warning btn-sm" onclick="voidBillPrompt(${b.id}, '${b.bill_number}')" title="Void Invoice">🚫 Void</button>
                                                ${b.payment_status !== 'Paid' ? `
                                                    <button class="btn btn-danger btn-sm" onclick="cancelBillPrompt(${b.id}, '${b.bill_number}')" title="Cancel Invoice">✕ Cancel</button>
                                                ` : ''}
                                            ` : ''}
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function openVerifyPaymentModal(billId, billNumber, amount, txnId, method) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">💳 Verify Customer Payment</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="padding:14px;background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:var(--radius-sm);margin-bottom:14px">
            <div style="font-size:0.85rem;color:var(--text-muted)">Invoice: <b>${billNumber}</b></div>
            <div style="font-size:1.5rem;font-weight:700;color:var(--primary);margin:4px 0">${formatCurrency(amount)}</div>
            <div style="font-size:0.85rem;margin-top:4px">
                Payment Method: <b>${method}</b><br/>
                Submitted Transaction ID / UTR: <span class="font-mono" style="font-weight:700;background:var(--bg-input);padding:2px 6px;border-radius:4px">${txnId || 'N/A'}</span>
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">Verification Note (Optional)</label>
            <input type="text" class="form-control" id="verify-notes" placeholder="e.g. Confirmed in bank statement / GPay">
        </div>
        <div class="flex gap-2 flex-wrap" style="margin-top:16px">
            <button class="btn btn-success flex-1" onclick="submitVerifyPayment(${billId}, 'Approve')">✅ Approve (Mark Paid)</button>
            <button class="btn btn-danger flex-1" onclick="submitVerifyPayment(${billId}, 'Reject')">❌ Reject</button>
            <button class="btn btn-outline flex-1" onclick="submitVerifyPayment(${billId}, 'Refund')">↩️ Refund</button>
        </div>
    `);
}

async function submitVerifyPayment(billId, action) {
    const notes = document.getElementById('verify-notes')?.value || '';
    try {
        const res = await api.post(`/bills/${billId}/verify-payment`, { action, notes });
        showToast(res.message, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminBills();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** ─── ADMIN EDIT MODALS ──────────────────────────────── */

function openEditUserModal(userId, name, email, phone, salary = 0, joiningDate = '', isActive = 1) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">✏️ Edit Staff Member</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-row">
            <div class="form-group"><label class="form-label">Full Name *</label>
                <input type="text" class="form-control" id="edit-user-name" value="${name}" required></div>
            <div class="form-group"><label class="form-label">Email Address *</label>
                <input type="email" class="form-control" id="edit-user-email" value="${email}" required></div>
        </div>
        <div class="form-row">
            <div class="form-group"><label class="form-label">Phone Number</label>
                <input type="tel" class="form-control" id="edit-user-phone" value="${phone || ''}"></div>
            <div class="form-group"><label class="form-label">Monthly Salary (₹)</label>
                <input type="number" class="form-control" id="edit-user-salary" value="${salary || 0}" min="0"></div>
        </div>
        <div class="form-row">
            <div class="form-group"><label class="form-label">Joining Date</label>
                <input type="date" class="form-control" id="edit-user-joined" value="${joiningDate || ''}"></div>
            <div class="form-group"><label class="form-label">Account Status</label>
                <select class="form-control" id="edit-user-active">
                    <option value="1" ${isActive ? 'selected' : ''}>Active</option>
                    <option value="0" ${!isActive ? 'selected' : ''}>Deactivated</option>
                </select></div>
        </div>
        <button class="btn btn-primary w-full" style="margin-top:8px" onclick="submitEditUser(${userId})">Save Changes</button>
    `);
}

async function submitEditUser(userId) {
    const name = document.getElementById('edit-user-name')?.value.trim();
    const email = document.getElementById('edit-user-email')?.value.trim();
    const phone = document.getElementById('edit-user-phone')?.value.trim();
    const salary = parseFloat(document.getElementById('edit-user-salary')?.value || 0);
    const joined = document.getElementById('edit-user-joined')?.value || null;
    const isActive = parseInt(document.getElementById('edit-user-active')?.value || 1);

    if (!name || !email) {
        showToast('Name and Email are required.', 'warning');
        return;
    }

    try {
        await api.put(`/auth/users/${userId}`, {
            name,
            email,
            phone: phone || null,
            monthly_salary: salary,
            joining_date: joined,
            is_active: isActive
        });
        showToast('Staff member updated successfully! ✅', 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminStaff();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deleteStaffMember(userId, name) {
    if (!confirm(`Are you sure you want to remove/deactivate staff member '${name}'?`)) return;
    try {
        const res = await api.delete(`/auth/users/${userId}`);
        showToast(res.message || 'Staff removed successfully', 'success');
        renderAdminStaff();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// Edit Inventory Item
function openEditInventoryModal(id, name, code, cat, qty, price, reorder, supplier) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">✏️ Edit Inventory Item</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-row">
            <div class="form-group"><label class="form-label">Part Name</label>
                <input class="form-control" id="ei-name" value="${name}"></div>
            <div class="form-group"><label class="form-label">Part Code</label>
                <input class="form-control" id="ei-code" value="${code}"></div>
        </div>
        <div class="form-row">
            <div class="form-group"><label class="form-label">Category</label>
                <select class="form-control" id="ei-cat">
                    ${['Fan Parts', 'Cooler Parts', 'Mixer Parts', 'Motor Parts', 'Geyser Parts', 'Pump Parts', 'Wires & Cables', 'Switches & Sockets', 'Capacitors', 'MCB & Fuse', 'Relays', 'Connectors', 'LED Bulbs', 'Tape & Insulation', 'Fasteners', 'Misc Electrical'].map(c => '<option value="' + c + '"' + (c == cat ? ' selected' : '') + '>' + c + '</option>').join('')}
                </select></div>
            <div class="form-group"><label class="form-label">Quantity</label>
                <input type="number" class="form-control" id="ei-qty" value="${qty}" min="0"></div>
        </div>
        <div class="form-row">
            <div class="form-group"><label class="form-label">Unit Price (₹)</label>
                <input type="number" class="form-control" id="ei-price" value="${price}"></div>
            <div class="form-group"><label class="form-label">Reorder Level</label>
                <input type="number" class="form-control" id="ei-reorder" value="${reorder}"></div>
        </div>
        <div class="form-group"><label class="form-label">Supplier</label>
            <input class="form-control" id="ei-supplier" value="${supplier}"></div>
        <button class="btn btn-primary w-full" onclick="submitEditInventory(${id})">Save Changes</button>
    `);
}
async function submitEditInventory(itemId) {
    try {
        await api.put(`/inventory/${itemId}`, {
            part_name: document.getElementById('ei-name').value,
            part_code: document.getElementById('ei-code').value,
            category: document.getElementById('ei-cat').value,
            compatible_devices: [],
            quantity: parseInt(document.getElementById('ei-qty').value || 0),
            unit_price: parseFloat(document.getElementById('ei-price').value || 0),
            reorder_level: parseInt(document.getElementById('ei-reorder').value || 5),
            supplier: document.getElementById('ei-supplier').value
        });
        showToast('Inventory item updated!', 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminInventory();
    } catch (e) { showToast(e.message, 'error'); }
}

// Edit Bill
function openEditBillModal(billId, labour, parts, discount, status) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">✏️ Edit Bill</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-row">
            <div class="form-group"><label class="form-label">Labour Charge (₹)</label>
                <input type="number" class="form-control" id="eb-labour" value="${labour}"></div>
            <div class="form-group"><label class="form-label">Parts Cost (₹)</label>
                <input type="number" class="form-control" id="eb-parts" value="${parts}"></div>
        </div>
        <div class="form-row">
            <div class="form-group"><label class="form-label">Discount (₹)</label>
                <input type="number" class="form-control" id="eb-discount" value="${discount}"></div>
            <div class="form-group"><label class="form-label">Payment Status</label>
                <select class="form-control" id="eb-status">
                    ${['Pending', 'Paid', 'Partial'].map(s => '<option value="' + s + '"' + (s == status ? ' selected' : '') + '>' + s + '</option>').join('')}
                </select></div>
        </div>
        <button class="btn btn-primary w-full" onclick="submitEditBill(${billId})">Save Changes</button>
    `);
}
async function submitEditBill(billId) {
    try {
        const res = await api.put(`/bills/${billId}`, {
            labour_charge: parseFloat(document.getElementById('eb-labour').value || 0),
            parts_cost: parseFloat(document.getElementById('eb-parts').value || 0),
            discount: parseFloat(document.getElementById('eb-discount').value || 0),
            payment_status: document.getElementById('eb-status').value
        });
        showToast(`Bill updated! Total: ${formatCurrency(res.total)}`, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminBills();
    } catch (e) { showToast(e.message, 'error'); }
}

async function deleteBill(billId, billNumber) {
    if (!confirm(`Are you sure you want to cancel/delete Invoice #${billNumber}?`)) return;
    try {
        const res = await api.delete(`/bills/${billId}`);
        showToast(res.message || 'Invoice cancelled successfully.', 'success');
        renderAdminBills();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function voidBillPrompt(billId, billNumber) {
    const reason = prompt(`Please enter the mandatory reason to VOID Invoice #${billNumber}:`);
    if (!reason || reason.trim().length < 3) {
        if (reason !== null) showToast('A valid reason (minimum 3 characters) is required to void an invoice.', 'warning');
        return;
    }
    try {
        const res = await api.post(`/bills/${billId}/void`, { reason: reason.trim() });
        showToast(res.message || 'Invoice voided successfully.', 'success');
        renderAdminBills();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function cancelBillPrompt(billId, billNumber) {
    const reason = prompt(`Please enter the mandatory reason to CANCEL Invoice #${billNumber}:`);
    if (!reason || reason.trim().length < 3) {
        if (reason !== null) showToast('A valid reason (minimum 3 characters) is required to cancel an invoice.', 'warning');
        return;
    }
    try {
        const res = await api.post(`/bills/${billId}/cancel`, { reason: reason.trim() });
        showToast(res.message || 'Invoice cancelled successfully.', 'success');
        renderAdminBills();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deleteRepairJob(id, repairId) {
    if (!confirm(`Are you sure you want to permanently delete repair job ${repairId}? All associated records, notes, and photos will be removed.`)) return;
    try {
        const res = await api.delete(`/repairs/${id}`);
        showToast(res.message || `Repair ${repairId} deleted successfully! 🗑️`, 'success');
        if (window.location.hash.includes('/admin/repairs/')) {
            router.navigate('/admin/repairs');
        } else {
            renderAdminRepairs();
        }
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function openAdminEditRepairModal(job) {
    const statuses = [
        'Requested', 'Assigned', 'Diagnosing', 'Approved',
        'Repairing', 'Ready', 'Delivered', 'Completed',
        'On Hold', 'Cancelled', 'Rejected'
    ];
    const priorities = ['Normal', 'High', 'Urgent'];
    const serviceModes = ['Store Drop-off', 'Home Pickup'];
    const electricalDevices = [
        'Ceiling Fan', 'Table/Stand Fan', 'Exhaust Fan',
        'Air Cooler', 'Water Geyser/Heater', 'Mixer Grinder',
        'Water Pump/Motor', 'Induction Cooktop', 'Electric Iron',
        'Microwave/Oven', 'Room Heater', 'Inverter/UPS',
        'Stabilizer', 'Washing Machine', 'Refrigerator', 'Other Electrical'
    ];

    showModal(`
        <div class="modal-header">
            <span class="modal-title">✏️ Admin Full Edit – Repair #${job.repair_id}</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:12px">
            Customer: <b>${job.customer_name || 'N/A'}</b> (${job.customer_phone || ''})
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Electrical Device Type *</label>
                <input list="admin-device-types" class="form-control" id="aed-device" value="${job.device_type || ''}" required>
                <datalist id="admin-device-types">
                    ${electricalDevices.map(d => `<option value="${d}"></option>`).join('')}
                </datalist>
            </div>
            <div class="form-group">
                <label class="form-label">Brand</label>
                <input type="text" class="form-control" id="aed-brand" value="${job.brand || ''}">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Model / Capacity</label>
                <input type="text" class="form-control" id="aed-model" value="${job.model || ''}">
            </div>
            <div class="form-group">
                <label class="form-label">Priority</label>
                <select class="form-control" id="aed-priority">
                    ${priorities.map(p => `<option value="${p}" ${p === job.priority ? 'selected' : ''}>${p}</option>`).join('')}
                </select>
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Status</label>
                <select class="form-control" id="aed-status">
                    ${statuses.map(s => `<option value="${s}" ${s === job.status ? 'selected' : ''}>${s}</option>`).join('')}
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Service Type</label>
                <select class="form-control" id="aed-service-type">
                    ${serviceModes.map(m => `<option value="${m}" ${m === job.service_type ? 'selected' : ''}>${m}</option>`).join('')}
                </select>
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Estimated Cost (₹)</label>
                <input type="number" class="form-control" id="aed-est-cost" value="${job.estimated_cost || 0}">
            </div>
            <div class="form-group">
                <label class="form-label">Actual Cost (₹)</label>
                <input type="number" class="form-control" id="aed-act-cost" value="${job.actual_cost || 0}">
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">Problem Description</label>
            <textarea class="form-control" id="aed-problem" rows="2">${job.problem_description || ''}</textarea>
        </div>
        <div class="form-group">
            <label class="form-label">Service / Pickup Address</label>
            <input type="text" class="form-control" id="aed-address" value="${job.pickup_address || ''}" placeholder="House no, Street, Landmark...">
        </div>
        <div class="form-group">
            <label class="form-label">Admin / Technician Notes</label>
            <textarea class="form-control" id="aed-notes" rows="2">${job.technician_notes || ''}</textarea>
        </div>
        <button class="btn btn-primary w-full" style="margin-top:8px" onclick="submitAdminEditRepair(${job.id})">Save All Changes ✅</button>
    `);
}

async function submitAdminEditRepair(jobId) {
    const payload = {
        device_type: document.getElementById('aed-device')?.value.trim(),
        brand: document.getElementById('aed-brand')?.value.trim(),
        model: document.getElementById('aed-model')?.value.trim(),
        priority: document.getElementById('aed-priority')?.value,
        status: document.getElementById('aed-status')?.value,
        service_type: document.getElementById('aed-service-type')?.value,
        estimated_cost: parseFloat(document.getElementById('aed-est-cost')?.value || 0),
        actual_cost: parseFloat(document.getElementById('aed-act-cost')?.value || 0),
        problem_description: document.getElementById('aed-problem')?.value.trim(),
        pickup_address: document.getElementById('aed-address')?.value.trim(),
        technician_notes: document.getElementById('aed-notes')?.value.trim()
    };

    try {
        const res = await api.put(`/repairs/${jobId}`, payload);
        showToast(res.message || 'Repair details updated successfully! ✅', 'success');
        document.querySelector('.modal-overlay')?.remove();
        if (window.location.hash.includes('/admin/repairs/')) {
            renderAdminRepairDetail(jobId);
        } else {
            renderAdminRepairs();
        }
    } catch (e) {
        showToast(e.message, 'error');
    }
}


/** Admin Feedback View */
async function renderAdminFeedback() {
    showLoading();
    try {
        const feedbacks = await api.get('/feedback/');
        const avgRating = feedbacks.length
            ? (feedbacks.reduce((s, f) => s + f.rating, 0) / feedbacks.length).toFixed(1)
            : '—';
        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="page-title">⭐ Customer Feedback</div>
                    <div class="page-subtitle">${feedbacks.length} reviews · Average Rating: ${avgRating} ⭐</div>
                </div>
                ${feedbacks.length === 0 ? `
                    <div class="empty-state card">
                        <div class="empty-state-icon">⭐</div>
                        <div class="empty-state-title">No feedback yet</div>
                        <div class="text-muted">Feedback will appear here once customers submit reviews.</div>
                    </div>
                ` : `
                    <div class="table-container">
                        <table>
                            <thead><tr><th>Customer</th><th>Repair</th><th>Device</th><th>Rating</th><th>Comment</th><th>Date</th></tr></thead>
                            <tbody>
                                ${feedbacks.map(f => `
                                    <tr>
                                        <td>
                                            <div style="font-weight:500">${f.customer_name}</div>
                                            <div style="font-size:0.75rem;color:var(--text-muted)">${f.customer_email}</div>
                                        </td>
                                        <td class="font-mono text-primary-color">${f.repair_id}</td>
                                        <td style="font-size:0.85rem">${f.device_type} — ${f.brand} ${f.model}</td>
                                        <td style="font-size:1.1rem;letter-spacing:1px">${'⭐'.repeat(f.rating)}${'☆'.repeat(5 - f.rating)}</td>
                                        <td style="font-size:0.85rem;color:var(--text-muted);max-width:200px">${f.comment || '—'}</td>
                                        <td style="font-size:0.78rem;color:var(--text-muted)">${formatDate(f.created_at)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `}
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** ─── ADMIN WARRANTIES & CLAIMS VIEW ────────────────────────── */
async function renderAdminWarranties() {
    showLoading();
    try {
        const [warranties, claims] = await Promise.all([
            api.get('/warranties/list').catch(() => []),
            api.get('/warranties/claims').catch(() => [])
        ]);

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="page-title">🛡️ Warranty & Claims Management</div>
                    <div class="page-subtitle">${warranties.length} issued warranties · ${claims.length} customer claims filed</div>
                </div>

                <!-- Claims Section -->
                <div class="card" style="margin-bottom:24px">
                    <div style="font-weight:700;font-size:1.1rem;margin-bottom:12px;display:flex;align-items:center;gap:8px">
                        <span>📢 Customer Warranty Claims (${claims.filter(c => c.status === 'Pending').length} Pending Action)</span>
                    </div>
                    ${claims.length === 0 ? `
                        <div style="color:var(--text-muted);font-size:0.85rem;font-style:italic">No warranty claims filed yet.</div>
                    ` : `
                        <div class="table-container">
                            <table>
                                <thead><tr><th>Claim #</th><th>Customer</th><th>Warranty Code</th><th>Issue Description</th><th>Status</th><th>Filed Date</th><th>Action</th></tr></thead>
                                <tbody>
                                    ${claims.map(c => `
                                        <tr>
                                            <td class="font-mono" style="font-weight:600">#${c.id}</td>
                                            <td>
                                                <div style="font-weight:500">${c.customer_name}</div>
                                                <div style="font-size:0.75rem;color:var(--text-muted)">${c.customer_phone || ''}</div>
                                            </td>
                                            <td class="font-mono text-primary-color" style="font-weight:600">${c.warranty_code}</td>
                                            <td style="max-width:220px;font-size:0.85rem">${c.issue_description}</td>
                                            <td><span class="badge ${c.status === 'Approved' ? 'badge-completed' : c.status === 'Pending' ? 'badge-diagnosing' : c.status === 'Resolved' ? 'badge-delivered' : 'badge-low'}">${c.status}</span></td>
                                            <td style="font-size:0.78rem;color:var(--text-muted)">${formatDate(c.created_at)}</td>
                                            <td>
                                                ${c.status === 'Pending' ? `
                                                    <button class="btn btn-outline btn-sm" onclick="openResolveClaimModal(${c.id}, '${c.customer_name}')">⚖️ Resolve</button>
                                                ` : `<span style="font-size:0.75rem;color:var(--text-muted)">${c.resolution_notes || c.status}</span>`}
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `}
                </div>

                <!-- Warranties Directory -->
                <div class="table-container">
                    <div class="table-header-row">
                        <div class="table-title">Issued Warranties Directory</div>
                    </div>
                    ${warranties.length === 0 ? `
                        <div style="padding:20px;color:var(--text-muted);font-style:italic">No warranties issued yet. You can issue warranties directly from the Repair Detail page.</div>
                    ` : `
                        <table>
                            <thead><tr><th>Code</th><th>Repair ID</th><th>Customer</th><th>Device</th><th>Valid Until</th><th>Days Left</th><th>Status</th></tr></thead>
                            <tbody>
                                ${warranties.map(w => `
                                    <tr>
                                        <td class="font-mono text-primary-color" style="font-weight:700">${w.warranty_code}</td>
                                        <td class="font-mono" style="cursor:pointer" onclick="renderAdminRepairDetail(${w.repair_job_id})">${w.repair_id}</td>
                                        <td>${w.customer_name}</td>
                                        <td>${w.device_type} — ${w.brand} ${w.model}</td>
                                        <td style="font-size:0.8rem">${formatDate(w.end_date)}</td>
                                        <td style="font-weight:600;color:${w.days_remaining > 15 ? 'var(--success)' : 'var(--danger)'}">
                                            ${w.days_remaining > 0 ? w.days_remaining + ' days left' : 'Expired'}
                                        </td>
                                        <td>${statusBadge(w.status)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `}
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function openResolveClaimModal(claimId, customerName) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">⚖️ Resolve Claim #${claimId} (${customerName})</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-group">
            <label class="form-label">Decision</label>
            <select class="form-control" id="claim-decision">
                <option value="Approved">Approved (Free rework/replacement under warranty)</option>
                <option value="Rejected">Rejected (Not covered / Misuse / Physical damage)</option>
                <option value="Resolved">Resolved (Rework completed and handed over)</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Resolution Notes / Instructions</label>
            <textarea class="form-control" id="claim-notes" rows="3" placeholder="Explain decision or instructions for the customer..."></textarea>
        </div>
        <button class="btn btn-primary w-full" onclick="submitResolveClaim(${claimId})">Save Resolution</button>
    `);
}

async function submitResolveClaim(claimId) {
    const status = document.getElementById('claim-decision').value;
    const notes = document.getElementById('claim-notes').value;
    try {
        await api.put(`/warranties/claims/${claimId}`, {
            status,
            resolution_notes: notes || undefined
        });
        showToast('Claim decision saved successfully!', 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminWarranties();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** ─── ADMIN AUDIT LOGS VIEW ────────────────────────── */
async function renderAdminAuditLogs() {
    showLoading();
    try {
        const logs = await api.get('/reports/audit-logs?limit=100').catch(() => []);
        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="page-title">📜 Enterprise System Audit Trail</div>
                    <div class="page-subtitle">Tamper-evident logs of status transitions, assignments, stock deductions, and security checks</div>
                </div>

                <div class="table-container">
                    ${logs.length === 0 ? `
                        <div style="padding:24px;text-align:center;color:var(--text-muted)">No audit events recorded yet.</div>
                    ` : `
                        <table>
                            <thead><tr><th>Timestamp</th><th>User</th><th>Action</th><th>Entity</th><th>IP Address</th><th>Details</th></tr></thead>
                            <tbody>
                                ${logs.map(l => `
                                    <tr>
                                        <td style="font-size:0.75rem;color:var(--text-muted);white-space:nowrap">${formatDate(l.created_at)}</td>
                                        <td>
                                            <div style="font-weight:600;font-size:0.85rem">${l.user_name || 'System'}</div>
                                            <div style="font-size:0.72rem;color:var(--text-muted)">${l.user_role || 'system'} (ID: ${l.user_id || '—'})</div>
                                        </td>
                                        <td>
                                            <span class="badge ${l.action.includes('SECURITY') ? 'badge-low' : l.action.includes('ASSIGN') ? 'badge-diagnosing' : 'badge-completed'}" style="font-size:0.72rem">
                                                ${l.action}
                                            </span>
                                        </td>
                                        <td class="font-mono" style="font-size:0.8rem">${l.entity_type} #${l.entity_id || '—'}</td>
                                        <td class="font-mono" style="font-size:0.75rem;color:var(--text-muted)">${l.ip_address || '127.0.0.1'}</td>
                                        <td style="font-size:0.78rem;color:var(--text-muted);max-width:280px;word-break:break-word">${l.details || '—'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    `}
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** ─── ADMIN PROMOTIONAL & FESTIVAL OFFERS ──────────────────── */

async function renderAdminOffers() {
    showLoading();
    try {
        const [offers, users] = await Promise.all([
            api.get('/bills/offers').catch(() => []),
            api.get('/auth/users').catch(() => [])
        ]);
        const customers = users.filter(u => u.role === 'customer');

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="page-title">🎁 Promotional & Festival Offers</div>
                            <div class="page-subtitle">Configure special festival discounts and personalized offers for regular customers</div>
                        </div>
                        <div class="flex gap-2">
                            <button class="btn btn-primary btn-sm" onclick="openCreateOfferModal()">➕ Create New Offer</button>
                            <button class="btn btn-outline btn-sm" onclick="router.navigate('/admin/bills')">← Back to Bills</button>
                        </div>
                    </div>
                </div>

                <div class="table-container">
                    ${offers.length === 0 ? `
                        <div style="padding:24px;text-align:center;color:var(--text-muted)">No promotional offers found. Create your first festival offer!</div>
                    ` : `
                        <table>
                            <thead>
                                <tr>
                                    <th>Coupon Code</th>
                                    <th>Offer Title & Description</th>
                                    <th>Discount</th>
                                    <th>Min Bill</th>
                                    <th>Target Audience</th>
                                    <th>Valid Until</th>
                                    <th>Usage</th>
                                    <th>Status</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${offers.map(o => {
                                    const isPct = (o.discount_type === 'percentage');
                                    const discountLabel = isPct ? `${o.discount_value}% OFF` : `₹${o.discount_value} OFF`;
                                    const targetLabel = o.target_customer_name ? `👤 Regular Customer: <b>${o.target_customer_name}</b>` : '🎉 Public / All Customers';

                                    return `
                                        <tr style="${o.is_active === 0 ? 'opacity:0.6' : ''}">
                                            <td class="font-mono" style="font-weight:700;color:var(--primary);font-size:1rem">${o.code}</td>
                                            <td>
                                                <div style="font-weight:600">${o.title}</div>
                                                <div style="font-size:0.75rem;color:var(--text-muted)">${o.description || '—'}</div>
                                            </td>
                                            <td style="font-weight:700;color:var(--success)">${discountLabel}</td>
                                            <td>${o.min_bill_amount ? formatCurrency(o.min_bill_amount) : 'None'}</td>
                                            <td style="font-size:0.82rem">${targetLabel}</td>
                                            <td style="font-size:0.82rem">${o.valid_until || 'No Expiry'}</td>
                                            <td><span class="badge badge-assigned">${o.usage_count || 0} times</span></td>
                                            <td>
                                                ${o.is_active === 1 
                                                    ? '<span class="badge badge-completed">Active</span>' 
                                                    : '<span class="badge badge-cancelled">Disabled</span>'}
                                            </td>
                                            <td>
                                                <button class="btn btn-outline btn-sm" onclick="toggleOfferStatus(${o.id})">
                                                    ${o.is_active === 1 ? 'Disable' : 'Enable'}
                                                </button>
                                            </td>
                                        </tr>
                                    `;
                                }).join('')}
                            </tbody>
                        </table>
                    `}
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function openCreateOfferModal() {
    showLoading();
    try {
        const users = await api.get('/auth/users');
        const customers = users.filter(u => u.role === 'customer');

        showModal(`
            <div class="modal-header">
                <span class="modal-title">🎁 Create Discount / Festival Offer</span>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Coupon Code (Uppercase) <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="offer-code" placeholder="DIWALI20" style="text-transform:uppercase;font-weight:700">
                </div>
                <div class="form-group">
                    <label class="form-label">Offer Title <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="offer-title" placeholder="Diwali Festival 20% OFF">
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Description</label>
                <input type="text" class="form-control" id="offer-desc" placeholder="Celebrate Diwali with flat 20% discount on all repair services!">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Discount Type</label>
                    <select class="form-control" id="offer-type" style="height:44px">
                        <option value="percentage">Percentage (%) Discount</option>
                        <option value="flat">Flat Amount (₹) Discount</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Discount Value <span class="text-danger">*</span></label>
                    <input type="number" class="form-control" id="offer-val" placeholder="20" min="1" style="height:44px">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Minimum Bill Amount (₹)</label>
                    <input type="number" class="form-control" id="offer-min" placeholder="300" value="0" style="height:44px">
                </div>
                <div class="form-group">
                    <label class="form-label">Valid Until (Expiry Date)</label>
                    <input type="date" class="form-control" id="offer-expiry" style="height:44px">
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Target Audience (Leave blank for public festival offer)</label>
                <select class="form-control" id="offer-target" style="height:44px">
                    <option value="">🎉 All Customers (Public Festival Coupon)</option>
                    ${customers.map(c => `<option value="${c.id}">👤 Specific Customer: ${c.name} (${c.email})</option>`).join('')}
                </select>
            </div>
            <button class="btn btn-primary w-full" style="height:44px;margin-top:10px" onclick="submitCreateOffer()">Create & Publish Offer</button>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function submitCreateOffer() {
    const code = document.getElementById('offer-code').value.trim().toUpperCase();
    const title = document.getElementById('offer-title').value.trim();
    const desc = document.getElementById('offer-desc').value.trim();
    const type = document.getElementById('offer-type').value;
    const val = parseFloat(document.getElementById('offer-val').value || 0);
    const minBill = parseFloat(document.getElementById('offer-min').value || 0);
    const expiry = document.getElementById('offer-expiry').value || null;
    const target = document.getElementById('offer-target').value || null;

    if (!code) { showToast('Please enter a coupon code.', 'warning'); return; }
    if (!title) { showToast('Please enter a title for the offer.', 'warning'); return; }
    if (val <= 0) { showToast('Discount value must be greater than 0.', 'warning'); return; }

    try {
        const res = await api.post('/bills/offers', {
            code: code,
            title: title,
            description: desc || null,
            discount_type: type,
            discount_value: val,
            min_bill_amount: minBill,
            valid_until: expiry,
            target_customer_id: target ? parseInt(target) : null
        });
        showToast(res.message, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminOffers();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function toggleOfferStatus(offerId) {
    try {
        const res = await api.delete(`/bills/offers/${offerId}`);
        showToast(res.message, 'info');
        renderAdminOffers();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** ─── ADMIN CUSTOMER SUPPORT TICKETS ──────────────────────── */

async function renderAdminSupportTickets(filterStatus = 'All') {
    showLoading();
    try {
        const tickets = await api.get('/support/tickets');
        const filtered = filterStatus === 'All' ? tickets : tickets.filter(t => t.status === filterStatus);
        const openCount = tickets.filter(t => t.status === 'Open').length;

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="page-title">🎧 Customer Support & Help Tickets</div>
                            <div class="page-subtitle">${tickets.length} total tickets · ${openCount} open requiring attention</div>
                        </div>
                    </div>
                </div>

                <!-- Status Filter Pills -->
                <div class="flex gap-2 mb-4 flex-wrap items-center">
                    <span style="font-size:0.85rem;color:var(--text-muted);font-weight:600">Filter:</span>
                    ${['All', 'Open', 'In Progress', 'Resolved', 'Closed'].map(s => `
                        <button class="btn btn-sm ${filterStatus === s ? 'btn-primary' : 'btn-outline'}" onclick="renderAdminSupportTickets('${s}')">
                            ${s} ${s === 'Open' && openCount > 0 ? `(${openCount})` : ''}
                        </button>
                    `).join('')}
                </div>

                <div class="table-container">
                    ${filtered.length === 0 ? `
                        <div style="padding:24px;text-align:center;color:var(--text-muted)">No tickets found matching "${filterStatus}".</div>
                    ` : `
                        <table>
                            <thead>
                                <tr>
                                    <th>Ticket Code</th>
                                    <th>Customer</th>
                                    <th>Subject & Category</th>
                                    <th>Repair Ref</th>
                                    <th>Priority</th>
                                    <th>Status</th>
                                    <th>Updated</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${filtered.map(t => {
                                    const prioColor = t.priority === 'Urgent' ? 'var(--danger)' : t.priority === 'High' ? '#eab308' : 'var(--primary)';
                                    return `
                                        <tr>
                                            <td class="font-mono text-primary-color" style="font-weight:700">${t.ticket_code}</td>
                                            <td>
                                                <div style="font-weight:600">${t.customer_name}</div>
                                                <div style="font-size:0.75rem;color:var(--text-muted)">${t.customer_phone || t.customer_email}</div>
                                            </td>
                                            <td>
                                                <div style="font-weight:600">${t.subject}</div>
                                                <div style="font-size:0.75rem;color:var(--text-muted)">Category: ${t.category} · ${t.message_count || 1} msg(s)</div>
                                            </td>
                                            <td>${t.repair_id ? `<span class="font-mono">${t.repair_id}</span>` : '—'}</td>
                                            <td><span class="badge" style="color:${prioColor};border:1px solid ${prioColor}44">${t.priority}</span></td>
                                            <td><span class="badge ${t.status === 'Resolved' ? 'badge-completed' : t.status === 'Open' ? 'badge-diagnosing' : 'badge-assigned'}">${t.status}</span></td>
                                            <td style="font-size:0.78rem;color:var(--text-muted)">${formatDate(t.updated_at || t.created_at)}</td>
                                            <td>
                                                <button class="btn btn-outline btn-sm" onclick="openAdminTicketModal(${t.id})">
                                                    💬 View & Reply
                                                </button>
                                            </td>
                                        </tr>
                                    `;
                                }).join('')}
                            </tbody>
                        </table>
                    `}
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function openAdminTicketModal(ticketId) {
    showLoading();
    try {
        const ticket = await api.get(`/support/tickets/${ticketId}`);
        const messages = ticket.messages || [];

        showModal(`
            <div class="modal-header">
                <span class="modal-title">🎧 Ticket: ${ticket.ticket_code}</span>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            <div style="padding:12px;background:var(--surface-2);border-radius:var(--radius-sm);margin-bottom:14px">
                <div class="flex justify-between items-start flex-wrap gap-2">
                    <div>
                        <div style="font-weight:700;font-size:1.1rem">${ticket.subject}</div>
                        <div style="font-size:0.82rem;color:var(--text-muted)">Customer: <b>${ticket.customer_name}</b> · ${ticket.customer_phone || ticket.customer_email}</div>
                        ${ticket.repair_id ? `<div style="font-size:0.8rem;margin-top:2px">Referenced Repair: <b>${ticket.repair_id}</b> (${ticket.brand || ''} ${ticket.model || ''})</div>` : ''}
                    </div>
                    <div class="flex gap-2 items-center">
                        <select class="form-control" id="ticket-new-status" style="height:36px;font-size:0.85rem">
                            ${['Open', 'In Progress', 'Resolved', 'Closed'].map(s => `
                                <option value="${s}" ${s === ticket.status ? 'selected' : ''}>Status: ${s}</option>
                            `).join('')}
                        </select>
                        <button class="btn btn-outline btn-sm" onclick="updateAdminTicketStatus(${ticketId})">Update</button>
                    </div>
                </div>
            </div>

            <!-- Conversation Thread -->
            <div style="max-height:350px;overflow-y:auto;display:flex;flex-direction:column;gap:10px;padding:8px;background:var(--bg-input);border-radius:var(--radius-sm);margin-bottom:14px">
                ${messages.map(m => {
                    const isAdmin = (m.sender_role === 'admin');
                    const isStaff = (m.sender_role === 'staff');
                    const isCust = (m.sender_role === 'customer');

                    return `
                        <div style="align-self:${isCust ? 'flex-start' : 'flex-end'};max-width:82%;background:${isCust ? 'var(--surface-2)' : 'rgba(99,102,241,0.15)'};border:1px solid ${isCust ? 'var(--border)' : 'rgba(99,102,241,0.35)'};border-radius:8px;padding:10px 12px">
                            <div class="flex justify-between items-center gap-2" style="font-size:0.75rem;margin-bottom:4px">
                                <b style="color:${isCust ? 'var(--text-primary)' : 'var(--primary)'}">${m.sender_name} (${m.sender_role})</b>
                                <span style="color:var(--text-muted)">${formatDate(m.created_at)}</span>
                            </div>
                            <div style="font-size:0.9rem;line-height:1.4;white-space:pre-wrap">${m.message}</div>
                        </div>
                    `;
                }).join('')}
            </div>

            <!-- Reply Box -->
            <div class="form-group">
                <textarea class="form-control" id="ticket-reply-msg" rows="2" placeholder="Write official support reply to customer..."></textarea>
            </div>
            <div class="flex justify-between items-center">
                <button class="btn btn-outline btn-sm" onclick="this.closest('.modal-overlay').remove()">Close</button>
                <button class="btn btn-primary" onclick="submitAdminTicketReply(${ticketId})">📨 Send Reply</button>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function submitAdminTicketReply(ticketId) {
    const msg = document.getElementById('ticket-reply-msg')?.value.trim();
    if (!msg) { showToast('Please enter a message.', 'warning'); return; }

    try {
        await api.post(`/support/tickets/${ticketId}/reply`, { message: msg });
        showToast('Reply sent to customer!', 'success');
        document.querySelector('.modal-overlay')?.remove();
        openAdminTicketModal(ticketId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function updateAdminTicketStatus(ticketId) {
    const newStatus = document.getElementById('ticket-new-status')?.value;
    try {
        await api.put(`/support/tickets/${ticketId}/status`, { status: newStatus });
        showToast(`Ticket status updated to ${newStatus}!`, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminSupportTickets();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** ─── ADMIN PAYMENTS & CASH AUDIT REPORT ───────────────────── */

async function renderAdminPaymentsReport() {
    showLoading();
    try {
        const report = await api.get('/bills/payments-report');
        const summary = report.summary || {};
        const payments = report.payments || [];
        const staffCash = summary.cash_by_staff || [];

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="page-title">💵 Cash & Payments Audit Report</div>
                            <div class="page-subtitle">Track in-person physical cash collections by staff and online UPI settlements</div>
                        </div>
                        <button class="btn btn-outline btn-sm" onclick="router.navigate('/admin/bills')">← Back to Bills</button>
                    </div>
                </div>

                <!-- Financial Metrics -->
                <div class="stats-grid">
                    <div class="stat-card" style="border-left:4px solid #10b981">
                        <div class="stat-icon">💵</div>
                        <div class="stat-value" style="color:#10b981">${formatCurrency(summary.total_cash_collected || 0)}</div>
                        <div class="stat-label">Total Cash Collected</div>
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">Collected by technicians in person</div>
                    </div>
                    <div class="stat-card" style="border-left:4px solid #38bdf8">
                        <div class="stat-icon">⚡</div>
                        <div class="stat-value" style="color:#38bdf8">${formatCurrency(summary.total_upi_collected || 0)}</div>
                        <div class="stat-label">Total UPI / Online Paid</div>
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">Verified online transactions</div>
                    </div>
                    <div class="stat-card" style="border-left:4px solid #eab308">
                        <div class="stat-icon">⏳</div>
                        <div class="stat-value" style="color:#eab308">${formatCurrency(summary.total_pending_verification || 0)}</div>
                        <div class="stat-label">Pending Verification</div>
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">Requires admin approval</div>
                    </div>
                    <div class="stat-card" style="border-left:4px solid var(--primary)">
                        <div class="stat-icon">💰</div>
                        <div class="stat-value text-primary-color">${formatCurrency(summary.total_revenue || 0)}</div>
                        <div class="stat-label">Gross Settled Revenue</div>
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">Cash + Verified Online</div>
                    </div>
                </div>

                <!-- Cash Handover by Staff -->
                <div class="card" style="margin-bottom:24px">
                    <div class="chart-title" style="margin-bottom:12px">👨‍🔧 Physical Cash Collected by Technicians</div>
                    ${staffCash.length === 0 ? `
                        <div class="text-muted" style="font-size:0.85rem">No cash collections recorded yet.</div>
                    ` : `
                        <div class="table-container">
                            <table>
                                <thead><tr><th>Technician</th><th>Total Cash Collected</th><th>Transactions Count</th><th>Audit Status</th></tr></thead>
                                <tbody>
                                    ${staffCash.map(sc => `
                                        <tr>
                                            <td style="font-weight:600">${sc.staff_name} (ID: #${sc.staff_id})</td>
                                            <td style="font-weight:700;color:#10b981;font-size:1.05rem">${formatCurrency(sc.total_collected)}</td>
                                            <td><span class="badge badge-assigned">${sc.payment_count} payment(s)</span></td>
                                            <td><span class="badge badge-completed">Verified & Documented</span></td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `}
                </div>

                <!-- All Payments Log -->
                <div class="card">
                    <div class="chart-title" style="margin-bottom:12px">📋 Detailed Payment Transactions History</div>
                    ${payments.length === 0 ? `
                        <div class="text-muted" style="font-size:0.85rem">No transactions recorded yet.</div>
                    ` : `
                        <div class="table-container">
                            <table>
                                <thead><tr><th>Date</th><th>Bill #</th><th>Customer</th><th>Amount</th><th>Method</th><th>Collected By</th><th>Verified By</th><th>Reference / UTR</th><th>Status</th></tr></thead>
                                <tbody>
                                    ${payments.map(p => `
                                        <tr>
                                            <td style="font-size:0.78rem;color:var(--text-muted)">${formatDate(p.paid_at)}</td>
                                            <td class="font-mono" style="font-weight:600">${p.bill_number}</td>
                                            <td>
                                                <div style="font-weight:500">${p.customer_name}</div>
                                                <div style="font-size:0.75rem;color:var(--text-muted)">${p.customer_phone || ''}</div>
                                            </td>
                                            <td style="font-weight:700">${formatCurrency(p.amount)}</td>
                                            <td><span class="badge ${p.payment_method === 'Cash' ? 'badge-completed' : 'badge-assigned'}">${p.payment_method}</span></td>
                                            <td style="font-size:0.85rem">${p.collected_by_name || (p.payment_method === 'Cash' ? 'Shop Admin' : 'Online / Customer')}</td>
                                            <td style="font-size:0.85rem">${p.verified_by_name || (p.status === 'Confirmed' ? 'Auto/Admin' : 'Pending')}</td>
                                            <td class="font-mono" style="font-size:0.75rem">${p.transaction_id || '—'}</td>
                                            <td><span class="badge ${p.status === 'Confirmed' ? 'badge-completed' : p.status === 'Pending' ? 'badge-diagnosing' : 'badge-cancelled'}">${p.status}</span></td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `}
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** ─── ADMIN CUSTOMER MANAGEMENT ────────────────────────────────── */
async function renderAdminCustomers() {
    showLoading();
    try {
        const customers = await api.get('/auth/customers').catch(() => api.get('/auth/users').then(users => users.filter(u => u.role === 'customer')));
        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="page-title">👤 Customer Management</div>
                            <div class="page-subtitle">${customers.length} registered customers</div>
                        </div>
                        <div class="flex gap-2">
                            <div class="search-bar" style="max-width:300px">
                                <span class="search-icon">🔍</span>
                                <input type="text" placeholder="Search customers..." oninput="filterTable('cust-tbody', this.value)">
                            </div>
                        </div>
                    </div>
                </div>
                <div class="table-container">
                    <table>
                        <thead><tr>
                            <th>Customer</th><th>Contact</th><th>Address</th><th>Joined</th><th>Auth</th><th>Status</th><th>Actions</th>
                        </tr></thead>
                        <tbody id="cust-tbody">
                            ${customers.map(c => `
                                <tr style="${c.is_active === 0 ? 'opacity:0.6' : ''}">
                                    <td>
                                        <div style="font-weight:600">${c.name}</div>
                                        <div style="font-size:0.75rem;color:var(--text-muted)">${c.email}</div>
                                    </td>
                                    <td style="font-size:0.85rem">${c.phone || '—'}</td>
                                    <td style="font-size:0.82rem">${[c.address, c.landmark, c.pincode].filter(Boolean).join(', ') || '—'}</td>
                                    <td style="font-size:0.78rem;color:var(--text-muted)">${formatDate(c.created_at)}</td>
                                    <td><span class="badge badge-assigned">${c.auth_provider || 'email'}</span></td>
                                    <td>
                                        <span class="badge ${c.is_active !== 0 ? 'badge-completed' : 'badge-cancelled'}">
                                            ${c.is_active !== 0 ? 'Active' : 'Inactive'}
                                        </span>
                                    </td>
                                    <td>
                                        <div class="flex gap-1">
                                            <button class="btn btn-outline btn-sm" onclick="openEditCustomerModal(${c.id},'${(c.name||'').replace(/'/g,'`')}','${c.email}','${c.phone||''}','${(c.address||'').replace(/'/g,'`')}','${(c.landmark||'').replace(/'/g,'`')}','${c.pincode||''}',${c.is_active !== 0 ? 1 : 0})">✏️ Edit</button>
                                            <button class="btn btn-outline btn-sm text-danger" style="border-color:var(--danger)" onclick="deleteCustomer(${c.id}, '${(c.name||'').replace(/'/g,'`')}')">🗑️</button>
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `);
    } catch(e) { showToast(e.message, 'error'); }
}

async function deleteCustomer(userId, name) {
    if (!confirm(`Are you sure you want to deactivate/remove customer '${name}'?`)) return;
    try {
        const res = await api.delete(`/auth/users/${userId}`);
        showToast(res.message || 'Customer removed successfully', 'success');
        renderAdminCustomers();
    } catch(e) {
        showToast(e.message, 'error');
    }
}

function filterTable(tbodyId, query) {
    document.querySelectorAll('#' + tbodyId + ' tr').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(query.toLowerCase()) ? '' : 'none';
    });
}

function openEditCustomerModal(id, name, email, phone, address, landmark, pincode, isActive) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">✏️ Edit Customer</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-row">
            <div class="form-group"><label class="form-label">Full Name</label>
                <input class="form-control" id="ec-name" value="${name}"></div>
            <div class="form-group"><label class="form-label">Phone</label>
                <input class="form-control" id="ec-phone" value="${phone}"></div>
        </div>
        <div class="form-group"><label class="form-label">Email</label>
            <input type="email" class="form-control" id="ec-email" value="${email}"></div>
        <div class="form-row">
            <div class="form-group"><label class="form-label">Address</label>
                <input class="form-control" id="ec-address" value="${address}"></div>
            <div class="form-group"><label class="form-label">Landmark</label>
                <input class="form-control" id="ec-landmark" value="${landmark}"></div>
        </div>
        <div class="form-row">
            <div class="form-group"><label class="form-label">Pincode</label>
                <input class="form-control" id="ec-pincode" value="${pincode}" maxlength="6"></div>
            <div class="form-group"><label class="form-label">Status</label>
                <select class="form-control" id="ec-active">
                    <option value="1" ${isActive ? 'selected' : ''}>Active</option>
                    <option value="0" ${!isActive ? 'selected' : ''}>Inactive</option>
                </select></div>
        </div>
        <button class="btn btn-primary w-full" onclick="submitEditCustomer(${id})">Save Changes</button>
    `);
}
async function submitEditCustomer(userId) {
    try {
        await api.put('/auth/users/' + userId, {
            name: document.getElementById('ec-name').value,
            email: document.getElementById('ec-email').value,
            phone: document.getElementById('ec-phone').value,
            address: document.getElementById('ec-address').value,
            landmark: document.getElementById('ec-landmark').value,
            pincode: document.getElementById('ec-pincode').value,
            is_active: parseInt(document.getElementById('ec-active').value)
        });
        showToast('Customer updated!', 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminCustomers();
    } catch(e) { showToast(e.message, 'error'); }
}

/** ─── ADMIN PER-ITEM WARRANTY ────────────────────────────────── */
function openItemWarrantyModal(jobId, itemName, deviceType) {
    const warrantyOptions = [
        {label: 'No Warranty', days: 0},
        {label: '7 Days', days: 7},
        {label: '15 Days', days: 15},
        {label: '30 Days', days: 30},
        {label: '3 Months', days: 90},
        {label: '6 Months', days: 180},
        {label: '1 Year', days: 365},
    ];
    showModal(`
        <div class="modal-header">
            <span class="modal-title">🛡️ Warranty: ${itemName}</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="padding:10px;background:rgba(249,115,22,0.08);border:1px solid rgba(249,115,22,0.2);border-radius:var(--radius-sm);margin-bottom:14px;font-size:0.85rem">
            Set individual warranty for <b>${itemName}</b>. This is independent of other items in the same request.
        </div>
        <div class="form-group">
            <label class="form-label">Warranty Duration <span class="text-danger">*</span></label>
            <select class="form-control" id="iw-type" onchange="updateWarrantyDays(this)">
                ${warrantyOptions.map(o => `<option value="${o.days}" data-label="${o.label}">${o.label}</option>`).join('')}
                <option value="custom" data-label="Custom">Custom Duration</option>
            </select>
        </div>
        <div class="form-group" id="iw-custom-box" style="display:none">
            <label class="form-label">Custom Days</label>
            <input type="number" class="form-control" id="iw-custom-days" placeholder="e.g. 45" min="1">
        </div>
        <div class="form-group">
            <label class="form-label">Covered Issues</label>
            <input class="form-control" id="iw-covered" value="Covers parts replaced and workmanship.">
        </div>
        <div class="form-group">
            <label class="form-label">Excluded Issues</label>
            <input class="form-control" id="iw-excluded" value="Physical damage, water damage, misuse, unauthorized repair excluded.">
        </div>
        <input type="hidden" id="iw-job-id" value="${jobId}">
        <input type="hidden" id="iw-item-name" value="${itemName}">
        <input type="hidden" id="iw-device-type" value="${deviceType || ''}">
        <button class="btn btn-primary w-full" onclick="submitItemWarranty()">Set Warranty</button>
    `);
}

function updateWarrantyDays(sel) {
    const box = document.getElementById('iw-custom-box');
    if (box) box.style.display = sel.value === 'custom' ? 'block' : 'none';
}

async function submitItemWarranty() {
    const jobId = parseInt(document.getElementById('iw-job-id').value);
    const itemName = document.getElementById('iw-item-name').value;
    const deviceType = document.getElementById('iw-device-type').value;
    const typeEl = document.getElementById('iw-type');
    const selectedOpt = typeEl.options[typeEl.selectedIndex];
    let days = parseInt(typeEl.value) || 0;
    let warrantyLabel = selectedOpt.getAttribute('data-label') || 'No Warranty';
    if (typeEl.value === 'custom') {
        days = parseInt(document.getElementById('iw-custom-days').value) || 0;
        warrantyLabel = days > 0 ? days + ' Days (Custom)' : 'No Warranty';
    }
    const covered = document.getElementById('iw-covered').value;
    const excluded = document.getElementById('iw-excluded').value;
    try {
        const res = await api.post('/warranties/item', {
            repair_job_id: jobId,
            item_name: itemName,
            device_type: deviceType,
            warranty_type: warrantyLabel,
            duration_days: days,
            covered_terms: covered,
            excluded_terms: excluded
        });
        showToast(res.message, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminRepairDetail(jobId);
    } catch(e) { showToast(e.message, 'error'); }
}

/** ─── OFFER EDIT MODAL ─────────────────────────────────────── */
async function openEditOfferModal(offerId) {
    showLoading();
    try {
        const offers = await api.get('/bills/offers');
        const o = offers.find(x => x.id === offerId);
        if (!o) { showToast('Offer not found', 'error'); return; }
        
        const users = await api.get('/auth/users');
        const customers = users.filter(u => u.role === 'customer');
        
        showModal(`
            <div class="modal-header">
                <span class="modal-title">✏️ Edit Offer: ${o.code}</span>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            <div class="form-row">
                <div class="form-group"><label class="form-label">Coupon Code *</label>
                    <input class="form-control" id="eo-code" value="${o.code}" style="text-transform:uppercase;font-weight:700"></div>
                <div class="form-group"><label class="form-label">Offer Title *</label>
                    <input class="form-control" id="eo-title" value="${o.title || ''}"></div>
            </div>
            <div class="form-group"><label class="form-label">Description</label>
                <input class="form-control" id="eo-desc" value="${o.description || ''}"></div>
            <div class="form-row">
                <div class="form-group"><label class="form-label">Discount Type</label>
                    <select class="form-control" id="eo-type">
                        <option value="percentage" ${o.discount_type === 'percentage' ? 'selected' : ''}>Percentage (%)</option>
                        <option value="flat" ${o.discount_type === 'flat' ? 'selected' : ''}>Flat Amount (₹)</option>
                    </select></div>
                <div class="form-group"><label class="form-label">Discount Value *</label>
                    <input type="number" class="form-control" id="eo-val" value="${o.discount_value || ''}"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label class="form-label">Min Bill Amount (₹)</label>
                    <input type="number" class="form-control" id="eo-min" value="${o.min_bill_amount || 0}"></div>
                <div class="form-group"><label class="form-label">Max Discount Cap (₹)</label>
                    <input type="number" class="form-control" id="eo-maxd" value="${o.max_discount || ''}"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label class="form-label">Valid From</label>
                    <input type="date" class="form-control" id="eo-from" value="${o.valid_from || ''}"></div>
                <div class="form-group"><label class="form-label">Valid Until (Expiry)</label>
                    <input type="date" class="form-control" id="eo-until" value="${o.valid_until || ''}"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label class="form-label">Total Usage Limit</label>
                    <input type="number" class="form-control" id="eo-ulimit" value="${o.usage_limit || ''}" placeholder="Leave blank = unlimited"></div>
                <div class="form-group"><label class="form-label">Per-Customer Limit</label>
                    <input type="number" class="form-control" id="eo-pclimit" value="${o.per_customer_limit || 1}" min="1"></div>
            </div>
            <div class="form-group"><label class="form-label">Target Customer (leave blank = all)</label>
                <select class="form-control" id="eo-target">
                    <option value="">🎉 All Customers</option>
                    ${customers.map(c => `<option value="${c.id}" ${o.target_customer_id === c.id ? 'selected' : ''}>👤 ${c.name} (${c.email})</option>`).join('')}
                </select></div>
            <button class="btn btn-primary w-full" style="margin-top:10px" onclick="submitEditOffer(${offerId})">Save Changes</button>
        `);
    } catch(e) { showToast(e.message, 'error'); }
}

async function submitEditOffer(offerId) {
    const code = document.getElementById('eo-code')?.value.trim().toUpperCase();
    const title = document.getElementById('eo-title')?.value.trim();
    const val = parseFloat(document.getElementById('eo-val')?.value || 0);
    if (!code || !title || val <= 0) { showToast('Please fill required fields.', 'warning'); return; }
    try {
        await api.put('/bills/offers/' + offerId, {
            code, title,
            description: document.getElementById('eo-desc')?.value || null,
            discount_type: document.getElementById('eo-type')?.value,
            discount_value: val,
            min_bill_amount: parseFloat(document.getElementById('eo-min')?.value || 0),
            max_discount: parseFloat(document.getElementById('eo-maxd')?.value) || null,
            valid_from: document.getElementById('eo-from')?.value || null,
            valid_until: document.getElementById('eo-until')?.value || null,
            usage_limit: parseInt(document.getElementById('eo-ulimit')?.value) || null,
            per_customer_limit: parseInt(document.getElementById('eo-pclimit')?.value) || 1,
            target_customer_id: parseInt(document.getElementById('eo-target')?.value) || null
        });
        showToast('Offer updated!', 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminOffers();
    } catch(e) { showToast(e.message, 'error'); }
}
