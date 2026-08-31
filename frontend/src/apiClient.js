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

// Dynamic Tile Server Base URL resolution (port 8081 for local containerized PMTiles/MBTiles server)
const getTileBaseUrl = () => {
  if (import.meta.env.VITE_TILE_BASE_URL) {
    return import.meta.env.VITE_TILE_BASE_URL.replace(/\/$/, '');
  }
  const hostname = window.location.hostname || 'localhost';
  return `http://${hostname}:8081`;
};

export const TILE_BASE_URL = getTileBaseUrl();

/**
 * Returns a configured tile URL endpoint or standard template.
 * @param {string|number} z - Zoom level or template placeholder '{z}'
 * @param {string|number} x - X coordinate or template placeholder '{x}'
 * @param {string|number} y - Y coordinate or template placeholder '{y}'
 * @param {string} [style='SATELLITE'] - Basemap style ('SATELLITE', 'VOYAGER', 'OSM', 'GREY', 'DARK')
 * @returns {string} Fully resolved tile URL
 */
export const getTileUrl = (style = 'SATELLITE', z = 12, x = 0, y = 0) => {
  const s = (style || 'SATELLITE').toUpperCase();
  if (s === 'SATELLITE') {
    // City of Coquitlam 7.5cm orthophotos only -- see BASE_LAYERS.SATELLITE.
    return `${TILE_BASE_URL}/services/ortho/tiles/${z}/${x}/${y}.jpg`;
  }
  if (s === 'GREY' || s === 'DARK' || s === 'LIGHT') {
    return `${TILE_BASE_URL}/services/street_nolabels/tiles/${z}/${x}/${y}.png`;
  }
  return `${TILE_BASE_URL}/services/street/tiles/${z}/${x}/${y}.png`;
};

/**
 * Returns a complete tile layer configuration for Leaflet, strictly serving from
 * local containerized disk cache with zero external WAN dependencies.
 * @param {string} style - Basemap style key ('GREY', 'DARK', 'LIGHT', 'VOYAGER', 'OSM', 'SATELLITE')
 */
export const getTileLayerConfig = (style = 'SATELLITE') => {
  const s = (style || 'SATELLITE').toUpperCase();
  let url = `${TILE_BASE_URL}/services/street/tiles/{z}/{x}/{y}.png`;
  // Deepest zoom actually crawled per layer -- must match "max_zoom" in
  // compile_mbtiles.py LAYER_CONFIGS. Street styles stop at 18 (operator
  // decision 2026-08-30, punch-list #47); aerial goes to 20 because that is
  // where the City's imagery cache ends. Leaflet upscales beyond this, so the map still
  // zooms to maxZoom -- it just stops requesting new tiles.
  let maxNativeZoom = 18;
  let attribution = '© OpenStreetMap contributors (100% Offline Local Cache)';
  
  if (s === 'SATELLITE') {
    url = `${TILE_BASE_URL}/services/ortho/tiles/{z}/{x}/{y}.jpg`;
    maxNativeZoom = 20;   // City cache ends at z20, see BASE_LAYERS.SATELLITE
    attribution = 'City of Coquitlam 2025 7.5cm Orthophoto (Open Government Licence, Offline Local Cache)';
  } else if (s === 'GREY' || s === 'DARK' || s === 'LIGHT') {
    url = `${TILE_BASE_URL}/services/street_nolabels/tiles/{z}/{x}/{y}.png`;
    maxNativeZoom = 18;
    attribution = '© OpenStreetMap contributors & Carto (100% Offline Local Cache)';
  }

  return {
    url,
    fallbackUrl: null, // 100% pure offline local pre-cached tiles
    attribution,
    subdomains: ['a', 'b', 'c'],
    maxNativeZoom,
    maxZoom: 22,
  };
};


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
    async fetchAll(limit = 500) {
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
