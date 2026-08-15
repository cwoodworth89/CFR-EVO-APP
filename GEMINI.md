# CFR EVO: Workspace & Architectural Rules

This rule file defines domain constraints, runtime environments, and workflow standards for **CFR EVO**.

---

## 1. 100% Local Container Stack Architecture
* **Primary Database**: All dispatch records, audio metadata, and MLOps metrics persist directly to containerized PostgreSQL 16 (`localhost:5432`).
* **API Gateway**: REST operations and dispatch persistence route via FastAPI (`http://localhost:8000/api/dispatches`).
* **Frontend API Endpoint Resolution**: All frontend components performing `fetch()` operations MUST import and use `API_BASE_URL` from [`frontend/src/apiClient.js`](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/frontend/src/apiClient.js) (e.g., `fetch(\`${API_BASE_URL}/api/route?...\`)`). Never use raw relative paths (`fetch('/api/...')`) or hardcoded `localhost` strings, as remote kiosk browsers accessing the UI over Tailscale (`http://100.95.146.94:5173`) will route relative requests to the Vite static server (resulting in 404s).
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

---

## 4. Mandatory Agent Skill & Sub-agent Search Protocol
To prevent duplicate work, reduce AI token usage (saving credit spending), and guarantee standard workflows:
1. **Check Local Skills First**: Before drafting implementation plans or performing developer tasks, the agent MUST search and read the corresponding `SKILL.md` in the local [**`.agents/skills/`**](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.agents/skills) directory.
2. **Consult the Master Index**:
   * **`dispatch-pipeline-ops`**: Core 2-phase audio processing pipeline architecture.
   * **`e2e-dispatch-testing`**: Live simulation guides, QA tests, and database purge rules.
   * **`local-stack-orchestrator`**: Docker Compose local container stack (PostgreSQL, MQTT, FastAPI) control.
   * **`emergency-routing-engine`**: Apparatus-aware pathfinding and route biasing logic.
   * **`stt-mlops-backtest`** / **`hitl-log-analysis`**: Word Error Rate metrics, Whisper STT regressions, and parsing corrections.
   * **`gis-spatial-analysis`** / **`gis-pipeline-sync`**: Shapefile bounds geocoding, parcel layers, and ESRI updates.
   * **`road-closure-management`**: Ingestion, hazard mapping, and dynamic routing updates.
   * **`kiosk-remote-ops`** / **`kiosk-ui-audit`**: Kiosk screen builds, daemon restarts, and display testing.
   * **`kiosk-responsive-ergonomics`**: CSS/UI ergonomic layout rules for kiosks.
   * **`google-imagery-streetview`**: Orienting aerial maps and panorama street-view renders.
   * **`performance-metrics-analytics`**: Latency profiling and management KPI telemetry.
3. **Use Specialized Sub-agents**: Delegate relevant sub-tasks to the pre-configured sub-agents:
   * **`call-review-analyst`** (Auditing, HITL logs, parser regressions)
   * **`dispatch-qa-engineer`** (End-to-end simulation pipelines, teardown scripts)
   * **`performance-metrics-analyst`** (Dashboard metrics and latency stats)
4. **Learn & Persist**: Propose updating rules in `GEMINI.md` or creating new custom skills in `.agents/skills/` when introducing recurring developer workflows.

---

## 5. Mandatory Sub-Agent Delegation & Model Tier Cost Enforcement
To maximize token economy and avoid burning coordinator reasoning credits on mechanical tasks:
1. **Coordinator Role**: The main chat acts exclusively as the **System Architect & Coordinator** (managing roadmap phases, reviewing sub-agent deliverables, making architectural trade-offs, and reporting to the user).
2. **Mandatory Sub-Agent Invocation**: The coordinator MUST delegate implementation tasks to sub-agents via `invoke_subagent` instead of executing bulk file edits, script writing, test runners, or tile downloads in the main coordinator loop.
3. **Model Tier Allocation Matrix**:
   * **`Model: 'flash_lite'`**: Deterministic test runners (`feed_recorded_call.py`, `pytest`), mechanical file renames, dead code/import pruning, log parsing, and linting.
   * **`Model: 'flash'`**: Feature engineering, database migrations, shapefile ingestion scripts, React JSX component decomposition, tile pre-caching scripts, API route development.
   * **`Model: 'pro'`**: Deep mathematical reasoning, DSP STFT/FFT harmonic filter calculations, OSRM Lua routing profile math, LoRA quantization analysis, and complex concurrency deadlock diagnosis.
4. **Autonomous Background Execution**: Once a sub-agent is launched with clear instructions and acceptance criteria, the coordinator MUST provide a concise update to the user and immediately end the turn, letting the sub-agent run in the background.

