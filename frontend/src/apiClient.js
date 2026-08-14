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
 * @param {string} [style='voyager'] - Basemap style ('voyager', 'dark', 'grey', 'light', 'osm', 'satellite')
 * @returns {string} Fully resolved tile URL
 */
export const getTileUrl = (z = '{z}', x = '{x}', y = '{y}', style = 'voyager') => {
  const normalizedStyle = (style || 'voyager').toLowerCase();
  if (normalizedStyle === 'satellite') {
    return `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`;
  }
  if (normalizedStyle === 'dark') {
    return `${TILE_BASE_URL}/services/vancouver_dark/tiles/${z}/${x}/${y}.png`;
  }
  if (normalizedStyle === 'grey' || normalizedStyle === 'light') {
    return `${TILE_BASE_URL}/services/vancouver_light/tiles/${z}/${x}/${y}.png`;
  }
  return `${TILE_BASE_URL}/services/vancouver/tiles/${z}/${x}/${y}.png`;
};

/**
 * Returns a complete tile layer configuration for Leaflet, including local URL,
 * fallback online URL, attribution, and zoom levels.
 * @param {string} style - Basemap style key ('GREY', 'DARK', 'VOYAGER', 'OSM', 'SATELLITE')
 */
export const getTileLayerConfig = (style = 'VOYAGER') => {
  const normalized = (style || 'VOYAGER').toUpperCase();
  switch (normalized) {
    case 'DARK':
      return {
        url: `${TILE_BASE_URL}/services/vancouver_dark/tiles/{z}/{x}/{y}.png`,
        fallbackUrl: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
        attribution: '© OpenStreetMap contributors & Carto (Offline Local)',
        subdomains: ['a', 'b', 'c', 'd'],
        maxNativeZoom: 19,
        maxZoom: 22,
      };
    case 'GREY':
    case 'LIGHT':
      return {
        url: `${TILE_BASE_URL}/services/vancouver_light/tiles/{z}/{x}/{y}.png`,
        fallbackUrl: 'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png',
        attribution: '© OpenStreetMap contributors & Carto (Offline Local)',
        subdomains: ['a', 'b', 'c', 'd'],
        maxNativeZoom: 19,
        maxZoom: 22,
      };
    case 'OSM':
      return {
        url: `${TILE_BASE_URL}/services/vancouver/tiles/{z}/{x}/{y}.png`,
        fallbackUrl: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        attribution: '© OpenStreetMap contributors (Offline Local)',
        subdomains: ['a', 'b', 'c'],
        maxNativeZoom: 19,
        maxZoom: 22,
      };
    case 'SATELLITE':
      return {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        fallbackUrl: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attribution: 'Esri, Maxar, Earthstar Geographics',
        subdomains: ['a', 'b', 'c'],
        maxNativeZoom: 18,
        maxZoom: 22,
      };
    case 'VOYAGER':
    default:
      return {
        url: `${TILE_BASE_URL}/services/vancouver/tiles/{z}/{x}/{y}.png`,
        fallbackUrl: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
        attribution: '© OpenStreetMap contributors & Carto (Offline Local)',
        subdomains: ['a', 'b', 'c', 'd'],
        maxNativeZoom: 19,
        maxZoom: 22,
      };
  }
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
  // Auth methods matching Supabase Auth interface
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
        } catch (e) {}
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
      } catch (err) {
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
          } catch (e) {}
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
      } catch (e) {
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
      } catch (e) {
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
      } catch (e) {
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
