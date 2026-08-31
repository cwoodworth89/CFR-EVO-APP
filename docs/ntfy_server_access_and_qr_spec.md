# 📱 Ntfy Push Server Access & Mobile Subscription Specification

This document provides technical specifications for the local Ntfy push notification server, topic architecture and QR code pairing links for developers and frontend AI agents.

---

## 📡 1. Ntfy Server Access Specs

| Parameter | Value / Setting | Description |
| :--- | :--- | :--- |
| **Container Image** | `binwiederhier/ntfy:v2.11.0` | Containerized push notification broker. |
| **Port** | `8080` (HTTP) | Server port bound in `docker-compose.yml`. |
| **Protocol** | **`http://`** *(UNENCRYPTED)* | **CRITICAL**: The local server runs on plain HTTP. **Do NOT use `https://`** as it causes SSL handshake timeouts on mobile devices. |
| **Web Root Mode** | `--web-root app` | Serves the Ntfy Web UI at `http://<host>:8080/app` and `http://<host>:8080/<topic>`. |
| **Tailscale IP** | `100.95.146.94` | Primary VPN access host for off-site mobile drivers. |
| **Local Station IP** | Dynamic LAN IP (e.g. `10.0.1.x`) | Local station network IP. |
| **Future Domain** | — | Not planned. Public-domain exposure was considered and rejected: it is incompatible with CLAUDE.md §1 (100% offline, $0) and would put dispatch records on a remote. |

---

## 🔐 2. Topic Architecture

**There are two topics, both permanent, neither salted.** An earlier version of this
document specified `<apparatus_id>-<monthly_salt>` per-apparatus topics rotating monthly on
an MD5 formula. **That was never built and has been removed** — verified 2026-08-31, no
`salt`, `master_salt` or rotation logic exists anywhere in `backend/`, `services/` or
`frontend/src`. The section is deleted rather than annotated so nobody implements against it.

### A. Dispatch Topic — crews and chiefs
- **Topic**: `chief-master`
- Receives every station dispatch. Lock-screen audio attachment
  (`Attach: http://<host>:8000/api/audio/<id>.wav`) and action buttons for listening and
  navigating.
- Set by `NTFY_TOPIC` in **both** `backend/.env` (read by the host agent) and
  `docker-compose.yml` (read by the API container). **They must match** — a mismatch
  publishes agent and API notifications to different topics, and one of them silently goes
  nowhere. Confirmed 2026-08-31: both are `chief-master`.

### B. Error Topic — maintainer only
- **Topic**: `dev-errors`
- **Nobody operational subscribes.** Chiefs and crews get dispatches; a stack trace is not a
  dispatch, and putting one on their topic trains people to swipe past both.
- Carries pipeline exceptions from `process_phase_1_check` and `process_phase_2_finalize`:
  exception type and message, dispatch id, and the `journalctl` line to run next.
- Set by `NTFY_ERROR_TOPIC`, default `dev-errors`.
- **Why it exists**: punch-list **#59**. Two `UnboundLocalError`s aborted Phase 2 after the
  audio was written but before the record was updated. Fifteen dispatches lost their audio
  player. The error named the dispatch and the variable in `journalctl -u cfr-agent` from the
  first occurrence and went unread for two days. Punch-list #26 restored that logging in
  August; nothing watched it.

```
ntfy://100.95.146.94:8080/dev-errors
```

> [!WARNING]
> **`DriverStationSetup.jsx` hardcodes `cfr-dispatches`** (line 23), which is not what
> anything publishes to. A driver scanning that QR subscribes to a topic that receives
> nothing. `ntfy_broker.py` carries the same string as its env default. Both should read
> `chief-master`, or the topic should come from configuration rather than three separate
> literals.

---

## 📲 3. QR Code & Subscription Specifications (Frontend Agent Guide)

When updating `DriverStationSetup.jsx` or creating new mobile pairing interfaces, enforce the following payload rules:

### A. Scheme Enforcement
- **Native Ntfy App Deep Link**:
  ```
  ntfy://<host>:8080/<topic>
  ```
  *Example*: `ntfy://100.95.146.94:8080/chief-master`
  - When scanned with a phone camera, this deep link opens the Ntfy app directly and prompts the driver to subscribe with one tap.

- **Web Browser Fallback URL**:
  ```
  http://<host>:8080/<topic>
  ```
  *Example*: `http://100.95.146.94:8080/chief-master`
  - Opens the Ntfy web app UI in mobile Chrome/Safari.
  - **MUST ALWAYS start with `http://`** — never `https://`.

### B. Dynamic Host Input Logic
- The pairing modal allows drivers to specify the host address (`effectiveHost`).
- Default: `window.location.hostname` or `100.95.146.94`.
- Host input must automatically strip any trailing `/`, `http://`, or `https://` prefixes before forming the URL.

### C. Recommended Connection Settings in Ntfy App
- Connection Protocol: **WebSockets** (`ws://<host>:8080/<topic>/ws`).
- Allows instant low-latency push alerts while conserving mobile battery.
