---
name: kiosk-remote-ops
description: Non-interactive operational runbook for executing remote audio diagnostics, service restarts, and frontend asset builds on the station kiosk display (cfr-mapping-tcfh via Tailscale SSH).
---

# Kiosk Remote Operations & Diagnostics

This skill provides step-by-step procedures for managing the remote kiosk host over Tailscale SSH.

## Connection & Security Specifications
* **Host**: `100.95.146.94` (hostname: `cfr-mapping-tcfh`)
* **User**: `tcfire`
* **Docker Container Stack**:
  - PostgreSQL: `cfr_postgres` (DB: `cfr_dispatch`, User: `cfr_user`, Port: `5432`)
  - API Gateway: `cfr_api` (FastAPI, Port: `8000`)
  - MQTT Broker: `cfr_mosquitto` (WebSockets Port: `9001`)
  - Push Server: `cfr_ntfy` (Port: `8080`)
* **PortAudio Environment**: Must prepend `XDG_RUNTIME_DIR=/run/user/1000` for all sounddevice / audio commands.

---

## 1. System Health & Container Stack Inspection

Check system uptime and container status:
```bash
ssh tcfire@100.95.146.94 "uptime && docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
```

Query PostgreSQL directly without shell escaping issues (`tcfire` is in the `docker` group: no `sudo`, and never a password on a command line):
```bash
ssh tcfire@100.95.146.94 "docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch -c 'SELECT * FROM streetview_overrides;'"
```

---

## 2. Audio Capture Diagnostics & Log Auditing

List audio input devices using PortAudio:
```bash
ssh tcfire@100.95.146.94 "XDG_RUNTIME_DIR=/run/user/1000 /home/tcfire/CFR-EVO-APP/.venv/bin/python -c 'import sounddevice as sd; print(sd.query_devices())'"
```

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

That needs sudo, which needs a password at a prompt. The unit has `Restart=always` with
`RestartSec=5s` and runs as `tcfire`, so a SIGTERM to the main process is a restart that needs
no password (used 2026-09-05; the worker child is in the same cgroup and goes with it):
```bash
ssh tcfire@100.95.146.94 "kill -TERM \$(systemctl show cfr-agent -p MainPID --value); sleep 15; systemctl is-active cfr-agent; tail -n 5 /home/tcfire/CFR-EVO-APP/backend/dispatch.log"
```

Importing `cfr_dispatch` in a one-off check pulls in PortAudio; without `XDG_RUNTIME_DIR=/run/user/1000`
it dies on `PulseAudio_Initialize`.

Rebuild frontend production assets (since `frontend/dist` is `.gitignore`d):
```bash
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/frontend && npm install && npm run build"
```

---

## 4. Full-Stack Remote Verification Workflow

Whenever a bug fix or feature edit is completed:
1. **Stage, commit, and push changes locally**:
   ```bash
   git add .
   git commit -m "fix/feat: description"
   git push origin main
   ```
2. **Pull updates and rebuild frontend assets on remote kiosk**:
   ```bash
   ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull && cd frontend && npm run build"
   ```

---

## 5. Human-Readable Database & Dispatch Inspection Rule

To prevent Windows PowerShell quoting errors and keep all command logs 100% human-readable:
1. **Use Version-Controlled Helper Scripts**:
   - Run helper scripts (e.g. `tools/inspect_dispatch.py`, `tools/update_streetview.py`) on the kiosk host with the project virtualenv, from the repository root. They are not in the API image (`tools/` is not copied into it), and both `backend/api/database.py` (since punch-list #61) and `inspect_dispatch.py` refuse to run without a Postgres `DATABASE_URL` from the environment or `backend/.env`:
     ```bash
     ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && .venv/bin/python tools/inspect_dispatch.py DISP-2026-55B7B6"
     ```
2. **Execute Dedicated SQL Scripts**:
   - Use `docker exec -i cfr_postgres psql -U cfr_user -d cfr_dispatch` with standard SQL queries rather than deeply nested inline quotes.
