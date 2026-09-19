/**
 * Mistri API Client
 * Centralized fetch wrapper with JWT auth handling
 */

const API_BASE = '/api';

const api = {
    /** Store JWT token */
    setToken(token) {
        localStorage.setItem('mistri_token', token);
    },
    getToken() {
        return localStorage.getItem('mistri_token');
    },
    clearToken() {
        localStorage.removeItem('mistri_token');
        localStorage.removeItem('mistri_user');
    },

    /** Core fetch wrapper */
    async request(path, options = {}) {
        const token = this.getToken();
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        // Remove Content-Type for FormData (browser sets it with boundary)
        if (options.body instanceof FormData) {
            delete headers['Content-Type'];
        }

        const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
        if (res.status === 401) {
            const err = await res.json().catch(() => ({ detail: 'Authentication failed' }));
            if (path.includes('/auth/login') || path.includes('/auth/register')) {
                throw new Error(err.detail || 'Invalid email or password');
            }
            this.clearToken();
            router.navigate('/login');
            throw new Error(err.detail || 'Session expired. Please login again.');
        }
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
            let message = err.message || err.detail || `HTTP ${res.status}`;
            if (Array.isArray(err.detail)) {
                message = err.detail.map(d => {
                    if (typeof d === 'string') return d;
                    const field = d.loc && d.loc.length > 1 ? d.loc.slice(1).join('.') : '';
                    return field ? `${field}: ${d.msg || JSON.stringify(d)}` : (d.msg || JSON.stringify(d));
                }).join(', ');
            } else if (typeof err.detail === 'object' && err.detail !== null) {
                message = err.detail.msg || JSON.stringify(err.detail);
            }
            throw new Error(message);
        }
        if (res.headers.get('content-type')?.includes('application/json')) {
            return res.json();
        }
        return res;
    },

    get: (path) => api.request(path),
    post: (path, data) => api.request(path, { method: 'POST', body: data instanceof FormData ? data : JSON.stringify(data) }),
    put: (path, data) => api.request(path, { method: 'PUT', body: JSON.stringify(data) }),
    patch: (path, data) => api.request(path, { method: 'PATCH', body: data ? JSON.stringify(data) : undefined }),
    delete: (path) => api.request(path, { method: 'DELETE' }),

    /** Download file (PDF, CSV) using auth token and trigger native browser download */
    async download(path, filename) {
        try {
            const token = this.getToken();
            const headers = {};
            if (token) headers['Authorization'] = `Bearer ${token}`;

            const url = path.startsWith('http') ? path : `${API_BASE}${path.startsWith('/api') ? path.slice(4) : path}`;
            const res = await fetch(url, { headers });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: 'Download failed' }));
                if (typeof showToast === 'function') showToast(err.detail || 'Download failed', 'error');
                return;
            }
            const blob = await res.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = blobUrl;
            a.download = filename || 'download';
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                a.remove();
                window.URL.revokeObjectURL(blobUrl);
            }, 1000);
            if (typeof showToast === 'function') showToast(`Downloaded ${filename || 'file'}! ✅`, 'success');
        } catch (e) {
            if (typeof showToast === 'function') showToast(e.message || 'Download failed', 'error');
        }
    },

    /** Auth helpers */
    async login(email, password) {
        const res = await this.post('/auth/login', { email, password });
        this.setToken(res.access_token);
        localStorage.setItem('mistri_user', JSON.stringify({ name: res.name, role: res.role, user_id: res.user_id }));
        return res;
    },
    async register(data) {
        const res = await this.post('/auth/register', data);
        this.setToken(res.access_token);
        localStorage.setItem('mistri_user', JSON.stringify({ name: res.name, role: res.role, user_id: res.user_id }));
        return res;
    },
    getUser() {
        const u = localStorage.getItem('mistri_user');
        return u ? JSON.parse(u) : null;
    },
    isLoggedIn() {
        return !!this.getToken();
    },
};
