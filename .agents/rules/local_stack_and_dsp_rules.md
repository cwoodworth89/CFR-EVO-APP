# CFR EVO Project Rules & Architectural Guidelines

This rule file specifies domain constraints, DSP tone spotter thresholds, STT configuration standards, and database/frontend rules established during the local stack migration.

---

## 1. Local Container Stack & Persistence Rules
- **Primary Database**: All dispatch data must persist directly to the local containerized PostgreSQL database via the FastAPI API Gateway endpoint (`http://localhost:8000/api/dispatches`).
- **Audio Serving**: Audio recordings are saved locally to `backend/audio_files/recordings/` and served via relative path `/api/audio/{dispatch_id}.wav`.
- **API Port Check**: `main.py` must check socket port 8000 before spawning Uvicorn to avoid duplicate binding errors when running under Docker container mode.
- **Offline Poller**: Do NOT run the legacy Supabase offline queue poller (`offline_sync.py`).

---

## 2. Audio DSP & Tone Spotting Calibration
- **Tone Burst Duration Gating**: Require `MIN_TONE_BURST_DURATION_S = 2.0` (sustained tone capture $\ge 2.0\text{s}$) for valid apparatus pager tones before call recording begins. Short station PA chime beeps ($< 1.5\text{s}$) must be discarded.
- **Frequency Tolerance**: Lock `FREQUENCY_TOLERANCE_HZ = 8` in [`backend/cfr_dispatch/config/dsp.py`](../../backend/cfr_dispatch/config/dsp.py) to prevent frequency overlap between PA Chimes (595.00 Hz) and Engine Tones (601.56 Hz).
- **PA Precedence**: Station PA announcements matching `PA Tone` must reset the listener immediately without triggering false call recordings.
- **No Gain Amplification**: Do NOT apply peak gain normalization or digital audio boosting to scanner line-in feeds (volume is direct and loud; gain boosting causes clipping).

---

## 3. Speech-to-Text (STT) & MLOps Pipeline
- **Local Faster-Whisper Lock**: Lock `STT_ENGINE = "whisper"` in [`backend/cfr_dispatch/config/cloud.py`](../../backend/cfr_dispatch/config/cloud.py). Do NOT re-introduce Google STT v2 dependencies or GCP credential requirements.
- **Prompt Boosting**: Always inject `units_vocabulary` (*Engine*, *Rescue*, *Chief*, *Ladder*) into Whisper's `initial_prompt` and `hotwords` via `build_stt_bias_words()`.
- **Hallucination Prevention**: Always pass `vad_filter=True` (Silero VAD) and `condition_on_previous_text=False` to `model.transcribe()` to prevent line-in static from generating text hallucinations.
- **Non-blocking STT Bias Fetch**: Wrap `get_hitl_verified_streets()` in a 10-minute in-memory TTL cache to eliminate blocking network requests during live transcription.
- **WER Text Normalization**: Standardize text normalization using `sanitize_transcript()` on both reference and hypothesis when computing WER in `backtest_regression.py`.

---

## 4. PostgreSQL Database & API Gateway
- **Index Optimization**: `dispatch_id TEXT UNIQUE` automatically creates a B-tree unique index in PostgreSQL; do NOT create duplicate manual indexes on `dispatch_id`.
- **JSONB & HITL Indexes**: Maintain JSONB GIN index `idx_live_calls_target_gin` on `target` and partial index `idx_live_calls_feedback_verified` on `(timestamp DESC) WHERE feedback_submitted = TRUE AND verified_address IS NOT NULL`.
- **Pagination**: Always include `limit` (default 100) and `offset` pagination on `GET /api/dispatches` in [`backend/api/server.py`](../../backend/api/server.py).
- **Connection Management**: Configure SQLAlchemy engine with `pool_recycle=1800` (30 mins) and `pool_timeout=30` in [`backend/api/database.py`](../../backend/api/database.py).

---

## 5. React Frontend & Real-Time MQTT WebSockets
- **Persistent WebSocket Connection**: Store callback handlers (`onInsert`, `onUpdate`, `onDelete`) in a `useRef` inside [`frontend/src/hooks/useMqttListener.js`](../../frontend/src/hooks/useMqttListener.js) to prevent WebSocket teardown/reconnection loops on component re-renders.
- **SSL WSS Protocol**: Under HTTPS/Nginx reverse proxy, target WebSocket path `wss://${hostname}/mqtt` over port 443.

---

## 6. STT Backtesting & WER Evaluation Rules
- **HITL Dataset Filtering**: When running `scripts/analyze_historical_tones.py` or STT backtests, filter strictly for dispatches where `feedback_submitted = TRUE`, `verified_units` is non-empty, and `target.tone_name` is confirmed.
- **Symmetric Normalization**: Always apply `sanitize_transcript()` (digit and street normalization) to **both** ground-truth reference text and model hypothesis before computing Levenshtein WER in [`backend/scripts/backtest_regression.py`](../../backend/scripts/backtest_regression.py). Never score raw text against sanitized text.
- **Round Alignment**: For long dispatches (> 25s double-round broadcasts), dynamically align reference and hypothesis round counts before calculating WER to prevent artificial ~50% deletion penalties.
- **Model Versioning**: Record run results in `evaluation_history` table using explicit model tags (e.g. `whisper-base-boost-classes`).

---

## 7. Remote Kiosk Server Access & Workflow Best Practices
- **Tailscale SSH Target**: Connect to remote kiosk via Tailscale IP `100.95.146.94` or hostname `cfr-mapping-tcfh` (`ssh tcfire@100.95.146.94`).
- **Local Edits First**: Make all code, config, and doc changes in local Git repository first. Do NOT edit production code directly on kiosk.
- **Non-Sudo Docker Commands**: `tcfire` is in the `docker` user group; run `docker ps`, `docker logs`, and `docker compose` directly without `sudo`.
- **Audio Environment Variable (`XDG_RUNTIME_DIR`)**: When running remote commands or python scripts interacting with soundcards/PortAudio (`sounddevice`, ALSA, PulseAudio), **MUST** prepend `XDG_RUNTIME_DIR=/run/user/1000`.
- **Frontend Assets Re-build**: Because `frontend/dist` is `.gitignore`d, rebuild frontend assets on kiosk after pulling git changes:
  `ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/frontend && npm run build"`
- **Git-Ignored File Server Management**: Files in `.gitignore` (such as `backend/.env`, `frontend/.env.local`, offline model caches in `backend/models/`, GIS shapefiles in `backend/data/`, and credentials JSON files) are **NOT** synced via `git pull`. Any configuration changes to these ignored files must be manually transferred via `scp` or updated directly on the remote server.
- **Daemon Restart**: Restart audio listener daemon via `sudo systemctl restart cfr-agent`.

---

## 8. System Metrics, Latency Waterfall & CAD Boundary Slicing Rules
- **`"Coquitlam"` Anchor Locking**: Always inject `initial_prompt="Coquitlam, "` into `WhisperModel.transcribe()` to anchor opening apparatus names. Use 1st spoken `"Coquitlam"` post-tone burst to lock `t_speech_start`.
- **`"map grid [N]"` Boundary Rule**: Slice Phase 1 preliminary audio immediately when `"map grid [N]"` is recognized in rolling text. Enforce strict range validation `1 <= N <= 134` (Coquitlam Emergency Response Zones).
- **Do NOT Search for 2nd `"Coquitlam"`**: Talkgroup names contain `"Coquitlam"` mid-call (`"talk group 5 Coquitlam"`). Rely strictly on `"map grid [N]"` or `1.2s VAD pause` for Round 1 boundary detection.
- **Waterfall Telemetry Schema**: Store latency waterfall timestamps (`t0_tone_detected`, `t1_capture_started`, `t2_anchor_coquitlam`, `t3_map_grid_spotted`, `t4_phase1_stt`, `t5_gis_lookup`, `t6_ntfy_push`) inside `live_calls.target['telemetry']` in PostgreSQL.
- **Dedicated Admin Tab Navigation**: Keep `DispatchReview.jsx` de-cluttered for call review ergonomics; display latency waterfall charts, STT WER trends, and Docker container health inside `frontend/src/components/admin/SystemMetricsPanel.jsx`.



