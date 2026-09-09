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

/**
 * Resolve a server-relative path against the API origin. Absolute URLs pass through.
 *
 * The database stores media paths host-relative ("/api/audio/DISP-....wav"). Handed to the
 * browser as-is, such a path resolves against the *page* origin -- on the kiosk that is
 * nginx on port 80, which serves the SPA and proxies no /api/ route at all, so the caller
 * silently receives index.html with a 200. That is how the review panel's audio player came
 * to report "No decoders for requested formats: text/html" (2026-09-08): measured on the
 * kiosk, :8000 returned 200 audio/x-wav and :80 returned 200 text/html for the same path.
 *
 * This existed three times over -- here in spirit, in dispatchModel.toActiveCall, and
 * inline in DispatchReview -- and the bug was in the one place that had no copy at all.
 * CLAUDE.md s1: frontend requests go through API_BASE_URL, never a relative path.
 *
 * @param base override for the API origin; the injection seam toActiveCall relies on.
 */
export const resolveApiUrl = (path, base = API_BASE_URL) => {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  if (!base) return path;
  return `${base}${path.startsWith('/') ? '' : '/'}${path}`;
};

// Dynamic Tile Server Base URL resolution (port 8081 for local containerized PMTiles/MBTiles server)
const getTileBaseUrl = () => {
  if (import.meta.env.VITE_TILE_BASE_URL) {
    return import.meta.env.VITE_TILE_BASE_URL.replace(/\/$/, '');
  }
  const hostname = window.location.hostname || 'localhost';
  return `http://${hostname}:8081`;
};

export const TILE_BASE_URL = getTileBaseUrl();




// Auth Token & Cookie management
export const getToken = () => {
  const token = localStorage.getItem('cfr_auth_token');
  if (token) return token;
  const match = document.cookie.match(new RegExp('(^| )cfr_auth_token=([^;]+)'));
  return match ? match[2] : null;
};

export const setToken = (token) => {
  if (token) {
    localStorage.setItem('cfr_auth_token', token);
    document.cookie = `cfr_auth_token=${token}; path=/; max-age=2592000; SameSite=Lax`;
  } else {
    localStorage.removeItem('cfr_auth_token');
    document.cookie = 'cfr_auth_token=; path=/; max-age=0; SameSite=Lax';
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
  // Auth methods for local FastAPI
  auth: {
    async getSession() {
      let token = getToken();
      if (!token) {
        // Auto-authenticate station devices on local network
        try {
          const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: 'cfradmin', password: 'rescue' })
          });
          if (res.ok) {
            const data = await res.json();
            setToken(data.access_token);
            return { data: { session: { user: data.user, access_token: data.access_token } }, error: null };
          }
        } catch { /* non-fatal: caller handles the absent value */ }
        return { data: { session: null }, error: null };
      }
      try {
        const res = await fetch(`${API_BASE_URL}/api/auth/session`, { headers: getHeaders() });
        const data = await res.json();
        if (data && data.session) {
          return { data: { session: data.session }, error: null };
        } else {
          setToken(null);
          return this.getSession();
        }
      } catch {
        return { data: { session: { user: { username: 'cfradmin', role: 'admin' } } }, error: null };
      }
    },

    async signInWithPassword({ username, password }) {
      try {
        const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password })
        });
        if (!res.ok) {
          let msg = 'Login failed';
          try {
            const errData = await res.json();
            if (typeof errData.detail === 'string') {
              msg = errData.detail;
            } else if (Array.isArray(errData.detail) && errData.detail[0]?.msg) {
              msg = errData.detail[0].msg;
            } else if (errData.detail) {
              msg = JSON.stringify(errData.detail);
            }
          } catch { /* non-fatal: caller handles the absent value */ }
          throw new Error(msg);
        }
        const data = await res.json();
        setToken(data.access_token);
        const session = { user: data.user, access_token: data.access_token };
        return { data: { session }, error: null };
      } catch (err) {
        const errObj = err instanceof Error ? err : new Error(typeof err === 'string' ? err : 'Login failed');
        return { data: { session: null }, error: errObj };
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
    // The review screen lists from this. 500 dropped the oldest calls once the table passed
    // 500 rows (569 on 2026-09-05): two July 13 calls the operator went to correct were not
    // there. The API allows up to 5000.
    async fetchAll(limit = 5000) {
      const res = await fetch(`${API_BASE_URL}/api/dispatches?limit=${limit}`, { headers: getHeaders() });
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
  },

  listener: {
    async fetchStatus() {
      const res = await fetch(`${API_BASE_URL}/api/listener/status`, { headers: getHeaders() });
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return await res.json();
    }
  },

  roadClosures: {
    async fetchAll() {
      const res = await fetch(`${API_BASE_URL}/api/road-closures`, { headers: getHeaders() });
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return await res.json();
    }
  },

  parcels: {
    async lookup(query) {
      if (!query) return null;
      try {
        const res = await fetch(`${API_BASE_URL}/api/parcels/lookup?query=${encodeURIComponent(query)}`, { headers: getHeaders() });
        if (!res.ok) return null;
        return await res.json();
      } catch {
        return null;
      }
    },

    async saveStreetView(payload) {
      const res = await fetch(`${API_BASE_URL}/api/parcels/streetview`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return await res.json();
    },

    // The operator-verified arrival point of one parcel (punch-list #49). lat/lng null
    // clears it. set_by is required by the API: every override is attributable.
    async saveEntrance(payload) {
      const res = await fetch(`${API_BASE_URL}/api/parcels/entrance`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try { detail = (await res.json()).detail || detail; } catch { /* keep the status */ }
        throw new Error(detail);
      }
      return await res.json();
    }
  },

  streetviewOverrides: {
    async get(address) {
      if (!address) return null;
      try {
        const res = await fetch(`${API_BASE_URL}/api/streetview-overrides/${encodeURIComponent(address)}`, { headers: getHeaders() });
        if (!res.ok) return null;
        return await res.json();
      } catch {
        return null;
      }
    },

    async save(payload) {
      return apiClient.streetView.saveOverride(payload);
    }
  },

  streetView: {
    async fetchAll() {
      const res = await fetch(`${API_BASE_URL}/api/streetview-overrides`, { headers: getHeaders() });
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return await res.json();
    },

    async fetchOverride(address) {
      if (!address) return null;
      try {
        const res = await fetch(`${API_BASE_URL}/api/streetview-overrides/${encodeURIComponent(address)}`, { headers: getHeaders() });
        if (!res.ok) return null;
        return await res.json();
      } catch {
        return null;
      }
    },

    async saveOverride(payload) {
      const res = await fetch(`${API_BASE_URL}/api/streetview-overrides`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return await res.json();
    }
  }
};
