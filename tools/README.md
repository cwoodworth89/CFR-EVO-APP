# `tools/`

What a developer runs to build, test, measure, train and audit CFR EVO. Nothing here runs on
the kiosk unattended; the scripts that *operate* the system (backups, municipal data loads,
tile archives, sound-card checks) are in [`backend/scripts/`](../backend/scripts/README.md).
Moved here from `backend/scripts/` and the old top-level `scripts/` on 2026-09-04 so the tree
itself shows the divide ([`docs/README.md`](../docs/README.md)).

> [!IMPORTANT]
> **This file is checked, not trusted.** `python tools/audit_skill_references.py --scripts
> --scripts-dir tools` fails if a script here has no row below, or if a row names a script that
> does not exist. The pre-commit hook runs it whenever `tools/` is touched.

**How a script here finds the code.** Every script starts with `from _repo import BACKEND` (or
just `import _repo`). [`_repo.py`](_repo.py) is the one place that knows where `backend/` and
`services/*/src` are relative to this directory and puts them on `sys.path`. Before the move each
script climbed out of its own directory with `os.path.dirname(os.path.dirname(__file__))`,
which is exactly the kind of thing that breaks silently when a directory moves.

**Run from the repository root** with the project virtualenv: `.venv/bin/python
tools/backtest_parser_corpus.py` on the kiosk, `.\.venv\Scripts\python.exe
tools\backtest_parser_corpus.py` on the laptop. Anything that imports `cfr_dispatch` pulls in
PortAudio; over SSH set `XDG_RUNTIME_DIR=/run/user/1000` first (`docs/agent_onboarding.md`).

**Already-run scripts live in [`oneshot/`](oneshot/).** They ran once against a specific
problem and will not run again. They are kept for provenance, not for use.

---

## Repository and environment

| Script | Purpose |
|:--|:--|
| `_repo.py` | Locates the repository from any script here and puts `backend/` and `services/*/src` on `sys.path`. Imported, never run. |
| `install_dev_packages.sh` | Development-environment package installer for Linux (the kiosk side). Read it before running; it is not part of the kiosk build. |
| `install_dev_packages.ps1` | The same installer for the Windows laptop. |

## QA harnesses and measurement

Produce numbers. None of them modify operational data.

| Script | Purpose |
|:--|:--|
| `backtest_parser.py` | Production parser against the sequential destructive parser, on ground truth. |
| `backtest_parser_corpus.py` | Replays verified dispatches through the current parser, scoring each field. |
| `backtest_regression.py` | WER / Levenshtein regression for STT output. |
| `backtest_round_comparison.py` | Scores cross-round disagreement as a warning signal. |
| `trace_geocode_corpus.py` | Scores the geocoder against the human-verified corpus. |
| `verify_snapping_corpus.py` | Parcel arrival-point benchmark: boundary-to-arrival distance and OSRM ETA. |
| `audit_skill_references.py` | Finds identifiers a `SKILL.md` names that exist nowhere in the code. `--scripts` checks this README. |
| `audit_staleness.py` | Deterministic staleness scan: dangling paths in markdown (honours `audit-ok`), schema objects dropped by migrations but still named in code, modules and components nothing imports, frontend/pipeline API calls vs backend routes, compose names, env vars, punch-list status drift, `file://` links, doc age. Writes a Markdown report (`--out`). Overlaps `--docs` above; merging them is on the post-freeze backlog. |
| `export_complex_sites_for_review.sql` | Sites where a crew arriving at the computed point still has property to search — the `#49` review queue. |

## STT / MLOps

| Script | Purpose |
|:--|:--|
| `extract_training_data.py` | Builds the training set from HITL-verified dispatches; adds verified incident types to `public.vocabulary`. |
| `check_verified_transcripts.py` | Spell- and street-checks the operator's verified transcripts against `public.roads`, `public.vocabulary`, `public.parcels` and the corpus before they become training labels; exits 1 on blocking issues. Run by `prepare_training_clips.py`. |
| `prepare_training_clips.py` | Builds the round-1 clip dataset for fine-tuning: measures speech onset per call, cuts at the round boundary, drops rounds over Whisper's 30s window. |
| `train_whisper_lora.py` | LoRA fine-tune of the local Whisper model, on the round-1 clips. |
| `eval_round1_holdout.py` | Scores models on the held-out round-1 clips the fine-tune never saw; prints stock `base` against the fine-tuned model. |

## Ad-hoc inspection

Reach for these while debugging something specific.

| Script | Purpose |
|:--|:--|
| `inspect_dispatch.py` | Dumps one dispatch record by id as JSON. Run on the host with the project venv; refuses to run without a Postgres `DATABASE_URL` (the API's own SQLite fallback was removed in #61; the check stays for a clearer message). Rewritten 2026-09-04: the original imported a module that never existed and had never run. |
| `clean_old_dispatches.py` | Lists old dispatches for review. **Deletion requires manual confirmation.** |
| `update_streetview.py` | Refreshes Street View heading/pitch/fov for parcels. |
| `test_dual_push.py` | Exercises the MQTT and Ntfy push paths. **Not a pytest test** despite the name. |

## Audio and DSP analysis

Measurement over recordings. The sound-card diagnostics that a person runs *on the kiosk*
(`debug_audio.py`, `record_test.py`, `live_monitor.py`, `calibrate_audio_interactive.py`) stayed
in `backend/scripts/`.

| Script | Purpose |
|:--|:--|
| `analyze_wav.py` | Frequency and level analysis of a WAV file at 50 ms blocks. |
| `fingerprint_source.py` | Extracts dominant tone frequencies with sub-Hz precision, for building tone profiles. |
| `backfill_tone_spectra.py` | Reconstructs tone peak data from archived recordings. Re-runnable as the archive grows. |
| `analyze_historical_tones.py` | Tone-spotter backtest over every recording in `backend/audio_files/recordings`, scored against dispatch metadata fetched from the kiosk API; writes `backend/data/historical_tone_backtest_report.json`. |
