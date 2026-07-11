# Phase 2 Micro-Domain Service Split Walkthrough

We have successfully completed the structural split of the CFR Dispatch mapping monolithic backend into decoupled microservices and moved the client to `/frontend`. All dependencies are strictly parameterized with zero cyclical imports.

---

## 1. Directory Restructuring & Domain Isolation

The project structure has been refactored into the following micro-domain directories:

### Frontend
* Renamed React client directory `/client` to `/frontend`.

### Sibling Services (`/services/*`)
* **GIS Service (`/services/gis`)**:
  * Moved spatial datasets (`Emergency_Response_Zones/` and `Property_Information/`) under `/services/gis/data/`.
  * Moved shapefile loading logic into `gis_service/shapefile_loader.py`.
  * Moved parcel matching, intersection parsing, local geocoding, and grid boundary validation into `gis_service/geocoder.py`.
* **Audio Analysis Service (`/services/audio_analysis`)**:
  * Moved Butterworth filters, Hamming window FFT peak finding, and fingerprint tone matching algorithms into `audio_service/dsp_tone_spotter.py`.
  * Moved sounddevice block-by-block listening stream and continuous recording logic into `audio_service/sound_capture.py`.
* **Dispatch Notifications Service (`/services/dispatch_notifications`)**:
  * Moved database payload posting, patches, and audio uploads into `notification_service/supabase_sync.py`.
  * Moved mobile push notification triggers into `notification_service/ntfy_broker.py`.

### Backend
* Relocated core orchestration to `/backend` (previously `/agent`).
* Deleted monolithic components: `backend/cfr_dispatch/gis.py`, `backend/cfr_dispatch/dsp.py`, and `backend/cfr_dispatch/integration.py`.

---

## 2. Decoupling Configuration & stable APIs

To guarantee isolation, services no longer import `cfr_dispatch.config`:
1. **API Re-exporters**: Added `__init__.py` files inside each service package (e.g. `gis_service`, `audio_service`, `notification_service`) to re-export a stable public API.
2. **Parameterized Dependencies**: Refactored constructor and functions (such as `CoquitlamDataValidator`, `capture_full_dispatch`, `get_best_match`, and `filter_known_tones`) to take configurations dynamically (column labels, threshold limits, sample rates, etc.) passed from the central orchestrator.
3. **Dynamic Import Resolver**: Updated `backend/cfr_dispatch/__init__.py` to inject the source directories of `/services/*/src` to `sys.path` dynamically. Sibling packages can now be imported globally (e.g., `from gis_service import CoquitlamDataValidator`) with zero environment configuration.

---

## 3. Verification Results

We verified the new architecture using the local diagnostic tools:

### Console Output & Emoji Correction
* Fixed CP1252 character mapping crashes in Windows PowerShell by removing non-ASCII cross-mark emojis (`\u274c`) from diagnostic console prints.
* Updated `transcribe_audio_file` in the orchestration library to dynamically fall back to Whisper local transcription when `STT_ENGINE=whisper`.

### QA Diagnostics Test Suite
* Command: `.venv\Scripts\python.exe backend/tests/run_test_suite.py`
* **Result**: `PASSED` (Shapefiles parsed, local address geocoder initialized, and chest pain test case processed with zero config or package import errors).
