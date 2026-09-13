/**
 * Mistri Staff Views
 * Job list, job detail with status update and parts management
 */

async function renderStaffDashboard() {
    showLoading();
    try {
        const jobs = await api.get('/repairs/');
        const user = api.getUser();

        const activeJobs = jobs.filter(j => !['Delivered'].includes(j.status));
        const completedJobs = jobs.filter(j => ['Completed', 'Delivered'].includes(j.status));

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="page-title">👨‍🔧 My Jobs — ${user.name}</div>
                    <div class="page-subtitle">${jobs.length} assigned jobs · ${activeJobs.length} active</div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon">🔧</div>
                        <div class="stat-value">${jobs.length}</div>
                        <div class="stat-label">Total Assigned</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">⏳</div>
                        <div class="stat-value">${activeJobs.length}</div>
                        <div class="stat-label">Active Jobs</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">✅</div>
                        <div class="stat-value">${completedJobs.length}</div>
                        <div class="stat-label">Completed</div>
                    </div>
                </div>

                ${activeJobs.length > 0 ? `
                    <h2 style="margin-bottom:16px;font-size:1rem;font-weight:600">🔴 Active Jobs</h2>
                    <div class="dashboard-grid" style="margin-bottom:28px">
                        ${activeJobs.map(job => renderStaffJobCard(job)).join('')}
                    </div>
                ` : ''}

                ${completedJobs.length > 0 ? `
                    <h2 style="margin-bottom:16px;font-size:1rem;font-weight:600">✅ Completed Jobs</h2>
                    <div class="dashboard-grid">
                        ${completedJobs.map(job => renderStaffJobCard(job)).join('')}
                    </div>
                ` : ''}

                ${jobs.length === 0 ? `
                    <div class="empty-state card">
                        <div class="empty-state-icon">📋</div>
                        <div class="empty-state-title">No jobs assigned yet</div>
                        <div class="text-muted">The admin will assign jobs to you shortly.</div>
                    </div>
                ` : ''}
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function renderStaffJobCard(job) {
    const priorityColors = { Low: '#27D67B', Normal: '#42AAFF', High: '#FFB547', Urgent: '#FF4D4D' };
    const pColor = priorityColors[job.priority || 'Normal'] || '#42AAFF';
    return `
        <div class="repair-card" onclick="renderStaffJobDetail(${job.id})">
            <div class="flex justify-between items-center mb-2">
                <span class="repair-card-id">${job.repair_id}</span>
                <div class="flex gap-2 items-center">
                    ${job.priority && job.priority !== 'Normal' ? `<span class="badge" style="color:${pColor};background:${pColor}22">${job.priority}</span>` : ''}
                    ${statusBadge(job.status)}
                </div>
            </div>
            <div class="repair-card-device">${job.brand} ${job.model}</div>
            <div class="repair-card-problem">${job.problem_description}</div>
            <div class="repair-card-footer">
                <div style="font-size:0.78rem;color:var(--text-muted)">Customer: ${job.customer_name || '—'}</div>
                <div class="repair-cost">${job.estimated_cost ? formatCurrency(job.estimated_cost) : '—'}</div>
            </div>
        </div>
    `;
}

async function renderStaffJobDetail(jobId) {
    showLoading();
    try {
        const [job, inventory] = await Promise.all([
            api.get(`/repairs/${jobId}`),
            api.get('/inventory/')
        ]);
        const statuses = ['Assigned', 'Diagnosing', 'Approved', 'Repairing', 'Ready', 'Completed', 'On Hold'];
        const partsUsed = job.parts_used ? JSON.parse(job.parts_used) : [];
        const photos = await api.get(`/repairs/${jobId}/photos`).catch(() => []);

        setContent(`
            <div class="page" style="max-width:800px;margin:0 auto">
                <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">
                    <button class="btn btn-outline btn-sm" onclick="router.navigate('/staff')">← Back to Jobs</button>
                    ${statusBadge(job.status)}
                </div>

                <!-- Device Card & Customer Call -->
                <div class="card" style="margin-bottom:16px;border-left:4px solid var(--primary)">
                    <div class="flex justify-between items-start flex-wrap gap-2">
                        <div>
                            <div class="font-mono text-primary-color" style="font-size:1.1rem;font-weight:700">${job.repair_id}</div>
                            <h2 style="font-size:1.3rem;margin:4px 0">${job.brand} ${job.model}</h2>
                            <div class="text-muted" style="font-size:0.85rem">${job.device_type} · Priority: <b>${job.priority || 'Normal'}</b></div>
                        </div>
                        ${job.customer_phone ? `
                            <a href="tel:${job.customer_phone}" class="btn btn-outline btn-sm" style="display:flex;align-items:center;gap:6px;text-decoration:none">
                                📞 Call Customer (${job.customer_name})
                            </a>
                        ` : ''}
                    </div>
                    <div style="margin-top:12px;padding:8px 12px;background:var(--bg-input);border-radius:var(--radius-sm);font-size:0.85rem">
                        <b>Reported Problem:</b> ${job.problem_description}
                    </div>
                </div>

                <!-- Unified 1-Click Repair Workflow -->
                <div class="card" style="margin-bottom:16px">
                    <div class="chart-title" style="margin-bottom:14px">⚡ Fast Repair Actions</div>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label" style="font-weight:600">Update Status</label>
                            <select class="form-control" id="job-status" style="font-size:1rem;height:44px">
                                ${statuses.map(s => `<option value="${s}" ${s === job.status ? 'selected' : ''}>${getStatusIcon(s)} ${s}</option>`).join('')}
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label" style="font-weight:600">Final / Actual Cost (₹)</label>
                            <input type="number" class="form-control" id="job-cost" value="${job.actual_cost || ''}" placeholder="0" style="font-size:1rem;height:44px">
                        </div>
                    </div>

                    <div class="form-group">
                        <label class="form-label" style="font-weight:600">Technician Progress Note</label>
                        <textarea class="form-control" id="job-notes" rows="2" placeholder="e.g. Coil replaced, testing motor current...">${job.technician_notes || ''}</textarea>
                    </div>

                    <button class="btn btn-primary w-full" style="height:46px;font-size:1rem;font-weight:600" onclick="staffUpdateStatus(${jobId})">
                        💾 Update Status & Save Notes
                    </button>
                </div>

                <!-- Atomic Parts Consumption -->
                <div class="card" style="margin-bottom:16px">
                    <div class="chart-title" style="margin-bottom:12px">🔩 Parts Consumption (Auto-deducts Stock)</div>
                    <div id="parts-list">
                        ${partsUsed.length === 0 ? '<div class="text-muted" style="font-size:0.85rem">No spare parts charged to this repair yet.</div>' : ''}
                        ${partsUsed.map((p, i) => `
                            <div class="flex justify-between items-center" style="padding:10px;background:var(--bg-input);border-radius:var(--radius-sm);margin-bottom:8px">
                                <div>
                                    <div style="font-weight:600">${p.part_name}</div>
                                    <div style="font-size:0.8rem;color:var(--text-muted)">Qty: ${p.quantity} × ${formatCurrency(p.unit_price)}</div>
                                </div>
                                <div style="font-weight:700;color:var(--primary)">${formatCurrency(p.quantity * p.unit_price)}</div>
                            </div>
                        `).join('')}
                    </div>

                    <div style="margin-top:14px;padding:12px;background:var(--surface-2);border-radius:var(--radius-sm);border:1px solid var(--border)">
                        <div style="font-size:0.85rem;font-weight:700;margin-bottom:8px">Charge Part from Inventory</div>
                        <div class="form-row">
                            <div class="form-group">
                                <select class="form-control" id="part-select" style="height:42px">
                                    <option value="">Select available part...</option>
                                    ${inventory.map(p => `<option value="${p.id}" ${p.quantity <= 0 ? 'disabled' : ''}>${p.part_name} (${p.quantity} in stock) — ${formatCurrency(p.unit_price)}</option>`).join('')}
                                </select>
                            </div>
                            <div class="form-group" style="max-width:110px">
                                <input type="number" class="form-control" id="part-qty" placeholder="Qty" min="1" value="1" style="height:42px">
                            </div>
                        </div>
                        <button class="btn btn-outline btn-sm w-full" onclick="addPartToJobAtomic(${jobId})">
                            ➕ Deduct Stock & Add Part
                        </button>
                    </div>
                </div>

                <!-- Staged Photo Upload (Before / During / After) -->
                <div class="card" style="margin-bottom:16px">
                    <div class="chart-title" style="margin-bottom:12px">📸 Upload Repair Evidence Photo</div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Photo Stage</label>
                            <select class="form-control" id="photo-stage" style="height:42px">
                                <option value="during">During Repair (Work in Progress)</option>
                                <option value="after">After Repair (Completed Condition)</option>
                                <option value="before">Before Repair (Intake Condition)</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Select Photo</label>
                            <input type="file" class="form-control" id="stage-photo-file" accept="image/*" style="height:42px;padding:6px">
                        </div>
                    </div>
                    <div class="form-group">
                        <input type="text" class="form-control" id="photo-caption" placeholder="Caption (e.g. New bearing installed)">
                    </div>
                    <button class="btn btn-outline btn-sm w-full" onclick="uploadStaffPhoto(${jobId})" id="upload-photo-btn">
                        📤 Upload Staged Photo
                    </button>

                    ${photos && photos.length > 0 ? `
                        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(130px, 1fr));gap:10px;margin-top:14px">
                            ${photos.map(p => `
                                <div style="border:1px solid var(--border);border-radius:var(--radius-sm);overflow:hidden">
                                    <div style="padding:2px 6px;font-size:0.68rem;font-weight:700;background:var(--surface-2);color:var(--primary)">${p.photo_stage}</div>
                                    <img src="${p.photo_url}" style="width:100%;height:90px;object-fit:cover">
                                    <div style="font-size:0.7rem;padding:4px;color:var(--text-muted)">${p.caption || ''}</div>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>

                <div class="flex gap-2">
                    <button class="btn btn-outline" onclick="showQRCode('${job.repair_id}')">📱 QR Code</button>
                    <button class="btn btn-outline btn-sm" onclick="router.navigate('/staff')">Done</button>
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
        router.navigate('/staff');
    }
}

async function staffUpdateStatus(jobId) {
    const status = document.getElementById('job-status').value;
    const cost = document.getElementById('job-cost').value;
    const notes = document.getElementById('job-notes').value;
    try {
        await api.put(`/repairs/${jobId}/status`, {
            status,
            actual_cost: cost ? parseFloat(cost) : null,
            technician_notes: notes || null,
            note: notes || `Technician moved status to ${status}`
        });
        showToast('Job updated successfully! 🎉', 'success');
        renderStaffJobDetail(jobId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function addPartToJobAtomic(jobId) {
    const select = document.getElementById('part-select');
    const partId = select.value;
    if (!partId) { showToast('Please select a part first', 'warning'); return; }
    const qty = parseInt(document.getElementById('part-qty').value || 1);

    try {
        const res = await api.post(`/repairs/${jobId}/add-part`, { part_id: parseInt(partId), quantity: qty });
        showToast(res.message, 'success');
        renderStaffJobDetail(jobId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function uploadStaffPhoto(jobId) {
    const fileInput = document.getElementById('stage-photo-file');
    if (!fileInput.files || !fileInput.files[0]) {
        showToast('Please choose a photo file to upload', 'warning');
        return;
    }
    const stage = document.getElementById('photo-stage').value;
    const caption = document.getElementById('photo-caption').value;
    const btn = document.getElementById('upload-photo-btn');
    btn.innerHTML = 'Uploading...';
    btn.disabled = true;

    try {
        const form = new FormData();
        form.append('stage', stage);
        form.append('caption', caption);
        form.append('photo', fileInput.files[0]);

        await api.post(`/repairs/${jobId}/photos`, form);
        showToast(`${stage.toUpperCase()} photo uploaded!`, 'success');
        renderStaffJobDetail(jobId);
    } catch (e) {
        showToast(e.message, 'error');
        btn.innerHTML = '📤 Upload Staged Photo';
        btn.disabled = false;
    }
}
        showToast('Part added!', 'success');
        renderStaffJobDetail(jobId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** Staff Inventory View (read-only) */
async function renderStaffInventory() {
    showLoading();
    try {
        const items = await api.get('/inventory/');
        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="page-title">📦 Parts Inventory</div>
                    <div class="page-subtitle">Read-only view of available parts</div>
                </div>
                <div class="table-container">
                    <table>
                        <thead><tr><th>Part</th><th>Code</th><th>Category</th><th>Stock</th><th>Price</th></tr></thead>
                        <tbody>
                            ${items.map(item => `
                                <tr>
                                    <td style="font-weight:500">${item.part_name}</td>
                                    <td class="font-mono" style="font-size:0.8rem">${item.part_code}</td>
                                    <td>${item.category}</td>
                                    <td>
                                        <span class="${item.low_stock ? 'text-danger' : 'text-success'}" style="font-weight:600">${item.quantity}</span>
                                        ${item.low_stock ? ' ⚠️' : ''}
                                    </td>
                                    <td>${formatCurrency(item.unit_price)}</td>
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
