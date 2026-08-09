# Backend Domain Rules & Audio/DSP Constraints

Rules and constraints for Python backend code in `backend/`.

---

## 1. Audio DSP & Hardware Tone Spotting
* **Tone Burst Duration Gating**: Require `MIN_TONE_BURST_DURATION_S = 2.0` (sustained tone capture $\ge 2.0\text{s}$) for valid apparatus pager tones before recording begins. Discard short station PA chime beeps ($< 1.5\text{s}$) immediately.
* **Frequency Tolerance**: Enforce `FREQUENCY_TOLERANCE_HZ = 8` in [`backend/cfr_dispatch/config/dsp.py`](cfr_dispatch/config/dsp.py) to prevent frequency overlap between PA Chimes (595.00 Hz) and Engine Tones (601.56 Hz).
* **PA Precedence**: Station PA announcements matching `PA Tone` must reset the listener immediately without saving or triggering false calls.
* **No Digital Boosting**: Do NOT apply peak gain normalization or digital audio boosting to scanner line-in feeds (volume is direct; boosting causes clipping).

---

## 2. Speech-to-Text (STT) & MLOps Pipeline
* **Local Faster-Whisper Lock**: Lock `STT_ENGINE = "whisper"` in [`backend/cfr_dispatch/config/cloud.py`](cfr_dispatch/config/cloud.py). Do NOT re-introduce Google STT v2 dependencies or GCP credential requirements.
* **Prompt Biasing**: Inject `units_vocabulary` (*Engine*, *Rescue*, *Chief*, *Ladder*) into Whisper's `initial_prompt` and `hotwords` via `build_stt_bias_words()`.
* **Hallucination Prevention**: Pass `vad_filter=True` (Silero VAD) and `condition_on_previous_text=False` to `model.transcribe()` to prevent line-in static from generating text hallucinations.
* **Non-blocking STT Bias Fetch**: Wrap `get_hitl_verified_streets()` in a 10-minute in-memory TTL cache to eliminate blocking network requests during live transcription.
* **Symmetric WER Normalization**: Always apply `sanitize_transcript()` to both reference and hypothesis when computing WER in `backtest_regression.py`.

---

## 3. PostgreSQL Database & FastAPI Gateway
* **Index Rules**: `dispatch_id TEXT UNIQUE` automatically creates a B-tree unique index in PostgreSQL; do NOT create duplicate manual indexes on `dispatch_id`.
* **JSONB & HITL Indexes**: Maintain JSONB GIN index `idx_live_calls_target_gin` on `target` and partial index `idx_live_calls_feedback_verified` on `(timestamp DESC) WHERE feedback_submitted = TRUE AND verified_address IS NOT NULL`.
* **Pagination**: Always include `limit` (default 100) and `offset` pagination on `GET /api/dispatches` in [`backend/api/server.py`](api/server.py).
* **Connection Pooling**: Configure SQLAlchemy engine with `pool_recycle=1800` (30 mins) and `pool_timeout=30` in [`backend/api/database.py`](api/database.py).
