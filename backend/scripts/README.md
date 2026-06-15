# Developer & Preprocessing Scripts

This directory contains utility scripts for system calibration, geographic preprocessing, manual test feed uploads, and tone analysis.

## Scripts Directory Map

| Script Name | Purpose | Usage / Execution |
| :--- | :--- | :--- |
| `analyze_wav.py` | Analyzes volume levels and silence pauses in a WAV file at a fine 50ms block size. Useful to check RMS thresholds. | `python scripts/analyze_wav.py` |
| `calibrate_audio_interactive.py` | Command-line utility to interactively select your input hardware and test/calibrate the ambient noise floor thresholds. | `python scripts/calibrate_audio_interactive.py` |
| `create_adaptation_resources.py` | Pre-compiles and loads adaptation datasets (streets, unit vocabs, call types) into Google Cloud Speech-to-Text v2 recognizer resource models. | `python scripts/create_adaptation_resources.py` |
| `debug_audio.py` | Lists all audio devices detected on the host system to find appropriate PortAudio device IDs. | `python scripts/debug_audio.py` |
| `feed_recorded_call.py` | Simulates a live call by streaming a pre-recorded WAV file through the system's microphone loopback device. | `python scripts/feed_recorded_call.py` |
| `fingerprint_source.py` | Analyzes raw dispatcher tones and outputs frequency peaks to build golden tone matching configuration templates. | `python scripts/fingerprint_source.py` |
| `fix_shapefiles.py` | Checks spatial shapefile geometries for indexing errors and formats coordinate rings. | `python scripts/fix_shapefiles.py` |
| `generate_street_list.py` | Helper script to extract a clean, unique list of Coquitlam streets from shapefile files or geocoders. | `python scripts/generate_street_list.py` |
| `update_gis_data.py` | Automated CLI tool that downloads and updates raw shapefile datasets from Coquitlam's Open Data API. | `python scripts/update_gis_data.py` |
