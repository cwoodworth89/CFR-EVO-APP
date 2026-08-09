# CFR EVO: Workspace & Architectural Rules

This rule file defines domain constraints, runtime environments, and workflow standards for **CFR EVO**.

---

## 1. 100% Local Container Stack Architecture
* **Primary Database**: All dispatch records, audio metadata, and MLOps metrics persist directly to containerized PostgreSQL 16 (`localhost:5432`).
* **API Gateway**: REST operations and dispatch persistence route via FastAPI (`http://localhost:8000/api/dispatches`).
* **Real-Time Broadcast**: Station kiosks listen to Mosquitto MQTT over WebSockets on port `9001` (topic: `cfr/dispatches`).
* **Cloud Deprecation**: Do NOT re-introduce Supabase, Firebase, or external cloud database dependencies. The system is designed to function with zero monthly costs and total offline survival.

---

## 2. Sibling Service Import Path Resolution
Sibling microservices in `/services/*/src` (`gis_service`, `audio_service`, `notification_service`) are decoupled from `/backend`.
* **Important**: Do NOT modify or "fix" sibling import statements in the backend orchestration files (e.g., `from gis_service...`).
* **Runtime Injection**: Sibling paths are injected into `sys.path` dynamically inside [`backend/cfr_dispatch/__init__.py`](backend/cfr_dispatch/__init__.py).
* **Static Analysis**: Workspace `.vscode/settings.json` appends these paths to `python.analysis.extraPaths`.

---

## 3. Git & Remote Kiosk Deployment Protocol
The station kiosk is accessible over Tailscale SSH (`tcfire@100.95.146.94`, hostname `cfr-mapping-tcfh`).
1. **Local Edits First**: Make all code, config, and doc changes in the local Git repository first. **Never edit production code directly on the remote kiosk.**
2. **Local Scope Restriction**: Local command execution is reserved strictly for pre-development mini-scripts, scratch isolation tests, or standalone unit checks.
3. **Mandatory Remote Full-Stack Testing**: Once a fix or feature is implemented, you MUST commit and push to Git, pull changes on the remote kiosk, rebuild assets, and verify on the physical remote full stack before declaring completion.
4. **Commit, Pull & Rebuild Execution**:
   ```bash
   git add . && git commit -m "..." && git push origin main
   ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull && cd frontend && npm run build"
   ```
5. **Git-Ignored Files**: Files in `.gitignore` (e.g. `backend/.env`, `frontend/.env.local`, model caches in `backend/models/`, shapefiles in `backend/data/`) are not synced via git and must be transferred manually via `scp` when updated.

