# Execution Plan: CFR EVO v1.0.0 Multi-Perspective Architectural Review, Model Tier Allocation & Offline Hardening Validation

## Mission Overview
Deliver a comprehensive, multi-perspective architectural review across all four system pillars (Backend/DSP, Frontend/Kiosk Ergonomics, GIS/Master Properties, MLOps/Whisper Training), construct the complete model tier cost allocation matrix (Flash-Lite / Flash / Pro), and define strict zero-online-fallback offline verification rubrics across all development phases (Phase 0 to Phase 5).

---

## Step-by-Step Plan

### Phase 1: Setup & Initialization
- [x] Record original request in `ORIGINAL_REQUEST.md` and `DISPATCH.md`.
- [x] Initialize persistent `BRIEFING.md`, `plan.md`, and `progress.md`.
- [ ] Start recurring heartbeat cron (`schedule(CronExpression="*/10 * * * *")`).

### Phase 2: Multi-Domain Specialized Technical Exploration
Dispatch 4 specialized Explorers concurrently with domain-specific focus areas:
1. **Explorer 1 (Backend & DSP Architecture)**:
   - Audio streaming loop, RMS noise gating, 2-phase dispatch slicing.
   - Dual-tone FFT harmonic analysis, Station PA Golden Fingerprints (`595 Hz / 647 Hz`).
   - Sibling microservice separation (`sys.path`), FastAPI endpoints, and local PostgreSQL / MQTT event flow.
2. **Explorer 2 (Frontend & Kiosk Ergonomics Architecture)**:
   - 10-foot apparatus bay display ergonomics vs. desktop / laptop workstation console.
   - Component decomposition into dedicated sub-folders (`ReviewTable/`, `AudioWaveformPlayer/`, `VerificationSidebar/`).
   - Rapid review workflows: `Ctrl+Space`, `Alt+Enter`, `Ctrl+Enter`, prefilling, auto-advance, and audio auto-play.
   - Offline Leaflet tile integration and vector polygon rendering.
3. **Explorer 3 (GIS, Master Properties & Routing Architecture)**:
   - 69k+ Coquitlam property shapefile indexing and parcel polygon matching.
   - 3,381 NFPA 291 fire hydrants in-memory Turf.js filtering and class color coding.
   - Containerized OSRM routing engine with `continue_straight=true` momentum preservation and Station 1 tactical corridor waypoint injection.
   - Google Street View `atan2` vantage vector math and camera orientation geometry.
   - Dynamic road closure ingestion and emergency bypass routing.
4. **Explorer 4 (MLOps & Whisper STT Architecture)**:
   - Offline Whisper LoRA fine-tuning and CTranslate2 `int8` CPU quantization.
   - Ground-truth dataset extraction, 35s cut-off filter, and double-round call duplication.
   - Structured Metadata Match Rate (SMMR) and template-normalized WER backtesting harness.
   - Phonetic homophone dictionary sanitizer and vocabulary bias lists.

### Phase 3: Synthesis & Framework Construction
- [ ] Synthesize Explorer reports into a unified 4-pillar architectural assessment.
- [ ] Construct the definitive **Model Tier Cost Allocation Matrix** (Flash-Lite vs Flash vs Pro) across all operational, refactoring, and AI-assisted workflows.
- [ ] Formulate the **Zero-Online-Fallback & Offline Verification Rubrics** across Phases 0 to 5 with strict pass/fail criteria and edge-case coverage.

### Phase 4: Adversarial Validation & Integrity Audit
- [ ] Dispatch Challenger to stress-test offline resilience, boundary conditions, and model tier allocation logic.
- [ ] Dispatch Forensic Auditor to verify compliance with zero-cloud dependencies and architectural rules in `GEMINI.md`.
- [ ] Gate check: Validate all findings against strict pass criteria.

### Phase 5: Master Review Package & Handoff
- [ ] Compile comprehensive master report in `.agents/orchestrator_1/architectural_review_package.md`.
- [ ] Update `progress.md`, `BRIEFING.md`, and generate `handoff.md`.
- [ ] Send final synthesis to caller agent via `send_message`.
