# ARCHIVED: Code Review & Optimization Analysis: CFR Dispatch Mapping

> [!NOTE]
> **Archived Document**: The structural refactoring, modular package setup, `faster-whisper` integration, in-memory geocoder shapefile indexing, and multiprocessing concurrency proposals outlined below were successfully implemented during the **Phase 2 structural refactoring** of the repository. This document is kept for historical context.

---

This document provides a systematic review of the **CFR Dispatch Mapping** project structure, code readability, and performance. It outlines key architectural pivots to implement before integrating with external applications.


---

## 📂 File Names & Structures

### Current Architecture Assessment
*   **`main.py` Monolith**: The main entrypoint is a ~1,100 line script that mixes multiple concerns: audio streaming hardware controls, DSP tone-matching, transcription APIs, fuzzy string parsers, Geopandas/Shapely spatial projections, and HTTP network requests.
*   **Duplicate Code (`test_main.py`)**: `test_main.py` is a 100% duplicate of `main.py` except for the `DEVICE_ID` configuration variable. This creates immediate maintenance overhead, split-brain bugs, and is a violation of the DRY (Don't Repeat Yourself) principle.

### Proposed Restructured Package
We recommend refactoring the monolith into a modular Python package structure:

```
cfr_dispatch/
│
├── config.py                 # Configuration thresholds, constants, paths, and API endpoints.
├── main.py                   # Orchestration entrypoint (lightweight main loop).
│
├── audio/
│   ├── listener.py           # InputStream controller and RMS calculators.
│   └── dsp.py                # FFT tone matching, butterworth bandpass, and notch filtering.
│
├── parser/
│   ├── metadata.py           # Sanitization, regex parsers, and unit abbreviations.
│   └── geocoder.py           # Shapefile loading, coordinates projections, and grid checks.
│
└── integration/
    ├── supabase.py           # REST database client.
    └── push_notif.py         # Ntfy.sh and Join API connectors.
```

*   **Benefit**: This allows you to import only what you need, write clean unit tests for individual modules (e.g. testing parsing regexes without loading Geopandas), and eliminates code duplication.

---

## 🏷️ Variable Names & Commenting Style

### Variable Names Assessment
*   **Casing Inconsistencies**: The codebase mixes casing styles (e.g. `UNITS_VOCABULARY` vs `units_vocab`, `CALL_TYPES` vs `call_types`).
*   **Cryptic Abbreviations**: Variables like `pcm`, `rms`, `fft_data`, `leg1`/`leg2`, and `d` are used. While some (like PCM and RMS) are standard DSP terms, others could be descriptive (e.g. `intersection_leg_1` or `dispatch_candidate`).

### Commenting and Coding Habits
*   **Packed Statements (Python Anti-Pattern)**: The code frequently uses semi-colons to pack multiple statements on a single line:
    ```python
    is_currently_loud = rms > NOISE_AMPLITUDE_THRESHOLD; loudness_history.append(is_currently_loud)
    ```
    *   *Correction*: Separate statements onto individual lines. It improves code readability, trace logging, and breakpoint debugging.
*   **Missing Type Hinting**: Adding Python type annotations (e.g. `def local_geocode(self, parsed_address: str) -> Optional[dict]:`) will make it significantly easier to integrate other projects.

---

## ⚡ Speed & Processing Optimizations

Processing speed is critical on a Raspberry Pi. Below are areas where speed can be increased:

### 1. GIS Lookup Speed: Pre-Indexed Search
Currently, when a house number is parsed, we filter the Geopandas DataFrame:
```python
possible_matches = self.addresses_gdf[self.addresses_gdf[ADDRESS_HOUSE_NUM_COLUMN] == parsed_num]
```
Pandas DataFrame filtering carries overhead. 
*   **Optimization**: At startup, load the Shapefile and build an in-memory dictionary index:
    ```python
    self.house_number_index = {} # Maps house number string -> List of rows/indices
    ```
    When geocoding, retrieving possible matches becomes an $O(1)$ dictionary lookup. This turns a full-table query into a fast lookup, reducing geocoding latency from ~100ms to < 2ms.

### 2. Speech-to-Text: Switch to `faster-whisper`
Currently, the script uses the standard `openai-whisper` library.
*   **Optimization**: Replace it with `faster-whisper` (implemented in C++ using `ctranslate2`).
    *   It is **2x to 4x faster** than the standard OpenAI implementation.
    *   Supports `int8` CPU quantization, allowing the Whisper `base` model to transcribe a 10-second audio clip in **less than 1.5 seconds** on a Raspberry Pi 4/5.

### 3. CPU Concurrency: Threading vs. Multiprocessing
Currently, the script spawns a thread (`threading.Thread`) for `process_full_dispatch`.
*   **Problem**: Python has a **Global Interpreter Lock (GIL)**. Because transcription and GIS fuzzy geocoding are heavily CPU-bound, running them in a thread blocks the main audio loop thread. This can cause the audio input stream buffer to overflow, leading to missed tones or crackled recordings.
*   **Optimization**: Delegate the processing of dispatches to a separate **Process** (`multiprocessing.Process` or a `concurrent.futures.ProcessPoolExecutor`). This isolates CPU-intensive computations to a separate core, keeping the main audio stream listener latency-free.
