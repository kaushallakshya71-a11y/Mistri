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
                            <a href="/api/reports/export/csv?type=repairs" class="btn btn-outline btn-sm">⬇ Export CSV</a>
                        </div>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon">🔧</div>
                        <div class="stat-value">${stats.total}</div>
                        <div class="stat-label">Total Repairs</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">⏳</div>
                        <div class="stat-value">${stats.pending}</div>
                        <div class="stat-label">Pending</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">✅</div>
                        <div class="stat-value">${stats.completed}</div>
                        <div class="stat-label">Completed</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">💰</div>
                        <div class="stat-value">${formatCurrency(stats.revenue)}</div>
                        <div class="stat-label">Total Revenue</div>
                    </div>
                    ${stats.low_stock_alerts > 0 ? `
                        <div class="stat-card" style="border-color:rgba(255,77,77,0.4)">
                            <div class="stat-icon">⚠️</div>
                            <div class="stat-value text-danger">${stats.low_stock_alerts}</div>
                            <div class="stat-label">Low Stock Alerts</div>
                            <div class="stat-change down">Action required</div>
                        </div>
                    ` : ''}
                </div>

                <div class="charts-grid">
                    <div class="chart-card">
                        <div class="chart-title">📈 Revenue (Last 7 Days)</div>
                        <div class="chart-wrapper">
                            <canvas id="revenue-chart"></canvas>
                        </div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-title">🔄 Repair Status</div>
                        <div class="chart-wrapper">
                            <canvas id="status-chart"></canvas>
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

        // Render charts
        renderRevenueChart(stats.daily_revenue);
        renderStatusChart(stats.status_distribution);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function renderRevenueChart(data) {
    const ctx = document.getElementById('revenue-chart')?.getContext('2d');
    if (!ctx) return;
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.day || d.period || ''),
            datasets: [{
                label: 'Revenue (₹)',
                data: data.map(d => d.revenue || 0),
                borderColor: '#6C63FF',
                backgroundColor: 'rgba(108,99,255,0.1)',
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#6C63FF',
                pointRadius: 4,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#666', font: { size: 10 } } },
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#666', font: { size: 10 }, callback: v => '₹' + v } }
            }
        }
    });
}

function renderStatusChart(data) {
    const ctx = document.getElementById('status-chart')?.getContext('2d');
    if (!ctx || !data.length) return;
    const colors = { Received: '#42AAFF', Diagnosing: '#FFB547', Repairing: '#6C63FF', Completed: '#27D67B', Delivered: '#1fba6b' };
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.map(d => d.status),
            datasets: [{
                data: data.map(d => d.count),
                backgroundColor: data.map(d => colors[d.status] || '#999'),
                borderWidth: 0, hoverOffset: 6,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { color: '#aaa', font: { size: 11 }, padding: 12 } } }
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
                                            <button class="btn btn-outline btn-sm" onclick='openUpdateStatusModal(${j.id}, "${j.status}", ${JSON.stringify(technicians)})'>✏️ Update</button>
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
            tax_rate: parseFloat(document.getElementById('bill-tax').value || 0)
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
                                            <button class="btn btn-outline btn-sm" onclick="openRestockModal(${item.id},'${item.part_name}','${item.supplier || ''}',10)">📥 Restock</button>
                                            <button class="btn btn-outline btn-sm" onclick="openStockModal(${item.id},'${item.part_name}',${item.quantity})">⚡ Quick</button>
                                            <button class="btn btn-outline btn-sm" onclick="openEditInventoryModal(${item.id},'${item.part_name}','${item.part_code}','${item.category}',${item.quantity},${item.unit_price},${item.reorder_level},'${item.supplier || ''}')">✏️</button>
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
            item_id: itemId,
            quantity_added: qty,
            unit_cost: cost,
            supplier: supplier || undefined,
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

function openAddItemModal() {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">➕ Add Inventory Item</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Part Name</label>
                <input type="text" class="form-control" id="new-name" placeholder="iPhone 13 Screen">
            </div>
            <div class="form-group">
                <label class="form-label">Part Code</label>
                <input type="text" class="form-control" id="new-code" placeholder="SCR-IP13">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Category</label>
                <select class="form-control" id="new-cat">
                    <option>Screen</option><option>Battery</option><option>Motherboard</option><option>IC</option><option>Misc</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Quantity</label>
                <input type="number" class="form-control" id="new-qty" placeholder="10" min="0">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Unit Price (₹)</label>
                <input type="number" class="form-control" id="new-price" placeholder="1000">
            </div>
            <div class="form-group">
                <label class="form-label">Reorder Level</label>
                <input type="number" class="form-control" id="new-reorder" value="5">
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">Supplier</label>
            <input type="text" class="form-control" id="new-supplier" placeholder="Supplier name">
        </div>
        <button class="btn btn-primary w-full" onclick="submitAddItem()">Add Item</button>
    `);
}

async function submitAddItem() {
    try {
        await api.post('/inventory/', {
            part_name: document.getElementById('new-name').value,
            part_code: document.getElementById('new-code').value,
            category: document.getElementById('new-cat').value,
            compatible_devices: [],
            quantity: parseInt(document.getElementById('new-qty').value || 0),
            unit_price: parseFloat(document.getElementById('new-price').value || 0),
            reorder_level: parseInt(document.getElementById('new-reorder').value || 5),
            supplier: document.getElementById('new-supplier').value
        });
        showToast('Item added to inventory!', 'success');
        document.querySelector('.modal-overlay').remove();
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
                            <a href="/api/reports/export/csv?type=repairs" class="btn btn-outline btn-sm">⬇ Repairs CSV</a>
                            <a href="/api/reports/export/csv?type=payments" class="btn btn-outline btn-sm">⬇ Payments CSV</a>
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
                        <div class="chart-title">Monthly Revenue Trend</div>
                        <div class="chart-wrapper" style="height:280px"><canvas id="monthly-chart"></canvas></div>
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
                    <div class="chart-card">
                        <div class="chart-title">🔧 Revenue by Device Type</div>
                        <div class="chart-wrapper"><canvas id="device-chart"></canvas></div>
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
        renderMonthlyChart(data.revenue_over_time);
        renderDeviceChart(data.device_breakdown);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function renderMonthlyChart(data) {
    const ctx = document.getElementById('monthly-chart')?.getContext('2d');
    if (!ctx) return;
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.period),
            datasets: [{
                label: 'Revenue',
                data: data.map(d => d.revenue),
                backgroundColor: 'rgba(108,99,255,0.7)',
                borderRadius: 6,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { color: '#666' } },
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#666', callback: v => '₹' + v.toLocaleString() } }
            }
        }
    });
}

function renderDeviceChart(data) {
    const ctx = document.getElementById('device-chart')?.getContext('2d');
    if (!ctx || !data.length) return;
    const colors = ['#6C63FF', '#FF6B6B', '#27D67B', '#FFB547'];
    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: data.map(d => d.device_type),
            datasets: [{ data: data.map(d => d.count), backgroundColor: colors, borderWidth: 0 }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { color: '#aaa', font: { size: 11 } } } }
        }
    });
}

/** Admin Staff Management */
async function renderAdminStaff() {
    showLoading();
    try {
        const users = await api.get('/auth/users');
        const staff = users.filter(u => u.role === 'staff');
        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div><div class="page-title">👥 Staff Management</div></div>
                        <button class="btn btn-primary" onclick="openAddStaffModal()">➕ Add Staff</button>
                    </div>
                </div>
                <div class="table-container">
                    <table>
                        <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Role</th><th>Joined</th><th>Action</th></tr></thead>
                        <tbody>
                            ${staff.map(s => `
                                <tr>
                                    <td><div class="flex items-center gap-2">
                                        <div class="user-avatar" style="width:32px;height:32px;font-size:0.8rem">${s.name[0]}</div>
                                        <span style="font-weight:500">${s.name}</span>
                                    </div></td>
                                    <td>${s.email}</td>
                                    <td>${s.phone || '—'}</td>
                                    <td>${statusBadge(s.role)}</td>
                                    <td style="font-size:0.8rem;color:var(--text-muted)">${formatDate(s.created_at)}</td>
                                    <td><button class="btn btn-outline btn-sm" onclick="openEditUserModal(${s.id},'${s.name}','${s.email}','${s.phone || ''}')">✏️ Edit</button></td>
                                </tr >
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

function openAddStaffModal() {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">➕ Add Staff Member</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-group"><label class="form-label">Full Name</label>
            <input type="text" class="form-control" id="staff-name" placeholder="John Doe"></div>
        <div class="form-group"><label class="form-label">Email</label>
            <input type="email" class="form-control" id="staff-email" placeholder="tech@mistri.com"></div>
        <div class="form-group"><label class="form-label">Phone</label>
            <input type="tel" class="form-control" id="staff-phone"></div>
        <div class="form-group"><label class="form-label">Password</label>
            <input type="password" class="form-control" id="staff-pass" placeholder="Min 6 characters"></div>
        <button class="btn btn-primary w-full" onclick="submitAddStaff()">Add Staff</button>
    `);
}

async function submitAddStaff() {
    try {
        await api.post('/auth/staff', {
            name: document.getElementById('staff-name').value,
            email: document.getElementById('staff-email').value,
            phone: document.getElementById('staff-phone').value,
            password: document.getElementById('staff-pass').value
        });
        showToast('Staff member added!', 'success');
        document.querySelector('.modal-overlay').remove();
        renderAdminStaff();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** Admin Bills List */
async function renderAdminBills() {
    showLoading();
    try {
        const bills = await api.get('/bills/');
        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="page-title">💳 Bills & Payments</div>
                </div>
                <div class="table-container">
                    <table>
                        <thead><tr><th>Bill #</th><th>Customer</th><th>Repair ID</th><th>Amount</th><th>Status</th><th>Date</th><th>Action</th></tr></thead>
                        <tbody>
                            ${bills.map(b => `
                                <tr>
                                    <td class="font-mono">${b.bill_number}</td>
                                    <td>${b.customer_name}</td>
                                    <td class="font-mono text-primary-color">${b.repair_id}</td>
                                    <td style="font-weight:600">${formatCurrency(b.total_amount)}</td>
                                    <td>${statusBadge(b.payment_status)}</td>
                                    <td style="font-size:0.8rem">${formatDate(b.created_at)}</td>
                                    <td>
                                        <div class="flex gap-2">
                                            <a href="/api/bills/${b.id}/pdf" target="_blank" class="btn btn-outline btn-sm">⬇ PDF</a>
                                            ${b.payment_status !== 'Paid' ? `<button class="btn btn-success btn-sm" onclick="markPaid(${b.id})">✅ Mark Paid</button>` : ''}
                                            <button class="btn btn-outline btn-sm" onclick="openEditBillModal(${b.id},${b.labour_charge},${b.parts_cost},${b.discount},'${b.payment_status}')">✏️ Edit</button>
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

async function markPaid(billId) {
    try {
        await api.post(`/bills/${billId}/pay`);
        showToast('Payment recorded!', 'success');
        renderAdminBills();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** ─── ADMIN EDIT MODALS ──────────────────────────────── */

// Edit User (staff or customer)
function openEditUserModal(userId, name, email, phone) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">✏️ Edit User</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div class="form-group"><label class="form-label">Full Name</label>
            <input type="text" class="form-control" id="edit-user-name" value="${name}"></div>
        <div class="form-group"><label class="form-label">Email</label>
            <input type="email" class="form-control" id="edit-user-email" value="${email}"></div>
        <div class="form-group"><label class="form-label">Phone</label>
            <input type="tel" class="form-control" id="edit-user-phone" value="${phone}"></div>
        <button class="btn btn-primary w-full" onclick="submitEditUser(${userId})">Save Changes</button>
    `);
}
async function submitEditUser(userId) {
    try {
        await api.put(`/auth/users/${userId}`, {
            name: document.getElementById('edit-user-name').value,
            email: document.getElementById('edit-user-email').value,
            phone: document.getElementById('edit-user-phone').value
        });
        showToast('User updated!', 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderAdminStaff();
    } catch (e) { showToast(e.message, 'error'); }
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
                    ${['Screen', 'Battery', 'Motherboard', 'IC', 'Misc', 'Motor', 'Coil', 'Capacitor', 'Switch', 'Other'].map(c => '<option value="' + c + '"' + (c == cat ? ' selected' : '') + '>' + c + '</option>').join('')}
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
