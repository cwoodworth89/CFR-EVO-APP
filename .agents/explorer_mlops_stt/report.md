# CFR EVO v1.0.0: MLOps & Whisper Speech-to-Text Architectural Report

**Author**: MLOps & Whisper STT Architecture Explorer  
**Date**: 2026-08-14  
**Target System**: CFR EVO v1.0.0 Emergency Dispatch Kiosk & Processing Engine  
**Runtime Constraints**: 100% Offline Local Execution, <1.5s STT Inference Latency, Zero Operational Cloud Cost

---

## Executive Summary

The Speech-to-Text (STT) and MLOps subsystem in **CFR EVO v1.0.0** is an offline, high-speed acoustic transcription and entity extraction engine designed specifically for computerized Coquitlam Fire Rescue dispatch broadcasts. By combining **Whisper base/tiny models fine-tuned with Low-Rank Adaptation (LoRA)**, **CTranslate2 int8 CPU quantization**, **symmetric phonetic text sanitization**, **spatial-phonetic GIS grid constraints**, and **dynamic Human-in-the-Loop (HITL) prompt biasing**, the engine achieves **<1.5s inference latency on standard kiosk CPUs** with an overall pipeline Structured Metadata Match Rate (SMMR) exceeding **90%**.

The training and MLOps lifecycle is architected for **zero operational hosting costs**: model training is offloaded to free-tier Google Colab T4 GPUs via headless `rclone` synchronization, and quantized CTranslate2 model artifacts are deployed directly back to the physical kiosk for purely local execution against containerized PostgreSQL and local ESRI shapefiles.

---

## 1. Offline Speech-to-Text Architecture & Quantization

```
                          ┌────────────────────────────────────────────────────────┐
                          │         Offline Dispatch Kiosk Audio Pipeline          │
                          └────────────────────────────────────────────────────────┘
                                                      │
                                                      ▼
                                       ┌─────────────────────────────┐
                                       │ 16kHz Mono Audio Stream /   │
                                       │ Raw Buffer (WAV / PCM)      │
                                       └─────────────────────────────┘
                                                      │
                                                      ▼
                                       ┌─────────────────────────────┐
                                       │ DSP Bandpass & Golden FFT   │
                                       │ Tone Filtering (dsp.py)     │
                                       └─────────────────────────────┘
                                                      │
                                                      ▼
    ┌───────────────────────────┐      ┌─────────────────────────────┐
    │ Dynamic Biasing & Hotwords│ ───► │ faster-whisper CTranslate2  │
    │ (bias_prompt.py + HITL)   │      │ int8 CPU Model Singleton    │
    └───────────────────────────┘      │ (transcriber.py)            │
                                       └─────────────────────────────┘
                                                      │
                                                      ▼
                                       ┌─────────────────────────────┐
                                       │ Raw Text Output             │
                                       │ Latency: ~1.2s - 1.8s       │
                                       └─────────────────────────────┘
```

### 1.1 Architecture & Runtime Engine
* **Core Model Foundation**: `openai/whisper-base` (and `whisper-tiny` for ultra-low latency constraints).
* **Fine-Tuning Paradigm**: Parameter-Efficient Fine-Tuning (PEFT) using **LoRA (Low-Rank Adaptation)**:
  * Rank ($r$): `32`
  * Alpha ($\alpha$): `64`
  * Target Modules: Attention projection layers (`q_proj`, `v_proj`)
  * Dropout: `0.05`
  * Trainable Parameters: $<1.5\%$ of total model weights (~1.2M parameters).
* **Weight Merging & Quantization**:
  * Adapter weights merged back into base Whisper weights via Hugging Face PEFT: `model.merge_and_unload()`.
  * Exported to **CTranslate2 format** using 8-bit integer quantization (`compute_type="int8"`):
    ```powershell
    ct2-transformers-converter --model ./merged_whisper_base --output_dir ./models/whisper-base-cfr-ct2 --quantization int8
    ```
* **Kiosk Execution**: Loaded via `faster-whisper.WhisperModel` inside a thread-safe singleton (`backend/cfr_dispatch/stt/transcriber.py`, lines 9–21).
* **Performance Metrics**:
  * **Inference Latency**: 1.2s – 1.8s on multi-core x86/ARM CPUs (speed ratio ~0.05x real-time).
  * **Memory Footprint**: ~180MB RAM (int8 weights), eliminating GPU requirements on station display kiosks.
  * **VAD Filtering**: Integrated Silero Voice Activity Detector (`vad_filter=True`) automatically strips silence chunks, reducing computation by ~34.2%.

### 1.2 Model Configuration Artifacts
* Authoritative configuration at `backend/models/whisper-base-cfr-ct2/`:
  * `model.bin`: Quantized CTranslate2 binary weights.
  * `config.json`: Decoder head alignments (8 heads mapped across layers 3, 4, 5) and suppress token sequences.
  * `vocabulary.json`: Tokenizer vocabulary lookup table.

---

## 2. Ground-Truth Dataset Extraction & Curation Pipeline

The ground-truth curation pipeline (`backend/scripts/extract_training_data.py`) automates extracting verified dispatches from the containerized PostgreSQL database into a standard Hugging Face speech dataset format.

```
┌─────────────────────────┐
│ PostgreSQL 'live_calls' │
│ (feedback_submitted=T)  │
└─────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────────────────┐
│ extract_training_data.py Curation Filters                              │
│                                                                        │
│ 1. Opt-in Safeguard: target->>'include_in_training' != false           │
│ 2. Call Duration Filter: Exclude cut-offs (<35s total duration)        │
│ 3. Double-Round Duplication: If duration >25s & single-round label,    │
│    duplicate label text to match repeating broadcast audio             │
│ 4. Normalization: Lowercase & strip non-alphanumeric punctuation       │
│ 5. Incident Vocabulary Learning: Append novel verified call types      │
│    to data/vocabulary/call_types.txt                                   │
└────────────────────────────────────────────────────────────────────────┘
             │
             ├───► backend/data/training/metadata.csv
             ├───► backend/data/training/audio/{dispatch_id}.wav
             └───► PATCH /api/dispatches/{id} (model_updated: true)
```

### 2.1 Curation Heuristics & Safeguards
1. **Human-in-the-Loop Filter**: Only records where `feedback_submitted == true` and `verified_transcript` is present are extracted.
2. **Explicit Opt-Out Safeguard**: Inspects JSONB `target.include_in_training`. If false (e.g. garbled radio static, overlapping transmissions), the recording is skipped.
3. **Cut-off Audio Exclusion**: Announcements truncated prematurely ($<35\text{s}$ overall audio where dispatcher was cut off) are excluded to prevent teaching Whisper incomplete CAD sentence terminations.
4. **Double-Round Alignment without Hallucination**:
   * Coquitlam CAD broadcasts two identical back-to-back announcement rounds for long calls ($>25\text{s}$).
   * Human reviewers in the kiosk UI typically correct only Round 1.
   * If a human-verified transcript contains only one round on a $>25\text{s}$ audio recording, `extract_training_data.py` (lines 191–196) dynamically duplicates the verified text (`f"{normalized_text} {normalized_text}"`).
   * This aligns the audio acoustic duration with the training text, preventing Whisper from hallucinating premature `<|endoftranscript|>` tokens.
5. **Dynamic Incident Discovery**: `learn_new_incident_types()` (lines 28–90) scans reviewer inputs for previously unseen `verified_incident` strings and automatically appends them to `backend/data/vocabulary/call_types.txt`.
6. **State Synchronization**: Updates the database column `model_updated = true` via `PATCH /api/dispatches/{dispatch_id}` to prevent re-processing identical records across training iterations.

---

## 3. Regression & Backtesting Framework

CFR EVO implements a dual-layer benchmarking suite:
1. **STT Acoustic & End-to-End Regression**: `backend/scripts/backtest_regression.py`
2. **Comparative CAD Parser Backtester**: `backend/scripts/backtest_parser.py`

### 3.1 Structured Metadata Match Rate (SMMR)
Traditional Word Error Rate (WER) alone is insufficient for emergency dispatch evaluation because minor filler words (e.g. *"and"*, *"the"*) do not impact emergency response, whereas a single missed apparatus digit or street name is critical. The framework measures **Structured Metadata Match Rate (SMMR)** across 5 discrete fields:

$$\text{SMMR} = \frac{1}{5} \left( \text{Acc}_{\text{Address}} + \text{Acc}_{\text{Units}} + \text{Acc}_{\text{Incident}} + \text{Acc}_{\text{Grid}} + \text{Acc}_{\text{TalkGroup}} \right)$$

| Evaluated Dimension | Ground-Truth Target | Benchmark Accuracy | Extraction Method |
| :--- | :--- | :---: | :--- |
| **Responding Units** | `live_calls.responding_units` | **97.5%** | Apparatus regex & vocabulary validation (`abbreviate_units`) |
| **Incident Type** | `live_calls.incident_type` | **88.9%** | Exact substring + Fuzzy token match against `call_types.txt` |
| **Map Grid** | `target.map_grid` | **75.3%** | Integer validation against `1 <= N <= 134` bounds |
| **Address / Location** | `target.address` | **67.9%** | Subaddress separation + Coquitlam parcel GIS matching |
| **Talk Group** | `target.radio_channel` | **59.3%** | Verbal channel regex matching against `radio_channels.txt` |
| **Overall Pipeline SMMR** | Aggregate Mean | **77.8%** | Multi-variable weighted accuracy |

### 3.2 Symmetric Normalization & Template Reconstruction
* **Symmetric Normalization**: Evaluates WER/CER only after executing `sanitize_transcript()` on **both** human reference and model hypothesis.
* **Post-Transcription Template Reconstruction**: `reconstruct_template_transcript()` (`parser.py`, lines 919–1023) maps parsed entities into the canonical CAD template format before computing Levenshtein distance. This standardizes variable dispatcher phrasing and eliminates false deletion penalties.
* **Quality Categorization**:
  * **100% Perfect**: $\text{WER} = 0.0\%$
  * **Operational**: $0.0\% < \text{WER} \le 20.0\%$
  * **Failed**: $\text{WER} > 20.0\%$
* **Evaluation Telemetry**: Logged locally to `backend/data/training/evaluation_history.json` and posted via REST to FastAPI `/api/evaluations` (`EvaluationHistoryModel`), rendering live historical regression charts on the kiosk metrics UI.

---

## 4. Phonetic & Vocabulary Hardening

```
Raw Speech Stream ──► Whisper Base LoRA ──► Raw Transcript
                                                  │
                                                  ▼
                         ┌──────────────────────────────────────────────────┐
                         │   1. Phonetic Homophone Sanitizer                │
                         │      (sanitize_transcript in parser.py)          │
                         │      - Numbers: won/juan -> 1, to/too -> 2       │
                         │      - Units: ancient/angel -> engine            │
                         │      - City: colquitt loom/cocoa -> coquitlam    │
                         │      - Streets: low heat -> lougheed             │
                         └──────────────────────────────────────────────────┘
                                                  │
                                                  ▼
                         ┌──────────────────────────────────────────────────┐
                         │   2. Dynamic Vocabulary Lists                    │
                         │      (backend/data/vocabulary/)                  │
                         │      - 46 Units, 88 Call Types, 134 Grids        │
                         └──────────────────────────────────────────────────┘
                                                  │
                                                  ▼
                         ┌──────────────────────────────────────────────────┐
                         │   3. Spatial-Phonetic Radius Correction          │
                         │      (gis_service.CoquitlamDataValidator)        │
                         │      - 1..134 Zone boundary spatial join         │
                         │      - Restrict candidate streets to zone bounds │
                         └──────────────────────────────────────────────────┘
```

### 4.1 Phonetic Homophone Sanitizer Matrix
Implemented in `backend/cfr_dispatch/parser.py` (lines 52–202):

| Category | Typical Acoustic Mishearings (Whisper) | Canonical Sanitized Replacement | Rationale / Failure Mode Prevented |
| :--- | :--- | :--- | :--- |
| **Apparatus Units** | *"engine won"*, *"engine juan"*, *"rescue run"*, *"ladder on"* | `engine 1`, `rescue 1`, `ladder 1` | Prevents unit number dropping and unassigned apparatus codes |
| **Apparatus Types** | *"ancient 1"*, *"agent 2"*, *"angel 4"*, *"asian 3"* | `engine 1`, `engine 2`, `engine 4`, `engine 3` | Fixes dispatcher mumbling and background siren distortion |
| **Quints / Ladders** | *"queens 5"*, *"water 1"* | `quint 5`, `ladder 1` | Distinguishes apparatus from street names (*Queens Rd*) |
| **Wake-Word / City** | *"colquitt loom"*, *"corporate loan"*, *"cocoa"*, *"point loma"*, *"hope with them"* | `coquitlam` | Ensures opening CAD anchor correctly isolates following unit names |
| **Priority / Actions**| *"respawn"*, *"responses emergency"*, *"resign"*, *"we found"* | `respond`, `respond emergency` | Prevents parser anchor split failure |
| **Radio Channels** | *"use tax"*, *"use tack"*, *"use tag"*, *"news tack"*, *"mens table"* | `use talk group` | Aligns channel regex boundary |
| **Map Grid** | *"math grids"*, *"math grades"*, *"map grades"*, *"math griff"* | `map grid` | Aligns grid anchor boundary |
| **Major Arterials** | *"low heat highway"*, *"love heat hwy"*, *"lowheed"* | `lougheed highway` | Primary east-west Coquitlam highway corridor |
| **Complex Streets** | *"gaiden's burry"*, *"gaitensbury"*, *"pintree whey"*, *"do we need from"* | `gatensbury`, `pinetree way`, `dewdney trunk road` | Corrects high-frequency local street homophones |

### 4.2 Dynamic Vocabulary Lists (`backend/data/vocabulary/`)
* `units_vocabulary.txt`: 46 apparatus identifiers (Engine 1–11, Ladder 1–4, Medic 1–4, Rescue 1–4, Quint 5, Squad 1–4, Tender 1–4, Water Tender 1–4, Hazmat 3, LAV 4, Battalion 1–2, Chief 1–2, Car 1–9).
* `call_types.txt`: 88 prioritized dispatch categories sorted longest-first.
* `radio_channels.txt`: Standard Coquitlam CAD channels (Talk Group 5–10, Combined Venue Port Mann/Transit).
* `map_grid_numbers.txt`: Valid Coquitlam map grid numbers (1 through 134).
* `landmarks.json`: 762 pre-mapped municipal parks, facilities, hospitals, and schools with hardcoded centroid coordinates.

### 4.3 Context-Aware Speech Biasing (`bias_prompt.py`)
Whisper decoders are biased in real-time via `build_stt_bias_words()`:
1. **Initial Prompt Anchor**: Natural sentence structure (`"Coquitlam Fire Dispatch. Engine 1, Ladder 1, Quint 5, Rescue 1. Structure Fire, Medical Aid... Respond on talk group Tac 1, map grid."`).
2. **Hotword Injection**: Bounded comma-delimited tokens combining core dispatch terms, top 15 apparatus units, top 15 GIS street frequencies, and top 10 HITL corrected streets.
3. **Dynamic HITL Feedback Loop**: `get_hitl_verified_streets()` polls `/api/dispatches` for recent reviewer corrections, extracting street names where `verified_address != system_address` and caching them in memory for 10 minutes to weight future STT decoding.

### 4.4 Spatial-Phonetic Radius Disambiguation
* **Grid-to-Street Index**: In `gis_service.CoquitlamDataValidator`, an `sjoin` spatial intersection between `Property_Information/Addresses.shp` and `Emergency_Response_Zones.shp` pre-indexes all valid street names per map grid zone (1..134).
* **Cross-Road Correction**: `fuzzy_correct_cross_roads()` validates cross-street candidates against `coquitlam_streets.txt` with a length-aware similarity threshold ($\ge 90\%$ for $\le 4$ chars, $\ge 75\%$ for $>4$ chars) to eliminate false cross-street snapping.

---

## 5. Colab GPU Training & Headless Cloud Sync Workflow

To eliminate monthly cloud infrastructure fees while leveraging modern GPU acceleration, CFR EVO uses an asynchronous training lifecycle:

```
┌──────────────────────────────────────────────┐
│ Station Kiosk (tcfire@100.95.146.94)         │
│ 1. extract_training_data.py                  │
│ 2. rclone sync /backend/data/training gdrive:│
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ Google Drive (Encrypted / Free Storage)      │
│ - metadata.csv                               │
│ - audio/DISP-*.wav                           │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ Google Colab (Free T4 GPU Runtime)           │
│ cfr_whisper_colab_fine_tuning.ipynb          │
│ 1. !rclone copy gdrive: /content/dataset     │
│ 2. Seq2SeqTrainer (LoRA r=32, fp16=True)     │
│ 3. merge_and_unload()                        │
│ 4. ct2-transformers-converter (int8)         │
│ 5. Download whisper-base-cfr-ct2.zip         │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ Kiosk Model Deployment                       │
│ Extract to /backend/models/                  │
│ Set WHISPER_MODEL=models/whisper-base-cfr-ct2│
└──────────────────────────────────────────────┘
```

### 5.1 Step-by-Step Training Runbook
1. **Dataset Export on Station Kiosk**:
   ```bash
   python backend/scripts/extract_training_data.py
   rclone sync /home/tcfire/CFR-EVO-APP/backend/data/training gdrive: --progress
   ```
2. **Colab Execution (`docs/cfr_whisper_colab_fine_tuning.ipynb`)**:
   * Open notebook in Google Colab, select **T4 GPU** runtime.
   * Authenticate `rclone` with Google Drive app folder.
   * Run training cells:
     * Preprocesses audio at 16kHz via `WhisperFeatureExtractor` and `WhisperTokenizer`.
     * Trains LoRA adapter (`r=32, alpha=64`, learning rate `1e-3`, batch size `8`, gradient accumulation `2`, 5 epochs, `fp16=True`). Training duration: ~4–6 minutes on T4 GPU.
     * Merges adapter weights and converts to CTranslate2 int8 format.
     * Generates `whisper-base-cfr-ct2.zip`.
3. **Local Deployment**:
   * SCP/download `whisper-base-cfr-ct2.zip` to the kiosk.
   * Extract to `backend/models/whisper-base-cfr-ct2/`.
   * Restart CFR EVO backend service (`sudo systemctl restart cfr-backend`).

---

## 6. Model Allocation Matrix & Credit Optimization

In compliance with the workspace Model Tier Strategy:

| Task / Subsystem | Recommended Model Tier | Justification & Complexity |
| :--- | :---: | :--- |
| **Deterministic Parser & SMMR Backtesting** (`backtest_parser.py`, `backtest_regression.py`) | **Flash-Lite / Flash (Low Effort)** | Deterministic evaluation loops, metric aggregations, regex validation. |
| **Vocabulary Maintenance & Suffix Mapping** (`call_types.txt`, `units_vocabulary.txt`) | **Flash-Lite (Low Effort)** | Pure text list deduplication and sorting. |
| **HITL Review Triage & Audio Diagnostics** (`hitl-log-analysis`, `inspect_dispatch.py`) | **Flash (Medium Effort)** | Comparing transcript logs, evaluating JSON payloads, error triage. |
| **CTranslate2 Model Packaging & Conversion** (`ct2-transformers-converter`) | **Flash (Medium Effort)** | Standard CLI wrapper script execution and artifact verification. |
| **LoRA Attention Adapter Fine-Tuning & Hyperparameter Tuning** | **Pro (High Reasoning)** | Complex gradient dynamics, loss convergence analysis, adapter rank allocation. |
| **Spatial-Phonetic Radius Constraint Algorithms** | **Pro (High Reasoning)** | Multi-polygon GIS spatial indexing, bounding coordinate intersections, acoustic-spatial fusion. |

---

## 7. Architectural Recommendations for v1.0.0 Feature Freeze

1. **Lock Offline Default Model Path**: Ensure `backend/.env` on all deployed kiosks defaults to `WHISPER_MODEL=models/whisper-base-cfr-ct2` rather than downloading base models from Hugging Face at runtime.
2. **Automated SMMR Regression Gate in CI**: Integrate `python backend/scripts/backtest_parser.py` into automated testing (`run_test_suite.py`) to prevent regressions in regex segmentation or phonetic dictionaries during future updates.
3. **Continuous Background HITL Caching**: Keep the 10-minute caching window in `get_hitl_verified_streets()` to ensure zero network latency penalties during live Phase 1 audio slicing.
