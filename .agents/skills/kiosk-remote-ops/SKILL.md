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

---

## 4. Full-Stack Remote Verification Workflow

Whenever a bug fix or feature edit is completed:
1. Stage, commit, and push changes locally:
   ```bash
   git add .
   git commit -m "fix/feat: description"
   git push origin main
   ```
2. Pull updates and rebuild frontend assets on the remote kiosk:
   ```bash
## 5. Human-Readable Database & Dispatch Inspection Rule

To prevent Windows PowerShell quoting errors and keep all command logs 100% human-readable:
1. **Use Version-Controlled Helper Scripts**:
   - Run `inspect_dispatch.py` inside the container stack for clean human-readable output:
     ```bash
     ssh tcfire@100.95.146.94 "echo rescue | sudo -S docker exec cfr_api python backend/scripts/inspect_dispatch.py DISP-2026-2659EC"
     ```
2. **Stream Local Python Files via Stdin**:
   - Stream local python scripts over SSH stdin without shell quote escaping or Base64 encoding:
     ```bash
     ssh tcfire@100.95.146.94 "python3 -s" < local_script.py
     ```

