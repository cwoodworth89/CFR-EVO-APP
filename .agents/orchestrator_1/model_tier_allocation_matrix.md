# CFR EVO v1.0.0 — Definitive Model Tier Cost Allocation Matrix (Hardened)

**Objective**: Maximize AI credit efficiency and operational throughput by assigning every engineering task, architectural refactor, and verification workflow to the optimal LLM model tier (**Flash-Lite**, **Gemini 3.7 Flash Standard**, **Gemini 3.7 Flash Thinking**, or **Gemini 3.1 Pro**) based on cognitive demand, structural complexity, and mathematical rigor.

---

## 1. Model Tier Selection Methodology (Featuring Gemini 3.7 Flash)

```
+-------------------------------------------------------------------------------------------------------------------------------+
|                                            UPDATED MODEL TIER SELECTION RUBRIC                                                |
+--------------------------+--------------------------------------------+-------------------------------------------------------+
| Model Tier               | Complexity & Reasoning Profile             | Typical Workflows in CFR EVO                          |
+--------------------------+--------------------------------------------+-------------------------------------------------------+
| **Flash-Lite**           | - Deterministic execution & linting        | - Test runner invocation (backtest_parser.py)         |
| (Lowest Cost /           | - Patterned renaming & string substitutions| - Dead code & orphan file pruning                     |
|  Instant Speed)          | - Direct grep / regex checks               | - Terminology alignment (Simulate -> Review)          |
|                          | - Simple config & environment updates      | - Static JSON & vocabulary list cross-checking        |
+--------------------------+--------------------------------------------+-------------------------------------------------------+
| **Gemini 3.7 Flash**     | - Fast modular refactoring & UI coding     | - Component decomposition (ReviewTable, AudioPlayer)  |
| **(Standard Mode)**      | - Standard REST API endpoint creation      | - SQL DDL migration & master_properties schema        |
| (High Speed / Balanced)  | - React state hooks & context extraction   | - Frontend API resolution & Leaflet layer updates     |
|                          | - Browser visual inspection & screenshots  | - Standard spatial queries (Shapely / Turf.js)        |
+--------------------------+--------------------------------------------+-------------------------------------------------------+
| **Gemini 3.7 Flash**     | - Multi-step algorithmic reasoning         | - Two-phase audio slicing state machines              |
| **(Thinking Mode)**      | - Complex geometry & vector math           | - Street View atan2 vantage vector math & heading     |
| (Hybrid Deep Reasoning / | - Road closure polygon containment         | - OSRM custom Lua profile road weighting & biasing    |
|  High Speed & Cost-Eff.) | - Squelch & dynamic noise floor tracking   | - Apparatus momentum & grade penalty kinematic curves |
+--------------------------+--------------------------------------------+-------------------------------------------------------+
| **Gemini 3.1 Pro**       | - Deepest mathematical modeling            | - PA Golden Fingerprint FFT harmonic analysis         |
| (Maximum Reasoning /     | - Advanced acoustic filter design          | - 5th-order Butterworth HPF & IIR notch filter math   |
|  Complex Architectures)  | - Parameter-Efficient Fine-Tuning (PEFT)   | - LoRA attention adapter projection matrix fine-tuning|
|                          | - Multi-process GIL-isolation supervisors  | - Cross-process race condition resolution & locks     |
+--------------------------+--------------------------------------------+-------------------------------------------------------+
```

---

## 2. Complete Model Tier Allocation Matrix Across Phases 0 to 5

| Phase & Domain | Task ID | Task Description | Cognitive Demand & Scope | Allocated Model Tier | AI Credit Cost Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 0: Infrastructure** | P0-01 | Docker Compose container health checks & restart policies | Deterministic YAML service configuration | **Flash-Lite** | Minimal |
| **Phase 0: Infrastructure** | P0-02 | PostgreSQL 16 schema creation (`migration.sql`, `master_properties`) | Standard relational DDL & indexes | **3.7 Flash (Standard)** | Low |
| **Phase 0: Infrastructure** | P0-03 | Sibling microservice dynamic `sys.path` injection | Modular Python import path routing (6 lines) | **Flash-Lite** | Minimal |
| **Phase 0: Infrastructure** | P0-04 | Dead code pruning (`test_main.py`, legacy Supabase code) | Patterned deletion & cleanup | **Flash-Lite** | Minimal |
| **Phase 1: Audio & DSP** | P1-01 | RMS dynamic noise floor rolling average (`deque(maxlen=50)`) | Moving average threshold logic | **3.7 Flash (Standard)** | Low |
| **Phase 1: Audio & DSP** | P1-02 | 5th-order Butterworth HPF & Hamming window FFT peak spotting | Signal processing, filter design & Z-score math | **3.1 Pro** | Moderate |
| **Phase 1: Audio & DSP** | P1-03 | Station PA Golden Fingerprint (595/647 Hz) page discriminator | Spectral harmonic analysis & notch filtering | **3.1 Pro** | Moderate |
| **Phase 1: Audio & DSP** | P1-04 | Audio listener silence timeout & squelch termination | Audio streaming state transitions | **3.7 Flash (Thinking)** | Low |
| **Phase 1: Audio & DSP** | P1-05 | Multiprocessing CPU core isolation, supervisor & restart loop| IPC, process supervisor, memory isolation | **3.7 Flash (Thinking)** | Moderate |
| **Phase 2: STT & NLP** | P2-01 | CTranslate2 `int8` model singleton & thread lock setup | Standard Python wrapper integration | **3.7 Flash (Standard)** | Low |
| **Phase 2: STT & NLP** | P2-02 | PEFT LoRA attention adapter fine-tuning (`q_proj`, `v_proj`)| Deep learning architecture & loss convergence | **3.1 Pro** | High |
| **Phase 2: STT & NLP** | P2-03 | Phonetic homophone dictionary regex sanitizer table | Regex mapping (`won`/`juan` -> `1`, etc.) | **Flash-Lite** | Minimal |
| **Phase 2: STT & NLP** | P2-04 | Dynamic prompt hotwords construction (`bias_prompt.py`) | Context string formatting & caching | **3.7 Flash (Standard)** | Low |
| **Phase 2: STT & NLP** | P2-05 | Double-round transcript duplication & `<35s` cutoff filter | Heuristic text length alignment | **Flash-Lite** | Minimal |
| **Phase 2: STT & NLP** | P2-06 | Two-Phase dispatch slicing state machine (Phase 1 vs 2) | Complex dual-stage async pipeline logic | **3.7 Flash (Thinking)** | Moderate |
| **Phase 3: GIS & Cadastre** | P3-01 | 69k+ Coquitlam shapefile in-memory hash index ($O(1)$) | Fast in-memory dict structuring | **3.7 Flash (Standard)** | Low |
| **Phase 3: GIS & Cadastre** | P3-02 | Subaddress & suite number regex stripping rules | Patterned regex string cleansing | **Flash-Lite** | Minimal |
| **Phase 3: GIS & Cadastre** | P3-03 | Riverview & station override spatial mapping | Key-value dictionary overrides | **Flash-Lite** | Minimal |
| **Phase 3: GIS & Cadastre** | P3-04 | Option 2 boundary polygon rings extraction (`target.rings`)| Coordinate transformation (WGS84) | **3.7 Flash (Standard)** | Low |
| **Phase 3: GIS & Cadastre** | P3-05 | NFPA 291 fire hydrant compact JSON serialization | Data compaction & class threshold logic | **Flash-Lite** | Minimal |
| **Phase 3: GIS & Cadastre** | P3-06 | Client-side Turf.js bounding box & on-route hydrant filter | Spatial geometry bounding box queries | **3.7 Flash (Thinking)** | Low |
| **Phase 4: Routing & Geo** | P4-01 | Containerized OSRM MLD engine query client (`:5000`) | Standard HTTP REST client integration | **3.7 Flash (Standard)** | Low |
| **Phase 4: Routing & Geo** | P4-02 | Station 1 tactical corridor waypoint injection | Spatial trajectory biasing & corridor geometry | **3.7 Flash (Thinking)** | Low |
| **Phase 4: Routing & Geo** | P4-03 | 3-tier apparatus speed physics & momentum preservation | Dynamic kinematic modeling & grade penalties | **3.7 Flash (Thinking)** | Low |
| **Phase 4: Routing & Geo** | P4-04 | Google Street View Great Circle `atan2` vantage vector math | Spherical trigonometry & camera azimuth | **3.7 Flash (Thinking)** | Low |
| **Phase 4: Routing & Geo** | P4-05 | Ray-casting Point-in-Polygon road closure zone filtering | GeoPandas polygon containment queries | **3.7 Flash (Thinking)** | Low |
| **Phase 5: Kiosk & UI** | P5-01 | Remediate raw relative `fetch()` calls to `API_BASE_URL` | Mechanical string replacement across 2 files | **Flash-Lite** | Minimal |
| **Phase 5: Kiosk & UI** | P5-02 | Bundle external GitHub/CDN Leaflet marker icons locally | Asset download & local path rewrites | **Flash-Lite** | Minimal |
| **Phase 5: Kiosk & UI** | P5-03 | Decompose `DispatchReview.jsx` (1,602 lines) into sub-folders| Structural component refactoring & clean props| **3.7 Flash (Standard)** | Medium |
| **Phase 5: Kiosk & UI** | P5-04 | Extract `ReviewContext` & `useKeyboardShortcuts` hooks | React state abstraction & custom hooks | **3.7 Flash (Standard)** | Low |
| **Phase 5: Kiosk & UI** | P5-05 | 10-foot bay HUD responsive layout & touch styling | CSS ergonomics, Tailwind utility styling | **3.7 Flash (Standard)** | Low |
| **Phase 5: Kiosk & UI** | P5-06 | Offline GeoJSON vector fallback for Planning/Fire Zones | Leaflet layer state & offline error handling | **3.7 Flash (Standard)** | Low |
| **Phase 5: MLOps & QA** | P5-07 | SMMR & template-normalized WER backtesting test runner | Script execution & benchmark parsing | **Flash-Lite** | Minimal |
| **Phase 5: MLOps & QA** | P5-08 | Full-stack remote kiosk automated deployment script | SSH command chaining & npm build runner | **Flash-Lite** | Minimal |

---

## 3. Cost Allocation Summary & Efficiency Gains (with Gemini 3.7 Flash)

```
+-----------------------------------+-----------------+---------------------------------------+---------------------+
| Model Tier                        | Task Count      | Percentage of Backlog                 | Cost Savings vs Pro |
+-----------------------------------+-----------------+---------------------------------------+---------------------+
| **Flash-Lite**                    | 12 Tasks        | 36.4%                                 | ~95% Cost Reduction |
| **Gemini 3.7 Flash (Standard)**   | 10 Tasks        | 30.3%                                 | ~80% Cost Reduction |
| **Gemini 3.7 Flash (Thinking)**   | 8 Tasks         | 24.2%                                 | ~70% Cost Reduction |
| **Gemini 3.1 Pro**                | 3 Tasks         | 9.1%                                  | Baseline Benchmark  |
+-----------------------------------+-----------------+---------------------------------------+---------------------+
| **TOTAL**                         | 33 Tasks        | 100.0%                                | **~84.8% Net Savings**|
+-----------------------------------+-----------------+---------------------------------------+---------------------+
```

### Strategic Allocation Summary:
1. **3 Pro Tasks (9.1%)**: Reserved exclusively for the deepest mathematical modeling (FFT Butterworth/Z-score harmonic analysis, PA Golden Fingerprint notch filter design, and PEFT LoRA attention adapter fine-tuning).
2. **8 Gemini 3.7 Flash Thinking Tasks (24.2%)**: Solves multi-step spatial and async algorithms (Street View `atan2` vantage math, OSRM corridor weighting, kinematics curves, two-phase audio slicing state machines, Turf.js spatial queries) with high reasoning at Flash pricing.
3. **10 Gemini 3.7 Flash Standard Tasks (30.3%)**: Modular component decomposition, React context state abstractions, SQL DDL migrations, and kiosk HUD styling.
4. **12 Flash-Lite Tasks (36.4%)**: Fast deterministic script runners, string find-and-replace, dead code pruning, and regex sanitizer tables.
