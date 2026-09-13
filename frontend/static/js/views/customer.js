/**
 * Mistri Customer Views - Bilingual (Hindi/English) + Feedback Support
 */

async function renderCustomerDashboard() {
    showLoading();
    try {
        const [jobs, notifs] = await Promise.all([
            api.get('/repairs/'),
            api.get('/notifications/')
        ]);
        const activeJobs = jobs.filter(j => !['Delivered'].includes(j.status));
        const user = api.getUser();

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px">
                        <div>
                            <div class="page-title">👋 ${t('welcome')}, ${user.name.split(' ')[0]}!</div>
                            <div class="page-subtitle">${t('overview')}</div>
                        </div>
                        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                            ${langToggleBtn()}
                            <button class="btn btn-primary" onclick="router.navigate('/customer/submit')">${t('newRepair')}</button>
                        </div>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon">🔧</div>
                        <div class="stat-value">${jobs.length}</div>
                        <div class="stat-label">${t('totalRepairs')}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">⏳</div>
                        <div class="stat-value">${activeJobs.length}</div>
                        <div class="stat-label">${t('activeRepairs')}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">✅</div>
                        <div class="stat-value">${jobs.filter(j => j.status === 'Delivered').length}</div>
                        <div class="stat-label">${t('completed')}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">🔔</div>
                        <div class="stat-value">${notifs.filter(n => !n.is_read).length}</div>
                        <div class="stat-label">${t('unreadAlerts')}</div>
                    </div>
                </div>

                ${activeJobs.length ? `
                    <h2 style="margin-bottom:16px;font-size:1rem;font-weight:600">${t('activeRepairsTitle')}</h2>
                    <div class="dashboard-grid" style="margin-bottom:24px">
                        ${activeJobs.map(job => renderRepairCard(job, true)).join('')}
                    </div>
                ` : ''}

                <div class="flex justify-between items-center mb-3">
                    <h2 style="font-size:1rem;font-weight:600">${t('allRepairs')}</h2>
                </div>
                ${jobs.length === 0 ? `
                    <div class="empty-state card">
                        <div class="empty-state-icon">🔧</div>
                        <div class="empty-state-title">${t('noRepairsYet')}</div>
                        <div class="text-muted" style="margin-bottom:16px">${t('submitFirstRepair')}</div>
                        <button class="btn btn-primary" onclick="router.navigate('/customer/submit')">${t('submitRepair')}</button>
                    </div>
                ` : `
                    <div class="dashboard-grid">
                        ${jobs.map(job => renderRepairCard(job, false)).join('')}
                    </div>
                `}
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function renderRepairCard(job, compact = false) {
    return `
        <div class="repair-card" onclick="renderRepairDetail(${job.id})">
            <div class="flex justify-between items-center mb-2">
                <span class="repair-card-id">${job.repair_id}</span>
                ${statusBadge(job.status)}
            </div>
            <div class="repair-card-device">${job.brand} ${job.model}</div>
            <div class="repair-card-problem">${job.problem_description}</div>
            ${!compact ? renderTimeline(job.status) : ''}
            <div class="repair-card-footer">
                <div style="font-size:0.78rem;color:var(--text-muted)">${formatDate(job.created_at)}</div>
                ${job.estimated_cost ? `<div class="repair-cost">${formatCurrency(job.estimated_cost)}</div>` : ''}
            </div>
        </div>
    `;
}

async function renderRepairDetail(jobId) {
    showLoading();
    try {
        const [job, history, photos, warranty, fbCheck] = await Promise.all([
            api.get(`/repairs/${jobId}`),
            api.get(`/repairs/${jobId}/history`).catch(() => []),
            api.get(`/repairs/${jobId}/photos`).catch(() => []),
            api.get(`/warranties/repair/${jobId}`).catch(() => ({ has_warranty: false })),
            api.get(`/feedback/repair/${jobId}`).catch(() => ({ exists: false }))
        ]);

        const showFeedback = ['Completed', 'Delivered', 'Ready'].includes(job.status);

        setContent(`
            <div class="page" style="max-width:800px;margin:0 auto">
                <div style="margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                    <button class="btn btn-outline btn-sm" onclick="router.navigate('/customer')">${t('back')}</button>
                    ${langToggleBtn()}
                </div>
                <div class="page-header">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="font-mono text-primary-color" style="font-size:1.2rem;font-weight:700">${job.repair_id}</div>
                            <div class="page-title">${job.brand} ${job.model}</div>
                            <div class="page-subtitle">${job.device_type}</div>
                        </div>
                        ${statusBadge(job.status)}
                    </div>
                </div>

                <!-- Status Progress & Lifecycle History -->
                <div class="card" style="margin-bottom:20px">
                    <div class="chart-title">${t('repairProgress')}</div>
                    ${renderTimeline(job.status, history)}
                </div>

                <!-- Warranty Card if Active -->
                ${warranty.has_warranty ? `
                    <div class="card" style="margin-bottom:20px;border:1px solid ${warranty.is_active ? 'var(--success)' : 'var(--border)'};background:${warranty.is_active ? '#27D67B11' : 'var(--surface-2)'}">
                        <div class="flex justify-between items-center flex-wrap gap-2">
                            <div>
                                <div style="font-size:0.8rem;font-weight:700;color:${warranty.is_active ? 'var(--success)' : 'var(--text-muted)'};text-transform:uppercase">
                                    🛡️ ${warranty.status_label}
                                </div>
                                <div style="font-size:0.85rem;color:var(--text-secondary);margin-top:4px">
                                    Valid until <b>${formatDate(warranty.end_date)}</b> (${warranty.duration_days} days total)
                                </div>
                                <div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px">
                                    Terms: ${warranty.covered_terms}
                                </div>
                            </div>
                            ${warranty.is_active ? `
                                <button class="btn btn-outline btn-sm" style="border-color:var(--success);color:var(--success)" onclick="openWarrantyClaimModal(${jobId})">
                                    🔄 Request Revisit / Claim
                                </button>
                            ` : ''}
                        </div>
                    </div>
                ` : ''}

                <!-- Problem & Device Specs -->
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
                    <div class="card">
                        <div class="text-muted" style="font-size:0.75rem;margin-bottom:8px">${t('problemDescription')}</div>
                        <div style="font-size:0.9rem">${job.problem_description}</div>
                    </div>
                    <div class="card">
                        <div class="text-muted" style="font-size:0.75rem;margin-bottom:8px">${t('deviceDetails')}</div>
                        <div style="font-size:0.9rem"><strong>${job.device_type}</strong> — ${job.brand} ${job.model}</div>
                    </div>
                </div>

                <!-- Technician & Pricing Info -->
                <div class="card" style="margin-bottom:20px">
                    <div class="flex justify-between items-center flex-wrap gap-2">
                        <div>
                            <div class="text-muted" style="font-size:0.75rem;margin-bottom:4px">${t('assignedTechnician')}</div>
                            <div style="font-weight:600">${job.technician_name || t('notYetAssigned')}</div>
                        </div>
                        <div>
                            <div class="text-muted" style="font-size:0.75rem;margin-bottom:4px">${t('estimatedCost')}</div>
                            <div style="font-weight:600;color:var(--primary)">${job.actual_cost ? formatCurrency(job.actual_cost) : job.estimated_cost ? formatCurrency(job.estimated_cost) : t('pending')}</div>
                        </div>
                        <div>
                            <div class="text-muted" style="font-size:0.75rem;margin-bottom:4px">${t('submitted')}</div>
                            <div style="font-size:0.9rem">${formatDate(job.created_at)}</div>
                        </div>
                    </div>
                    ${job.technician_notes ? `
                        <hr class="divider">
                        <div class="text-muted" style="font-size:0.75rem;margin-bottom:4px">${t('technicianNotes')}</div>
                        <div style="font-size:0.9rem">${job.technician_notes}</div>
                    ` : ''}
                </div>

                <!-- Staged Repair Photos Evidence (Before / During / After) -->
                ${photos && photos.length > 0 ? `
                    <div class="card" style="margin-bottom:20px">
                        <div class="chart-title" style="margin-bottom:12px">📸 Repair Photo Evidence</div>
                        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:12px">
                            ${photos.map(p => `
                                <div style="border:1px solid var(--border);border-radius:var(--radius-sm);overflow:hidden;background:var(--bg-input)">
                                    <div style="padding:4px 8px;font-size:0.72rem;font-weight:700;text-transform:uppercase;background:var(--surface-2);color:var(--primary)">
                                        Stage: ${p.photo_stage}
                                    </div>
                                    <img src="${p.photo_url}" style="width:100%;height:130px;object-fit:cover;cursor:pointer" onclick="window.open('${p.photo_url}', '_blank')">
                                    <div style="padding:6px 8px;font-size:0.75rem;color:var(--text-secondary)">
                                        ${p.caption || p.photo_stage}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}

                <!-- Feedback Section -->
                ${showFeedback ? renderFeedbackSection(jobId, fbCheck, job.technician_name) : ''}

                <div class="flex gap-2 flex-wrap">
                    <button class="btn btn-outline" onclick="showQRCode('${job.repair_id}')">${t('qrCode')}</button>
                    <button class="btn btn-outline btn-sm" onclick="router.navigate('/customer/invoices')">${t('viewInvoices')}</button>
                </div>
            </div>
        `);
    } catch (e) {
        showToast(e.message, 'error');
        router.navigate('/customer');
    }
}

function openWarrantyClaimModal(jobId) {
    showModal(`
        <div style="max-width:480px">
            <h3 style="margin-bottom:12px">🔄 Raise Warranty Revisit Request</h3>
            <p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:16px">
                If the repaired issue has recurred during your active warranty window, describe the issue below. Our team will arrange priority diagnosis.
            </p>
            <div class="form-group" style="margin-bottom:14px">
                <label class="form-label">Issue Details</label>
                <textarea class="form-control" id="claim-desc" rows="3" placeholder="Explain what problem occurred again..."></textarea>
            </div>
            <div class="flex justify-end gap-2">
                <button class="btn btn-outline btn-sm" onclick="document.querySelector('.modal-overlay').remove()">Cancel</button>
                <button class="btn btn-primary btn-sm" onclick="submitWarrantyClaim(${jobId})">Submit Revisit Request</button>
            </div>
        </div>
    `);
}

async function submitWarrantyClaim(jobId) {
    const desc = document.getElementById('claim-desc')?.value;
    if (!desc || desc.length < 5) {
        showToast('Please provide details about the recurring issue.', 'warning');
        return;
    }
    try {
        await api.post('/warranties/claim', { repair_job_id: jobId, issue_description: desc });
        document.querySelector('.modal-overlay')?.remove();
        showToast('Warranty claim registered! We will prioritize your revisit.', 'success');
        renderRepairDetail(jobId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function renderFeedbackSection(jobId, fbCheck, techName) {
    if (fbCheck && fbCheck.exists) {
        const stars = '⭐'.repeat(fbCheck.rating) + '☆'.repeat(5 - fbCheck.rating);
        return `
            <div class="card" style="margin-bottom:20px;border:1px solid var(--border);background:var(--surface-2)">
                <div class="chart-title">${t('leaveReview')}</div>
                <div style="color:var(--success);font-size:0.9rem;margin-bottom:8px">${t('alreadyFeedback')}</div>
                <div style="font-size:1.3rem;letter-spacing:2px">${stars}</div>
                ${fbCheck.comment ? `<div style="font-size:0.9rem;color:var(--text-muted);margin-top:8px">"${fbCheck.comment}"</div>` : ''}
            </div>
        `;
    }
    return `
        <div class="card" style="margin-bottom:20px;border:1px solid var(--primary-30)" id="feedback-section">
            <div class="chart-title">${t('leaveReview')}</div>
            <div class="text-muted" style="font-size:0.85rem;margin-bottom:16px">${t('feedbackDesc')}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:14px">
                <div>
                    <div style="font-size:0.82rem;font-weight:600;margin-bottom:6px">Overall Service Rating</div>
                    <div class="star-rating" id="star-rating" style="font-size:1.8rem;letter-spacing:3px;cursor:pointer">
                        ${[1, 2, 3, 4, 5].map(i => `<span class="star" data-val="${i}" onclick="selectStar(${i})" style="color:var(--text-muted);transition:color 0.15s">☆</span>`).join('')}
                    </div>
                    <input type="hidden" id="fb-rating" value="0">
                </div>
                <div>
                    <div style="font-size:0.82rem;font-weight:600;margin-bottom:6px">Technician (${techName || 'Staff'}) Rating</div>
                    <div class="star-rating" id="tech-star-rating" style="font-size:1.8rem;letter-spacing:3px;cursor:pointer">
                        ${[1, 2, 3, 4, 5].map(i => `<span class="star-tech" data-val="${i}" onclick="selectTechStar(${i})" style="color:var(--text-muted);transition:color 0.15s">☆</span>`).join('')}
                    </div>
                    <input type="hidden" id="fb-tech-rating" value="0">
                </div>
            </div>
            <div class="form-group" style="margin-bottom:12px">
                <label class="form-label">${t('comment')}</label>
                <textarea class="form-control" id="fb-comment" rows="3" placeholder="${t('commentPlaceholder')}" style="min-height:80px"></textarea>
            </div>
            <button class="btn btn-primary" onclick="submitFeedback(${jobId})" id="fb-submit-btn">${t('submitFeedback')}</button>
        </div>
    `;
}

function selectTechStar(val) {
    document.getElementById('fb-tech-rating').value = val;
    document.querySelectorAll('.star-tech').forEach((el, i) => {
        el.textContent = i < val ? '⭐' : '☆';
        el.style.color = i < val ? '#f59e0b' : 'var(--text-muted)';
    });
}

function selectStar(val) {
    document.getElementById('fb-rating').value = val;
    document.querySelectorAll('.star').forEach((el, i) => {
        el.textContent = i < val ? '⭐' : '☆';
        el.style.color = i < val ? '#f59e0b' : 'var(--text-muted)';
    });
}

async function submitFeedback(jobId) {
    const rating = parseInt(document.getElementById('fb-rating').value);
    const techRating = parseInt(document.getElementById('fb-tech-rating')?.value || rating);
    if (!rating) {
        showToast('Please select an overall star rating first!', 'error');
        return;
    }
    const comment = document.getElementById('fb-comment').value;
    const btn = document.getElementById('fb-submit-btn');
    btn.innerHTML = '<div class="spinner"></div>';
    btn.disabled = true;
    try {
        await api.post('/feedback/', { repair_job_id: jobId, rating, technician_rating: techRating, comment });
        const section = document.getElementById('feedback-section');
        const stars = '⭐'.repeat(rating) + '☆'.repeat(5 - rating);
        section.innerHTML = `
            <div class="chart-title">${t('leaveReview')}</div>
            <div style="color:var(--success);font-size:0.95rem;margin-bottom:8px">${t('feedbackThanks')}</div>
            <div style="font-size:1.3rem;letter-spacing:2px">${stars}</div>
        `;
        showToast(t('feedbackThanks'), 'success');
    } catch (e) {
        showToast(e.message || t('feedbackError'), 'error');
        btn.innerHTML = t('submitFeedback');
        btn.disabled = false;
    }
}

/** Submit Repair with AI Estimator */
async function renderSubmitRepair() {
    setContent(`
        <div class="page" style="max-width:700px;margin:0 auto">
            <div style="margin-bottom:20px;display:flex;justify-content:space-between;align-items:center">
                <button class="btn btn-outline btn-sm" onclick="router.navigate('/customer')">${t('back')}</button>
                ${langToggleBtn()}
            </div>
            <div class="page-header">
                <div class="page-title">${t('submitRepairTitle')}</div>
                <div class="page-subtitle">${t('submitRepairSub')}</div>
            </div>
            <div class="card">
                <form id="repair-form" onsubmit="handleSubmitRepair(event)">
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">${t('applianceType')}</label>
                            <select class="form-control" id="device-type" onchange="triggerAIEstimate()" required>
                                <option value="">${t('selectAppliance')}</option>
                                <option value="Fan">🌀 Fan</option>
                                <option value="Cooler">❄️ Cooler</option>
                                <option value="Mixer/Grinder">🥤 Mixer / Grinder</option>
                                <option value="Motor">⚙️ Motor</option>
                                <option value="Geyser">🔥 Geyser / Water Heater</option>
                                <option value="Pump">💧 Water Pump</option>
                                <option value="Other">🔌 Other</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">${t('brand')}</label>
                            <input type="text" class="form-control" id="device-brand" placeholder="${t('brandPlaceholder')}" required>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">${t('modelSize')}</label>
                        <input type="text" class="form-control" id="device-model" placeholder="${t('modelPlaceholder')}" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">${t('problemDesc')}</label>
                        <textarea class="form-control" id="problem-desc" rows="4" placeholder="${t('problemPlaceholder')}" required oninput="triggerAIEstimate()" style="min-height:100px"></textarea>
                    </div>
                    <div class="form-group">
                        <label class="form-label">${t('uploadImage')}</label>
                        <input type="file" class="form-control" id="device-image" accept="image/*">
                    </div>

                    <!-- AI Estimator Widget -->
                    <div class="ai-estimator" id="ai-estimator">
                        <div class="ai-label">${t('aiEstimator')} <span class="ai-badge">AI</span></div>
                        <div id="ai-result" style="color:var(--text-muted);font-size:0.875rem">${t('fillToEstimate')}</div>
                    </div>

                    <button type="submit" class="btn btn-primary w-full" id="submit-btn" style="margin-top:20px">
                        ${t('submitBtn')}
                    </button>
                </form>
            </div>
        </div>
    `);
}

let aiTimeout = null;
async function triggerAIEstimate() {
    clearTimeout(aiTimeout);
    aiTimeout = setTimeout(async () => {
        const deviceType = document.getElementById('device-type')?.value;
        const problem = document.getElementById('problem-desc')?.value;
        if (!deviceType || problem.length < 8) return;

        const resultEl = document.getElementById('ai-result');
        resultEl.innerHTML = `<div class="spinner"></div> ${t('estimating')}`;
        try {
            const est = await api.post('/ai/estimate', { device_type: deviceType, problem_description: problem });
            resultEl.innerHTML = `
                <div class="ai-result">
                    <div class="ai-cost-range">₹${est.estimated_cost_min.toLocaleString()} – ₹${est.estimated_cost_max.toLocaleString()}</div>
                    <div class="ai-confidence">${t('confidence')}: ${est.confidence}% | Suspected: <b>${est.symptom_detected || est.primary_part}</b></div>
                    ${est.explanation ? `
                        <div style="background:var(--surface-2);border-left:3px solid var(--primary);padding:8px 12px;border-radius:4px;margin:10px 0;font-size:0.8rem;line-height:1.4;color:var(--text-secondary)">
                            💡 <b>AI Diagnostic Note:</b> ${est.explanation}
                        </div>
                    ` : ''}
                    <div class="ai-breakdown">
                        <div class="ai-breakdown-item">
                            <div class="ai-breakdown-key">${t('estTime')}</div>
                            <div>${est.estimated_time_min_hours}–${est.estimated_time_max_hours} ${t('hours')}</div>
                        </div>
                        <div class="ai-breakdown-item">
                            <div class="ai-breakdown-key">${t('mainPart')}</div>
                            <div>${est.primary_part}</div>
                        </div>
                    </div>
                    <div style="font-size:0.72rem;color:var(--text-muted);margin-top:8px">${est.disclaimer || est.note}</div>
                </div>
            `;
            window._aiEstimate = est.estimated_cost_min;
        } catch (e) { }
    }, 600);
}

async function handleSubmitRepair(e) {
    e.preventDefault();
    const btn = document.getElementById('submit-btn');
    btn.innerHTML = `<div class="spinner"></div> ${t('submitting')}`;
    btn.disabled = true;
    try {
        const form = new FormData();
        form.append('device_type', document.getElementById('device-type').value);
        form.append('brand', document.getElementById('device-brand').value);
        form.append('model', document.getElementById('device-model').value);
        form.append('problem_description', document.getElementById('problem-desc').value);
        form.append('estimated_cost', window._aiEstimate || 0);
        const imageFile = document.getElementById('device-image').files[0];
        if (imageFile) form.append('image', imageFile);

        const res = await api.post('/repairs/submit', form);
        showToast(`Repair ${res.repair_id} submitted! 🎉`, 'success');
        router.navigate('/customer');
    } catch (err) {
        showToast(err.message, 'error');
        btn.innerHTML = t('submitBtn');
        btn.disabled = false;
    }
}

/** Customer Invoices */
async function renderCustomerInvoices() {
    showLoading();
    try {
        const bills = await api.get('/bills/');
        setContent(`
            <div class="page">
                <div class="page-header">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                        <div>
                            <div class="page-title">${t('myInvoices')}</div>
                            <div class="page-subtitle">${t('downloadInvoices')}</div>
                        </div>
                        ${langToggleBtn()}
                    </div>
                </div>
                ${bills.length === 0 ? `
                    <div class="empty-state card">
                        <div class="empty-state-icon">📄</div>
                        <div class="empty-state-title">${t('noInvoicesYet')}</div>
                    </div>
                ` : `
                    <div class="table-container">
                        <table>
                            <thead><tr>
                                <th>${t('billNum')}</th><th>${t('repairId')}</th><th>${t('device')}</th><th>${t('amount')}</th><th>${t('status')}</th><th>${t('date')}</th><th>${t('action')}</th>
                            </tr></thead>
                            <tbody>
                                ${bills.map(b => `
                                    <tr>
                                        <td class="font-mono">${b.bill_number}</td>
                                        <td class="font-mono text-primary-color">${b.repair_id}</td>
                                        <td>${b.brand} ${b.model}</td>
                                        <td><strong>${formatCurrency(b.total_amount)}</strong></td>
                                        <td>${statusBadge(b.payment_status)}</td>
                                        <td style="font-size:0.8rem;color:var(--text-muted)">${formatDate(b.created_at)}</td>
                                        <td>
                                            <a href="/api/bills/${b.id}/pdf" target="_blank" class="btn btn-outline btn-sm">⬇ PDF</a>
                                        </td>
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

/** QR Code Modal */
async function showQRCode(repairId) {
    const overlay = showModal(`
        <div class="modal-header">
            <span class="modal-title">📱 Repair QR Code</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <p class="text-muted" style="font-size:0.85rem;margin-bottom:16px">Share this QR code to track repair status</p>
        <div id="qr-loading" style="text-align:center;padding:32px"><div class="spinner" style="margin:auto;width:48px;height:48px;border-width:4px"></div></div>
    `);
    try {
        const data = await api.get(`/qr/${repairId}`);
        const qrDiv = overlay.querySelector('#qr-loading');
        qrDiv.innerHTML = `
            <img src="data:image/png;base64,${data.qr_code}" class="qr-image" alt="QR Code">
            <div class="qr-url">${data.tracking_url}</div>
            <div style="margin-top:12px;font-size:0.8rem;color:var(--text-muted)">Repair ID: ${repairId}</div>
        `;
    } catch (e) {
        showToast('Failed to generate QR code', 'error');
    }
}
