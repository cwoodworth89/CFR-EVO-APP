# CFR EVO Backend Listening Agent

The backend handles continuous DSP listening, audio tone detection, speech-to-text (STT) transcription, parsing, geocoding, PostgreSQL persistence via FastAPI, and real-time broadcasting via Mosquitto MQTT and Ntfy push notifications.

## ⚡ System Prerequisites

* **Python 3.10+** (64-bit recommended)
* **PortAudio** (required for the `sounddevice` library to capture live audio)
  * *Windows*: Typically packaged inside the `sounddevice` wheel.
  * *Linux*: `sudo apt-get install libportaudio2`
  * *macOS*: `brew install portaudio`
* **FFmpeg** (required for audio slicing and Whisper transcription)
* **Docker Compose** (PostgreSQL 16, Mosquitto MQTT, Ntfy, and FastAPI Gateway)

---

## 🛠️ Installation Setup

1. **Create and Activate a Virtual Environment**:
   ```bash
   python -m venv .venv
   # Windows PowerShell
   .venv\Scripts\Activate.ps1
   # Linux/macOS
   source .venv/bin/activate
   ```

2. **Install Sibling Packages in Editable Mode**:
   ```bash
   # Windows PowerShell
   powershell -File scripts/install_dev_packages.ps1
   # Linux/macOS
   bash scripts/install_dev_packages.sh
   ```

3. **Environment**:
   `backend/.env` is git-ignored and has no template in the tree (the `.env.example` files were
   deleted 2026-09-03 because they named variables the code no longer reads). The running copy
   lives on the kiosk; copy it from there or from the operator (CLAUDE.md §3).

---

## 🚀 Running the Agent

To start the continuous listening loop:
```bash
python main.py
```

To run the test suite:
```bash
pytest backend/tests/
```

---

## 📂 Code & Package Structure

* **`cfr_dispatch/`**: Central package logic:
  * [cfr_dispatch/orchestration.py](./cfr_dispatch/orchestration.py): Coordinates queue processes, listeners, STT, and notification pipelines.
  * [cfr_dispatch/parser/](./cfr_dispatch/parser/): Address/cross-street parser package (`sanitize`, `call_types`, `units`, `channels`, `location`, `announcement`).
  * [cfr_dispatch/config/](./cfr_dispatch/config/): Houses hardware, vocab, DSP, and runtime configurations.
* **`scripts/`**: Preprocessing and utility scripts. Refer to [scripts/README.md](./scripts/README.md) for individual script details.
* **`tests/`**: Integration and component tests.
