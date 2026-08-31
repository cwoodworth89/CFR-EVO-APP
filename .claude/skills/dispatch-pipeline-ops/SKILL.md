---
name: dispatch-pipeline-ops
description: Operational runbook and architectural guide for developing, debugging, tuning, and testing the CFR EVO two-phase real-time dispatch audio pipeline.
---

# Dispatch Pipeline Operations Runbook

This skill provides comprehensive instructions for debugging, testing, tuning, and extending the two-phase dispatch audio pipeline in **CFR EVO**.

---

## 1. Modular Architecture Overview

The dispatch ingestion pipeline is organized into single-responsibility, typed modules under `backend/cfr_dispatch/`:

| Module | Responsibility | Key Classes / Functions |
| :--- | :--- | :--- |
| **`orchestration.py`** | Top-level facade & process lifecycle | `run_dispatch_system()`, `setup_logging()` |
| **`audio_listener.py`** | PortAudio input stream & tone gating | `run_audio_listener_loop()`, `update_listener_heartbeat()` |
| **`worker.py`** | Background multiprocessing task router | `background_worker_loop()`, `DispatchSessionManager` |
| **`stt/transcriber.py`** | Local Whisper CTranslate2 int8 inference | `transcribe_audio_local()`, `get_whisper_model()` |
| **`stt/bias_prompt.py`** | Apparatus, grid & HITL prompt biasing | `build_stt_bias_words()`, `get_hitl_verified_streets()` |
| **`pipeline/models.py`** | Strongly-typed result dataclasses | `Phase1Result`, `Phase2Result`, `PipelineTimer` |
| **`pipeline/payload_builder.py`** | Geocoding & Option 1/2 payload builder | `build_dispatch_payload()`, `clean_address_string()` |
| **`pipeline/phase1.py`** | Rapid preliminary broadcast (<15s) | `process_phase_1_check()`, `is_round_1_complete_check()` |
| **`pipeline/phase2.py`** | Final call verification & correction | `process_phase_2_finalize()`, `save_and_upload_audio()` |

---

## 2. Two-Phase Dispatch Mechanics

```mermaid
sequenceDiagram
    autonumber
    participant Mic as PortAudio Stream
    participant Listener as Audio Listener
    participant Queue as Multiprocessing Queue
    participant Worker as Background Worker
    participant STT as Whisper Engine
    participant GIS as GIS Validator
    participant MQTT as Mosquitto MQTT

    Mic->>Listener: 1024-sample PCM blocks (16 kHz)
    Listener->>Listener: FFT Peak Matching vs Golden Fingerprints
    Note over Listener: Apparatus Tone Confirmed!
    Listener->>Queue: {"type": "phase_1_check", "dispatch_id": "DISP-..."}
    Queue->>Worker: Dequeue Phase 1 task
    Worker->>STT: Transcribe preliminary audio buffer
    Worker->>GIS: Geocode address candidate
    Worker->>MQTT: Broadcast Phase 1 INSERT payload (<15s Time-to-Alert)
    
    Note over Listener: Dispatcher finishes; Silence >= 8.0s detected
    Listener->>Queue: {"type": "phase_2_finalize", "dispatch_id": "DISP-..."}
    Queue->>Worker: Dequeue Phase 2 task
    Worker->>STT: Transcribe full call audio
    Worker->>GIS: Cross-verify Round 1 vs Round 2 address
    Worker->>MQTT: Broadcast Phase 2 UPDATE payload (Verified / Corrected)
```

---

## 3. Interpreting Logs & Structured Metrics

All pipeline logs are tagged with `[dispatch_id]` prefixes and structured metrics tags:

### Phase 1 Time-to-Alert Metric:
```text
[METRICS] [DISP-2026-1793D9] Phase 1 TTA: 1.28s (DSP: 420ms, STT: 780ms, GIS: 14ms, MQTT: 3ms) | Units: ['E1', 'L1'] | Addr: '2648 Sandstone Cres' (100% conf)
```

### Phase 2 Verification & Correction Audit:
```text
[CORRECTION_AUDIT] ID=DISP-2026-1793D9 | Mismatch detected: P1='Austin Ave' vs P2='1963 Lougheed Hwy'. Attempting correction...
[CORRECTION_AUDIT] Geocoded match SUCCEEDED: '1963 Lougheed Hwy' (Score: 100%)
[METRICS] [DISP-2026-1793D9] Phase 2 Finalized | Match=False | Corrected=True | Addr='1963 Lougheed Hwy' | Audio=28.4s
```

---

## 4. Testing & Simulating Dispatch Calls

### Rapid Unit Testing (No Audio Hardware Required):
```powershell
.\.venv\Scripts\python.exe backend/tests/test_pipeline_unit.py
```

### Database Integration & Polygon Contract Verification:
```powershell
.\.venv\Scripts\python.exe backend/tests/test_database_integration.py
```

### End-to-End Testing
There is no WAV feeder. `feed_recorded_call.py` was retired 2026-08-31 along with the
synthesised `test_calls/` corpus, which §6.5 forbids. Real dispatches -- about eleven a day --
exercise the whole path, and the HITL review panel is where correctness is judged.

---

## 5. Key Tuning Parameters (`backend/cfr_dispatch/config/`)

* **`MIN_PHASE_1_DURATION_S`** (`20.0`s): Minimum audio duration before Phase 1 checks begin.
* **`PHASE_1_CHECK_INTERVAL_S`** (`5.0`s): Interval between periodic Phase 1 completion checks.
* **`END_OF_DISPATCH_SILENCE_S`** (`8.0`s): Continuous silence required to trigger Phase 2 finalization.
* **`NOISE_AMPLITUDE_THRESHOLD`** (`500` RMS): Minimum sound amplitude to begin tone spotting.
