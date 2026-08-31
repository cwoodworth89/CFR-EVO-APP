# 📱 Ntfy Push Server Access & Mobile Subscription Specification

This document provides technical specifications for the local Ntfy push notification server, topic architecture, security salts, and QR code pairing links for developers and frontend AI agents.

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

## 🔐 2. Topic Architecture & Security Salt Scheme

### A. Permanent Master Topic (Chief / Admin)
- **Topic Name**: `chief-master`
- **Expiry**: Permanent (No monthly rotation).
- **Features**:
  - Receives all station dispatches across all halls and apparatus.
  - Lock-screen audio file attachments (`Attach: http://<host>:8000/api/audio/<id>.wav`).
  - Interactive lock-screen action buttons (`view, 🎧 Listen to Call Audio, <url>; view, 🗺️ Open Map Navigation, <url>`).

### A2. Permanent Maintainer Topic (Errors)
- **Topic Name**: `chief-errors`
- **Expiry**: Permanent, unsalted — same class as `chief-master`, not rotated.
- **Who subscribes**: the maintainer only. **Not crews.**
- **Carries**: pipeline exceptions from `process_phase_1_check` and
  `process_phase_2_finalize` — exception type, message, dispatch id, and the
  `journalctl` line to run.
- **Why separate from `chief-master`**: crews subscribe to the dispatch topic. A stack
  trace is not a dispatch, and mixing them trains people to swipe past both. The salted
  monthly rotation in §B exists for topics carrying incident detail to apparatus; this
  carries none.
- **Override**: `NTFY_ERROR_TOPIC` in the environment.
- **Origin**: punch-list **#59** — two `UnboundLocalError`s aborted Phase 2 after the
  audio was written but before the record was updated. Fifteen dispatches lost their
  audio player. The error named the dispatch and the variable in
  `journalctl -u cfr-agent` from the first occurrence, and went unread for two days.
  Punch-list #26 restored that logging; nothing watched it. This is the watching.

Subscribe the same way as any other topic:
```
ntfy://100.95.146.94:8080/chief-errors
```

---

### B. Monthly Secret Apparatus Topics
- **Format**: `<apparatus_id>-<monthly_salt>` (e.g., `engine-1-aug2026-9f8a3b`, `rescue-2-aug2026-9f8a3b`).
- **Rotation**: Automatically calculated monthly with a 3-day shift transition grace period.
- **Salt Formula**:
  $$\text{Salt} = \text{MonthCode} + \text{"-"} + \text{MD5}(\text{MasterSalt} + \text{"-"} + \text{Year} + \text{"-"} + \text{MonthNum})[0..6]$$
  *(Example for August 2026: `aug2026-9f8a3b`)*.

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
