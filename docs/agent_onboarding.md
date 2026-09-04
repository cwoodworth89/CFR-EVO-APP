# CFR EVO: AI Agent & Developer Onboarding Guide

Welcome! This onboarding document is designed to get future developers and AI coding assistants up to speed on the **CFR EVO** workspace layout, runtime heuristics, and testing procedures.

---

## 🧭 Repository Domain Map

The project is decoupled into isolated domain directories to ensure modularity and zero cyclical imports:

1. **`/frontend`** (React + Vite):
   - The web app client interface. Manages Leaflet map boards, nearest-hydrant routing overlays, road closures, and the HITL review panel. **Training mode was removed at `d5fbdcc`** — if you find a reference to recruit training games, it is stale.
2. **`/backend`** (Python 3.10+):
   - The core orchestrator. Manages continuous audio capture, DSP tone-spotting, **local faster-whisper transcription**, parsing, and database synchronisation. **There is no cloud STT and no engine selector** — the `STT_ENGINE` setting was removed on 2026-08-31. A cloud dependency would break both the offline and the $0-cost requirements (CLAUDE.md §1).
3. **`/services`** (Decoupled Microservices):
   - **`/services/gis`**: Boundary spatial indexes and local geocoding validators.
   - **`/services/audio_analysis`**: DSP Butterworth filters and Hamming window peak calculators.
   - **`/services/dispatch_notifications`**: DB connection post/patch handlers and push notification brokers.

---

## 🔎 Before you believe anything: verify it

**The punch list lags the code.** On 2026-08-31 a sweep of the 21 crew-visible open items found
**five already fixed and simply unrecorded** — `#42`, `#31`, `#43a`, `#12`, `#38`. Reading the
tracker and starting work would have meant re-fixing what was already done.

So the first move on any item is a query, not a read:

```bash
# Is the defect still real? Ask the running system, not the document.
python -c "import os;from sqlalchemy import create_engine,text;\
print(create_engine(os.environ['DATABASE_URL']).connect().execute(text('SELECT ...')).fetchall())"
```

**`DATABASE_URL` is per-machine — check which side you are on.** On the dev laptop it is set
in your shell and points across Tailscale at the kiosk, which is what makes the one-liner above
work locally. On the **kiosk itself** it lives in `backend/.env` (git-ignored, so it is not
synced — it was missing entirely until 2026-08-31).

Its absence there is close to invisible, because the codebase handles it three different ways:

| Code path | With `DATABASE_URL` unset |
|:--|:--|
| `config/vocab.py` (×3), `session_store.py`, `worker.py` | falls back to a hardcoded `postgresql://cfr_user:...@localhost:5432/cfr_dispatch` — works, so nothing looks wrong |
| `extract_training_data.py` → `learn_new_incident_types()` | no fallback: logs an error and returns. It had never once written; `public.vocabulary` held **0** rows with `source='hitl_learned'` |
| `backtest_parser_corpus.py`, `backtest_round_comparison.py` | deliberate `sys.exit` with a message |

So "is it set?" has no single answer, and the live pipeline running fine is not evidence that
it is. Read `backend/.env` on the machine you are actually targeting.

The `cfr-postgres` MCP server is **read-only** — fine for checking, and writes must go through
SQLAlchemy or `psql` on the kiosk.

This is CLAUDE.md §6.6 pointed at our own records: *distinguish reported from confirmed.*
A punch-list item is a **report**. The database is the system of record.

---

## 🧰 Environment gotchas that cost real time

| | |
|:--|:--|
| **No `geopandas` / `shapely` locally** | The local `.venv` is minimal. Anything importing them runs on the kiosk: `ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && .venv/bin/python …"`. `dbfread` is available locally, and a `.shp` bounding box can be parsed directly from the binary if you only need extents. |
| **`PYTHONIOENCODING=utf-8`** | Windows consoles default to cp1252. Any script printing an em-dash or emoji dies with `UnicodeEncodeError`. Prefix every `python` invocation that prints prose. |
| **SSH can hang silently** | If the sandbox blocks the SSH binary it produces **zero output and never returns**, ignoring even `-o ConnectTimeout=10`. It is not a network problem. Confirm the host is alive by querying Postgres — that path is independent. |
| **API changes need `--build`** | `docker compose up -d --build api`. A restart alone ships nothing. The compose service is `api`; the container is `cfr_api`. |
| **Shapefiles are kiosk-only** | `backend/data/` is git-ignored (§3.6). Addresses live in `backend/data/Property_Information/`, zones in `backend/data/Emergency_Response_Zones/` — different directories, and the import's defaults already know both. |
| **Run the full suite early** | `pytest backend/tests/` — three modules fail to collect on a dev laptop for missing `geopandas`, `pvporcupine`, `librosa` (punch-list #10); that is expected. On 2026-08-31 running it surfaced a live 500 in an endpoint nobody was working on. |

---

## 🗂️ Where things belong

Follow the existing convention rather than inventing one.

| Artifact | Goes in |
|:--|:--|
| Schema change | `backend/migrations/YYYY-MM-DD_short_name.sql` — with a `WHY` block; they are read far more than they are run |
| A defect or open question | A file under `docs/punchlist/`, plus a row in `docs/debug_and_qa_punchlist.md` |
| A decision, with its evidence | `docs/briefings/<topic>.md`, linked from the punch-list item it settles |
| What governs an operational value | `docs/standards/README.md` — and if nothing covers it, **stop and ask** (§7.2) |
| A library or field that does not behave like its name | [`docs/standards/dependency-behaviour.md`](standards/dependency-behaviour.md) |
| A repeatable procedure | `.claude/skills/<name>/SKILL.md` — check there before writing a runbook |
| A script | `backend/scripts/`, with a row in its README. Already-run ones go to `backend/scripts/oneshot/` |
| Something found mid-task that is out of scope | `docs/post_freeze_backlog.md`, one line — unless it is crew-visible, which promotes immediately |

**These are checked, not merely documented:**

```bash
python backend/scripts/audit_skill_references.py            # skills naming absent identifiers
python backend/scripts/audit_skill_references.py --scripts  # a row per script, a script per row
python backend/scripts/audit_skill_references.py --docs     # broken links, prose naming nothing
```

Run the last two before committing documentation. Everything that rotted badly enough to
mislead — the scripts README, the routing standard, the `GEMINI.md` files, this file's own
domain map — had nothing checking it. Everything that stayed true did.

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
  * `backend/.env` and `frontend/.env.local` are git-ignored and have no template in the tree; the `.env.example` files were deleted 2026-09-03 because they named variables the code no longer reads. The running copies are on the kiosk (CLAUDE.md §3). **There is no GCP credentials path** — an earlier version of this line said there was, and cloud STT is forbidden by CLAUDE.md §1.
* **Consolidated Python Configurations**:
  * All DSP noise floor values, audio sample rates, vocab target directories, and GIS shapefile mappings are centralized and re-exported in [backend/cfr_dispatch/config/\_\_init\_\_.py](../backend/cfr_dispatch/config/__init__.py).

---

## 🎛️ CLI Quickstart Commands

| Command | Location | Purpose |
| :--- | :--- | :--- |
| `docker compose up -d` | `./` | Start the local containerized stack (PostgreSQL 16, Mosquitto MQTT, Ntfy, FastAPI). |
| `python main.py` | `backend/` | Launch the continuous audio listener background runner. |
| `python scripts/backtest_parser.py` | `backend/` | Run comparative accuracy benchmarks between production and test parsers on database ground-truth calls. |
| `python scripts/update_gis_data.py` | `backend/` | Execute the monthly GIS update and compare cache changes (runs automated via Windows Scheduler). |
| `npm run dev` | `frontend/` | Run the React dashboard development server. |
| `npm run build` | `frontend/` | Compile the frontend client production build into `frontend/dist`. |

---

## 📂 Documentation Catalog

For the reading map grouped by purpose, start at [`docs/README.md`](./README.md).

Please refer to the following documents for comprehensive domain-specific blueprints:

| Document | Target Location | Scope | Active Agent Skill |
| :--- | :--- | :--- | :--- |
| **Project Overview** | [README.md](../README.md) | High-level system structure and two-phase pipelines. | `dispatch-pipeline-ops` |
| **Ntfy Server & QR Spec** | [docs/ntfy_server_access_and_qr_spec.md](./ntfy_server_access_and_qr_spec.md) | Ntfy server access, HTTPS, and QR payloads. | None |
| **Call Structure** | [docs/call_structure.md](./call_structure.md) | Dispatch templates and phonetic matrices. | `hitl-log-analysis` |
| **Hardware Spec** | [docs/hardware_specification.md](./hardware_specification.md) | Pi soundcards and laptop kiosk hardware. | None |
| **Laptop Kiosk Setup** | [docs/laptop_kiosk_setup.md](./laptop_kiosk_setup.md) | Kiosk displays and auto-updates. | `kiosk-remote-ops` |
| **Milestones** | [docs/milestones.md](./milestones.md) | Development roadmap and releases. | None |
| **Privacy Compliance** | [docs/privacy.md](./privacy.md) | Voice monitoring rules and local RAM buffer. | None |
| **Development Freeze Summary** | [docs/development_freeze_summary.md](./development_freeze_summary.md) | Current implementation status (Phase A–F): PostGIS migration, STT vocab biasing, API decomposition, geocoder 2.0. **Start here for current state.** | `gis-spatial-analysis` |
| **Dispatch Integration Options** | [docs/dispatch_integration_options.md](./dispatch_integration_options.md) | Radio/audio ingestion integration approaches. | `dispatch-pipeline-ops` |
| **Project Purpose & History** | [docs/PROJECT_PURPOSE_AND_HISTORY.md](./PROJECT_PURPOSE_AND_HISTORY.md) | Origin story and evolution from training-game prototype to dispatch HUD. | None |
| **Project Ideas / Future Features** | [docs/PROJECT_IDEAS.md](./PROJECT_IDEAS.md) | Backlog of future feature candidates (e.g. reimplemented driver training module). | None |

---

## 🤖 AI Agent Customizations (Custom Skills & Sub-agents)

CFR EVO is equipped with a set of specialized **custom skills** and **sub-agents** located in [**`.claude/skills`**](../.claude/skills) and [**`.claude/agents`**](../.claude/agents) (Claude Code's native convention). These resources extend agent capabilities and document domain runbooks. The original Antigravity-authored copies were archived out of the repository on 2026-08-30 (see `../CFR-EVO-APP-agent-archive/`); `.claude/` is the sole canonical, auto-loaded location.

### 🛠️ Specialized Sub-agents
When spawning helper sub-agents, inherit from these type specifications:
* **`call-review-analyst`**: Specialist in auditing dispatch call logs, triaging HITL reviews, diagnosing audio transcripts, and phonetic ambiguity analysis.
* **`performance-metrics-analyst`**: Specialist in operational metrics analytics (Turnout Lead Time, Parsing Accuracy %, Stage Latency) and executive HUD telemetry design.
* **`frontend-kiosk-architect`**, **`gis-spatial-engineer`**, **`kiosk-remote-operator`**, **`pipeline-core-engineer`**, **`stt-mlops-evaluator`**: see [`.claude/agents/`](../.claude/agents) for the full roster.

### 📚 Domain Skills
These markdown runbooks guide agents through complex developer workflows:
* [**`dispatch-pipeline-ops`**](../.claude/skills/dispatch-pipeline-ops/SKILL.md): Architecture of the 2-phase real-time dispatch audio pipeline.
* [**`performance-metrics-analytics`**](../.claude/skills/performance-metrics-analytics/SKILL.md): Guidelines for measuring pipeline latencies and business intelligence metrics.
* [**`gis-spatial-analysis`**](../.claude/skills/gis-spatial-analysis/SKILL.md): Procedures for shapefile queries, coordinate reference transformations, and NFPA 291 hydrants.
* [**`gis-pipeline-sync`**](../.claude/skills/gis-pipeline-sync/SKILL.md): Pulling Coquitlam ESRI shapefiles and GIS caching updates.
* [**`google-imagery-streetview`**](../.claude/skills/google-imagery-streetview/SKILL.md): Ingestion and display of satellite imagery and Google Street View.
* [**`road-closure-management`**](../.claude/skills/road-closure-management/SKILL.md): Tracking active road closures, construction zones, and routing around hazards.

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

The full runbook is the **`stt-mlops-backtest`** skill
([`.claude/skills/stt-mlops-backtest/SKILL.md`](../.claude/skills/stt-mlops-backtest/SKILL.md)).
This section is the shape of it; the skill has the commands and the traps.

### 🔄 HITL Dispatch Verification & Corrections Workflow
When reviewing dispatches in the admin interface:
- **HITL Ratings**: the **Perfect**, **Operational**, and **Failed** badges tag dispatch quality
  without overwriting manual corrections. `FAILED` means crews would not have reached the address.
- **Prefilling System Data**: **"📋 Prefill Defaults"** copies the Stage 3 template text,
  geocoded address, incident type, and responding units into the inputs.
- **Whisper Training Dataset Opt-in** (`target.include_in_training`): defaults to unchecked
  for calls under 35 seconds and checked for full calls. **This flag is the authoritative
  selection for training** -- the operator un-flags PA pages (`[PA]` in the review note),
  cut-offs, and the post-round-addendum calls by hand.
- **Review notes live in `target->>'review_notes'`.** The `review_notes` column is a stale
  partial mirror (60 of 276 notes) and holds none of the `[PA]` tags. Read
  `COALESCE(target->>'review_notes', review_notes)`.

### The pipeline, in order

| Step | Script | What it does |
|:--|:--|:--|
| 0 | `check_verified_transcripts.py` | Spell- and street-checks every flagged verified transcript against `public.roads` / `public.vocabulary` / `public.parcels` / the corpus. **Blocks** training on a main-address street the city does not have. |
| 1 | `prepare_training_clips.py --force` | One clip per call: round 1 only, cut at measured word timestamps (onset = first "Coquitlam", boundary = start of round 2 via `split_rounds`). Writes a deterministic 10% holdout. Runs step 0 first. |
| 2 | `train_whisper_lora.py` | LoRA fine-tune, merge, CTranslate2 int8. **Set `WHISPER_CT2_OUT` to a fresh directory**; never over the deployed one. |
| 3 | `eval_round1_holdout.py` | WER on the clips training never saw, several models side by side. |
| 4 | `backtest_regression.py` | Round-aligned SMMR against the stored production transcripts; writes `public.evaluation_history`. |
| 5 | `.env` + `systemctl restart cfr-agent` | Deploy. Ask first -- the restart drops the listener. |
| 6 | `tar` to `cfr-backups/`, then `pull_backups.ps1` | Archive the whole model directory off the kiosk. |

All of it runs **on the kiosk** with `XDG_RUNTIME_DIR=/run/user/1000` -- importing
`cfr_dispatch` initialises PortAudio. The Colab notebook
(`docs/cfr_whisper_colab_fine_tuning.ipynb`) is an untested alternative for step 2; every
real training run to date has been on the kiosk under `nice -n 15`.

### Why the labels are round 1 and not the whole call
`WhisperFeatureExtractor` keeps the first 30 s of audio and says nothing (verified against
installed transformers 5.14.1). Dispatch broadcasts run ~48 s. The 2026-07-17 dataset paired
30 s of audio with a label for the whole call and trained the model to keep talking after the
audio stopped; its "3.5% WER" was train-on-test. Full account:
[`docs/briefings/whisper_training_round1_labelling.md`](./briefings/whisper_training_round1_labelling.md).

### Changing the Whisper model
**There is no engine selector.** STT is local faster-whisper only (CLAUDE.md §1). The one knob
is `WHISPER_MODEL` in `backend/.env` on the kiosk -- `tiny`, `base`, `small`, or a path to a
fine-tuned model directory (which must contain `config.json`, `model.bin`, `vocabulary.json`
**and `tokenizer.json`**, or it loads over the WAN or not at all). Read by
[`backend/cfr_dispatch/config/runtime.py`](../backend/cfr_dispatch/config/runtime.py).
`backend/.env` **overrides** the shell environment on import, so `WHISPER_MODEL=x python ...`
does nothing; to run a script against a different model, patch
`cfr_dispatch.stt.transcriber.WHISPER_MODEL` after import.

Then restart the daemon (**ask first** -- a real call in the restart window is missed):
```bash
ssh tcfire@100.95.146.94 "sudo systemctl restart cfr-agent"
```

<!-- audit-ok: backend/migrations/YYYY-MM-DD_short_name.sql -- a naming template, not a real file -->
