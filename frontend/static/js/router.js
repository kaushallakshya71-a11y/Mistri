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
        // Auth guard
        const publicRoutes = ['/', '/login', '/register', '/track'];
        const user = api.getUser();
        const isPublic = publicRoutes.some(r => path === r || path.startsWith('/track'));

        if (!api.isLoggedIn() && !isPublic) {
            this.navigate('/login', true);
            return;
        }

        // Role-based redirect after login
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
            this.currentPath = path;
            this._currentRoute = path;
            updateNavbar();
            handler(path);
        } else {
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
        ],
        staff: [
            { label: '🏠 My Jobs', path: '/staff' },
            { label: '💼 Salary & Leaves', path: '/staff/leaves' },
            { label: '📦 Inventory', path: '/staff/inventory' },
            { label: '🛒 Shop', path: '/shop' },
        ],
        customer: [
            { label: '🏠 Dashboard', path: '/customer' },
            { label: '➕ New Repair', path: '/customer/submit' },
            { label: '📄 Invoices', path: '/customer/invoices' },
            { label: '🎧 Help & Support', path: '/customer/support' },
            { label: '🛒 Shop', path: '/shop' },
        ],
    };

    const userLinks = links[user.role] || [];
    const currentPath = router.currentPath;

    linksEl.innerHTML = userLinks.map(l =>
        `<button class="nav-link ${currentPath === l.path ? 'active' : ''}" onclick="router.navigate('${l.path}')">${l.label}</button>`
    ).join('');

    // Load notifications count
    loadNotifCount();
}

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
    router.navigate('/login');
    updateNavbar();
    showToast('Logged out successfully', 'info');
}

/** Toggle user dropdown */
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('user-avatar')?.addEventListener('click', (e) => {
        e.stopPropagation();
        document.getElementById('user-dropdown').classList.toggle('open');
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
    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${icons[type]}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
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

function showModal(content) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `<div class="modal">${content}</div>`;
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
    return overlay;
}

function renderTimeline(currentStatus, historyList = []) {
    const steps = ['Requested', 'Assigned', 'Diagnosing', 'Approved', 'Repairing', 'Ready', 'Completed', 'Delivered'];
    const normalizedStatus = (currentStatus === 'Received') ? 'Requested' : currentStatus;
    const isException = ['Cancelled', 'On Hold', 'Rejected'].includes(normalizedStatus);
    const currentIdx = steps.indexOf(normalizedStatus);

    return `
        <div class="timeline-container">
            ${isException ? `
                <div style="padding:8px 12px;background:#FF4D4D22;border:1px solid #FF4D4D66;border-radius:var(--radius-sm);margin-bottom:14px;color:#FF4D4D;font-weight:600;display:flex;align-items:center;gap:8px">
                    ${getStatusIcon(normalizedStatus)} Status: ${normalizedStatus}
                </div>
            ` : ''}
            <div class="status-timeline" style="overflow-x:auto;padding-bottom:8px">
                ${steps.map((s, i) => {
                    const isDone = (!isException && currentIdx !== -1 && i < currentIdx);
                    const isActive = (!isException && i === currentIdx);
                    return `
                        <div class="timeline-step">
                            <div class="timeline-dot ${isDone ? 'done' : isActive ? 'active' : ''}">
                                ${isDone ? '✓' : getStatusIcon(s)}
                            </div>
                            <div class="timeline-label ${isDone ? 'done' : isActive ? 'active' : ''}">${s}</div>
                        </div>
                    `;
                }).join('')}
            </div>
            ${historyList && historyList.length > 0 ? `
                <div class="status-history-log" style="margin-top:14px;border-top:1px solid var(--border);padding-top:10px">
                    <div style="font-size:0.75rem;font-weight:700;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase">Timeline Updates</div>
                    ${historyList.map(h => `
                        <div style="display:flex;justify-content:space-between;align-items:center;font-size:0.8rem;padding:4px 0;border-bottom:1px dashed var(--border)">
                            <div><span class="badge badge-received" style="font-size:0.68rem;padding:2px 6px">${h.to_status}</span> <span style="margin-left:4px">${h.note || ''}</span></div>
                            <span style="color:var(--text-muted);font-size:0.75rem">${formatDate(h.created_at)}</span>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        </div>
    `;
}

function setContent(html) {
    document.getElementById('main-content').innerHTML = html;
}

function showLoading() {
    setContent(`<div style="display:flex;align-items:center;justify-content:center;height:60vh;">
        <div style="text-align:center">
            <div class="spinner" style="width:48px;height:48px;border-width:4px;margin:0 auto 16px"></div>
            <div class="text-muted">Loading...</div>
        </div>
    </div>`);
}
