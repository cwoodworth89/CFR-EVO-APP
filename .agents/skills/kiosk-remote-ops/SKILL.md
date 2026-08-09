---
name: kiosk-remote-ops
description: Non-interactive operational runbook for executing remote audio diagnostics, service restarts, and frontend asset builds on the station kiosk display (cfr-mapping-tcfh via Tailscale SSH).
---

# Kiosk Remote Operations & Diagnostics

This skill provides step-by-step procedures for managing the remote kiosk host over Tailscale SSH.

## Connection & Security Specifications
* **Host**: `100.95.146.94` (hostname: `cfr-mapping-tcfh`)
* **User**: `tcfire`
* **PortAudio Environment**: Must prepend `XDG_RUNTIME_DIR=/run/user/1000` for all sounddevice / audio commands.

---

## 1. System Health & Audio Hardware Inspection

Check system uptime and list all detected audio capture cards:
```bash
ssh tcfire@100.95.146.94 "uname -a; uptime"
```

List audio input devices using PortAudio:
```bash
ssh tcfire@100.95.146.94 "XDG_RUNTIME_DIR=/run/user/1000 /home/tcfire/CFR-EVO-APP/.venv/bin/python -c 'import sounddevice as sd; print(sd.query_devices())'"
```

---

## 2. Audio Capture Diagnostics & Log Auditing

Run a 15-second audio capture diagnostic on device index 13:
```bash
ssh tcfire@100.95.146.94 "XDG_RUNTIME_DIR=/run/user/1000 /home/tcfire/CFR-EVO-APP/.venv/bin/python /home/tcfire/CFR-EVO-APP/backend/scripts/record_test.py 13"
```

Tail live dispatch audio listener logs:
```bash
ssh tcfire@100.95.146.94 "tail -n 50 /home/tcfire/CFR-EVO-APP/backend/dispatch.log"
```

---

## 3. Daemon Control & Frontend Asset Compilation

Restart the audio listener daemon:
```bash
ssh tcfire@100.95.146.94 "sudo systemctl restart cfr-agent"
```

Rebuild frontend production assets (since `frontend/dist` is `.gitignore`d):
```bash
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/frontend && npm install && npm run build"
```
