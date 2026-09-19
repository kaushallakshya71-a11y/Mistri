/**
 * Mistri Client-Side Router
 * Hash-based SPA routing
 */

const router = {
    routes: {},
    currentPath: null,

    register(path, handler) {
        this.routes[path] = handler;
    },

    navigate(path, replace = false) {
        if (replace) {
            history.replaceState(null, '', '#' + path);
        } else {
            history.pushState(null, '', '#' + path);
        }
        this.resolve(path);
    },

    resolve(path) {
        // Special logout action route
        if (path === '/logout') {
            logout();
            return;
        }

        // Auth guard
        const publicRoutes = ['/', '/login', '/register', '/track', '/logout'];
        const user = api.getUser();
        const isPublic = publicRoutes.some(r => path === r || path.startsWith('/track'));

        if (!api.isLoggedIn() && !isPublic) {
            this.navigate('/login', true);
            return;
        }

        // Role-based redirect only when explicitly visiting /login or /register while already logged in
        if (api.isLoggedIn() && (path === '/login' || path === '/register')) {
            this.redirectByRole(user?.role);
            return;
        }

        // Find handler - exact match or prefix match
        let handler = this.routes[path];
        if (!handler) {
            // Check prefix routes
            for (const [route, fn] of Object.entries(this.routes)) {
                if (route.endsWith('*') && path.startsWith(route.slice(0, -1))) {
                    handler = () => fn(path);
                    break;
                }
            }
        }

        if (handler) {
            closeMobileNav();
            this.currentPath = path;
            this._currentRoute = path;
            updateNavbar();
            handler(path);
        } else {
            closeMobileNav();
            this.navigate('/', true);
        }
    },

    redirectByRole(role) {
        const destinations = { admin: '/admin', staff: '/staff', customer: '/customer' };
        this.navigate(destinations[role] || '/', true);
    },

    start() {
        window.addEventListener('popstate', () => {
            const path = location.hash.replace('#', '') || '/';
            this.resolve(path);
        });
        const path = location.hash.replace('#', '') || '/';
        this.resolve(path);
    }
};

/** Update navbar links based on current user role */
function updateNavbar() {
    const user = api.getUser();
    const linksEl = document.getElementById('navbar-links');
    const navbar = document.getElementById('navbar');

    if (!user) {
        navbar.style.display = 'none';
        return;
    }
    navbar.style.display = 'flex';

    // Avatar & dropdown
    document.getElementById('user-avatar').textContent = user.name?.[0]?.toUpperCase() || 'U';
    document.getElementById('dropdown-name').textContent = user.name;
    document.getElementById('dropdown-role').textContent = user.role;

    const links = {
        admin: [
            { label: '📊 Dashboard', path: '/admin' },
            { label: '🔧 Repairs', path: '/admin/repairs' },
            { label: '👥 Staff', path: '/admin/staff' },
            { label: '💳 Bills & Pay', path: '/admin/bills' },
            { label: '🎁 Offers', path: '/admin/offers' },
            { label: '🎧 Support', path: '/admin/support' },
            { label: '📦 Inventory', path: '/admin/inventory' },
            { label: '🛒 Shop', path: '/shop' },
            { label: '📈 Reports', path: '/admin/reports' },
            { label: '🛡️ Warranties', path: '/admin/warranties' },
            { label: '📜 Audit Logs', path: '/admin/audit-logs' },
            { label: '⭐ Feedback', path: '/admin/feedback' },
            { label: '🚪 Logout', path: '/logout', isLogout: true },
        ],
        staff: [
            { label: '🏠 My Jobs', path: '/staff' },
            { label: '💼 Salary & Leaves', path: '/staff/leaves' },
            { label: '📦 Inventory', path: '/staff/inventory' },
            { label: '🛒 Shop', path: '/shop' },
            { label: '🚪 Logout', path: '/logout', isLogout: true },
        ],
        customer: [
            { label: '🏠 Dashboard', path: '/customer' },
            { label: '➕ New Repair', path: '/customer/submit' },
            { label: '📄 Invoices', path: '/customer/invoices' },
            { label: '🎧 Help & Support', path: '/customer/support' },
            { label: '🛒 Shop', path: '/shop' },
            { label: '🚪 Logout', path: '/logout', isLogout: true },
        ],
    };

    const userLinks = links[user.role] || [];
    const currentPath = router.currentPath;

    // Desktop navbar links
    if (linksEl) {
        linksEl.innerHTML = userLinks.map(l =>
            l.isLogout ?
            `<button class="nav-link" onclick="logout()" style="color:#ef4444;font-weight:700;margin-left:auto">${l.label}</button>` :
            `<button class="nav-link ${currentPath === l.path ? 'active' : ''}" onclick="router.navigate('${l.path}')">${l.label}</button>`
        ).join('');
    }

    // Mobile drawer navigation links
    const mobileLinksEl = document.getElementById('mobile-nav-links');
    if (mobileLinksEl) {
        mobileLinksEl.innerHTML = userLinks.filter(l => !l.isLogout).map(l =>
            `<button class="mobile-nav-link ${currentPath === l.path ? 'active' : ''}" onclick="closeMobileNav(); router.navigate('${l.path}')">
                <span>${l.label}</span>
                <span class="mobile-nav-arrow">›</span>
            </button>`
        ).join('');
    }

    // Mobile user profile header
    const mobAvatar = document.getElementById('mobile-user-avatar');
    if (mobAvatar) mobAvatar.textContent = user.name?.[0]?.toUpperCase() || 'U';
    const mobName = document.getElementById('mobile-user-name');
    if (mobName) mobName.textContent = user.name;
    const mobBadge = document.getElementById('mobile-user-role-badge');
    if (mobBadge) {
        mobBadge.textContent = (user.role || 'user').toUpperCase();
        mobBadge.className = `badge badge-${user.role || 'customer'}`;
    }

    // Load notifications count
    loadNotifCount();
}

function openMobileNav() {
    const drawer = document.getElementById('mobile-nav-drawer');
    const overlay = document.getElementById('mobile-nav-overlay');
    if (drawer) drawer.classList.add('open');
    if (overlay) overlay.classList.add('open');
    document.body.classList.add('mobile-nav-active');
}

function closeMobileNav() {
    const drawer = document.getElementById('mobile-nav-drawer');
    const overlay = document.getElementById('mobile-nav-overlay');
    if (drawer) drawer.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
    document.body.classList.remove('mobile-nav-active');
}

function toggleMobileNav(event) {
    if (event) event.stopPropagation();
    const drawer = document.getElementById('mobile-nav-drawer');
    if (drawer && drawer.classList.contains('open')) {
        closeMobileNav();
    } else {
        openMobileNav();
    }
}
window.openMobileNav = openMobileNav;
window.closeMobileNav = closeMobileNav;
window.toggleMobileNav = toggleMobileNav;

async function loadNotifCount() {
    try {
        const notifs = await api.get('/notifications/');
        const unread = notifs.filter(n => !n.is_read).length;
        const badge = document.getElementById('notif-badge');
        badge.textContent = unread;
        badge.style.display = unread > 0 ? 'flex' : 'none';
    } catch (e) { }
}

function logout() {
    api.clearToken();
    const navbar = document.getElementById('navbar');
    if (navbar) navbar.style.display = 'none';
    const dropdown = document.getElementById('user-dropdown');
    if (dropdown) dropdown.classList.remove('open');
    router.navigate('/login', true);
    if (typeof showToast === 'function') {
        showToast('Logged out successfully', 'info');
    }
}

function toggleUserDropdown(event) {
    if (event) event.stopPropagation();
    const dropdown = document.getElementById('user-dropdown');
    if (dropdown) {
        dropdown.classList.toggle('open');
    }
}

/** Toggle user dropdown fallback */
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('user-avatar')?.addEventListener('click', (e) => {
        e.stopPropagation();
        document.getElementById('user-dropdown')?.classList.toggle('open');
    });
    document.addEventListener('click', () => {
        document.getElementById('user-dropdown')?.classList.remove('open');
    });
});

/** Notification panel */
function openNotifPanel() {
    const panel = document.getElementById('notif-panel');
    const overlay = document.getElementById('notif-overlay');
    panel.style.display = 'block';
    overlay.style.display = 'block';
    loadNotifications();
}
function closeNotifPanel() {
    document.getElementById('notif-panel').style.display = 'none';
    document.getElementById('notif-overlay').style.display = 'none';
}

async function loadNotifications() {
    try {
        const notifs = await api.get('/notifications/');
        const list = document.getElementById('notif-list');
        if (!notifs.length) {
            list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔔</div><div class="empty-state-title">No notifications</div></div>';
            return;
        }
        list.innerHTML = notifs.map(n => `
            <div class="notif-item ${n.is_read ? '' : 'unread'}">
                <div class="notif-title">${n.title}</div>
                <div class="notif-msg">${n.message}</div>
                <div class="notif-time">🕒 ${formatNotificationTime(n.created_at)}</div>
            </div>
        `).join('');
    } catch (e) { }
}

async function markAllRead() {
    try {
        await api.patch('/notifications/read-all');
        loadNotifCount();
        loadNotifications();
    } catch (e) { }
}

/** Toast notifications */
function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards';
        setTimeout(() => { if (toast.parentNode) toast.remove(); }, 250);
    }, duration);
}

/** Helpers: Indian Standard Time (IST - Asia/Kolkata, UTC+5:30) */
function parseDateIST(dateStr) {
    if (!dateStr) return null;
    let dStr = dateStr;
    if (typeof dateStr === 'string' && !dateStr.includes('Z') && !dateStr.includes('+')) {
        dStr = dateStr.replace(' ', 'T') + 'Z';
    }
    const d = new Date(dStr);
    return isNaN(d.getTime()) ? new Date(dateStr) : d;
}

function formatDate(dateStr) {
    const d = parseDateIST(dateStr);
    if (!d) return '—';
    return d.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}

function formatNotificationTime(dateStr) {
    const d = parseDateIST(dateStr);
    if (!d) return '—';
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);

    const timeStr = d.toLocaleTimeString('en-IN', {
        timeZone: 'Asia/Kolkata',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });

    if (diffSec >= 0 && diffSec < 60) return `Just now (${timeStr} IST)`;
    if (diffSec >= 60 && diffSec < 3600) {
        const mins = Math.floor(diffSec / 60);
        return `${mins} min${mins > 1 ? 's' : ''} ago (${timeStr} IST)`;
    }
    if (diffSec >= 3600 && diffSec < 86400) {
        const hrs = Math.floor(diffSec / 3600);
        return `${hrs} hr${hrs > 1 ? 's' : ''} ago (${timeStr} IST)`;
    }
    return d.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    }) + ' IST';
}

function formatCurrency(amount) {
    if (!amount) return '₹0';
    return `₹${parseFloat(amount).toLocaleString('en-IN')}`;
}

function statusBadge(status) {
    const cls = status?.toLowerCase().replace(' ', '-') || 'received';
    return `<span class="badge badge-${cls}">${status || 'Unknown'}</span>`;
}

function getStatusIcon(status) {
    const icons = {
        Requested: '📥',
        Received: '📥',
        Assigned: '👨‍🔧',
        Diagnosing: '🔍',
        Approved: '👍',
        Repairing: '🔧',
        Ready: '📦',
        Delivered: '🎉',
        Completed: '✅',
        'On Hold': '⏳',
        Cancelled: '❌',
        Rejected: '⛔'
    };
    return icons[status] || '⚙️';
}

function closeModal(overlay) {
    if (!overlay) return;
    if (overlay.classList.contains('closing')) return;
    overlay.classList.add('closing');
    setTimeout(() => {
        if (overlay && overlay.parentNode) overlay.remove();
    }, 160);
}
window.closeModal = closeModal;

function showModal(content) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `<div class="modal">${content}</div>`;
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal(overlay);
    });
    // Wire modal close buttons if present
    const closeBtn = overlay.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.onclick = (e) => {
            e.stopPropagation();
            closeModal(overlay);
        };
    }
    document.body.appendChild(overlay);
    return overlay;
}

function renderTimeline(currentStatus, historyList = []) {
    const steps = ['Requested', 'Assigned', 'Diagnosing', 'Approved', 'Repairing', 'Ready', 'Completed', 'Delivered'];
    const normalizedStatus = (currentStatus === 'Received') ? 'Requested' : currentStatus;
    const isException = ['Cancelled', 'On Hold', 'Rejected'].includes(normalizedStatus);
    const currentIdx = steps.indexOf(normalizedStatus);
    const isDelivered = (normalizedStatus === 'Delivered');

    let progressPct = 0;
    if (!isException && currentIdx !== -1) {
        progressPct = isDelivered ? 100 : Math.round((currentIdx / (steps.length - 1)) * 100);
    }

    return `
        <div class="timeline-container">
            ${isException ? `
                <div style="padding:8px 12px;background:#FF4D4D22;border:1px solid #FF4D4D66;border-radius:var(--radius-sm);margin-bottom:14px;color:#FF4D4D;font-weight:600;display:flex;align-items:center;gap:8px" class="animate-shake">
                    ${getStatusIcon(normalizedStatus)} Status: ${normalizedStatus}
                </div>
            ` : ''}
            <div class="status-timeline">
                <div class="timeline-progress-fill" style="width:${progressPct}%;--prog:${progressPct}%"></div>
                ${steps.map((s, i) => {
                    const isDone = (!isException && currentIdx !== -1 && (isDelivered ? i <= currentIdx : i < currentIdx));
                    const isActive = (!isException && !isDelivered && i === currentIdx);
                    const stepClass = isDone ? 'done' : isActive ? 'active' : 'pending';

                    let subtext = 'Pending';
                    if (isDone) {
                        subtext = (s === 'Delivered') ? 'Delivered 🎉' : 'Completed';
                    } else if (isActive) {
                        subtext = (s === 'Ready') ? 'Ready for Pickup' : 'In Progress';
                    }

                    return `
                        <div class="timeline-step ${stepClass}">
                            <div class="timeline-dot ${stepClass}">
                                ${isDone ? '✓' : getStatusIcon(s)}
                            </div>
                            <div class="timeline-content">
                                <div class="timeline-label ${stepClass}">${s}</div>
                                <div class="timeline-subtext">${subtext}</div>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
            ${historyList && historyList.length > 0 ? `
                <div class="status-history-log" style="margin-top:14px;border-top:1px solid var(--border);padding-top:10px">
                    <div style="font-size:0.75rem;font-weight:700;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase">Timeline Updates</div>
                    ${historyList.map(h => `
                        <div style="display:flex;justify-content:space-between;align-items:center;font-size:0.8rem;padding:4px 0;border-bottom:1px dashed var(--border)">
                            <div><span class="badge ${h.to_status === 'Delivered' ? 'badge-delivered' : 'badge-received'}" style="font-size:0.68rem;padding:2px 6px">${h.to_status}</span> <span style="margin-left:4px">${h.note || ''}</span></div>
                            <span style="color:var(--text-muted);font-size:0.75rem">${formatDate(h.created_at)}</span>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        </div>
    `;
}

function setContent(html) {
    const main = document.getElementById('main-content');
    if (!main) return;
    main.innerHTML = html;
    const firstChild = main.firstElementChild;
    if (firstChild && !firstChild.classList.contains('animate-page') && !firstChild.classList.contains('animate-fade-in')) {
        firstChild.classList.add('animate-page');
    }
}

function showLoading() {
    setContent(`<div style="display:flex;align-items:center;justify-content:center;height:60vh;">
        <div style="text-align:center" class="animate-fade-in">
            <div class="spinner" style="width:40px;height:40px;border-width:3px;margin:0 auto 16px"></div>
            <div class="text-muted" style="font-size:0.88rem;font-weight:500">Loading...</div>
        </div>
    </div>`);
}
