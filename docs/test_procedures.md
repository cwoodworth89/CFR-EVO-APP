# CFR EVO: Test Procedures & Diagnostics

One procedure remains. Four were removed on 2026-08-31 because every command in them
referenced something that no longer exists, and the comparative parser backtest went on
2026-09-04 with the experimental parser it compared (`call_structure.md` keeps the result):

| Removed | Why |
|:--|:--|
| Automated QA & Diagnostics Suite | `run_test_suite.py` deleted with its synthesised `test_calls/` corpus |
| PostgreSQL & Gateway Contract Verification | ran `test_supabase_integration.py` — no such file, and Supabase is forbidden by §1 |
| End-to-End Pipeline Feeding (WAV simulation) | `feed_recorded_call.py` retired |
| Local Stack Web Simulation | posted to `/api/dispatches/simulate`, an endpoint that does not exist |

**What replaces end-to-end testing.** Real dispatches — roughly eleven a day — exercise the
whole path continuously, and the HITL review panel is where their correctness is judged.
CLAUDE.md §6.5 forbids synthesising calls to test with, so replaying real history through the
review panel is the sanctioned route. `pytest backend/tests/` covers the units.

---

## Environment

Activate the local virtual environment from the repository root
(`.venv\Scripts\Activate.ps1` on Windows). The full stack runs on the kiosk, not locally
(CLAUDE.md §3) — anything needing `geopandas`, `shapely` or live audio runs there:

```bash
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && XDG_RUNTIME_DIR=/run/user/1000 .venv/bin/python ..."
```

`XDG_RUNTIME_DIR` is required for anything touching PortAudio over SSH, or it fails with
`PulseAudio_Initialize: Can't connect to server`.

---

## 🧪 Procedure 3: Live Microphone & DSP Volume Diagnostics

Before leaving the listener active, verify that the microphone is unmuted, has the correct system index, and has a high enough gain to register decibels.

### 1. View & Select Audio Device Index
Run the sounddevice query utility to list all recording interfaces detected by the OS:
```powershell
python -c "import sounddevice as sd; print(sd.query_devices())"
```
*Note the ID number or unique query name string of your microphone array or virtual cable (e.g., `1` or `alsa_input.usb-Burr-Brown_from_TI_USB_Audio_CODEC-00.analog-stereo-input`). Set this value as `AUDIO_DEVICE_ID=...` in your `backend/.env` if you want to lock the agent to a specific device.*

### 2. Live Volume Meter Calibration
Listen to a microphone and display live signal levels to check if sound is registering:
```powershell
python backend/scripts/debug_audio.py
```
*   **Standby/Silence Level**: Should register near `0.00` to `200.00` RMS.
*   **Loud Sound / Tone Spike**: Should easily exceed your configured `NOISE_AMPLITUDE_THRESHOLD` (default: `1500` RMS).

### 3. Tone Verification & Interactive Calibration
To calibrate the DSP threshold so the agent doesn't false-trigger on background noise, run the interactive validator:
```powershell
python backend/scripts/calibrate_audio_interactive.py
```
This utility records loud sound events, matches them against the golden frequency profiles for `Chief Tone`, `Engine Tone`, and `Rescue Tone`, and prompts you to log correct matches or false positives.

---
## 🛑 Troubleshooting Reference

| Issue | Root Cause | Resolution |
| :--- | :--- | :--- |
| **RMS stays near `0.00`** | Microphone muted or blocked | Check OS microphone permissions and that device volume is not 0%. |
| **`PaErrorCode -9997`** | Invalid sample rate | The device does not support 16 kHz capture. Target one that does, or use a loopback driver. |
| **`PaErrorCode -9999`, `PulseAudio_Initialize`** | Audio code over SSH with no session bus | Prefix with `XDG_RUNTIME_DIR=/run/user/1000`. |
| **Geocoding returns `None`** | Street absent from municipal data | Check `public.roads.roadname` against `public.parcels.street`. 56 parcels legitimately have no road — punch-list **#58**. A miss belongs in the database as a data fix, never as a string match in code (§6.2). |
| **No audio player on a call** | `audio_url` NULL on the record | The recording is almost certainly on disk under `backend/audio_files/recordings/`. See punch-list **#59**. |
| **Real-time updates not showing** | Mosquitto down or WebSocket port blocked | Ensure the container is running and port `9001` is open. Check the browser console. |
