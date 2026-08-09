# CFR EVO: Workspace Rules

Domain-specific rules have been modularized across the repository's directory hierarchy:
* **Root Architecture & Git Protocol**: Refer to [`GEMINI.md`](../../GEMINI.md)
* **Audio DSP & Whisper STT**: Refer to [`backend/GEMINI.md`](../../backend/GEMINI.md)
* **Frontend & MQTT WebSockets**: Refer to [`frontend/GEMINI.md`](../../frontend/GEMINI.md)
* **GIS Shapefiles & Geocoding**: Refer to [`services/gis/GEMINI.md`](../../services/gis/GEMINI.md)

For procedural runbooks, see specialized skills under `.agents/skills/`:
* `kiosk-remote-ops`: Tailscale SSH remoting and kiosk service controls.
* `stt-mlops-backtest`: Whisper transcription benchmarks and WER scoring.
* `gis-pipeline-sync`: Shapefile updates and NFPA 291 hydrant compact caching.
* `local-stack-orchestrator`: Docker Compose container stack lifecycle.
