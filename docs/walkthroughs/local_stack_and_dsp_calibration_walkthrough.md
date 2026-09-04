# Local Stack Migration, Ntfy Push & DSP Tone Spotter Calibration Walkthrough

> [!NOTE]
> **Historical walkthrough; the DSP and stack content still applies.** One item is dead: the
> `shapefile_loader.py` vectorisation described below is gone — in-memory shapefile loading
> was eliminated in favour of PostGIS (CLAUDE.md §1). The whisper-only rule is
> still current and still binding, though the `STT_ENGINE` constant that expressed it was
> removed on 2026-08-31 — nothing branched on it.

This document outlines the systematic diagnosis, container audits, tone spotter fixes, and STT optimizations executed following the cloud-to-local migration.

---

## 🛠️ Summary of Architectural Changes

### 1. Database & Persistence Layer (PostgreSQL 16)
- **Schema Improvements** ([`backend/api/init_db.sql`](../../backend/api/init_db.sql)):
  - Added `pgcrypto` extension for UUID generation.
  - Added JSONB GIN index `idx_dispatches_target_gin` on `target` column for fast metadata queries.
  - Added partial index `idx_dispatches_feedback_verified` on `(timestamp DESC) WHERE feedback_submitted = TRUE AND verified_address IS NOT NULL`.
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
- **Local Faster-Whisper Lock**: Removed Google STT v2 dependencies. The `STT_ENGINE` selector that pinned this was itself removed on 2026-08-31 — nothing branched on it — and `config/cloud.py` became [`config/runtime.py`](../../backend/cfr_dispatch/config/runtime.py), since nothing in it was cloud-related.
- **Whisper Hotwords & VAD**: Injected `units_vocabulary` into prompt boosting & enabled Silero VAD (`vad_filter=True`, `condition_on_previous_text=False`).
- **GIS Vector Indexing (10x Faster Startup)**: Replaced `iterrows()` in ``services/gis/src/gis_service/shapefile_loader.py`` *(deleted — in-memory shapefile loading was eliminated)* with vector dict mapping (`to_dict('records')`), cutting service boot-up indexing time by 10x and lowering memory usage by >80%. Compact JSON output (`separators=(',', ':')`) in [`backend/scripts/update_gis_data.py`](../../backend/scripts/update_gis_data.py) cuts `hydrants.json` payload size from ~2.5 MB to ~1.0 MB.

### 4. Admin Dispatch Review Dashboard & Call Flow Ergonomics
- **Call Flow Sequence Alignment**: Re-ordered input fields in [`frontend/src/components/DispatchReview.jsx`](../../frontend/src/components/DispatchReview.jsx) to follow the natural call review sequence (`Captured Dispatch Tone` $\rightarrow$ `Verified Units` $\rightarrow$ `Verified Incident Type` $\rightarrow$ `Verified Address` $\rightarrow$ `Subaddress` $\rightarrow$ `Talkgroup & Map Grid` $\rightarrow$ `Verified Ground-Truth Transcript`).
- **Auto-Advance & Audio Auto-Play**: On `Ctrl+Enter` submit, the system auto-selects the next dispatch row, resets form scroll to top, and automatically starts playing the new call recording audio (`audioRef.current.play()`).
- **Default Transcript Prefill**: When a call row is selected, the `verified_transcript` box is auto-filled with Stage 3 text for quick minor edits.
- **Audio Skip & Table Filters**: Added lightweight `⏪ -5s` jump-back button, Status filter tabs (`[All]`, `[Needs HITL Review]`, `[Low Confidence]`, `[Fine-Tuned]`), and metadata dropdown filters (Tone & Units).
- **WebSocket Lifecycle Fix**: Updated [`frontend/src/hooks/useMqttListener.js`](../../frontend/src/hooks/useMqttListener.js) with `useRef` callbacks to keep the Mosquitto MQTT WebSocket connection active across component re-renders.
- **Vite Production Build**: Compiled production build (`npm run build`) in 5.19s into `frontend/dist` on the kiosk.

---


## 🧪 Verification & Deployment Commands

```bash
# 1. Test local Ntfy push broker
curl -d "Diagnostic Test" http://localhost:8080/chief-master

# 2. Test local FastAPI REST gateway
curl -I http://localhost:8000/api/dispatches

# 3. Execute empirical historical tone backtest
python scripts/analyze_historical_tones.py

# 4. (removed) The WAV feeder was retired 2026-08-31 -- real dispatches are the end-to-end test.

# 5. Restart listener service
sudo systemctl restart cfr-agent
```

> [!NOTE]
> **Git-Ignored Files & Server Synchronization**
> Files specified in `.gitignore` (such as `backend/.env`, `frontend/.env.local`, offline STT model caches in `backend/models/`, shapefiles in `backend/data/`, and credentials JSON files) are **not** updated by running `git pull` on the remote kiosk. Any modifications to environment variables or ignored configuration assets must be transferred directly via `scp` or edited manually on the server.

<!-- audit-ok: services/gis/src/gis_service/shapefile_loader.py -- records that in-memory shapefile loading was eliminated -->

<!-- audit-ok: backend/cfr_dispatch/config/cloud.py -- renamed to runtime.py 2026-08-31 (57ab40c); the banner records it -->
