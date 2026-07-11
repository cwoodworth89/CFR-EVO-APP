# CFR EVO Backend Listening Agent

The backend handles the continuous DSP listening, audio tone detection, speech-to-text (STT) transcription, parsing, geocoding, and syncing with Supabase and NTFY notifications.

## ⚡ System Prerequisites

* **Python 3.10+** (64-bit recommended)
* **PortAudio** (required for the `sounddevice` library to capture live audio)
  * *Windows*: Typically packaged inside the `sounddevice` wheel.
  * *Linux*: `sudo apt-get install libportaudio2`
  * *macOS*: `brew install portaudio`
* **FFmpeg** (required for audio slicing and Whisper transcription)

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

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in the required fields:
   ```bash
   cp .env.example .env
   ```
   * Set `STT_ENGINE` (`google` or `whisper`).
   * Add Google Cloud Credentials JSON path to `GOOGLE_APPLICATION_CREDENTIALS` (if using GCP).
   * Fill in Supabase and NTFY endpoints/credentials.

---

## 🚀 Running the Agent

To start the continuous listening loop:
```bash
python main.py
```

To run the local developer/QA test suite:
```bash
python tests/run_test_suite.py
```

---

## 📂 Code & Package Structure

* **`cfr_dispatch/`**: Central package logic:
  * [cfr_dispatch/orchestration.py](./cfr_dispatch/orchestration.py): Coordinates queue processes, listeners, STT, and notification pipelines.
  * [cfr_dispatch/parser.py](./cfr_dispatch/parser.py): Address/cross-street parser using anchor-based templates.
  * [cfr_dispatch/config/](./cfr_dispatch/config/): Houses hardware, vocab, DSP, and cloud configurations.
* **`scripts/`**: Preprocessing and utility scripts. Refer to [scripts/README.md](./scripts/README.md) for individual script details.
* **`tests/`**: Integration and component tests.
