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
                            <button class="btn btn-outline" onclick="logout()" style="color:var(--danger);border-color:rgba(239,68,68,0.4)">🚪 Logout</button>
                        </div>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card animate-scale-in stagger-1">
                        <div class="stat-icon">🔧</div>
                        <div class="stat-value">${jobs.length}</div>
                        <div class="stat-label">${t('totalRepairs')}</div>
                    </div>
                    <div class="stat-card animate-scale-in stagger-2">
                        <div class="stat-icon">⏳</div>
                        <div class="stat-value">${activeJobs.length}</div>
                        <div class="stat-label">${t('activeRepairs')}</div>
                    </div>
                    <div class="stat-card animate-scale-in stagger-3">
                        <div class="stat-icon">✅</div>
                        <div class="stat-value">${jobs.filter(j => j.status === 'Delivered').length}</div>
                        <div class="stat-label">${t('completed')}</div>
                    </div>
                    <div class="stat-card animate-scale-in stagger-4">
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

        if ((window.location.search.includes('complete_profile=1') || (user && user.needs_profile_completion)) && typeof window.showCompleteProfileModal === 'function') {
            setTimeout(() => {
                window.showCompleteProfileModal(user.name, user.role);
            }, 300);
        }
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
                    <hr class="divider">
                    <div style="font-size:0.85rem">
                        <div class="flex justify-between items-center">
                            <span><b>Service Mode:</b> ${job.service_type === 'Home Pickup' ? '🏠 Doorstep Visit / Home Pickup' : '🏪 Store Drop-off (Walk-in)'}</span>
                            <span class="badge" style="background:${job.service_type === 'Home Pickup' ? '#8b5cf622' : '#0ea5e922'};color:${job.service_type === 'Home Pickup' ? '#a78bfa' : '#38bdf8'}">
                                ${job.service_type || 'Store Drop-off'}
                            </span>
                        </div>
                        ${job.pickup_address ? `
                            <div style="margin-top:6px;color:var(--text-secondary)">
                                📍 <b>Pickup Address:</b> ${job.pickup_address}
                            </div>
                        ` : ''}
                    </div>
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

/** Submit Repair with AI Estimator - v7: Improved with Hinglish AI, video upload, pincode validation */
async function renderSubmitRepair() {
    setContent(`
        <div class="page" style="max-width:740px;margin:0 auto">
            <div style="margin-bottom:20px;display:flex;justify-content:space-between;align-items:center">
                <button class="btn btn-outline btn-sm" onclick="router.navigate('/customer')">${t('back')}</button>
                ${langToggleBtn()}
            </div>
            <div class="page-header">
                <div class="page-title">${t('submitRepairTitle')}</div>
                <div class="page-subtitle">${t('submitRepairSub')}</div>
            </div>

            <!-- Device Cards Container -->
            <div id="devices-container"></div>

            <!-- Add Another Device Button -->
            <button type="button" class="btn btn-outline w-full" id="add-device-btn" onclick="addDeviceCard()"
                style="margin-bottom:20px;border-style:dashed;display:flex;align-items:center;justify-content:center;gap:8px">
                ➕ Add Another Device / Appliance
            </button>

            <!-- Service Mode Selection -->
            <div class="card" style="margin-bottom:20px">
                <div class="form-group" style="margin-bottom:16px">
                    <label class="form-label" style="font-weight:600">Service Mode / Delivery Preference</label>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                        <label style="display:flex;align-items:center;gap:10px;padding:12px;border:2px solid var(--primary);border-radius:var(--radius-sm);cursor:pointer;background:var(--surface-2)" id="mode-store-label">
                            <input type="radio" name="service_type" value="Store Drop-off" checked onchange="togglePickupFields(this.value)">
                            <div>
                                <div style="font-weight:600;font-size:0.95rem">🏪 Store Drop-off</div>
                                <div style="font-size:0.75rem;color:var(--text-muted)">Dukan par lekar aayenge</div>
                            </div>
                        </label>
                        <label style="display:flex;align-items:center;gap:10px;padding:12px;border:1px solid var(--border);border-radius:var(--radius-sm);cursor:pointer;background:var(--surface-1)" id="mode-home-label">
                            <input type="radio" name="service_type" value="Home Pickup" onchange="togglePickupFields(this.value)">
                            <div>
                                <div style="font-weight:600;font-size:0.95rem">🏠 Home Visit / Pickup</div>
                                <div style="font-size:0.75rem;color:var(--text-muted)">Technician ghar aayega</div>
                            </div>
                        </label>
                    </div>
                </div>

                <!-- Address Fields (visible when Home Pickup selected) -->
                <div id="pickup-address-container" style="display:none;background:var(--surface-2);border:1px dashed var(--primary);border-radius:var(--radius-sm);padding:14px">
                    <div style="font-weight:600;font-size:0.9rem;margin-bottom:10px;color:var(--primary)">📍 Ghar ka Pata (Home Address)</div>
                    <div class="form-group" style="margin-bottom:10px">
                        <label class="form-label">House / Flat No., Building & Street *</label>
                        <input type="text" class="form-control" id="pickup-street" placeholder="e.g. H.No 104, Block B, Main Market Road">
                        <div id="pickup-street-err" style="display:none;color:var(--danger);font-size:0.78rem;margin-top:4px"></div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label class="form-label">Landmark * (koi pehchaan ki jagah)</label>
                            <input type="text" class="form-control" id="pickup-landmark" placeholder="e.g. Near Shiv Mandir / SBI ATM">
                            <div id="pickup-landmark-err" style="display:none;color:var(--danger);font-size:0.78rem;margin-top:4px"></div>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Pincode * (exactly 6 digits)</label>
                            <input type="text" class="form-control" id="pickup-pincode" placeholder="e.g. 208001" maxlength="6"
                                oninput="validatePincodeField(this.value)" inputmode="numeric">
                            <div id="pickup-pincode-err" style="display:none;font-size:0.78rem;margin-top:4px"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Total Estimated Cost Bar (visible when 2+ devices) -->
            <div id="total-cost-bar" style="display:none;background:linear-gradient(135deg,var(--surface-2),var(--surface-1));border:1px solid var(--primary);border-radius:var(--radius-sm);padding:12px 16px;margin-bottom:16px">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                    <div>
                        <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:2px">AI Estimated Total (all devices)</div>
                        <div id="total-cost-value" style="font-size:1.4rem;font-weight:800;color:var(--primary)">₹0</div>
                    </div>
                    <div id="total-devices-count" style="font-size:0.85rem;color:var(--text-muted)"></div>
                </div>
            </div>

            <!-- Submit Button -->
            <button type="button" class="btn btn-primary w-full" id="submit-all-btn" onclick="handleSubmitAllRepairs()" style="margin-bottom:32px">
                ${t('submitBtn')}
            </button>
        </div>
    `);

    // Initialize device counter
    window._deviceCards = [];
    window._deviceCounter = 0;
    addDeviceCard();
}

// Track device card state
window._deviceCards = [];
window._deviceCounter = 0;

function addDeviceCard() {
    const idx = window._deviceCounter++;
    window._deviceCards.push({ idx, aiEstimate: 0 });

    const container = document.getElementById('devices-container');
    const card = document.createElement('div');
    card.className = 'card';
    card.id = `device-card-${idx}`;
    card.style.cssText = 'margin-bottom:16px;border:1px solid var(--border)';
    const cardNum = window._deviceCards.length;
    card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
            <div style="font-weight:700;font-size:0.95rem;color:var(--primary)" id="device-title-${idx}">🔧 Device ${cardNum}</div>
            ${cardNum > 1 ? `<button type="button" class="btn btn-outline btn-sm" style="border-color:var(--danger);color:var(--danger);padding:4px 10px" onclick="removeDeviceCard(${idx})">✕ Remove</button>` : ''}
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">${t('applianceType')}</label>
                <select class="form-control" id="dtype-${idx}" onchange="triggerDeviceAI(${idx})" required>
                    <option value="">— ${t('selectAppliance')} —</option>
                    <option value="Fan">🌀 Fan</option>
                    <option value="Cooler">❄️ Cooler</option>
                    <option value="Mixer/Grinder">🥤 Mixer / Grinder</option>
                    <option value="Motor">⚙️ Motor</option>
                    <option value="Geyser">🔥 Geyser / Water Heater</option>
                    <option value="Pump">💧 Water Pump</option>
                    <option value="Mobile">📱 Mobile</option>
                    <option value="Laptop">💻 Laptop</option>
                    <option value="Other">🔌 Other</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">${t('brand')}</label>
                <input type="text" class="form-control" id="dbrand-${idx}" placeholder="${t('brandPlaceholder')}" required>
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">${t('modelSize')}</label>
            <input type="text" class="form-control" id="dmodel-${idx}" placeholder="${t('modelPlaceholder')}" required>
        </div>
        <div class="form-group">
            <label class="form-label">${t('problemDesc')}</label>
            <textarea class="form-control" id="dproblem-${idx}" rows="3" placeholder="${t('problemPlaceholder')}"
                required oninput="triggerDeviceAI(${idx})" style="min-height:85px"></textarea>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">📷 Photo (Optional, max 5MB)</label>
                <input type="file" class="form-control" id="dimage-${idx}" accept="image/jpeg,image/png,image/webp"
                    onchange="validateMediaFile(this,'image','dimage-err-${idx}',5)">
                <div id="dimage-err-${idx}" style="display:none;font-size:0.78rem;margin-top:4px"></div>
            </div>
            <div class="form-group">
                <label class="form-label">🎥 Video (Optional, max 50MB)</label>
                <input type="file" class="form-control" id="dvideo-${idx}" accept="video/mp4,video/quicktime,video/avi,video/webm"
                    onchange="validateMediaFile(this,'video','dvideo-err-${idx}',50)">
                <div id="dvideo-err-${idx}" style="display:none;font-size:0.78rem;margin-top:4px"></div>
            </div>
        </div>
        <!-- AI Estimator per device -->
        <div class="ai-estimator" id="ai-estimator-${idx}" style="margin-top:4px">
            <div class="ai-label">${t('aiEstimator')} <span class="ai-badge">AI</span></div>
            <div id="ai-result-${idx}" style="color:var(--text-muted);font-size:0.875rem">${t('fillToEstimate')}</div>
        </div>
    `;
    container.appendChild(card);
    updateDeviceNumbers();
}

function removeDeviceCard(idx) {
    document.getElementById(`device-card-${idx}`)?.remove();
    window._deviceCards = window._deviceCards.filter(d => d.idx !== idx);
    updateDeviceNumbers();
    updateTotalCost();
}

function updateDeviceNumbers() {
    window._deviceCards.forEach((d, i) => {
        const title = document.getElementById(`device-title-${d.idx}`);
        if (title) title.textContent = `🔧 Device ${i + 1}`;
    });
    const addBtn = document.getElementById('add-device-btn');
    if (addBtn) addBtn.style.display = window._deviceCards.length >= 10 ? 'none' : 'flex';
}

function updateTotalCost() {
    const total = window._deviceCards.reduce((s, d) => s + (d.aiEstimate || 0), 0);
    const bar = document.getElementById('total-cost-bar');
    const valEl = document.getElementById('total-cost-value');
    const countEl = document.getElementById('total-devices-count');
    if (bar) bar.style.display = window._deviceCards.length > 1 && total > 0 ? 'block' : 'none';
    if (valEl) valEl.textContent = `₹${total.toLocaleString('en-IN')}`;
    if (countEl) countEl.textContent = `${window._deviceCards.length} device(s) total`;
}

function validateMediaFile(input, type, errId, maxMB) {
    const errEl = document.getElementById(errId);
    if (!errEl || !input.files[0]) { if (errEl) errEl.style.display = 'none'; return true; }
    const file = input.files[0];
    const maxBytes = maxMB * 1024 * 1024;
    if (file.size > maxBytes) {
        errEl.textContent = `❌ File too large. Max: ${maxMB}MB`;
        errEl.style.color = 'var(--danger)'; errEl.style.display = 'block';
        input.value = ''; return false;
    }
    errEl.textContent = `✓ ${file.name} (${(file.size/1024/1024).toFixed(1)}MB)`;
    errEl.style.color = 'var(--success)'; errEl.style.display = 'block';
    return true;
}

function validatePincodeField(value) {
    const errEl = document.getElementById('pickup-pincode-err');
    if (!errEl) return;
    if (!value) { errEl.style.display = 'none'; return; }
    if (/^[1-9][0-9]{5}$/.test(value)) {
        errEl.textContent = '✓ Valid Indian pincode';
        errEl.style.color = 'var(--success)'; errEl.style.display = 'block';
    } else {
        errEl.textContent = '❌ Pincode must be exactly 6 digits and cannot start with 0 (e.g. 208001)';
        errEl.style.color = 'var(--danger)'; errEl.style.display = 'block';
    }
}

function togglePickupFields(mode) {
    const container = document.getElementById('pickup-address-container');
    const storeLabel = document.getElementById('mode-store-label');
    const homeLabel = document.getElementById('mode-home-label');
    if (!container) return;
    if (mode === 'Home Pickup') {
        container.style.display = 'block';
        homeLabel.style.border = '2px solid var(--primary)';
        homeLabel.style.background = 'var(--surface-2)';
        storeLabel.style.border = '1px solid var(--border)';
        storeLabel.style.background = 'var(--surface-1)';
    } else {
        container.style.display = 'none';
        storeLabel.style.border = '2px solid var(--primary)';
        storeLabel.style.background = 'var(--surface-2)';
        homeLabel.style.border = '1px solid var(--border)';
        homeLabel.style.background = 'var(--surface-1)';
    }
}

// Legacy single-device AI trigger (still used)
let aiTimeout = null;
async function triggerAIEstimate() { triggerDeviceAI(0); }

const _aiTimeouts = {};
async function triggerDeviceAI(idx) {
    clearTimeout(_aiTimeouts[idx]);
    _aiTimeouts[idx] = setTimeout(async () => {
        const deviceType = document.getElementById(`dtype-${idx}`)?.value;
        const problem = document.getElementById(`dproblem-${idx}`)?.value;
        if (!deviceType || !problem || problem.length < 8) return;

        const resultEl = document.getElementById(`ai-result-${idx}`);
        if (!resultEl) return;
        resultEl.innerHTML = `
            <div class="animate-fade-in" style="display:flex;align-items:center;gap:10px;padding:8px 0">
                <div class="spinner" style="width:18px;height:18px;border-width:2px"></div>
                <span style="font-size:0.85rem;color:var(--text-secondary)">🤖 Analyzing fault & calculating spare parts...</span>
            </div>
        `;
        try {
            const est = await api.post('/ai/estimate', { device_type: deviceType, problem_description: problem });
            const confColors = { High: '#22c55e', Medium: '#f59e0b', Low: '#ef4444' };
            const confColor = confColors[est.confidence_level] || '#6b7280';

            resultEl.innerHTML = `
                <div class="ai-result animate-scale-in">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:10px">
                        <div>
                            <div class="ai-cost-range">₹${est.estimated_cost_min.toLocaleString()} – ₹${est.estimated_cost_max.toLocaleString()}</div>
                            <div style="font-size:0.72rem;color:var(--text-muted)">Total Estimate</div>
                        </div>
                        <div style="background:${confColor}22;color:${confColor};border:1px solid ${confColor}55;padding:4px 10px;border-radius:20px;font-size:0.75rem;font-weight:700">
                            ${est.confidence_level==='High'?'🟢':est.confidence_level==='Medium'?'🟡':'🔴'} ${est.confidence_level||'Medium'} (${est.confidence}%)
                        </div>
                    </div>
                    <div class="ai-breakdown" style="margin-bottom:10px">
                        <div class="ai-breakdown-item">
                            <div class="ai-breakdown-key">Parts</div>
                            <div>₹${(est.parts_cost_min||0).toLocaleString()} – ₹${(est.parts_cost_max||0).toLocaleString()}</div>
                        </div>
                        <div class="ai-breakdown-item">
                            <div class="ai-breakdown-key">Labour</div>
                            <div>₹${(est.labor_cost_min||0).toLocaleString()} – ₹${(est.labor_cost_max||0).toLocaleString()}</div>
                        </div>
                        <div class="ai-breakdown-item">
                            <div class="ai-breakdown-key">${t('estTime')}</div>
                            <div>${est.estimated_time_min_hours}–${est.estimated_time_max_hours}h</div>
                        </div>
                        <div class="ai-breakdown-item">
                            <div class="ai-breakdown-key">${t('mainPart')}</div>
                            <div style="font-size:0.78rem">${est.primary_part}</div>
                        </div>
                    </div>
                    ${est.hinglish_explanation ? `
                        <div style="background:var(--surface-2);border-left:3px solid var(--primary);padding:10px 12px;border-radius:4px;margin-bottom:8px;font-size:0.82rem;line-height:1.5;color:var(--text-secondary)">
                            🤖 <b>AI:</b> ${est.hinglish_explanation}
                        </div>
                    ` : ''}
                    ${est.follow_up_questions && est.follow_up_questions.length > 0 ? `
                        <div style="background:#ef444411;border:1px solid #ef444433;padding:8px 12px;border-radius:var(--radius-sm);margin-bottom:8px">
                            <div style="font-size:0.78rem;font-weight:700;color:#ef4444;margin-bottom:4px">❓ Better estimate ke liye:</div>
                            <ul style="font-size:0.78rem;color:var(--text-secondary);padding-left:16px;margin:0">
                                ${est.follow_up_questions.slice(0,3).map(q=>`<li style="margin-bottom:2px">${q}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                    <div style="font-size:0.7rem;color:var(--text-muted);font-style:italic">${est.disclaimer}</div>
                </div>
            `;
            const cardData = window._deviceCards.find(d => d.idx === idx);
            if (cardData) { cardData.aiEstimate = est.estimated_cost_min || 0; updateTotalCost(); }
            window._aiEstimate = est.estimated_cost_min; // legacy compat
        } catch (e) {
            resultEl.innerHTML = `<div class="animate-shake" style="color:var(--text-muted);font-size:0.8rem">⚠️ Problem thodi zyada detail mein describe karein.</div>`;
        }
    }, 700);
}

async function handleSubmitAllRepairs() {
    const btn = document.getElementById('submit-all-btn');
    if (!btn) return;

    // Validate all device cards
    const devices = [];
    for (const d of window._deviceCards) {
        const deviceType = document.getElementById(`dtype-${d.idx}`)?.value;
        const brand = document.getElementById(`dbrand-${d.idx}`)?.value?.trim();
        const model = document.getElementById(`dmodel-${d.idx}`)?.value?.trim();
        const problem = document.getElementById(`dproblem-${d.idx}`)?.value?.trim();
        const imageFile = document.getElementById(`dimage-${d.idx}`)?.files?.[0];
        const videoFile = document.getElementById(`dvideo-${d.idx}`)?.files?.[0];
        const num = window._deviceCards.indexOf(d) + 1;

        if (!deviceType) { showToast(`Device ${num}: Please select appliance type.`, 'error'); return; }
        if (!brand) { showToast(`Device ${num}: Please enter the brand name.`, 'error'); return; }
        if (!model) { showToast(`Device ${num}: Please enter the model/size.`, 'error'); return; }
        if (!problem || problem.length < 5) { showToast(`Device ${num}: Please describe the problem (min 5 chars).`, 'error'); return; }

        devices.push({ idx: d.idx, deviceType, brand, model, problem, imageFile, videoFile, aiEstimate: d.aiEstimate || 0 });
    }

    // Validate service type + address
    const serviceType = document.querySelector('input[name="service_type"]:checked')?.value || 'Store Drop-off';
    let pickupAddress = '';
    let landmark = '';
    let pincode = '';

    if (serviceType === 'Home Pickup') {
        const street = document.getElementById('pickup-street')?.value?.trim();
        landmark = document.getElementById('pickup-landmark')?.value?.trim() || '';
        pincode = document.getElementById('pickup-pincode')?.value?.trim() || '';

        if (!street || street.length < 10) {
            showToast('Please enter a complete street address (minimum 10 characters).', 'error'); return;
        }
        if (!landmark || landmark.length < 3) {
            showToast('Please enter a landmark (e.g. Near SBI ATM, Near Shiv Mandir).', 'error'); return;
        }
        if (!pincode || !/^[1-9][0-9]{5}$/.test(pincode)) {
            showToast('Please enter a valid 6-digit Indian pincode (e.g. 208001). It cannot start with 0.', 'error'); return;
        }
        pickupAddress = `${street}, Landmark: ${landmark}, ${pincode}`;
    }

    btn.innerHTML = `<div class="spinner" style="width:18px;height:18px;border-width:2px;display:inline-block;margin-right:8px"></div> Submitting...`;
    btn.disabled = true;

    try {
        const batchId = devices.length > 1 ? `BATCH-${Date.now().toString(36).toUpperCase().slice(-8)}` : null;
        let firstRepairId = null;

        for (let i = 0; i < devices.length; i++) {
            const d = devices[i];
            const form = new FormData();
            form.append('device_type', d.deviceType);
            form.append('brand', d.brand);
            form.append('model', d.model);
            form.append('problem_description', d.problem);
            form.append('estimated_cost', d.aiEstimate || 0);
            form.append('service_type', serviceType);
            form.append('pickup_address', pickupAddress);
            if (landmark) form.append('landmark', landmark);
            if (pincode) form.append('pincode', pincode);
            if (batchId) form.append('repair_batch_id', batchId);
            if (d.imageFile) form.append('image', d.imageFile);
            if (d.videoFile) form.append('video', d.videoFile);

            if (devices.length > 1) {
                btn.innerHTML = `<div class="spinner" style="width:18px;height:18px;border-width:2px;display:inline-block;margin-right:8px"></div> Submitting ${i+1}/${devices.length}...`;
            }
            const res = await api.post('/repairs/submit', form);
            if (i === 0) firstRepairId = res.repair_id;
        }

        if (devices.length === 1) {
            showToast(`Repair ${firstRepairId} submitted successfully! 🎉`, 'success');
        } else {
            const total = devices.reduce((s,d)=>s+d.aiEstimate,0);
            showToast(`${devices.length} repair requests submitted! Total Estimate: ₹${total.toLocaleString('en-IN')} 🎉`, 'success');
        }
        router.navigate('/customer');
    } catch (err) {
        showToast(err.message || 'Kuch galat ho gaya. Please dobara try karein.', 'error');
        btn.innerHTML = t('submitBtn');
        btn.disabled = false;
    }
}

// Legacy function alias for backward compatibility
async function handleSubmitRepair(e) {
    if (e) e.preventDefault();
    await handleSubmitAllRepairs();
}

/** Customer Invoices */
async function renderCustomerInvoices() {
    showLoading();
    try {
        const [bills, activeOffers] = await Promise.all([
            api.get('/bills/'),
            api.get('/bills/offers/active').catch(() => [])
        ]);
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

                <!-- Active Festival & Special Offers Banner -->
                ${activeOffers && activeOffers.length > 0 ? `
                    <div class="card" style="margin-bottom:20px;background:linear-gradient(135deg,rgba(255,183,77,0.15),rgba(255,112,67,0.12));border:1px solid #f59e0b;padding:16px;border-radius:12px">
                        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
                            <span style="font-size:1.5rem">🎁</span>
                            <div>
                                <strong style="font-size:1rem;color:#f59e0b">Special & Festival Offers Active!</strong>
                                <div style="font-size:0.8rem;color:var(--text-muted)">Use these discount coupon codes during billing or payment checkout.</div>
                            </div>
                        </div>
                        <div style="display:flex;flex-wrap:wrap;gap:10px">
                            ${activeOffers.map(o => `
                                <div style="background:var(--surface);padding:8px 14px;border-radius:8px;border:1px dashed #f59e0b;display:flex;align-items:center;gap:10px">
                                    <div>
                                        <div style="font-weight:700;letter-spacing:1px;color:#f59e0b">${o.code}</div>
                                        <div style="font-size:0.75rem;color:var(--text-muted)">${o.title} (${o.discount_type === 'percentage' ? o.discount_value + '% OFF' : '₹' + o.discount_value + ' OFF'}${o.min_bill_amount ? ', Min ₹' + o.min_bill_amount : ''})</div>
                                    </div>
                                    <button class="btn btn-outline btn-sm" onclick="navigator.clipboard.writeText('${o.code}');showToast('Copied ${o.code} to clipboard!','success')" style="padding:2px 8px;font-size:0.75rem">📋 Copy</button>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}

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
                                        <td class="font-mono">
                                            ${b.bill_number}
                                            ${b.applied_coupon ? `<div style="font-size:0.7rem;color:#f59e0b">🎟️ ${b.applied_coupon} (-₹${b.discount_amount})</div>` : ''}
                                        </td>
                                        <td class="font-mono text-primary-color">${b.repair_id}</td>
                                        <td>${b.brand} ${b.model}</td>
                                        <td><strong>${formatCurrency(b.total_amount)}</strong></td>
                                        <td>${statusBadge(b.payment_status)}</td>
                                        <td style="font-size:0.8rem;color:var(--text-muted)">${formatDate(b.created_at)}</td>
                                        <td>
                                            <div class="flex gap-2 items-center flex-wrap">
                                                <button onclick="api.download('/bills/${b.id}/pdf', 'Invoice-${b.bill_number}.pdf')" class="btn btn-outline btn-sm">⬇ PDF</button>
                                                ${b.payment_status === 'Unpaid' || b.payment_status === 'Failed' ? `
                                                    ${!b.applied_coupon ? `
                                                        <button onclick="openApplyCouponModal(${b.id}, '${b.bill_number}', ${b.total_amount})" class="btn btn-outline btn-sm" style="border-color:#f59e0b;color:#f59e0b">
                                                            🎟️ Coupon
                                                        </button>
                                                    ` : ''}
                                                    <button onclick="openCustomerUpiPaymentModal(${b.id}, '${b.bill_number}', ${b.total_amount})" class="btn btn-primary btn-sm" style="background:#16a34a;border-color:#16a34a">
                                                        💳 Pay UPI
                                                    </button>
                                                ` : b.payment_status === 'Pending' ? `
                                                    <span class="badge badge-warning" style="font-size:0.75rem">⏳ Verification Pending</span>
                                                ` : '<span class="badge badge-success" style="font-size:0.75rem">Paid ✅</span>'}
                                            </div>
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

/** Open Apply Coupon Modal */
function openApplyCouponModal(billId, billNumber, currentAmount) {
    const overlay = showModal(`
        <div class="modal-header">
            <span class="modal-title">🎟️ Apply Discount / Festival Coupon</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="padding:10px 0">
            <div style="font-size:0.9rem;color:var(--text-muted);margin-bottom:8px">Invoice #${billNumber} | Current: <b>${formatCurrency(currentAmount)}</b></div>
            <div class="form-group" style="margin-bottom:12px">
                <label class="form-label">Enter Coupon Code</label>
                <input type="text" class="form-control" id="coupon-code-input" placeholder="e.g. FESTIVE10, WELCOME50" style="text-transform:uppercase;font-weight:700">
            </div>
            <p style="font-size:0.8rem;color:var(--text-muted);margin-bottom:16px">
                Discounts apply instantly on taxable parts/services and recalculate total bill with GST.
            </p>
            <div class="flex justify-end gap-2">
                <button class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                <button class="btn btn-primary" id="apply-coupon-submit-btn" style="background:#f59e0b;border-color:#f59e0b">Apply Coupon</button>
            </div>
        </div>
    `);

    const submitBtn = overlay.querySelector('#apply-coupon-submit-btn');
    const inputEl = overlay.querySelector('#coupon-code-input');

    submitBtn.onclick = async () => {
        const code = (inputEl?.value || '').trim();
        if (!code) {
            inputEl?.classList.add('animate-shake');
            setTimeout(() => inputEl?.classList.remove('animate-shake'), 350);
            showToast('Please enter a coupon code', 'warning');
            return;
        }
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px"></div> Applying...';
        try {
            const res = await api.post(`/bills/${billId}/apply-offer`, { coupon_code: code });
            showToast(`Coupon applied! New Total: ${formatCurrency(res.new_total)} 🎉`, 'success');
            closeModal(overlay);
            renderCustomerInvoices();
        } catch (err) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Apply Coupon';
            inputEl?.classList.add('animate-shake');
            setTimeout(() => inputEl?.classList.remove('animate-shake'), 350);
            showToast(err.message || 'Failed to apply coupon', 'error');
        }
    };
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

/** Customer Real UPI QR Payment Modal */
async function openCustomerUpiPaymentModal(billId, billNumber, amount) {
    const overlay = showModal(`
        <div class="modal-header">
            <span class="modal-title">💳 Real UPI Payment QR</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="text-align:center;padding:10px 0">
            <div style="font-size:0.9rem;color:var(--text-muted);margin-bottom:4px">Invoice #${billNumber}</div>
            <div style="font-size:1.8rem;font-weight:800;color:var(--primary);margin-bottom:12px">${formatCurrency(amount)}</div>
            
            <div id="upi-qr-box" style="display:flex;justify-content:center;align-items:center;min-height:220px">
                <div class="spinner" style="margin:auto;width:40px;height:40px"></div>
            </div>

            <p style="font-size:0.85rem;color:var(--text-secondary);margin-top:12px">
                Scan with <b>Google Pay, PhonePe, Paytm, BHIM</b> or any UPI App to pay.
            </p>

            <div id="upi-intent-link-container" style="margin-top:10px"></div>

            <hr class="divider" style="margin:16px 0">

            <div style="text-align:left">
                <div class="form-group" style="margin-bottom:12px">
                    <label class="form-label" style="font-size:0.8rem">UPI Reference / UTR Number (Mandatory for verification)</label>
                    <input type="text" class="form-control" id="upi-payment-ref" placeholder="e.g. 423987123456" required>
                </div>
                <button class="btn btn-primary w-full" id="confirm-pay-btn" style="background:#16a34a;border-color:#16a34a;padding:10px">
                    ✅ I Have Paid — Submit for Verification
                </button>
            </div>
        </div>
    `);

    try {
        const qrData = await api.get(`/bills/${billId}/upi-qr`);
        const box = overlay.querySelector('#upi-qr-box');
        box.innerHTML = `
            <div style="padding:12px;background:#ffffff;border-radius:12px;display:inline-block;box-shadow:0 4px 12px rgba(0,0,0,0.15)">
                <img src="data:image/png;base64,${qrData.qr_code}" alt="UPI QR Code" style="width:200px;height:200px;display:block">
            </div>
        `;

        if (qrData.upi_intent) {
            const linkBox = overlay.querySelector('#upi-intent-link-container');
            linkBox.innerHTML = `
                <a href="${qrData.upi_intent}" class="btn btn-outline btn-sm" style="display:inline-flex;align-items:center;gap:6px">
                    📱 Open In UPI App (Mobile)
                </a>
            `;
        }

        const confirmBtn = overlay.querySelector('#confirm-pay-btn');
        confirmBtn.onclick = async () => {
            const utr = (overlay.querySelector('#upi-payment-ref')?.value || '').trim();
            if (!utr) {
                showToast('Kripaya payment ke baad UTR / Transaction Reference Number enter karein', 'warning');
                return;
            }
            const utrRegex = /^[A-Za-z0-9]{10,22}$/;
            if (!utrRegex.test(utr) || new Set(utr.toLowerCase()).size <= 2) {
                showToast('Kripaya valid 10-22 character alphanumeric UTR / Transaction reference daalein (e.g. 423987123456)', 'warning');
                return;
            }
            confirmBtn.disabled = true;
            confirmBtn.innerText = 'Submitting... ⏳';
            try {
                const res = await api.post(`/bills/${billId}/pay-online`, {
                    payment_method: 'UPI',
                    transaction_id: utr
                });
                showToast(res.message || 'Payment submitted! Admin verification pending.', 'info');
                overlay.remove();
                renderCustomerInvoices();
            } catch (err) {
                confirmBtn.disabled = false;
                confirmBtn.innerText = '✅ I Have Paid — Submit for Verification';
                showToast(err.message || 'Payment submission failed', 'error');
            }
        };
    } catch (e) {
        showToast('Failed to load UPI QR: ' + e.message, 'error');
    }
}

/** ----------------------------------------------------
 * Customer Help & Support Tickets
 * ---------------------------------------------------- */
async function renderCustomerSupport() {
    showLoading();
    try {
        const [tickets, repairs] = await Promise.all([
            api.get('/support/tickets'),
            api.get('/repairs/').catch(() => [])
        ]);

        setContent(`
            <div class="page">
                <div class="page-header">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
                        <div>
                            <div class="page-title">🎧 Help & Support Desk</div>
                            <div class="page-subtitle">Track help tickets or reach shop admin for repair / billing inquiries</div>
                        </div>
                        <div style="display:flex;gap:8px">
                            ${langToggleBtn()}
                            <button class="btn btn-primary" onclick="openNewCustomerTicketModal()">➕ Raise Ticket</button>
                        </div>
                    </div>
                </div>

                <div class="stats-grid" style="margin-bottom:24px">
                    <div class="stat-card">
                        <div class="stat-icon">📩</div>
                        <div class="stat-value">${tickets.length}</div>
                        <div class="stat-label">Total Tickets</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">⏳</div>
                        <div class="stat-value">${tickets.filter(t => t.status === 'Open' || t.status === 'In Progress').length}</div>
                        <div class="stat-label">Active Tickets</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon">✅</div>
                        <div class="stat-value">${tickets.filter(t => t.status === 'Resolved' || t.status === 'Closed').length}</div>
                        <div class="stat-label">Resolved</div>
                    </div>
                </div>

                ${tickets.length === 0 ? `
                    <div class="empty-state card">
                        <div class="empty-state-icon">🎧</div>
                        <div class="empty-state-title">No support tickets yet</div>
                        <div class="text-muted" style="margin-bottom:16px">Need help with a repair, bill, warranty, or delivery? Create your first ticket!</div>
                        <button class="btn btn-primary" onclick="openNewCustomerTicketModal()">➕ Raise New Ticket</button>
                    </div>
                ` : `
                    <div class="dashboard-grid">
                        ${tickets.map(t => `
                            <div class="card cursor-pointer" onclick="openCustomerTicketDetailModal(${t.id})" style="border-left:4px solid ${t.status === 'Resolved' ? 'var(--success)' : t.status === 'Closed' ? 'var(--text-muted)' : '#3b82f6'}">
                                <div class="flex justify-between items-center mb-2">
                                    <span class="font-mono text-primary-color" style="font-weight:700">${t.ticket_number}</span>
                                    ${statusBadge(t.status)}
                                </div>
                                <div style="font-weight:600;font-size:1.05rem;margin-bottom:6px">${t.subject}</div>
                                <div style="font-size:0.8rem;color:var(--text-muted);display:flex;gap:12px;flex-wrap:wrap">
                                    <span>Category: <b>${t.category}</b></span>
                                    <span>Priority: <b>${t.priority}</b></span>
                                    ${t.repair_id ? `<span>Repair: <b>${t.repair_id}</b></span>` : ''}
                                </div>
                                <div style="margin-top:10px;font-size:0.75rem;color:var(--text-muted);display:flex;justify-content:space-between">
                                    <span>Created: ${formatDate(t.created_at)}</span>
                                    <span style="color:var(--primary);font-weight:600">Open Chat 💬</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                `}
            </div>
        `);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

/** Open Modal to Raise New Customer Ticket */
async function openNewCustomerTicketModal() {
    let repairs = [];
    try {
        repairs = await api.get('/repairs/');
    } catch (e) { }

    const overlay = showModal(`
        <div class="modal-header">
            <span class="modal-title">🎧 Raise New Support Ticket</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <form id="raise-ticket-form" style="padding:10px 0">
            <div class="form-group" style="margin-bottom:12px">
                <label class="form-label">Subject *</label>
                <input type="text" class="form-control" id="ticket-subject" placeholder="e.g. Query regarding Fan Repair completion date" required minlength="5">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
                <div class="form-group">
                    <label class="form-label">Category</label>
                    <select class="form-control" id="ticket-category">
                        <option value="General">General Inquiry</option>
                        <option value="Repair Status">Repair Status</option>
                        <option value="Billing">Billing / Payment</option>
                        <option value="Warranty">Warranty Claim</option>
                        <option value="Delivery">Pickup / Delivery</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Priority</label>
                    <select class="form-control" id="ticket-priority">
                        <option value="Normal">Normal</option>
                        <option value="High">High</option>
                        <option value="Urgent">Urgent</option>
                    </select>
                </div>
            </div>
            <div class="form-group" style="margin-bottom:12px">
                <label class="form-label">Related Repair Job (Optional)</label>
                <select class="form-control" id="ticket-repair-id">
                    <option value="">-- None / General Question --</option>
                    ${repairs.map(r => `<option value="${r.id}">${r.repair_id} - ${r.brand} ${r.model} (${r.status})</option>`).join('')}
                </select>
            </div>
            <div class="form-group" style="margin-bottom:16px">
                <label class="form-label">Describe your issue / question in detail *</label>
                <textarea class="form-control" id="ticket-msg" rows="4" placeholder="Kripaya apni samasya detail mein batayein..." required minlength="10"></textarea>
            </div>
            <div class="flex justify-end gap-2">
                <button type="button" class="btn btn-outline" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                <button type="submit" class="btn btn-primary" id="ticket-submit-btn">Submit Ticket</button>
            </div>
        </form>
    `);

    overlay.querySelector('#raise-ticket-form').onsubmit = async (e) => {
        e.preventDefault();
        const subject = overlay.querySelector('#ticket-subject').value.trim();
        const category = overlay.querySelector('#ticket-category').value;
        const priority = overlay.querySelector('#ticket-priority').value;
        const repVal = overlay.querySelector('#ticket-repair-id').value;
        const message = overlay.querySelector('#ticket-msg').value.trim();
        const submitBtn = overlay.querySelector('#ticket-submit-btn');

        submitBtn.disabled = true;
        submitBtn.innerText = 'Creating... ⏳';

        try {
            await api.post('/support/tickets', {
                subject,
                category,
                priority,
                repair_id: repVal ? parseInt(repVal) : null,
                message
            });
            showToast('Support ticket raised successfully! Support team will respond shortly.', 'success');
            overlay.remove();
            renderCustomerSupport();
        } catch (err) {
            submitBtn.disabled = false;
            submitBtn.innerText = 'Submit Ticket';
            showToast(err.message || 'Failed to raise ticket', 'error');
        }
    };
}

/** Open Ticket Chat Thread Modal for Customer */
async function openCustomerTicketDetailModal(ticketId) {
    const overlay = showModal(`
        <div class="modal-header">
            <span class="modal-title">💬 Support Conversation</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div id="cust-ticket-content" style="padding:10px 0;min-height:260px;display:flex;justify-content:center;align-items:center">
            <div class="spinner"></div>
        </div>
    `);

    async function loadData() {
        try {
            const data = await api.get(`/support/tickets/${ticketId}`);
            const t = data.ticket;
            const messages = data.messages || [];

            overlay.querySelector('#cust-ticket-content').innerHTML = `
                <div style="width:100%">
                    <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border);padding-bottom:10px;margin-bottom:12px">
                        <div>
                            <strong style="font-size:1.1rem">${t.ticket_number}: ${t.subject}</strong>
                            <div style="font-size:0.8rem;color:var(--text-muted);margin-top:2px">
                                Category: <b>${t.category}</b> | Priority: <b>${t.priority}</b> ${t.repair_id ? '| Repair: ' + t.repair_id : ''}
                            </div>
                        </div>
                        ${statusBadge(t.status)}
                    </div>

                    <!-- Message Thread Box -->
                    <div style="max-height:300px;overflow-y:auto;display:flex;flex-direction:column;gap:10px;padding:8px 4px;margin-bottom:16px;background:var(--surface-2);border-radius:8px">
                        ${messages.length === 0 ? '<div class="text-muted" style="text-align:center;padding:16px">No messages yet.</div>' : messages.map(m => `
                            <div style="display:flex;flex-direction:column;align-self:${m.sender_role === 'customer' ? 'flex-end' : 'flex-start'};max-width:85%">
                                <div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:2px;align-self:${m.sender_role === 'customer' ? 'flex-end' : 'flex-start'}">
                                    <b>${m.sender_name}</b> (${m.sender_role}) • ${formatDate(m.created_at)}
                                </div>
                                <div style="background:${m.sender_role === 'customer' ? 'var(--primary)' : 'var(--surface)'};color:${m.sender_role === 'customer' ? '#fff' : 'var(--text)'};padding:10px 14px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.08);white-space:pre-wrap;font-size:0.9rem">
                                    ${m.message}
                                </div>
                            </div>
                        `).join('')}
                    </div>

                    ${t.status === 'Closed' ? `
                        <div class="badge badge-secondary w-full" style="text-align:center;padding:8px">This ticket is closed.</div>
                    ` : `
                        <form id="cust-ticket-reply-form" style="display:flex;gap:8px">
                            <input type="text" class="form-control" id="cust-reply-msg" placeholder="Type your reply here..." required style="flex:1">
                            <button type="submit" class="btn btn-primary" id="cust-reply-btn">Reply 💬</button>
                        </form>
                    `}
                </div>
            `;

            const replyForm = overlay.querySelector('#cust-ticket-reply-form');
            if (replyForm) {
                replyForm.onsubmit = async (e) => {
                    e.preventDefault();
                    const input = overlay.querySelector('#cust-reply-msg');
                    const msg = input.value.trim();
                    if (!msg) return;
                    const rBtn = overlay.querySelector('#cust-reply-btn');
                    rBtn.disabled = true;
                    try {
                        await api.post(`/support/tickets/${ticketId}/reply`, { message: msg });
                        input.value = '';
                        await loadData();
                    } catch (err) {
                        showToast(err.message || 'Failed to send reply', 'error');
                        rBtn.disabled = false;
                    }
                };
            }
        } catch (e) {
            overlay.querySelector('#cust-ticket-content').innerHTML = `<div class="text-danger">${e.message}</div>`;
        }
    }

    loadData();
}


/** ─── CUSTOMER OFFERS & COUPONS ─────────────────────────── */
async function renderCustomerOffers() {
    showLoading();
    try {
        const offers = await api.get('/bills/offers').catch(() => []);
        const today = new Date().toISOString().slice(0,10);
        const activeOffers = offers.filter(o => {
            if (o.is_active !== 1) return false;
            if (o.valid_from && today < o.valid_from) return false;
            if (o.valid_until && today > o.valid_until) return false;
            return true;
        });
        
        setContent(`
            <div class="page">
                <div class="page-header">
                    <div class="page-title">🎁 Offers & Coupons</div>
                    <div class="page-subtitle">Apply these coupons when paying your repair bill</div>
                </div>
                
                ${activeOffers.length === 0 ? `
                    <div class="empty-state card">
                        <div class="empty-state-icon">🎁</div>
                        <div class="empty-state-title">No Active Offers</div>
                        <div class="text-muted">Check back soon for festival discounts and special offers!</div>
                    </div>
                ` : `
                    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px">
                        ${activeOffers.map(o => {
                            const isPct = o.discount_type === 'percentage';
                            const discLabel = isPct ? o.discount_value + '% OFF' : '₹' + o.discount_value + ' OFF';
                            const expiryStr = o.valid_until ? 'Valid till: ' + new Date(o.valid_until).toLocaleDateString('en-IN', {day:'2-digit',month:'short',year:'numeric'}) : 'No Expiry';
                            return `
                                <div class="card" style="border:1px dashed var(--primary);position:relative;overflow:hidden">
                                    <div style="position:absolute;top:0;right:0;background:var(--primary);color:white;padding:4px 12px;font-size:0.75rem;font-weight:700;border-bottom-left-radius:8px">${discLabel}</div>
                                    <div style="margin-top:8px">
                                        <div style="font-size:1.4rem;font-weight:800;color:var(--primary);font-family:monospace;letter-spacing:2px">${o.code}</div>
                                        <div style="font-weight:600;margin:4px 0">${o.title}</div>
                                        <div style="font-size:0.82rem;color:var(--text-muted);margin-bottom:8px">${o.description || ''}</div>
                                        <div style="font-size:0.78rem;display:flex;flex-direction:column;gap:3px">
                                            ${o.min_bill_amount > 0 ? `<span>Min Bill: <b>₹${o.min_bill_amount}</b></span>` : ''}
                                            ${o.max_discount ? `<span>Max Discount: <b>₹${o.max_discount}</b></span>` : ''}
                                            <span style="color:var(--text-muted)">${expiryStr}</span>
                                        </div>
                                        <button class="btn btn-outline btn-sm w-full" style="margin-top:12px;border-color:var(--primary);color:var(--primary)" onclick="copyToClipboard('${o.code}')">
                                            📋 Copy Code
                                        </button>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                `}
                
                <div class="card" style="margin-top:24px">
                    <div style="font-weight:600;font-size:1rem;margin-bottom:12px">💡 How to Apply Coupon</div>
                    <ol style="font-size:0.9rem;color:var(--text-muted);padding-left:20px;line-height:2">
                        <li>Go to <b>Invoices</b> section when your repair is billed</li>
                        <li>Enter coupon code in the <b>"Apply Coupon"</b> box</li>
                        <li>Click <b>Apply</b> to see your discount</li>
                        <li>Discount is verified and applied securely</li>
                    </ol>
                </div>
            </div>
        `);
    } catch(e) { showToast(e.message, 'error'); }
}

function copyToClipboard(text) {
    navigator.clipboard?.writeText(text).then(() => {
        showToast('Coupon code copied: ' + text, 'success');
    }).catch(() => {
        showToast('Code: ' + text, 'info');
    });
}

async function applyCoupon(billId) {
    const code = document.getElementById('coupon-' + billId)?.value.trim();
    if (!code) { showToast('Please enter a coupon code', 'warning'); return; }
    try {
        const res = await api.post('/bills/apply-offer', { bill_id: billId, offer_code: code.toUpperCase() });
        showToast(res.message, 'success');
        renderCustomerInvoices();
    } catch(e) { showToast(e.message, 'error'); }
}

async function removeCoupon(billId) {
    try {
        await api.delete('/bills/apply-offer/' + billId);
        showToast('Coupon removed', 'info');
        renderCustomerInvoices();
    } catch(e) { showToast(e.message, 'error'); }
}

function openItemClaimModal(warrantyId, itemName) {
    showModal(`
        <div class="modal-header">
            <span class="modal-title">🔧 Warranty Claim: ${itemName}</span>
            <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        </div>
        <div style="padding:10px;background:rgba(249,115,22,0.08);border:1px solid rgba(249,115,22,0.2);border-radius:8px;margin-bottom:12px;font-size:0.85rem">
            Describe the issue with <b>${itemName}</b>. Our team will review and respond within 24 hours.
        </div>
        <div class="form-group">
            <label class="form-label">Issue Description <span class="text-danger">*</span></label>
            <textarea class="form-control" id="ic-desc" rows="3" placeholder="Describe the problem clearly..."></textarea>
        </div>
        <button class="btn btn-primary w-full" onclick="submitItemClaim(${warrantyId})">Submit Claim</button>
    `);
}
async function submitItemClaim(warrantyId) {
    const desc = document.getElementById('ic-desc')?.value.trim();
    if (!desc || desc.length < 10) { showToast('Please describe the issue (min 10 chars)', 'warning'); return; }
    try {
        const res = await api.post('/warranties/item-claim', { item_warranty_id: warrantyId, issue_description: desc });
        showToast(res.message, 'success');
        document.querySelector('.modal-overlay')?.remove();
    } catch(e) { showToast(e.message, 'error'); }
}
