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
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="page-title">👨‍🔧 My Jobs — ${user.name}</div>
                            <div class="page-subtitle">${jobs.length} assigned jobs · ${activeJobs.length} active</div>
                        </div>
                        <button onclick="logout()" class="btn btn-outline btn-sm" style="color:var(--danger);border-color:rgba(239,68,68,0.4)">🚪 Logout</button>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card animate-scale-in stagger-1">
                        <div class="stat-icon">🔧</div>
                        <div class="stat-value">${jobs.length}</div>
                        <div class="stat-label">Total Assigned</div>
                    </div>
                    <div class="stat-card animate-scale-in stagger-2">
                        <div class="stat-icon">⏳</div>
                        <div class="stat-value">${activeJobs.length}</div>
                        <div class="stat-label">Active Jobs</div>
                    </div>
                    <div class="stat-card animate-scale-in stagger-3">
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
                    <span class="badge" style="background:${job.service_type === 'Home Pickup' ? '#8b5cf622' : '#0ea5e922'};color:${job.service_type === 'Home Pickup' ? '#a78bfa' : '#38bdf8'}">
                        ${job.service_type === 'Home Pickup' ? '🏠 Home Visit' : '🏪 Store'}
                    </span>
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
        const [job, inventory, bills] = await Promise.all([
            api.get(`/repairs/${jobId}`),
            api.get('/inventory/'),
            api.get('/bills/').catch(() => [])
        ]);
        const jobBill = bills.find(b => b.repair_job_id === jobId);
        const statuses = ['Assigned', 'Diagnosing', 'Approved', 'Repairing', 'Ready', 'Completed', 'On Hold'];
        const partsUsed = job.parts_used ? JSON.parse(job.parts_used) : [];
        const photos = await api.get(`/repairs/${jobId}/photos`).catch(() => []);

        setContent(`
            <div class="page" style="max-width:800px;margin:0 auto">
                <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">
                    <button class="btn btn-outline btn-sm" onclick="router.navigate('/staff')">← Back to Jobs</button>
                    <div class="flex gap-2 items-center">
                        <span class="badge" style="background:${job.service_type === 'Home Pickup' ? '#8b5cf622' : '#0ea5e922'};color:${job.service_type === 'Home Pickup' ? '#a78bfa' : '#38bdf8'}">
                            ${job.service_type === 'Home Pickup' ? '🏠 Home Visit' : '🏪 Store Drop-off'}
                        </span>
                        ${statusBadge(job.status)}
                    </div>
                </div>

                ${job.rejection_reason ? `
                    <div style="padding:10px 14px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:var(--radius-sm);margin-bottom:16px">
                        <div style="font-weight:700;color:var(--danger)">⚠️ Rejection Notice On Record:</div>
                        <div style="font-size:0.85rem;margin-top:2px">Reason: <b>${job.rejection_reason}</b></div>
                        ${job.rejection_notes ? `<div style="font-size:0.8rem;color:var(--text-muted);margin-top:2px">Notes: ${job.rejection_notes}</div>` : ''}
                    </div>
                ` : ''}

                ${job.status === 'Assigned' ? `
                    <div class="card" style="margin-bottom:16px;border-left:4px solid var(--primary);background:rgba(99,102,241,0.06)">
                        <div class="flex justify-between items-center flex-wrap gap-2">
                            <div>
                                <div style="font-weight:700;color:var(--primary);font-size:1rem">📌 New Assignment Received</div>
                                <div style="font-size:0.82rem;color:var(--text-muted)">Please accept to start diagnosis or reject with reason if unable to service.</div>
                            </div>
                            <div class="flex gap-2">
                                <button class="btn btn-primary btn-sm" onclick="staffAcceptJob(${jobId})">✅ Accept & Start Diagnosis</button>
                                <button class="btn btn-outline btn-sm" style="color:var(--danger);border-color:var(--danger)" onclick="openStaffRejectModal(${jobId})">❌ Reject Job</button>
                            </div>
                        </div>
                    </div>
                ` : ''}

                ${jobBill && jobBill.payment_status !== 'Paid' ? `
                    <div class="card" style="margin-bottom:16px;border-left:4px solid #10b981;background:rgba(16,185,129,0.06)">
                        <div class="flex justify-between items-center flex-wrap gap-2">
                            <div>
                                <div style="font-weight:700;color:#10b981">💵 Collect In-Person Cash Payment</div>
                                <div style="font-size:0.85rem">Bill: <b>${jobBill.bill_number}</b> · Total: <b>${formatCurrency(jobBill.total_amount)}</b> (Status: <b>${jobBill.payment_status}</b>)</div>
                            </div>
                            <button class="btn btn-success btn-sm" onclick="openCollectCashModal(${jobBill.id}, ${jobBill.total_amount}, '${jobBill.bill_number}')">
                                💵 Record Cash Collected
                            </button>
                        </div>
                    </div>
                ` : ''}

                <!-- Customer Location & Dispatch Info -->
                <div class="card" style="margin-bottom:16px;border-left:4px solid ${job.service_type === 'Home Pickup' ? '#8b5cf6' : '#0ea5e9'}">
                    <div class="flex justify-between items-start flex-wrap gap-2">
                        <div>
                            <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;color:var(--text-muted);margin-bottom:4px">
                                Service Mode: <span style="color:${job.service_type === 'Home Pickup' ? '#a78bfa' : '#38bdf8'}">${job.service_type === 'Home Pickup' ? '🏠 Doorstep Visit / Home Pickup' : '🏪 Store Workshop Drop-off'}</span>
                            </div>
                            ${job.service_type === 'Home Pickup' ? `
                                <div style="font-size:1.05rem;font-weight:600;margin:6px 0;color:var(--text-primary)">
                                    📍 ${job.pickup_address || 'Address not specified'}
                                </div>
                                <div class="text-muted" style="font-size:0.8rem">
                                    Customer: <b>${job.customer_name}</b> | Phone: <b>${job.customer_phone || 'N/A'}</b>
                                </div>
                            ` : `
                                <div style="font-size:0.95rem;margin:6px 0;color:var(--text-secondary)">
                                    🏪 Customer will drop-off device at shop workshop.
                                </div>
                                <div class="text-muted" style="font-size:0.8rem">
                                    Customer: <b>${job.customer_name}</b> | Phone: <b>${job.customer_phone || 'N/A'}</b>
                                </div>
                            `}
                        </div>
                        <div class="flex gap-2 flex-wrap">
                            ${job.service_type === 'Home Pickup' && job.pickup_address ? `
                                <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(job.pickup_address)}" target="_blank" class="btn btn-primary btn-sm" style="display:flex;align-items:center;gap:6px;text-decoration:none">
                                    🗺️ Open Google Maps
                                </a>
                            ` : ''}
                            ${job.customer_phone ? `
                                <a href="tel:${job.customer_phone}" class="btn btn-outline btn-sm" style="display:flex;align-items:center;gap:6px;text-decoration:none">
                                    📞 Call Customer
                                </a>
                            ` : ''}
                        </div>
                    </div>
                </div>

                <!-- Device Card -->
                <div class="card" style="margin-bottom:16px;border-left:4px solid var(--primary)">
                    <div class="flex justify-between items-start flex-wrap gap-2">
                        <div>
                            <div class="font-mono text-primary-color" style="font-size:1.1rem;font-weight:700">${job.repair_id}</div>
                            <h2 style="font-size:1.3rem;margin:4px 0">${job.brand} ${job.model}</h2>
                            <div class="text-muted" style="font-size:0.85rem">${job.device_type} · Priority: <b>${job.priority || 'Normal'}</b></div>
                        </div>
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

                    ${!['Completed', 'Delivered', 'Cancelled'].includes(job.status) && job.status !== 'Assigned' ? `
                        <div style="margin-top:12px;display:flex;justify-content:flex-end">
                            <button class="btn btn-outline btn-sm" style="color:var(--danger);border-color:rgba(239,68,68,0.4)" onclick="openStaffRejectModal(${jobId})">
                                ❌ Unable to Complete? Reject / Cancel Job
                            </button>
                        </div>
                    ` : ''}
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

/** ─── STAFF REPAIR ACTIONS: ACCEPT & REJECT ──────────────── */

async function staffAcceptJob(jobId) {
    try {
        await api.post(`/repairs/${jobId}/accept`);
        showToast('Job accepted! Status moved to Diagnosing 🛠️', 'success');
        renderStaffJobDetail(jobId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function openStaffRejectModal(jobId) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title" style="color:var(--danger)">❌ Reject / Cancel Repair Job</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="padding:10px 14px;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);border-radius:var(--radius-sm);margin-bottom:14px;font-size:0.85rem">
            <b>Important:</b> The Admin will be notified immediately to reassign this repair. A valid business reason is mandatory.
        </div>
        <div class="form-group">
            <label class="form-label" style="font-weight:600">Select Rejection Reason <span class="text-danger">*</span></label>
            <select class="form-control" id="reject-reason" style="height:44px" onchange="toggleOtherReasonBox()">
                <option value="">-- Choose reason --</option>
                <option value="Skill mismatch (unfamiliar with this device model/circuit)">Skill mismatch (unfamiliar with this device model/circuit)</option>
                <option value="Required diagnostic tools / equipment unavailable">Required diagnostic tools / equipment unavailable</option>
                <option value="Spare parts out of stock / unavailable">Spare parts out of stock / unavailable</option>
                <option value="Excessive active repair workload">Excessive active repair workload</option>
                <option value="Emergency personal leave">Emergency personal leave</option>
                <option value="Customer location unreachable">Customer location unreachable</option>
                <option value="Other">Other (Requires detailed explanation)</option>
            </select>
        </div>
        <div class="form-group" id="reject-notes-group">
            <label class="form-label" style="font-weight:600">Technician Explanation / Notes <span class="text-danger">*</span></label>
            <textarea class="form-control" id="reject-notes" rows="3" placeholder="Provide honest details to help the admin reassign effectively..."></textarea>
            <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">Min 10 characters required for custom reasons.</div>
        </div>
        <div class="flex gap-2" style="margin-top:16px">
            <button class="btn btn-outline flex-1" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
            <button class="btn btn-danger flex-1" onclick="submitStaffReject(${jobId})">Confirm Rejection</button>
        </div>
    `);
}

function toggleOtherReasonBox() {
    const reason = document.getElementById('reject-reason').value;
    const notesGroup = document.getElementById('reject-notes-group');
    if (reason === 'Other') {
        notesGroup.querySelector('label').innerHTML = 'Detailed Explanation <span class="text-danger">* (Required)</span>';
    } else {
        notesGroup.querySelector('label').innerHTML = 'Technician Explanation / Notes <span style="font-size:0.75rem;color:var(--text-muted)">(Optional)</span>';
    }
}

async function submitStaffReject(jobId) {
    const reason = document.getElementById('reject-reason').value;
    const notes = document.getElementById('reject-notes').value.trim();

    if (!reason) {
        showToast('Please select a valid rejection reason.', 'warning');
        return;
    }
    if (reason === 'Other' && notes.length < 10) {
        showToast('Please provide an explanation of at least 10 characters.', 'warning');
        return;
    }

    try {
        await api.post(`/repairs/${jobId}/reject`, {
            rejection_reason: reason,
            rejection_notes: notes || null
        });
        showToast('Repair rejected. Admin notified for reassignment.', 'info');
        document.querySelector('.modal-overlay')?.remove();
        renderStaffDashboard();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** ─── CASH PAYMENT RECORDING ──────────────────────────── */

function openCollectCashModal(billId, amount, billNumber) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">💵 Collect Cash Payment</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="padding:12px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);border-radius:var(--radius-sm);margin-bottom:14px">
            <div style="font-size:0.85rem;color:var(--text-muted)">Invoice: <b>${billNumber}</b></div>
            <div style="font-size:1.4rem;font-weight:700;color:#10b981;margin:4px 0">${formatCurrency(amount)}</div>
            <div style="font-size:0.8rem;color:var(--text-secondary)">Please collect the exact cash amount from customer before confirming.</div>
        </div>
        <div class="form-group">
            <label class="form-label">Receipt / Collection Notes (Optional)</label>
            <input type="text" class="form-control" id="cash-notes" placeholder="e.g. Paid in 500 notes, customer verified appliance">
        </div>
        <div class="flex gap-2" style="margin-top:16px">
            <button class="btn btn-outline flex-1" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
            <button class="btn btn-success flex-1" onclick="submitCollectCash(${billId})">Confirm Cash Collected</button>
        </div>
    `);
}

async function submitCollectCash(billId) {
    const notes = document.getElementById('cash-notes')?.value || '';
    try {
        const res = await api.post(`/bills/${billId}/cash-payment`, { notes });
        showToast('Cash payment recorded successfully! Warranty activated.', 'success');
        document.querySelector('.modal-overlay')?.remove();
        router.navigate('/staff');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

/** ─── STAFF SALARY, LEAVES & TENURE MANAGEMENT ───────── */

async function renderStaffLeavesAndSalary() {
    showLoading();
    try {
        const [summaryRes, leavesRes, bonuses] = await Promise.all([
            api.get('/staff-mgmt/summary'),
            api.get('/staff-mgmt/leaves').catch(() => []),
            api.get('/staff-mgmt/bonuses/' + (api.getUser()?.user_id || api.getUser()?.id)).catch(() => [])
        ]);

        // Handle both Array (when backend returns list) and Object
        const staffData = Array.isArray(summaryRes) ? (summaryRes[0] || {}) : (summaryRes.staff || summaryRes);
        const policy = summaryRes.leave_policy || {
            allowed_leaves_per_month: staffData.allowed_leaves || 4,
            approved_leaves_this_month: staffData.leaves_used || 0,
            unpaid_leaves: staffData.unpaid_leaves || 0,
            salary_deduction_amount: staffData.salary_deduction || 0
        };
        const currentMonth = summaryRes.current_month || new Date().toISOString().slice(0, 7);
        const commitment = summaryRes.commitment || {
            required_months: staffData.minimum_commitment_months || 6,
            months_served: staffData.months_served || 0,
            months_remaining: Math.max(0, (staffData.minimum_commitment_months || 6) - (staffData.months_served || 0)),
            is_satisfied: !!staffData.commitment_completed,
            status: staffData.commitment_completed ? 'Satisfied' : 'In Progress'
        };

        const monthlySalary = staffData.monthly_salary || 0;
        const dailyRate = staffData.daily_rate || (monthlySalary ? Math.round(monthlySalary / 30) : 0);
        const bonusesAmount = staffData.current_month_bonuses || (Array.isArray(bonuses) ? bonuses.reduce((s,b) => s + (b.amount||0), 0) : 0);
        const netPayout = staffData.estimated_final_salary || Math.max(0, monthlySalary - (policy.salary_deduction_amount || 0) + bonusesAmount);
        const leaves = leavesRes || [];

        // Calculate minimum date for 2-day advance notice
        const minDate = new Date();
        minDate.setDate(minDate.getDate() + 2);
        const minDateStr = minDate.toISOString().split('T')[0];

        setContent(`
            <div class="page" style="max-width:960px;margin:0 auto">
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="page-title">💼 My Salary, Leaves & Commitment</div>
                            <div class="page-subtitle">Transparent payroll tracking, 4-leave monthly quota & service agreements</div>
                        </div>
                        <div class="flex gap-2">
                            <button class="btn btn-outline btn-sm" onclick="openResignationModal('${commitment.status}')">📝 Submit Resignation Notice</button>
                        </div>
                    </div>
                </div>

                <!-- Resignation or Termination Alert Banner -->
                ${staffData.resignation_status && staffData.resignation_status !== 'None' ? `
                    <div style="padding:12px 16px;background:rgba(234,179,8,0.1);border:1px solid rgba(234,179,8,0.3);border-radius:var(--radius-sm);margin-bottom:18px">
                        <div style="font-weight:700;color:#eab308">⚠️ Resignation In Progress (${staffData.resignation_status})</div>
                        <div style="font-size:0.85rem;margin-top:2px">Notice Filed: <b>${staffData.resignation_notice_date || 'N/A'}</b> · Proposed Last Date: <b>${staffData.resignation_last_date || 'N/A'}</b></div>
                        <div style="font-size:0.8rem;color:var(--text-muted);margin-top:2px">Reason: ${staffData.resignation_reason || 'N/A'}</div>
                    </div>
                ` : ''}

                ${staffData.termination_effective_date ? `
                    <div style="padding:12px 16px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:var(--radius-sm);margin-bottom:18px">
                        <div style="font-weight:700;color:var(--danger)">🚨 15-Day Exit / Termination Notice Issued</div>
                        <div style="font-size:0.85rem;margin-top:2px">Notice Date: <b>${staffData.termination_notice_date}</b> · Effective Exit Date: <b>${staffData.termination_effective_date}</b></div>
                    </div>
                ` : ''}

                <!-- Key Metrics -->
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon">💰</div>
                        <div class="stat-value">${formatCurrency(monthlySalary)}</div>
                        <div class="stat-label">Monthly Fixed Salary</div>
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">Daily Rate: <b>${formatCurrency(dailyRate)}</b> / day</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">📅</div>
                        <div class="stat-value">${policy.approved_leaves_this_month} / ${policy.allowed_leaves_per_month}</div>
                        <div class="stat-label">Leaves Taken (${currentMonth})</div>
                        <div style="font-size:0.75rem;color:${policy.unpaid_leaves > 0 ? 'var(--danger)' : 'var(--success)'};margin-top:4px">
                            ${policy.unpaid_leaves > 0 ? `⚠️ ${policy.unpaid_leaves} unpaid leaves (Deduction: ${formatCurrency(policy.salary_deduction_amount)})` : `✅ Within 4 allowed paid leaves`}
                        </div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">🎁</div>
                        <div class="stat-value">${formatCurrency(bonusesAmount)}</div>
                        <div class="stat-label">Bonuses This Month</div>
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">${Array.isArray(bonuses) ? bonuses.length : 0} bonus rewards on record</div>
                    </div>
                    <div class="stat-card" style="border-color:rgba(99,102,241,0.3)">
                        <div class="stat-icon">💵</div>
                        <div class="stat-value text-primary-color">${formatCurrency(netPayout)}</div>
                        <div class="stat-label">Estimated Payout (${currentMonth})</div>
                        <div style="font-size:0.72rem;color:var(--text-muted);margin-top:4px">Salary - Leaves + Bonuses</div>
                    </div>
                </div>

                <!-- 6-Month Commitment & Agreement Details -->
                <div class="card" style="margin-bottom:20px;border-left:4px solid var(--primary)">
                    <div class="chart-title" style="margin-bottom:10px">📜 Employment Agreement & Tenure Commitment</div>
                    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:16px;margin-bottom:14px">
                        <div>
                            <div style="font-size:0.78rem;color:var(--text-muted)">Joining Date</div>
                            <div style="font-size:1rem;font-weight:600">${staffData.joining_date || 'Initial System Staff'}</div>
                        </div>
                        <div>
                            <div style="font-size:0.78rem;color:var(--text-muted)">Minimum Commitment</div>
                            <div style="font-size:1rem;font-weight:600">${commitment.required_months} Months (${commitment.months_served} months served)</div>
                        </div>
                        <div>
                            <div style="font-size:0.78rem;color:var(--text-muted)">Tenure Commitment Status</div>
                            <span class="badge ${commitment.is_satisfied ? 'badge-completed' : 'badge-assigned'}" style="font-size:0.85rem">
                                ${commitment.is_satisfied ? '✅ Commitment Satisfied' : `⏳ In Progress (${commitment.months_remaining} months left)`}
                            </span>
                        </div>
                    </div>
                    <div style="padding:10px 14px;background:var(--surface-2);border-radius:var(--radius-sm);font-size:0.82rem;line-height:1.4">
                        <b>Tenure Rules Summary:</b><br/>
                        • Staff must complete the 6-month minimum tenure. Resigning early requires a verified critical emergency reason.<br/>
                        • Resignation notice must be served at least <b>30 days (1 month)</b> in advance.<br/>
                        • The shop provides a <b>15-day notice</b> prior to any scheduled staff termination.
                    </div>
                </div>

                <!-- Leave Application Form -->
                <div class="card" style="margin-bottom:20px">
                    <div class="chart-title" style="margin-bottom:6px">📝 Apply for Leave (2-Day Advance Notice Required)</div>
                    <div style="font-size:0.82rem;color:var(--text-muted);margin-bottom:14px">
                        Shop policy permits up to <b>4 paid leaves per calendar month</b>. Any additional leaves are transparently deducted at the daily rate of <b>${formatCurrency(dailyRate)}</b>/day. Leaves must be submitted at least 2 calendar days ahead.
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label" style="font-weight:600">Leave Date <span class="text-danger">*</span></label>
                            <input type="date" class="form-control" id="leave-date" min="${minDateStr}" value="${minDateStr}" style="height:44px">
                            <div style="font-size:0.75rem;color:var(--text-muted);margin-top:3px">Earliest eligible date: ${minDateStr} (2-day advance)</div>
                        </div>
                        <div class="form-group" style="max-width:140px">
                            <label class="form-label" style="font-weight:600">Days</label>
                            <input type="number" class="form-control" id="leave-days" min="1" max="15" value="1" style="height:44px">
                        </div>
                    </div>

                    <div class="form-group">
                        <label class="form-label" style="font-weight:600">Reason for Leave <span class="text-danger">*</span></label>
                        <textarea class="form-control" id="leave-reason" rows="2" placeholder="Describe the reason for leave (e.g. Family function, health checkup)..."></textarea>
                    </div>

                    <button class="btn btn-primary" onclick="submitLeaveRequest()">
                        📤 Submit Leave Application
                    </button>
                </div>

                <!-- My Leave History Table -->
                <div class="card" style="margin-bottom:20px">
                    <div class="chart-title" style="margin-bottom:12px">📋 My Leave History</div>
                    ${leaves.length === 0 ? `
                        <div class="text-muted" style="font-size:0.85rem">No leave requests submitted yet.</div>
                    ` : `
                        <div class="table-container">
                            <table>
                                <thead><tr><th>Leave Date</th><th>Days</th><th>Reason</th><th>Status</th><th>Submitted On</th><th>Admin Notes</th></tr></thead>
                                <tbody>
                                    ${leaves.map(l => `
                                        <tr>
                                            <td style="font-weight:600">${l.leave_date}</td>
                                            <td>${l.days} day(s)</td>
                                            <td>${l.reason}</td>
                                            <td><span class="badge ${l.status === 'Approved' ? 'badge-completed' : l.status === 'Rejected' ? 'badge-cancelled' : 'badge-assigned'}">${l.status}</span></td>
                                            <td style="font-size:0.78rem;color:var(--text-muted)">${formatDate(l.created_at)}</td>
                                            <td style="font-size:0.8rem">${l.admin_notes || '—'}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `}
                </div>

                <!-- Performance & Festival Bonuses -->
                <div class="card">
                    <div class="chart-title" style="margin-bottom:12px">🎉 Bonuses & Rewards on Record</div>
                    ${bonuses.length === 0 ? `
                        <div class="text-muted" style="font-size:0.85rem">No bonuses awarded yet. Performance & festival bonuses granted by Admin will appear here.</div>
                    ` : `
                        <div class="table-container">
                            <table>
                                <thead><tr><th>Date</th><th>Bonus Type</th><th>Amount</th><th>Reason</th><th>Awarded By</th></tr></thead>
                                <tbody>
                                    ${bonuses.map(b => `
                                        <tr>
                                            <td style="font-size:0.8rem;color:var(--text-muted)">${formatDate(b.awarded_at)}</td>
                                            <td><span class="badge badge-completed" style="font-size:0.78rem">${b.bonus_type}</span></td>
                                            <td style="font-weight:700;color:var(--primary)">${formatCurrency(b.amount)}</td>
                                            <td>${b.reason}</td>
                                            <td>${b.awarded_by_name || 'Admin'}</td>
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

async function submitLeaveRequest() {
    const leaveDate = document.getElementById('leave-date').value;
    const days = parseInt(document.getElementById('leave-days').value || 1);
    const reason = document.getElementById('leave-reason').value.trim();

    if (!leaveDate) {
        showToast('Please select a leave date.', 'warning');
        return;
    }
    if (reason.length < 5) {
        showToast('Please describe the reason for your leave (at least 5 characters).', 'warning');
        return;
    }

    // Client-side 2-day check
    const today = new Date();
    today.setHours(0,0,0,0);
    const targetDate = new Date(leaveDate + 'T00:00:00');
    const diffDays = Math.round((targetDate - today) / (1000 * 60 * 60 * 24));
    if (diffDays < 2) {
        showToast('Shop policy requires at least 2 calendar days advance notice for leaves.', 'error');
        return;
    }

    try {
        const res = await api.post('/staff-mgmt/leave/apply', {
            leave_date: leaveDate,
            days: days,
            reason: reason
        });
        showToast(res.message, 'success');
        renderStaffLeavesAndSalary();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function openResignationModal(commitmentStatus) {
    const minNoticeDate = new Date();
    minNoticeDate.setDate(minNoticeDate.getDate() + 30);
    const minNoticeDateStr = minNoticeDate.toISOString().split('T')[0];

    const isUnderCommitment = (commitmentStatus !== 'Satisfied');

    showModal(`
        <div class="modal-header">
            <span class="modal-title">📝 Submit Resignation Notice</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="padding:12px;background:rgba(234,179,8,0.1);border:1px solid rgba(234,179,8,0.3);border-radius:var(--radius-sm);margin-bottom:14px;font-size:0.85rem">
            <b>Notice Rules:</b><br/>
            • <b>30-day minimum notice</b> is strictly required before departure.<br/>
            ${isUnderCommitment ? '• <span class="text-danger"><b>Warning:</b> You have not yet completed the 6-month commitment. Resigning early requires a critical emergency justification.</span>' : '• 6-month commitment satisfied.'}
        </div>
        <div class="form-group">
            <label class="form-label" style="font-weight:600">Proposed Last Working Day <span class="text-danger">*</span></label>
            <input type="date" class="form-control" id="resignation-date" min="${minNoticeDateStr}" value="${minNoticeDateStr}" style="height:44px">
            <div style="font-size:0.75rem;color:var(--text-muted);margin-top:3px">Must be at least 30 days from today (${minNoticeDateStr}).</div>
        </div>
        <div class="form-group">
            <label class="form-label" style="font-weight:600">Reason for Resignation <span class="text-danger">*</span></label>
            <textarea class="form-control" id="resignation-reason" rows="2" placeholder="Primary reason for leaving..."></textarea>
        </div>
        ${isUnderCommitment ? `
            <div class="form-group">
                <label class="form-label" style="font-weight:600;color:var(--danger)">Emergency Justification (Required for < 6 months tenure) <span class="text-danger">*</span></label>
                <textarea class="form-control" id="resignation-emergency" rows="3" placeholder="Provide full details of the urgent/unavoidable personal reason..."></textarea>
            </div>
        ` : ''}
        <div class="flex gap-2" style="margin-top:16px">
            <button class="btn btn-outline flex-1" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
            <button class="btn btn-primary flex-1" onclick="submitResignation(${isUnderCommitment})">Submit Notice</button>
        </div>
    `);
}

async function submitResignation(isUnderCommitment) {
    const lastDate = document.getElementById('resignation-date').value;
    const reason = document.getElementById('resignation-reason').value.trim();
    const emergency = document.getElementById('resignation-emergency')?.value.trim() || null;

    if (!lastDate) {
        showToast('Please select your proposed last working day.', 'warning');
        return;
    }
    if (reason.length < 5) {
        showToast('Please state your reason for resignation.', 'warning');
        return;
    }
    if (isUnderCommitment && (!emergency || emergency.length < 10)) {
        showToast('Emergency justification of at least 10 characters is required for leaving before 6 months.', 'warning');
        return;
    }

    try {
        const res = await api.post('/staff-mgmt/resignation', {
            proposed_last_date: lastDate,
            reason: reason,
            emergency_justification: emergency
        });
        showToast(res.message, 'success');
        document.querySelector('.modal-overlay')?.remove();
        renderStaffLeavesAndSalary();
    } catch (e) {
        showToast(e.message, 'error');
    }
}
