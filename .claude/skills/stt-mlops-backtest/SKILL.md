---
name: stt-mlops-backtest
description: Procedures for extracting ground-truth dispatch audio, computing Word Error Rate (WER) benchmarks, evaluating Whisper speech-to-text accuracy, and running comparative parser regressions.
---

# STT MLOps & Regression Evaluation

This skill covers evaluating Whisper STT transcription quality, extracting ground-truth datasets, and benchmarking parser precision against verified dispatch records.

---

## 1. Extract Training Ground-Truth Dataset

Pull human-verified dispatches and audio recordings from the local database to the local cache:
```powershell
python backend/scripts/extract_training_data.py
```
* **Output**: Cached audio at `backend/data/training/audio/` and metadata at `backend/data/training/metadata.csv`.
* **Heuristics**: Automatically skips cut-off calls ($<35\text{s}$) where `include_in_training` is false.

---

## 2. Execute Backtest & Regression Benchmarking

Evaluate current model accuracy (WER and Character Error Rate) against historical ground-truth records:
```powershell
python backend/scripts/backtest_regression.py
```

### Critical Rules for WER Benchmarks:
1. **Symmetric Normalization**: Always apply `sanitize_transcript()` to **both** ground-truth reference text and model hypothesis before computing Levenshtein WER.
2. **Round Count Alignment**: For long dispatches ($>25\text{s}$ double-round broadcasts), dynamically align reference and hypothesis round counts before scoring to prevent artificial $\sim 50\%$ deletion penalties.
3. **Structured Metrics**: Inspect SMMR (Structured Metadata Match Rate) logged to the `evaluation_history` table.

---

## 3. Comparative Parser Backtesting

Benchmark the production parser ([`backend/cfr_dispatch/parser/`](../../backend/cfr_dispatch/parser/), a 6-module package since the 1,053-line `parser.py` was split) against alternative parsing modules:
```powershell
python backend/scripts/backtest_parser.py
```
Validates extraction accuracy across:
* Address / Street Suffixes
* Responding Apparatuses
* Incident Types
* Map Grid Zones (1..134)
* Radio Talk Groups
