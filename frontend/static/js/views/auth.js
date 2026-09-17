/**
 * Mistri Auth Views - Landing, Login, Register
 * v7: Real Gmail/phone/password validation + real Google OAuth support
 */

/** Landing Page */
function renderLandingPage() {
    const user = api.getUser();
    if (user) {
        router.redirectByRole(user.role);
        return;
    }
    document.getElementById('navbar').style.display = 'none';
    setContent(`
        <div class="landing-hero">
            <div class="hero-badge">⚡ AI-Powered Electrical/Electronic Appliance Repair</div>
            <h1 class="hero-title">Fix It Faster with <span>Mistri</span></h1>
            <p class="hero-desc">The complete management platform for electrical/electronic appliance repair shops. Track fan, cooler, mixer, motor, geyser & pump repairs — all in one smart dashboard.</p>
            <div class="hero-cta">
                <button class="btn btn-primary" onclick="router.navigate('/register')" style="font-size:1rem;padding:14px 32px">🚀 Get Started Free</button>
                <button class="btn btn-outline" onclick="router.navigate('/login')" style="font-size:1rem;padding:14px 32px">🔑 Login</button>
            </div>
            <div class="hero-img-row">
                <img src="/static/img/appliances_hero.png" alt="Electrical/Electronic Appliances" class="hero-img-appliances">
                <img src="/static/img/technician.png" alt="Expert Technician" class="hero-img-technician">
            </div>
            <div class="hero-features">
                <div class="feature-card">
                    <div class="feature-icon">🤖</div>
                    <div class="feature-title">AI Cost Estimator</div>
                    <div class="feature-desc">Get instant repair cost estimates for fans, coolers, motors & more using our smart AI before the customer even drops off the appliance.</div>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">📍</div>
                    <div class="feature-title">Real-Time Tracking</div>
                    <div class="feature-desc">Track repair status with a unique QR code. From Received to Delivered — always stay updated via SMS or app.</div>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">📊</div>
                    <div class="feature-title">Analytics Dashboard</div>
                    <div class="feature-desc">Property admin analytics with revenue charts, technician performance, and spare parts inventory insights.</div>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">📄</div>
                    <div class="feature-title">Auto PDF Invoices</div>
                    <div class="feature-desc">Generate professional PDF invoices instantly. Track payments and export reports in CSV.</div>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">📦</div>
                    <div class="feature-title">Spare Parts Inventory</div>
                    <div class="feature-desc">Track capacitors, coils, motors, brushes — get low-stock alerts and manage suppliers effortlessly.</div>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">👥</div>
                    <div class="feature-title">Multi-Role Access</div>
                    <div class="feature-desc">Separate dashboards for Admin, Technician, and Customer with secure role-based permissions.</div>
                </div>
            </div>
            <div style="margin-top:48px;text-align:center;color:var(--text-muted);font-size:0.85rem">
                <div style="margin-bottom:8px;font-weight:600">Demo Login Credentials</div>
                <div style="display:flex;gap:16px;flex-wrap:wrap;justify-content:center">
                    <span>🔴 <b>Admin:</b> admin@mistri.com / Admin@123</span>
                    <span>🟡 <b>Staff:</b> raju@mistri.com / Staff@123</span>
                    <span>🟢 <b>Customer:</b> arun@gmail.com / Customer@123</span>
                </div>
            </div>
        </div>
    `);
}

/** Login Page */
function renderLogin() {
    document.getElementById('navbar').style.display = 'none';
    setContent(`
        <div class="auth-page">
            <!-- Left Panel: Branding + Image -->
            <div class="auth-left">
                <div class="auth-left-content">
                    <div class="auth-brand">
                        <span class="auth-brand-icon">⚡</span>
                        <span class="auth-brand-name">Mistri</span>
                    </div>
                    <img src="/static/img/appliances_hero.png" alt="Electrical/Electronic Appliances" class="auth-hero-img">
                    <div class="auth-tagline">Your <span>Electrical/Electronic Repair</span><br>Business, Supercharged</div>
                    <div class="auth-tagline-sub">Manage fan, cooler, mixer, motor & geyser repairs with AI-powered cost estimates and real-time tracking.</div>
                    <div class="auth-appliance-pills">
                        <span class="appliance-pill">🌀 Fan Repair</span>
                        <span class="appliance-pill">❄️ Cooler</span>
                        <span class="appliance-pill">🥤 Mixer/Grinder</span>
                        <span class="appliance-pill">⚙️ Motor</span>
                        <span class="appliance-pill">🔥 Geyser</span>
                        <span class="appliance-pill">💧 Pump</span>
                    </div>
                </div>
            </div>

            <!-- Right Panel: Login Form -->
            <div class="auth-right">
                <div class="auth-card">
                    <div class="auth-title">Welcome Back 👋</div>
                    <div class="auth-sub">Sign in to your Mistri account</div>

                    <!-- Google Sign-In Button -->
                    <button class="btn btn-google" onclick="handleGoogleLogin()" id="google-btn">
                        <span class="google-icon"></span>
                        Continue with Google
                    </button>

                    <div class="auth-divider">or sign in with email</div>

                    <form id="login-form" onsubmit="handleLogin(event)" novalidate>
                        <div class="form-group">
                            <label class="form-label">Email Address</label>
                            <input type="email" class="form-control" id="login-email" placeholder="you@gmail.com or admin@mistri.com" required>
                            <div class="field-error" id="login-email-err" style="display:none;color:var(--danger);font-size:0.78rem;margin-top:4px"></div>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Password</label>
                            <div style="position:relative">
                                <input type="password" class="form-control" id="login-password" placeholder="••••••••" required style="padding-right:44px">
                                <button type="button" onclick="togglePasswordVisibility('login-password', 'pw-eye-1')" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;font-size:1.1rem;color:var(--text-muted)" id="pw-eye-1">👁</button>
                            </div>
                        </div>
                        <button type="submit" class="btn btn-primary w-full" id="login-btn" style="margin-top:8px">
                            🔑 Sign In
                        </button>
                    </form>

                    <div class="auth-switch" style="margin-top:16px">
                        Don't have an account? <a onclick="router.navigate('/register')">Register here</a>
                    </div>
                    <div class="auth-switch" style="margin-top:6px">
                        <a onclick="router.navigate('/')">← Back to home</a>
                    </div>

                    <div class="divider"></div>
                    <div style="font-size:0.75rem;color:var(--text-muted);text-align:center">
                        <div style="font-weight:600;margin-bottom:6px">⚡ Quick Demo Login</div>
                        <div style="display:flex;flex-direction:column;gap:5px">
                            <a onclick="quickLogin('admin@mistri.com','Admin@123')" style="cursor:pointer;color:var(--danger)">🔴 Login as Admin</a>
                            <a onclick="quickLogin('raju@mistri.com','Staff@123')" style="cursor:pointer;color:var(--warning)">🟡 Login as Staff</a>
                            <a onclick="quickLogin('arun@gmail.com','Customer@123')" style="cursor:pointer;color:var(--success)">🟢 Login as Customer</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `);
}

async function handleLogin(e) {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    btn.innerHTML = '<div class="spinner"></div> Signing in...';
    btn.disabled = true;
    try {
        const res = await api.login(email, password);
        showToast(`Welcome back, ${res.name}! 👋`, 'success');
        router.redirectByRole(res.role);
    } catch (err) {
        showToast(err.message, 'error');
        btn.innerHTML = '🔑 Sign In';
        btn.disabled = false;
    }
}

async function quickLogin(email, password) {
    document.getElementById('login-email').value = email;
    document.getElementById('login-password').value = password;
    document.getElementById('login-btn').click();
}

function showGoogleOAuthConfigModal() {
    const existing = document.getElementById('google-config-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'google-config-modal';
    modal.style.cssText = `
        position: fixed; inset: 0; background: rgba(0,0,0,0.75);
        display: flex; align-items: center; justify-content: center;
        z-index: 99999; padding: 20px; backdrop-filter: blur(4px);
    `;
    modal.innerHTML = `
        <div style="background: var(--bg-card, #161b22); border: 1px solid var(--border, #30363d); border-radius: 12px; max-width: 520px; width: 100%; padding: 24px; box-shadow: 0 16px 32px rgba(0,0,0,0.5);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <h3 style="margin:0; font-size:1.2rem; display:flex; align-items:center; gap:8px;">
                    <span>⚙️</span> Google OAuth Setup Required
                </h3>
                <button onclick="document.getElementById('google-config-modal').remove()" style="background:transparent;border:none;color:var(--text-muted,#8b949e);font-size:1.4rem;cursor:pointer;">&times;</button>
            </div>
            <p style="color:var(--text-secondary,#c9d1d9); font-size:0.9rem; line-height:1.5; margin-bottom:16px;">
                Google Sign-In requires OAuth 2.0 credentials from Google Cloud Console. To enable it:
            </p>
            <div style="background:var(--bg-input, #0d1117); border-radius:8px; padding:12px 16px; margin-bottom:16px; font-size:0.85rem; line-height:1.6; color:#58a6ff; font-family:monospace;">
                1. Open <b>backend/.env</b><br>
                2. Set <b>GOOGLE_CLIENT_ID</b>=&lt;your_client_id&gt;<br>
                3. Set <b>GOOGLE_CLIENT_SECRET</b>=&lt;your_client_secret&gt;<br>
                4. Restart server
            </div>
            <div style="font-size:0.85rem; color:var(--text-muted,#8b949e); margin-bottom:20px;">
                Authorized redirect URI should be:<br>
                <code style="background:rgba(255,255,255,0.08);padding:2px 6px;border-radius:4px;">http://localhost:8000/api/auth/google/callback</code>
            </div>
            <div style="display:flex; justify-content:flex-end; gap:10px;">
                <button class="btn btn-primary" onclick="document.getElementById('google-config-modal').remove()">Understood</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

window.showCompleteProfileModal = function(userName, role) {
    const existing = document.getElementById('complete-profile-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'complete-profile-modal';
    modal.style.cssText = `
        position: fixed; inset: 0; background: rgba(0,0,0,0.75);
        display: flex; align-items: center; justify-content: center;
        z-index: 99999; padding: 20px; backdrop-filter: blur(4px);
    `;
    modal.innerHTML = `
        <div style="background: var(--bg-card, #161b22); border: 1px solid var(--border, #30363d); border-radius: 12px; max-width: 500px; width: 100%; padding: 24px; box-shadow: 0 16px 32px rgba(0,0,0,0.5);">
            <div style="text-align:center; margin-bottom:20px;">
                <div style="font-size:2.4rem; margin-bottom:8px;">📍</div>
                <h3 style="margin:0; font-size:1.3rem;">Complete Your Profile</h3>
                <p style="color:var(--text-muted,#8b949e); font-size:0.85rem; margin-top:6px;">
                    Hi ${userName || 'Customer'}, please provide your contact and address details to book and track electrical/electronic appliance repairs smoothly.
                </p>
            </div>
            <div id="profile-modal-error" style="display:none; background:rgba(248,81,73,0.15); border:1px solid #f85149; color:#ff7b72; padding:10px 12px; border-radius:6px; font-size:0.85rem; margin-bottom:16px;"></div>
            
            <form id="complete-profile-form" onsubmit="submitCompleteProfile(event, '${role || 'customer'}')">
                <div class="form-group" style="margin-bottom:14px;">
                    <label style="font-size:0.85rem; font-weight:600; display:block; margin-bottom:6px;">
                        Mobile Number <span style="color:var(--danger,#f85149)">*</span>
                    </label>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="background:var(--bg-input,#0d1117); border:1px solid var(--border,#30363d); padding:8px 12px; border-radius:6px; font-size:0.9rem; color:var(--text-muted,#8b949e)">+91</span>
                        <input type="tel" id="cp-phone" class="form-control" placeholder="9876543210" maxlength="10" required style="flex:1;">
                    </div>
                    <small style="color:var(--text-muted,#8b949e); font-size:0.75rem;">10-digit Indian mobile number</small>
                </div>

                <div class="form-group" style="margin-bottom:14px;">
                    <label style="font-size:0.85rem; font-weight:600; display:block; margin-bottom:6px;">
                        Complete Address <span style="color:var(--danger,#f85149)">*</span>
                    </label>
                    <textarea id="cp-address" class="form-control" placeholder="House/Flat no, Building, Street, Colony/Sector" rows="2" required style="resize:none;"></textarea>
                </div>

                <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:20px;">
                    <div class="form-group">
                        <label style="font-size:0.85rem; font-weight:600; display:block; margin-bottom:6px;">Landmark (Optional)</label>
                        <input type="text" id="cp-landmark" class="form-control" placeholder="Near Temple / Park">
                    </div>
                    <div class="form-group">
                        <label style="font-size:0.85rem; font-weight:600; display:block; margin-bottom:6px;">
                            PIN Code <span style="color:var(--danger,#f85149)">*</span>
                        </label>
                        <input type="text" id="cp-pincode" class="form-control" placeholder="110001" maxlength="6" required>
                    </div>
                </div>

                <div style="display:flex; justify-content:flex-end; gap:10px;">
                    <button type="submit" id="cp-submit-btn" class="btn btn-primary" style="width:100%; justify-content:center;">
                        Save &amp; Continue to Dashboard
                    </button>
                </div>
            </form>
        </div>
    `;
    document.body.appendChild(modal);
};

window.submitCompleteProfile = async function(event, role) {
    event.preventDefault();
    const phone = document.getElementById('cp-phone').value.trim();
    const address = document.getElementById('cp-address').value.trim();
    const landmark = document.getElementById('cp-landmark').value.trim();
    const pincode = document.getElementById('cp-pincode').value.trim();
    const errBox = document.getElementById('profile-modal-error');
    const btn = document.getElementById('cp-submit-btn');

    // Validate phone
    if (!/^[6-9]\d{9}$/.test(phone)) {
        errBox.textContent = 'Please enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.';
        errBox.style.display = 'block';
        return;
    }
    // Validate address
    if (address.length < 5) {
        errBox.textContent = 'Please enter your complete address (at least 5 characters).';
        errBox.style.display = 'block';
        return;
    }
    // Validate pincode
    if (!/^[1-9]\d{5}$/.test(pincode)) {
        errBox.textContent = 'Please enter a valid 6-digit Indian PIN code.';
        errBox.style.display = 'block';
        return;
    }

    errBox.style.display = 'none';
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px"></div> Saving...';

    try {
        const res = await api.post('/auth/complete-profile', {
            phone, address, landmark: landmark || null, pincode
        });
        const currentUser = api.getUser() || {};
        currentUser.phone = phone;
        currentUser.address = address;
        currentUser.landmark = landmark;
        currentUser.pincode = pincode;
        currentUser.needs_profile_completion = false;
        localStorage.setItem('mistri_user', JSON.stringify(currentUser));

        const modal = document.getElementById('complete-profile-modal');
        if (modal) modal.remove();

        showToast('Profile completed successfully! Welcome to Mistri 🎉', 'success');
        router.redirectByRole(role || 'customer');
    } catch (err) {
        errBox.textContent = err.message || 'Failed to update profile. Please try again.';
        errBox.style.display = 'block';
        btn.disabled = false;
        btn.textContent = 'Save & Continue to Dashboard';
    }
};

async function handleGoogleLogin() {
    const btn = document.getElementById('google-btn') || document.getElementById('google-reg-btn');
    if (btn) {
        btn.innerHTML = '<div class="spinner" style="width:18px;height:18px;border-width:2px"></div> Connecting to Google...';
        btn.disabled = true;
    }
    try {
        const res = await api.get('/auth/google/url');
        if (res.url) {
            // Open Google OAuth in a popup window
            const width = 520, height = 620;
            const left = Math.max(0, (window.screen.width - width) / 2);
            const top = Math.max(0, (window.screen.height - height) / 2);
            const popup = window.open(
                res.url,
                'google_oauth',
                `width=${width},height=${height},top=${top},left=${left},scrollbars=yes,status=1`
            );

            // Listen for message from popup
            const handleMessage = (event) => {
                if (event.data && event.data.type === 'google_auth_success') {
                    window.removeEventListener('message', handleMessage);
                    api.setToken(event.data.token, {
                        name: event.data.name,
                        role: event.data.role,
                        user_id: event.data.user_id,
                        needs_profile_completion: event.data.needs_profile_completion
                    });
                    if (popup && !popup.closed) popup.close();

                    if (event.data.needs_profile_completion) {
                        window.showCompleteProfileModal(event.data.name, event.data.role);
                    } else {
                        showToast(`Welcome, ${event.data.name}! 🎉`, 'success');
                        router.redirectByRole(event.data.role);
                    }
                } else if (event.data && event.data.type === 'google_auth_error') {
                    window.removeEventListener('message', handleMessage);
                    showToast(event.data.message || 'Google Sign-In failed.', 'error');
                    if (popup && !popup.closed) popup.close();
                    if (btn) {
                        btn.innerHTML = '<span class="google-icon"></span> Continue with Google';
                        btn.disabled = false;
                    }
                }
            };
            window.addEventListener('message', handleMessage);

            // If popup is blocked by browser, fallback to redirect
            if (!popup || popup.closed || typeof popup.closed === 'undefined') {
                window.location.href = res.url;
            }
        } else {
            throw new Error('Could not get Google login URL');
        }
    } catch (err) {
        if (btn) {
            btn.innerHTML = '<span class="google-icon"></span> Continue with Google';
            btn.disabled = false;
        }
        if (err.message && (err.message.includes('not configured') || err.message.includes('503'))) {
            showGoogleOAuthConfigModal();
        } else {
            showToast(err.message || 'Google Sign-In error. Please try email & password.', 'error');
        }
    }
}

function togglePasswordVisibility(inputId, btnId) {
    const input = document.getElementById(inputId);
    const btn = document.getElementById(btnId);
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
    } else {
        input.type = 'password';
        btn.textContent = '👁';
    }
}

// ---------------------------------------------------------------------------
// Validation helpers (frontend mirrors backend)
// ---------------------------------------------------------------------------

function validateGmail(email) {
    const pattern = /^[a-zA-Z0-9._%+\-]+@gmail\.com$/i;
    return pattern.test(email.trim());
}

function validateIndianPhone(phone) {
    if (!phone || !phone.trim()) return true; // optional
    const digits = phone.trim().replace(/[\s\-\+()]/g, '');
    const cleaned = digits.startsWith('91') && digits.length === 12 ? digits.slice(2) : digits;
    return /^[6-9][0-9]{9}$/.test(cleaned);
}

function checkPasswordStrength(password) {
    const checks = {
        length: password.length >= 8,
        upper: /[A-Z]/.test(password),
        lower: /[a-z]/.test(password),
        digit: /[0-9]/.test(password),
        special: /[!@#$%^&*()_+\-=\[\]{};:'"|,.<>?/\\`~]/.test(password)
    };
    const passed = Object.values(checks).filter(Boolean).length;
    return { checks, passed, strong: passed === 5 };
}

function renderPasswordStrengthUI(password, containerId) {
    const { checks, passed } = checkPasswordStrength(password);
    const colors = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#16a34a'];
    const labels = ['Very Weak', 'Weak', 'Fair', 'Good', 'Strong'];
    const color = colors[Math.max(0, passed - 1)];
    const label = labels[Math.max(0, passed - 1)];

    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
        <div style="margin-top:6px">
            <div style="display:flex;gap:3px;margin-bottom:4px">
                ${[1,2,3,4,5].map(i => `<div style="height:4px;flex:1;border-radius:2px;background:${i <= passed ? color : 'var(--border)'}"></div>`).join('')}
            </div>
            <div style="font-size:0.72rem;color:${color};font-weight:600;margin-bottom:6px">${password ? label : ''}</div>
            <div style="display:flex;flex-direction:column;gap:3px;font-size:0.72rem">
                ${[
                    [checks.length, '8+ characters'],
                    [checks.upper, 'Uppercase letter (A-Z)'],
                    [checks.lower, 'Lowercase letter (a-z)'],
                    [checks.digit, 'Number (0-9)'],
                    [checks.special, 'Special character (!@#$%...)']
                ].map(([ok, text]) => `<div style="color:${ok ? '#22c55e' : 'var(--text-muted)'}">${ok ? '✓' : '○'} ${text}</div>`).join('')}
            </div>
        </div>
    `;
}

/** Register Page */
function renderRegister() {
    document.getElementById('navbar').style.display = 'none';
    setContent(`
        <div class="auth-page">
            <!-- Left Panel -->
            <div class="auth-left">
                <div class="auth-left-content">
                    <div class="auth-brand">
                        <span class="auth-brand-icon">⚡</span>
                        <span class="auth-brand-name">Mistri</span>
                    </div>
                    <img src="/static/img/technician.png" alt="Expert Technician" class="auth-hero-img" style="height:280px;object-fit:cover;object-position:top">
                    <div class="auth-tagline">Join <span>Thousands</span> of<br>Repair Shops</div>
                    <div class="auth-tagline-sub">Create your free account and start managing electrical/electronic appliance repairs smarter today.</div>
                    <div class="auth-appliance-pills">
                        <span class="appliance-pill">✅ Free Forever</span>
                        <span class="appliance-pill">🤖 AI Estimates</span>
                        <span class="appliance-pill">📊 Analytics</span>
                        <span class="appliance-pill">📄 PDF Invoices</span>
                    </div>
                </div>
            </div>

            <!-- Right Panel: Register Form -->
            <div class="auth-right">
                <div class="auth-card">
                    <div class="auth-title">Create Account 🚀</div>
                    <div class="auth-sub">Join Mistri to track your repairs</div>

                    <!-- Google Sign-Up Button -->
                    <button class="btn btn-google" onclick="handleGoogleLogin()" id="google-reg-btn">
                        <span class="google-icon"></span>
                        Sign up with Google
                    </button>

                    <div class="auth-divider">or register with email</div>

                    <form id="register-form" onsubmit="handleRegister(event)" novalidate>
                        <div class="form-group">
                            <label class="form-label">Full Name *</label>
                            <input type="text" class="form-control" id="reg-name" placeholder="Ramesh Kumar" required minlength="2">
                            <div class="field-error" id="reg-name-err" style="display:none;color:var(--danger);font-size:0.78rem;margin-top:4px"></div>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label class="form-label">Gmail Address *</label>
                                <input type="email" class="form-control" id="reg-email" placeholder="yourname@gmail.com"
                                    required oninput="validateGmailField(this.value)">
                                <div class="field-error" id="reg-email-err" style="display:none;color:var(--danger);font-size:0.78rem;margin-top:4px"></div>
                            </div>
                            <div class="form-group">
                                <label class="form-label">Phone (10 digits)</label>
                                <input type="tel" class="form-control" id="reg-phone" placeholder="9876543210"
                                    oninput="validatePhoneField(this.value)" maxlength="13">
                                <div class="field-error" id="reg-phone-err" style="display:none;color:var(--danger);font-size:0.78rem;margin-top:4px"></div>
                            </div>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Password *</label>
                            <div style="position:relative">
                                <input type="password" class="form-control" id="reg-password" placeholder="Min 8 chars, includes A-Z, 0-9, !@#"
                                    required oninput="renderPasswordStrengthUI(this.value, 'pw-strength')" style="padding-right:44px">
                                <button type="button" onclick="togglePasswordVisibility('reg-password', 'pw-eye-2')" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;font-size:1.1rem;color:var(--text-muted)" id="pw-eye-2">👁</button>
                            </div>
                            <div id="pw-strength"></div>
                        </div>
                        <button type="submit" class="btn btn-primary w-full" id="register-btn" style="margin-top:12px">
                            🚀 Create Account
                        </button>
                    </form>

                    <div class="auth-switch" style="margin-top:16px">
                        Already have an account? <a onclick="router.navigate('/login')">Sign in</a>
                    </div>
                    <div class="auth-switch" style="margin-top:6px">
                        <a onclick="router.navigate('/')">← Back to home</a>
                    </div>
                    <div style="margin-top:12px;padding:10px;background:var(--surface-2);border-radius:var(--radius-sm);font-size:0.75rem;color:var(--text-muted)">
                        <b>📧 Gmail required:</b> Customers must register with a Gmail address (@gmail.com).<br>
                        <b>🔒 Password requirements:</b> 8+ chars, uppercase, lowercase, number & special character.
                    </div>
                </div>
            </div>
        </div>
    `);
}

function validateGmailField(value) {
    const errEl = document.getElementById('reg-email-err');
    if (!errEl) return;
    if (!value) { errEl.style.display = 'none'; return; }
    if (!validateGmail(value)) {
        errEl.textContent = '❌ Please enter a valid Gmail address (e.g. yourname@gmail.com)';
        errEl.style.display = 'block';
    } else {
        errEl.textContent = '✓ Valid Gmail address';
        errEl.style.color = 'var(--success)';
        errEl.style.display = 'block';
    }
}

function validatePhoneField(value) {
    const errEl = document.getElementById('reg-phone-err');
    if (!errEl) return;
    if (!value || !value.trim()) { errEl.style.display = 'none'; return; }
    if (!validateIndianPhone(value)) {
        errEl.textContent = '❌ Enter a valid 10-digit Indian mobile number (starts with 6-9)';
        errEl.style.color = 'var(--danger)';
        errEl.style.display = 'block';
    } else {
        errEl.textContent = '✓ Valid mobile number';
        errEl.style.color = 'var(--success)';
        errEl.style.display = 'block';
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const btn = document.getElementById('register-btn');

    const name = document.getElementById('reg-name').value.trim();
    const email = document.getElementById('reg-email').value.trim();
    const phone = document.getElementById('reg-phone').value.trim();
    const password = document.getElementById('reg-password').value;

    // Frontend validation
    if (!name || name.length < 2) {
        showToast('Please enter your full name (at least 2 characters).', 'error');
        return;
    }
    if (!validateGmail(email)) {
        showToast('Customers must use a valid Gmail address (e.g. yourname@gmail.com).', 'error');
        return;
    }
    if (phone && !validateIndianPhone(phone)) {
        showToast('Please enter a valid 10-digit Indian mobile number (starts with 6, 7, 8, or 9).', 'error');
        return;
    }
    const pwCheck = checkPasswordStrength(password);
    if (!pwCheck.strong) {
        showToast('Password is too weak! It must have: 8+ chars, uppercase, lowercase, number & special character. Example: MyPass@123', 'error');
        return;
    }

    btn.innerHTML = '<div class="spinner"></div> Creating account...';
    btn.disabled = true;
    try {
        // Normalize phone: strip country code if present
        let phoneClean = phone ? phone.replace(/[\s\-\+()]/g, '') : '';
        if (phoneClean.startsWith('91') && phoneClean.length === 12) phoneClean = phoneClean.slice(2);

        const data = {
            name,
            email: email.toLowerCase(),
            phone: phoneClean || null,
            password,
            role: 'customer'
        };
        const res = await api.register(data);
        showToast(`Account created! Welcome, ${res.name}! 🎉`, 'success');
        router.navigate('/customer');
    } catch (err) {
        showToast(err.message, 'error');
        btn.innerHTML = '🚀 Create Account';
        btn.disabled = false;
    }
}

/** Public Repair Tracker */
async function renderRepairTracker(path) {
    const repairId = path.split('/track/')[1];
    document.getElementById('navbar').style.display = 'none';
    setContent(`<div class="page"><div class="spinner" style="margin:48px auto;width:48px;height:48px;border-width:4px;display:block"></div></div>`);
    try {
        const job = await api.get(`/repairs/track/${repairId}`);
        setContent(`
            <div class="page" style="max-width:600px;margin:0 auto">
                <div style="text-align:center;margin-bottom:32px">
                    <div class="logo-icon" style="font-size:3rem">⚡</div>
                    <div class="logo-text" style="font-family:'Space Grotesk',sans-serif;font-size:1.8rem;font-weight:700">Mistri</div>
                    <div class="text-muted" style="margin-top:4px">Appliance Repair Tracking</div>
                </div>
                <div class="card card-glow">
                    <div class="flex justify-between items-center mb-3">
                        <span class="font-mono text-primary-color" style="font-size:1.1rem;font-weight:700">${job.repair_id}</span>
                        ${statusBadge(job.status)}
                    </div>
                    <h2 style="font-size:1.2rem;margin-bottom:4px">${job.brand} ${job.model}</h2>
                    <div class="text-muted" style="font-size:0.85rem;margin-bottom:16px">${job.device_type} · Customer: ${job.customer_name}</div>
                    <div class="text-secondary" style="font-size:0.9rem;margin-bottom:20px">🔍 Issue: ${job.problem_description}</div>
                    ${renderTimeline(job.status)}
                    ${job.technician_notes ? `
                        <div style="margin-top:16px;padding:12px;background:var(--bg-input);border-radius:var(--radius-sm)">
                            <div style="font-size:0.75rem;color:var(--text-muted)">Technician Notes</div>
                            <div style="font-size:0.875rem;margin-top:4px">${job.technician_notes}</div>
                        </div>
                    ` : ''}
                    ${job.estimated_cost ? `<div style="margin-top:16px;font-size:0.85rem">Estimated Cost: <strong>${formatCurrency(job.estimated_cost)}</strong></div>` : ''}
                    <div style="margin-top:16px;font-size:0.75rem;color:var(--text-muted)">Submitted: ${formatDate(job.created_at)}</div>
                </div>
                <div style="text-align:center;margin-top:24px">
                    <button class="btn btn-outline" onclick="router.navigate('/login')">🔑 Login to Mistri</button>
                </div>
            </div>
        `);
    } catch (e) {
        setContent(`<div class="page"><div class="empty-state"><div class="empty-state-icon">❌</div><div class="empty-state-title">Repair not found</div><div class="text-muted">Check the repair ID and try again.</div></div></div>`);
    }
}
