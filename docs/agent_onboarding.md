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
  * Copy `.env.example` in `/backend` and `/frontend` respectively to configure environment parameters (GCP credentials path, Supabase Anon/Service-role keys, NTFY push topics, and STT engine types).
* **Consolidated Python Configurations**:
  * All DSP noise floor values, audio sample rates, vocab target directories, and GIS shapefile mappings are centralized and re-exported in [backend/cfr_dispatch/config/\_\_init\_\_.py](../backend/cfr_dispatch/config/__init__.py).

---

## 🎛️ CLI Quickstart Commands

| Command | Location | Purpose |
| :--- | :--- | :--- |
| `python main.py` | `backend/` | Launch the continuous audio listener background runner. |
| `python tests/run_test_suite.py` | `backend/` | Execute the QA verification test suite (transcription accuracy and geocoder matching checks). |
| `python scripts/feed_recorded_call.py <wav_path> [tone]` | `backend/` | Simulate an incoming radio dispatch feed by streaming a WAV file to the listener. |
| `python scripts/update_gis_data.py` | `backend/` | Execute the monthly GIS update and compare cache changes (runs automated via Windows Scheduler). |
| `npm run dev` | `frontend/` | Run the React dashboard development server. |
| `npm run build` | `frontend/` | Compile the frontend client production build into `frontend/dist`. |

---

## 📂 Documentation Catalog

Please refer to the following documents for comprehensive domain-specific blueprints:

| Document | Target Location | Scope |
| :--- | :--- | :--- |
| **Project Overview** | [README.md](../README.md) | High-level system structure, mermaid workflow schemas, and 2-phase pipelines. |
| **Call Structure** | [docs/call_structure.md](./call_structure.md) | Dispatch speech templates, regex parsing splits, and phonetic correction matrices. |
| **Supabase Setup** | [docs/supabase_setup.md](./supabase_setup.md) | PostgreSQL table contracts, RLS policies, and realtime WebSocket config script. |
| **GIS Endpoints** | [docs/gis_endpoints.md](./gis_endpoints.md) | Coquitlam ArcGIS MapServer layers list, and local Dynamic Viewport mock blueprints. |
| **Test Matrix** | [docs/test_procedures.md](./test_procedures.md) | Step-by-step diagnostic workflows for tone SPOT tests, database inserts, and mic levels. |
| **Hardware Spec** | [docs/hardware_specification.md](./hardware_specification.md) | Physical setup configs (Pi soundcards, Nginx server blocks, and x86 laptop kiosks). |
| **Laptop Kiosk Setup** | [docs/laptop_kiosk_setup.md](./laptop_kiosk_setup.md) | Detailed installation tutorial for headless Ubuntu kiosk displays and auto-updates. |
| **Milestones** | [docs/milestones.md](./milestones.md) | Development roadmap tracking completed steps and target release items. |
| **Privacy Compliance** | [docs/privacy.md](./privacy.md) | Voice monitoring rules, local RAM buffering specs, and FOI compliant data policies. |
| **Phase 2 Walkthrough** | [docs/walkthroughs/phase_2_micro_domain_service_split.md](./walkthroughs/phase_2_micro_domain_service_split.md) | Structural refactoring details of decoupling the monolith into microservices. |
| **Hydrant Walkthrough** | [docs/walkthroughs/hydrants_and_maintenance_walkthrough.md](./walkthroughs/hydrants_and_maintenance_walkthrough.md) | Turf.js nearest hydrant overlay integration and NFPA 291 vector markers mapping. |

---

## 📡 Remote Kiosk Access & Agent Commands

The remote station kiosk machine is connected to this development host via **Tailscale SSH**. This allows developers and AI agents to securely query status, read logs, restart services, and transfer files directly from this machine's terminal.

### 🔑 Connection Credentials
* **Remote Hostname**: `cfr-mapping-tcfh`
* **Tailscale IP**: `100.95.146.94`
* **Username**: `tcfire`

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

To optimize transcription quality and test new grammar sets or model parameters without breaking historic dispatches, the project includes an automated evaluation and feedback pipeline.

### 1. Extract Training Ground-Truth Data
Pull verified user corrections (ground truth reference transcripts) and their raw `.wav` recordings from Supabase to your local cache:
```bash
ssh tcfire@100.95.146.94 "XDG_RUNTIME_DIR=/run/user/1000 /home/tcfire/CFR-EVO-APP/.venv/bin/python /home/tcfire/CFR-EVO-APP/backend/scripts/extract_training_data.py"
```
* **Output**: Audio files cached at `backend/data/training/audio/` and metadata mappings saved to `backend/data/training/metadata.csv`.
* **Database Action**: Automatically patches the database, setting `model_updated = true` for the cached records, shifting their status in the React Dashboard column from `🟡 QUEUED` to `🟢 YES` to verify the sync.

### 2. Run Backtest & Regression Evaluation
Evaluate the current model's accuracy (Word Error Rate & Character Error Rate) against the historical ground-truth dataset to verify improvements and prevent regressions:
```bash
ssh tcfire@100.95.146.94 "XDG_RUNTIME_DIR=/run/user/1000 /home/tcfire/CFR-EVO-APP/.venv/bin/python /home/tcfire/CFR-EVO-APP/backend/scripts/backtest_regression.py"
```
* **Output**: Renders a side-by-side comparison (Human Reference, Old Hypothesis, New Hypothesis), logs results locally, and inserts a run summary into the Supabase `evaluation_history` table to feed the dashboard chart.

### 3. Toggling Speech-to-Text Engines
To switch between Google Cloud STT V2 and Local Offline Whisper:
* Edit `backend/.env` on the kiosk:
  * For Google: `STT_ENGINE=google`
  * For Whisper: `STT_ENGINE=whisper`
* After changing the engine configuration, restart the daemon:
  ```bash
  ssh tcfire@100.95.146.94 "sudo systemctl restart cfr-agent"
  ```


