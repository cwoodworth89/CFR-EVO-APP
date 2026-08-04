// CFR Dispatch IP-Agnostic API & Auth Client
// Connects to local FastAPI Gateway running on Hall 1 Server

const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '');
  }
  // Dynamic IP resolution based on browser URL
  const hostname = window.location.hostname || 'localhost';
  return `http://${hostname}:8000`;
};

export const API_BASE_URL = getApiBaseUrl();

// Auth Token management
export const getToken = () => localStorage.getItem('cfr_auth_token');
export const setToken = (token) => {
  if (token) {
    localStorage.setItem('cfr_auth_token', token);
  } else {
    localStorage.removeItem('cfr_auth_token');
  }
};

const getHeaders = () => {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

export const apiClient = {
  // Auth methods matching Supabase Auth interface
  auth: {
    async getSession() {
      const token = getToken();
      if (!token) return { data: { session: null }, error: null };
      try {
        const res = await fetch(`${API_BASE_URL}/api/auth/session`, { headers: getHeaders() });
        const data = await res.json();
        return { data: { session: data.session }, error: null };
      } catch (err) {
        return { data: { session: null }, error: err };
      }
    },

    async signInWithPassword({ email, password }) {
      try {
        const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || 'Login failed');
        }
        const data = await res.json();
        setToken(data.access_token);
        const session = { user: data.user, access_token: data.access_token };
        return { data: { session }, error: null };
      } catch (err) {
        return { data: { session: null }, error: err };
      }
    },

    async signOut() {
      setToken(null);
      return { error: null };
    },

    onAuthStateChange(callback) {
      // Simple auth state change subscriber
      const listener = (e) => {
        if (e.key === 'cfr_auth_token') {
          apiClient.auth.getSession().then(({ data }) => {
            callback(e.newValue ? 'SIGNED_IN' : 'SIGNED_OUT', data.session);
          });
        }
      };
      window.addEventListener('storage', listener);
      return {
        data: {
          subscription: {
            unsubscribe: () => window.removeEventListener('storage', listener)
          }
        }
      };
    }
  },

  // Dispatch REST query builder
  dispatches: {
    async fetchAll() {
      const res = await fetch(`${API_BASE_URL}/api/dispatches`, { headers: getHeaders() });
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return await res.json();
    },

    async create(payload) {
      const res = await fetch(`${API_BASE_URL}/api/dispatches`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return await res.json();
    },

    async update(id, payload) {
      const res = await fetch(`${API_BASE_URL}/api/dispatches/${id}`, {
        method: 'PATCH',
        headers: getHeaders(),
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return await res.json();
    },

    async delete(id) {
      const res = await fetch(`${API_BASE_URL}/api/dispatches/${id}`, {
        method: 'DELETE',
        headers: getHeaders()
      });
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return await res.json();
    }
  },

  evaluations: {
    async fetchAll() {
      const res = await fetch(`${API_BASE_URL}/api/evaluations`, { headers: getHeaders() });
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return await res.json();
    }
  }
};
