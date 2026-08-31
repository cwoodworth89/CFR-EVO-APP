# CFR EVO: AI Agent & Developer Onboarding Guide

Welcome! This onboarding document is designed to get future developers and AI coding assistants up to speed on the **CFR EVO** workspace layout, runtime heuristics, and testing procedures.

---

## 🧭 Repository Domain Map

The project is decoupled into isolated domain directories to ensure modularity and zero cyclical imports:

1. **`/frontend`** (React + Vite):
   - The web app client interface. Manages rendering Leaflet map boards, nearest hydrant routing overlays, DriveBC traffic hazards, and recruits training games.
2. **`/backend`** (Python 3.10+):
   - The core orchestrator. Manages continuous audio capture streams, DSP tone-spotting checks, Whisper/GCP Speech-to-Text transcription, regex templates parsing, and database synchronization.
3. **`/services`** (Decoupled Microservices):
   - **`/services/gis`**: Boundary spatial indexes and local geocoding validators.
   - **`/services/audio_analysis`**: DSP Butterworth filters and Hamming window peak calculators.
   - **`/services/dispatch_notifications`**: DB connection post/patch handlers and push notification brokers.

---

## ⚠️ CRITICAL: Sibling Import Path Resolution
To ensure domain isolation, sibling microservice packages (in `/services/*/src`) are decoupled from the `/backend` folder.

During static analysis, the IDE's python typechecker might throw `ImportError: cannot find module 'gis_service'` when inspecting orchestration files. 
* **Important**: **Do NOT modify or "fix" these sibling import statements.**
* **Heuristics**: Sibling service paths are dynamically injected to `sys.path` at runtime inside [backend/cfr_dispatch/\_\_init\_\_.py](../backend/cfr_dispatch/__init__.py) when the orchestrator starts up.
* **IDE Fix**: To resolve these warnings in your VS Code typechecker statically, the workspace includes `.vscode/settings.json` which appends these paths to `python.analysis.extraPaths`.

---

## ⚙️ Project Configuration & Environments

* **`.env` files**:
  * Copy `.env.example` in `/backend` and `/frontend` respectively to configure environment parameters (GCP credentials path, NTFY push topics, and STT engine types).
* **Consolidated Python Configurations**:
  * All DSP noise floor values, audio sample rates, vocab target directories, and GIS shapefile mappings are centralized and re-exported in [backend/cfr_dispatch/config/\_\_init\_\_.py](../backend/cfr_dispatch/config/__init__.py).

---

## 🎛️ CLI Quickstart Commands

| Command | Location | Purpose |
| :--- | :--- | :--- |
| `docker compose up -d` | `./` | Start the local containerized stack (PostgreSQL 16, Mosquitto MQTT, Ntfy, FastAPI). |
| `python main.py` | `backend/` | Launch the continuous audio listener background runner. |
| `python tests/run_test_suite.py` | `backend/` | Execute the QA verification test suite (transcription accuracy and geocoder matching checks). |
| `python scripts/feed_recorded_call.py <wav_path> [tone]` | `backend/` | Simulate an incoming radio dispatch feed by streaming a WAV file to the listener. |
| `python scripts/backtest_parser.py` | `backend/` | Run comparative accuracy benchmarks between production and test parsers on database ground-truth calls. |
| `python scripts/update_gis_data.py` | `backend/` | Execute the monthly GIS update and compare cache changes (runs automated via Windows Scheduler). |
| `npm run dev` | `frontend/` | Run the React dashboard development server. |
| `npm run build` | `frontend/` | Compile the frontend client production build into `frontend/dist`. |

---

## 📂 Documentation Catalog

Please refer to the following documents for comprehensive domain-specific blueprints:

| Document | Target Location | Scope | Active Agent Skill |
| :--- | :--- | :--- | :--- |
| **Project Overview** | [README.md](../README.md) | High-level system structure and two-phase pipelines. | `dispatch-pipeline-ops` |
| **Local DB Setup** | [docs/local_database_setup.md](./local_database_setup.md) | Containerized PostgreSQL 16 schema, FastAPI routes. | `local-stack-orchestrator` |
| **Ntfy Server & QR Spec** | [docs/ntfy_server_access_and_qr_spec.md](./docs/ntfy_server_access_and_qr_spec.md) | Ntfy server access, HTTPS, and QR payloads. | None |
| **Public Domain & SSL** | [docs/public_domain_and_ssl_migration.md](./docs/public_domain_and_ssl_migration.md) | Nginx reverse proxy and SSL certs. | None |
| **Call Structure** | [docs/call_structure.md](./docs/call_structure.md) | Dispatch templates and phonetic matrices. | `hitl-log-analysis` |
| **GIS Endpoints** | [docs/gis_endpoints.md](./docs/gis_endpoints.md) | MapServer layers and Dynamic Viewport mocks. | `gis-spatial-analysis` |
| **Test Matrix** | [docs/test_procedures.md](./docs/test_procedures.md) | Tone spot checks, database inserts, mic levels. | `e2e-dispatch-testing` |
| **Hardware Spec** | [docs/hardware_specification.md](./docs/hardware_specification.md) | Pi soundcards and laptop kiosk hardware. | None |
| **Laptop Kiosk Setup** | [docs/laptop_kiosk_setup.md](./docs/laptop_kiosk_setup.md) | Kiosk displays and auto-updates. | `kiosk-remote-ops` |
| **Milestones** | [docs/milestones.md](./docs/milestones.md) | Development roadmap and releases. | None |
| **Privacy Compliance** | [docs/privacy.md](./docs/privacy.md) | Voice monitoring rules and local RAM buffer. | None |
| **Phase 2 Walkthrough** | [docs/walkthroughs/phase_2_micro_domain_service_split.md](./walkthroughs/phase_2_micro_domain_service_split.md) | Decoupling monolith into microservices. | None |
| **Hydrant Walkthrough** | [docs/walkthroughs/hydrants_and_maintenance_walkthrough.md](./walkthroughs/hydrants_and_maintenance_walkthrough.md) | Turf.js nearest hydrant mapping. | `gis-pipeline-sync` |
| **Local Stack & DSP Walkthrough** | [docs/walkthroughs/local_stack_and_dsp_calibration_walkthrough.md](./walkthroughs/local_stack_and_dsp_calibration_walkthrough.md) | PostgreSQL index tuning and DSP calibration. | `performance-metrics-analytics` |
| **Development Freeze Summary** | [docs/development_freeze_summary.md](./development_freeze_summary.md) | Current implementation status (Phase A–F): PostGIS migration, STT vocab biasing, API decomposition, geocoder 2.0. **Start here for current state.** | `gis-spatial-analysis` |
| **Debug & QA Punch List** | [docs/debug_and_qa_punchlist.md](./debug_and_qa_punchlist.md) | Open bugs and edge cases (routing anomalies, geocoding fallbacks, UI refinements). | `e2e-dispatch-testing` |
| **Data Contracts** | [docs/data_contracts.md](./data_contracts.md) | Shared payload/schema shapes between backend, GIS, and frontend. | None |
| **Routing Engine Reference** | [docs/evo_routing_engine.md](./evo_routing_engine.md) | ⚠️ **Superseded** — presents staged, not-applied apparatus physics as live (§6.4). Use the skill; the doc is history. | `emergency-routing-engine` |
| **Dispatch Integration Options** | [docs/dispatch_integration_options.md](./dispatch_integration_options.md) | Radio/audio ingestion integration approaches. | `dispatch-pipeline-ops` |
| **Project Purpose & History** | [docs/PROJECT_PURPOSE_AND_HISTORY.md](./PROJECT_PURPOSE_AND_HISTORY.md) | Origin story and evolution from training-game prototype to dispatch HUD. | None |
| **Project Ideas / Future Features** | [docs/PROJECT_IDEAS.md](./PROJECT_IDEAS.md) | Backlog of future feature candidates (e.g. reimplemented driver training module). | None |

---

## 🤖 AI Agent Customizations (Custom Skills & Sub-agents)

CFR EVO is equipped with a set of specialized **custom skills** and **sub-agents** located in [**`.claude/skills`**](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.claude/skills) and [**`.claude/agents`**](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.claude/agents) (Claude Code's native convention). These resources extend agent capabilities and document domain runbooks. The original Antigravity-authored copies were archived out of the repository on 2026-08-30 (see `../CFR-EVO-APP-agent-archive/`); `.claude/` is the sole canonical, auto-loaded location.

### 🛠️ Specialized Sub-agents
When spawning helper sub-agents, inherit from these type specifications:
* **`call-review-analyst`**: Specialist in auditing dispatch call logs, triaging HITL reviews, diagnosing audio transcripts, and phonetic ambiguity analysis.
* **`dispatch-qa-engineer`**: Specialist in automated end-to-end dispatch simulations, testing protocol enforcement, and clean QA database teardowns.
* **`performance-metrics-analyst`**: Specialist in operational metrics analytics (Turnout Lead Time, Parsing Accuracy %, Stage Latency) and executive HUD telemetry design.
* **`frontend-kiosk-architect`**, **`gis-spatial-engineer`**, **`kiosk-remote-operator`**, **`pipeline-core-engineer`**, **`stt-mlops-evaluator`**: see [`.claude/agents/`](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.claude/agents) for the full roster.

### 📚 Domain Skills
These markdown runbooks guide agents through complex developer workflows:
* [**`dispatch-pipeline-ops`**](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.claude/skills/dispatch-pipeline-ops/SKILL.md): Architecture of the 2-phase real-time dispatch audio pipeline.
* [**`e2e-dispatch-testing`**](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.claude/skills/e2e-dispatch-testing/SKILL.md): Running system tests, MQTT validation, and purging test entries.
* [**`performance-metrics-analytics`**](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.claude/skills/performance-metrics-analytics/SKILL.md): Guidelines for measuring pipeline latencies and business intelligence metrics.
* [**`gis-spatial-analysis`**](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.claude/skills/gis-spatial-analysis/SKILL.md): Procedures for shapefile queries, coordinate reference transformations, and NFPA 291 hydrants.
* [**`gis-pipeline-sync`**](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.claude/skills/gis-pipeline-sync/SKILL.md): Pulling Coquitlam ESRI shapefiles and GIS caching updates.
* [**`google-imagery-streetview`**](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.claude/skills/google-imagery-streetview/SKILL.md): Ingestion and display of satellite imagery and Google Street View.
* [**`road-closure-management`**](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.claude/skills/road-closure-management/SKILL.md): Tracking active road closures, construction zones, and routing around hazards.

---

## 📡 Remote Kiosk Access & Agent Commands

The remote station kiosk machine is connected to this development host via **Tailscale SSH**. This allows developers and AI agents to securely query status, read logs, restart services, and transfer files directly from this machine's terminal.

### 🔑 Connection Credentials
* **Remote Hostname**: `cfr-mapping-tcfh`
* **Tailscale IP**: `100.95.146.94`
* **Username**: `tcfire`

### 💻 SSH Config Shortcuts (Dev Laptop Alignment)
To connect using simple shortcuts, add the following to your development machine's `~/.ssh/config` (or `C:\Users\Curtis\.ssh\config` on Windows):

```text
# --- Kiosk / Dispatch Display ---
Host tcfire-dispatch
    HostName cfr-mapping-tcfh.otter-sailfin.ts.net
    User tcfire

# --- Local & VPN NAS Shortcut (with automatic failover) ---
# 1. Use local physical IP if connected locally on network (pingable)
Match Host nas Exec "ping -n 1 -w 100 10.10.20.5"
    HostName 10.10.20.5
    User admin

# 2. Otherwise, fall back to Tailscale DNS domain
Host nas
    HostName nas.otter-sailfin.ts.net
    User admin
```

With this, future agents and developers can execute SSH commands using simple aliases:
* `ssh tcfire-dispatch`
* `ssh nas`

Additionally, you can map the local IP address permanently to hosts file on Windows (`C:\Windows\System32\drivers\etc\hosts`) to get `\\nas` sharing work locally:
```text
10.10.20.5  nas
```

### 🔄 Git & Remote Programming Workflow (CRITICAL)
To maintain code sanity and avoid divergence between development and production, follow this workflow:
1. **Local Edits**: Make all permanent code, configuration, or documentation changes in the local git repository workspace first. **Do not modify production code files directly on the remote kiosk.**
2. **Interactive Testing via SCP**: For fast iteration during debugging or testing, copy local scripts/changes to the kiosk using `scp`, and run them over SSH.
3. **Commit & Deploy**: Once changes are verified, commit and push them to the central Git repository from your local development machine. On the remote kiosk, run a `git pull` or execute the update script to pull down the changes cleanly.
4. **Rebuild Frontend Assets**: Since the compiled production folder (`frontend/dist`) is in `.gitignore`, you must manually re-compile the frontend assets on the remote kiosk after pulling code changes for Nginx to serve them:
   ```bash
   ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/frontend && npm install && npm run build"
   ```

### ⚠️ Audio System Remoting: XDG_RUNTIME_DIR Heuristic
When invoking python scripts or commands that interact with the audio subsystem (`sounddevice` / PortAudio / ALSA / PulseAudio) remotely over an SSH session, you **must** prepend the user's runtime directory environment variable:
* **Prefix**: `XDG_RUNTIME_DIR=/run/user/1000` (assuming user `tcfire` is UID 1000).
* If omitted, PortAudio will fail with: `sounddevice.PortAudioError: Error initializing PortAudio: Unanticipated host error [PaErrorCode -9999]: 'PulseAudio_Initialize: Can't connect to server'`.

### 💻 Command Reference for AI Agents

As an AI agent, you can propose and execute remote commands over SSH. Since the session runs in a non-interactive shell, verify that all commands are structured non-interactively (e.g., executing a quick check rather than spawning a prompt):

* **System Status & Uptime**:
  ```powershell
  ssh tcfire@100.95.146.94 "uname -a; uptime"
  ```
* **Query Audio Devices (Using sounddevice)**:
  ```powershell
  ssh tcfire@100.95.146.94 "XDG_RUNTIME_DIR=/run/user/1000 /home/tcfire/CFR-EVO-APP/.venv/bin/python -c 'import sounddevice as sd; print(sd.query_devices())'"
  ```
* **Run 15-Second Audio Diagnostic**:
  ```powershell
  # Copy local diagnostic script first
  scp ./backend/scripts/record_test.py tcfire@100.95.146.94:/home/tcfire/CFR-EVO-APP/backend/scripts/record_test.py
  # Execute with device environment prefix
  ssh tcfire@100.95.146.94 "XDG_RUNTIME_DIR=/run/user/1000 /home/tcfire/CFR-EVO-APP/.venv/bin/python /home/tcfire/CFR-EVO-APP/backend/scripts/record_test.py 13"
  ```
* **Verify Audio DSP / System Logs**:
  ```powershell
  ssh tcfire@100.95.146.94 "tail -n 50 /home/tcfire/CFR-EVO-APP/backend/dispatch.log"
  ```
* **Restart the Orchestration Daemon**:
  ```powershell
  ssh tcfire@100.95.146.94 "sudo systemctl restart cfr-agent"
  ```
* **Copy/Deploy files (e.g., Shapefiles)**:
  ```powershell
  scp -r ./backend/data/ tcfire@100.95.146.94:/home/tcfire/CFR-EVO-APP/backend/
  ```
* **Build Frontend Production Assets on Kiosk**:
  ```powershell
  ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/frontend && npm install && npm run build"
  ```

> [!NOTE]
> **Authentication Approval**: 
> If Tailscale SSH requires fresh authentication, the command output will print a browser approval URL. Prompt the user to open and approve the link in their browser. Once they click **Approve**, the command will resume and complete automatically.

## 📈 Speech-to-Text Training & MLOps Feedback Pipeline

To optimize transcription quality and test new grammar sets or model parameters without breaking historic dispatches, the project includes an automated evaluation, feedback, and training pipeline.

### 🔄 HITL Dispatch Verification & Corrections Workflow
When reviewing dispatches in the admin interface:
- **HITL Ratings**: The **Perfect**, **Operational**, and **Failed** rating badges purely tag dispatch quality without overwriting manual corrections.
- **Prefilling System Data**: Use the **"📋 Prefill Defaults"** button to copy Stage 3 template text, geocoded address, incident type, and responding units into the text input boxes.
- **Whisper Training Dataset Opt-in**: Automatically defaults to unchecked (`false`) for calls under 35 seconds (cut-off calls) and checked (`true`) for full calls. This is editable at any time.

### 1. Extract Training Ground-Truth Data
Pull verified user corrections (ground truth reference transcripts) and their raw `.wav` recordings from local PostgreSQL DB to your local cache:
```bash
ssh tcfire@100.95.146.94 "XDG_RUNTIME_DIR=/run/user/1000 /home/tcfire/CFR-EVO-APP/.venv/bin/python /home/tcfire/CFR-EVO-APP/backend/scripts/extract_training_data.py"
```
* **Output**: Audio files cached at `backend/data/training/audio/` and metadata mappings saved to `backend/data/training/metadata.csv`.
* **Standardization**: Text is converted to all-lowercase, and standard punctuation (periods, commas, semicolons) is stripped.
* **Double-Round Duplication**: If the call represents a double-round template dispatch (duration > 25s), the clean transcript is duplicated to match the double-round audio timeline (e.g. `[clean_transcript] [clean_transcript]`). This teaches the model to align both rounds without deletion hallucinations.
* **Dataset Opt-Out Filter**: The script automatically skips any records where `target.include_in_training` is set to `false` (e.g. cut-off or noisy calls opted out via the dashboard checkbox).
* **Database Action**: Automatically patches the database, setting `model_updated = true` for the cached records, shifting their status in the React Dashboard column from `🟡 QUEUED` to `🟢 YES` to verify the sync.

### 2. Run Backtest & Regression Evaluation
Evaluate the current model's accuracy (Word Error Rate & Character Error Rate) against the historical ground-truth dataset to verify improvements and prevent regressions:
```bash
ssh tcfire@100.95.146.94 "XDG_RUNTIME_DIR=/run/user/1000 /home/tcfire/CFR-EVO-APP/.venv/bin/python /home/tcfire/CFR-EVO-APP/backend/scripts/backtest_regression.py"
```
* **Output**: Renders a side-by-side comparison (Human Reference, Old Hypothesis, New Hypothesis), logs results locally, and inserts a run summary into the local `evaluation_history` table to feed the dashboard chart.
* **Template-Normalized WER**: The backtest parses and reconstructs the Human Reference text before calculating WER, providing a true 0-to-100% structured accuracy check (SMMR - Structured Metadata Match Rate).

### 3. Sync Dataset to Google Drive (rclone)
Sync your local training cache to Google Drive's private AppData folder:
```bash
ssh tcfire@100.95.146.94 "rclone sync /home/tcfire/CFR-EVO-APP/backend/data/training gdrive: --progress"
```

### 4. Load Dataset in Google Colab (Free T4 GPU)
Mount `rclone` directly inside Google Colab using your kiosk config to download the training files:
```python
# Install rclone on Colab
!apt-get update && apt-get install -y rclone

# Write credentials (copied from /home/tcfire/.config/rclone/rclone.conf)
import os
os.makedirs("/root/.config/rclone/", exist_ok=True)
with open("/root/.config/rclone/rclone.conf", "w") as f:
    f.write("""[gdrive]
type = drive
scope = drive.appfolder
root_folder_id = appDataFolder
token = {"access_token":"ya29.a0ARG...","token_type":"Bearer","refresh_token":"1//065...","expiry":"..."}
""")

# Download files
!rclone copy gdrive: /content/dataset
```

### 5. Toggling Speech-to-Text Engines
To switch between Google Cloud STT V2 and Local Offline Whisper:
* Edit `backend/.env` on the kiosk:
  * For Google: `STT_ENGINE=google`
  * For Whisper: `STT_ENGINE=whisper`
* After changing the engine configuration, restart the daemon:
  ```bash
  ssh tcfire@100.95.146.94 "sudo systemctl restart cfr-agent"
  ```


