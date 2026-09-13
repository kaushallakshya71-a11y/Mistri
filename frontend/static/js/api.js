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
            this.clearToken();
            router.navigate('/login');
            throw new Error('Session expired. Please login again.');
        }
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
            throw new Error(err.detail || 'Request failed');
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
        localStorage.setItem('mistri_user', JSON.stringify({ name: res.name, role: res.role }));
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
