# Local Stack Migration, Ntfy Push & DSP Tone Spotter Calibration Walkthrough

This document outlines the systematic diagnosis, container audits, tone spotter fixes, and STT optimizations executed following the cloud-to-local migration.

---

## 🛠️ Summary of Architectural Changes

### 1. Database & Persistence Layer (PostgreSQL 16)
- **Schema Improvements** ([`backend/api/init_db.sql`](../../backend/api/init_db.sql)):
  - Added `pgcrypto` extension for UUID generation.
  - Added JSONB GIN index `idx_live_calls_target_gin` on `target` column for fast metadata queries.
  - Added partial index `idx_live_calls_feedback_verified` on `(timestamp DESC) WHERE feedback_submitted = TRUE AND verified_address IS NOT NULL`.
  - Removed duplicate `dispatch_id` B-tree index (handled by `UNIQUE NOT NULL`).
- **API & Connection Management**:
  - Added `limit` and `offset` pagination to `GET /api/dispatches` in [`backend/api/server.py`](../../backend/api/server.py).
  - Added `pool_recycle=1800` and `pool_timeout=30` to [`backend/api/database.py`](../../backend/api/database.py).

### 2. Audio DSP & Tone Spotter Calibration
- **Duration Gating**: Set `MIN_TONE_BURST_DURATION_S = 2.0` in [`backend/cfr_dispatch/config/dsp.py`](../../backend/cfr_dispatch/config/dsp.py) to ignore short PA chime beeps ($< 1.5\text{s}$).
- **Empirical Golden Fingerprints**: Set `FREQUENCY_TOLERANCE_HZ = 8` to eliminate overlap between PA Chimes (595.00 Hz) and Engine Tones (601.56 Hz). Fingerprints calibrated against 245 HITL-verified recordings:
  - **Engine Tones**: `601.56 Hz` & `1351.56 Hz`
  - **Rescue Tones**: `726.56 Hz` & `890.62 Hz`
  - **Chief Tones**: `437.50 Hz` & `656.25 Hz`
- **PA Exclusion Precedence**: Updated [`backend/cfr_dispatch/orchestration.py`](../../backend/cfr_dispatch/orchestration.py) so station PA announcements reset the listener cleanly without capturing false call recordings.

### 3. Speech-to-Text & MLOps Streamlining
- **Local Faster-Whisper Lock**: Locked `STT_ENGINE = "whisper"` in [`backend/cfr_dispatch/config/cloud.py`](../../backend/cfr_dispatch/config/cloud.py), removing Google STT v2 dependencies.
- **Whisper Hotwords & VAD**: Injected `units_vocabulary` into prompt boosting & enabled Silero VAD (`vad_filter=True`, `condition_on_previous_text=False`).
- **TTL Cache**: Added a 10-minute TTL cache to `get_hitl_verified_streets()` to eliminate blocking network requests during transcription.

### 4. React Frontend & MQTT WebSockets
- **WebSocket Lifecycle Fix**: Updated [`frontend/src/hooks/useMqttListener.js`](../../frontend/src/hooks/useMqttListener.js) with `useRef` callbacks to keep the Mosquitto MQTT WebSocket connection active across component re-renders.
- **Vite Build**: Compiled production build (`npm run build`) into `frontend/dist` on the kiosk.

---

## 🧪 Verification & Deployment Commands

```bash
# 1. Test local Ntfy push broker
curl -d "Diagnostic Test" http://localhost:8080/chief-master

# 2. Test local FastAPI REST gateway
curl -I http://localhost:8000/api/dispatches

# 3. Execute empirical historical tone backtest
python scripts/analyze_historical_tones.py

# 4. Feed a verified WAV call to test pipeline
python backend/scripts/feed_recorded_call.py backend/audio_files/recordings/DISP-2026-044D8A.wav "Engine Tone"

# 5. Restart listener service
sudo systemctl restart cfr-agent
```
