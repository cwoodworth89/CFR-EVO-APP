# 🌐 Public Domain & SSL/TLS Migration Blueprint

> [!CAUTION]
> **Not the architecture. Do not follow this.** This blueprint migrates CFR EVO from
> Tailscale/LAN to a public web domain with Let's Encrypt certificates — which is
> incompatible with CLAUDE.md §1: the system must function **100% offline** with no WAN
> dependency and **$0 recurring cost**, and dispatch records must never reach a remote
> (a constraint `.gitignore` also enforces for database dumps).
>
> Kept as a record of an option that was considered and not taken. If public exposure is
> ever revisited it belongs in [`docs/PROJECT_IDEAS.md`](PROJECT_IDEAS.md) as a proposal,
> with the privacy implications of dispatch data — addresses, call details, HITL
> corrections — argued explicitly first.

This guide documents the architecture, Nginx reverse proxy configuration, Let's Encrypt SSL/TLS certificates, and container routing required when migrating **CFR EVO** from Tailscale/LAN to a public web domain (e.g., `dispatch.woodworthelectric.ca`).

---

## 🔒 1. Why SSL/TLS is Mandatory for Public Domains

When exposing the station server to a public domain:
1. **Browsers & WebSockets**: Modern browsers require `https://` and `wss://` for local storage, audio playback APIs, and WebSockets.
2. **Mobile Apps & Ntfy**: Mobile operating systems (iOS/Android) block unencrypted `http://` network requests to public domain names.
3. **PWA & Push Notifications**: Web Push APIs and Service Workers require HTTPS.

---

## 🏗️ 2. Production Port & Proxy Architecture

When using a single public domain (`dispatch.woodworthelectric.ca`), an **Nginx Reverse Proxy** (or Caddy/Traefik) terminates SSL/TLS on port `443` and routes internal traffic to Docker containers:

```
                          Internet (HTTPS / WSS)
                                    │
                                    ▼
                     ┌─────────────────────────────┐
                     │   Nginx Reverse Proxy       │
                     │   (Port 80 -> 443 HTTPS)    │
                     │   Let's Encrypt Certbot     │
                     └──────────────┬──────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │ (HTTP localhost:8000)    │ (HTTP localhost:8080)    │ (WS localhost:9001)
         ▼                          ▼                          ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  cfr_api         │       │  cfr_ntfy        │       │  cfr_mosquitto   │
│  (FastAPI DB)    │       │  (Ntfy Push)     │       │  (MQTT Broker)   │
└──────────────────┘       └──────────────────┘       └──────────────────┘
```

| Public Endpoint | Internal Container Proxy Target | Protocol |
| :--- | :--- | :--- |
| `https://dispatch.woodworthelectric.ca/` | Frontend Client Dist (`dist/index.html`) | HTTPS |
| `https://dispatch.woodworthelectric.ca/api/` | `http://localhost:8000/api/` | HTTPS $\rightarrow$ HTTP |
| `https://dispatch.woodworthelectric.ca/ntfy/` | `http://localhost:8080/` | HTTPS/WSS $\rightarrow$ HTTP/WS |
| `wss://dispatch.woodworthelectric.ca/mqtt` | `ws://localhost:9001/` | WSS $\rightarrow$ WS |

---

## 📜 3. Recommended Nginx Configuration (`/etc/nginx/sites-available/cfr-dispatch`)

```nginx
server {
    listen 80;
    server_name dispatch.woodworthelectric.ca;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dispatch.woodworthelectric.ca;

    ssl_certificate /etc/letsencrypt/live/dispatch.woodworthelectric.ca/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dispatch.woodworthelectric.ca/privkey.pem;

    # 1. Frontend Static Files
    location / {
        root /home/tcfire/CFR-EVO-APP/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 2. FastAPI Gateway Endpoint
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 3. Ntfy Push Broker & WebSockets
    location /ntfy/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 4. Mosquitto MQTT WebSockets
    location /mqtt {
        proxy_pass http://127.0.0.1:9001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

---

## 📱 4. Mobile QR Code & App Pairing Updates

Once SSL is active on the domain:
1. **Protocol Shift**: All QR code payloads switch to **`https://`**:
   - Web Link: `https://dispatch.woodworthelectric.ca/ntfy/chief-master`
   - Ntfy Deep Link: `ntfy://dispatch.woodworthelectric.ca/ntfy/chief-master`
2. **Ntfy App Settings**:
   - The Ntfy mobile app error will disappear because HTTPS is fully supported.
   - Connection protocol set to **WebSockets** (`wss://dispatch.woodworthelectric.ca/ntfy/chief-master/ws`).

---

## 🛠️ 5. Migration Checklist When Domain is Ready

- [ ] Point DNS A/AAAA record (`dispatch.woodworthelectric.ca`) to station server public IP.
- [ ] Install Certbot: `sudo apt update && sudo apt install certbot python3-certbot-nginx`.
- [ ] Generate SSL Cert: `sudo certbot --nginx -d dispatch.woodworthelectric.ca`.
- [ ] Update `frontend/.env`:
  - `VITE_API_URL=https://dispatch.woodworthelectric.ca`
  - `VITE_NTFY_URL=https://dispatch.woodworthelectric.ca/ntfy`
- [ ] Recompile frontend production build: `npm run build`.
