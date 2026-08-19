# Original User Request

## 2026-08-14T17:06:05Z

Comprehensive multi-agent architectural review and validation for the CFR EVO v1.0.0 Feature Freeze, Component Decomposition, Model Tier Cost Allocation, and 100% Offline Emergency Dispatch Kiosk Hardening.

Working directory: c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP
Integrity mode: development

## Requirements

### R1. Multi-Perspective Architectural Review
Evaluate the v1.0.0 Implementation Plan across Backend/DSP, Frontend/Kiosk Ergonomics, GIS/Master Properties, and MLOps/Whisper Training. Identify potential edge cases, architectural bottlenecks, and risk areas before code execution.

### R2. Model Tier & AI Credit Optimization Strategy
Assign every phase and task to the optimal model tier:
- **Flash-Lite / Flash (Low Effort)**: Deterministic test runners (backtest_parser.py, orphan scans), dead code pruning, terminology renames (Simulate -> Review), and batch test looping.
- **Flash (Medium/High Effort)**: Component decomposition into sub-folders (ReviewTable, AudioWaveformPlayer, VerificationSidebar), SQL schema definitions, and browser visual inspection.
- **Pro (High Reasoning)**: PA Golden Fingerprint FFT harmonic analysis, Street View atan2 vantage vector math, OSRM Lua profile road weighting, and LoRA attention adapter fine-tuning.

### R3. Zero-Online-Fallback & Offline Verification Guardrails
Validate that all runtime geocoding, emergency routing, and speech-to-text operations function 100% offline against local PostgreSQL and containerized OSRM without remote internet dependencies (except add-on Street View/Satellite PiPs).

## Acceptance Criteria

### Architectural Feasibility & Review Package
- [ ] Every phase (Phase 0 to Phase 5) is reviewed with actionable feedback from specialized engineering perspectives.
- [ ] A definitive model allocation matrix assigns each task to Flash-Lite, Flash, or Pro.
- [ ] Verification rubrics confirm zero online fallbacks and strict local data authority.
