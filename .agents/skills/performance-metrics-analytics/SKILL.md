---
name: performance-metrics-analytics
description: Operational runbook and architectural specifications for tracking, analyzing, and visualizing CFR EVO performance metrics, pipeline latency, STT Word Error Rate (WER), and executive management business KPIs.
---

# Performance Metrics & Operational Analytics Engine

This skill governs the collection, database aggregation, statistical modeling, and visual presentation of both **Executive Business Intelligence** and **Technical Pipeline Diagnostics** in CFR EVO.

---

## 1. Core Metrics Framework

### A. Executive & Management KPIs (The Business Case)
1. **Time-to-First-Visual-Alert (Turnout Lead Time)**:
   - Measures elapsed time (seconds) from radio broadcast tone drop to high-visibility bay kiosk render.
   - Benchmarks estimated seconds saved per callout vs. legacy thermal printer standby and paper lookup times (~45–90s reduction).
2. **End-to-End Autonomous Parsing Accuracy Rate**:
   - Percentage of calls where address, emergency zone, responding units, and call priority are accurately extracted without Human-in-the-Loop (HITL) correction.
3. **Station & Apparatus Response Workload**:
   - Dispatches by Fire Hall (Hall 1: Town Centre, Hall 2: Mariner, Hall 3: Austin Heights, Hall 4: Burke Mountain).
   - Volume by apparatus type (`Engine`, `Ladder`, `Rescue`, `Quint 5`, `Chief`, `Medic`), call priority, and peak response hours.
4. **Cost Avoidance & 100% Offline Uptime**:
   - Cumulative cost savings vs. commercial cloud CAD / alerting subscription services ($0/mo recurring operational expense).
   - System uptime and offline survival availability across station networks.

### B. Technical Pipeline Diagnostics (Engineering & MLOps Health)
1. **Sub-Stage Pipeline Latency Breakdown (Milliseconds)**:
   - Stage 1: Audio Ingestion & DSP Bandpass Filtering (`t_dsp`)
   - Stage 2: Faster-Whisper Local STT Transcription (`t_stt`)
   - Stage 3: Municipal GIS Address Parsing & Parcel Matching (`t_gis`)
   - Stage 4: PostgreSQL Persistence & Mosquitto MQTT Broadcast (`t_publish`)
2. **Speech-to-Text Benchmark & Model Progression**:
   - Historical Word Error Rate (WER) and Match Error Rate (MER) tracked across models (`base`, fine-tuned models, vocabulary injections).
3. **Human-in-the-Loop (HITL) Feedback & Correction Rate**:
   - Frequency and diff analysis of field reviews (address edits, unit adjustments, incident classification updates).

---

## 2. Database Schema & Aggregation Architecture

### A. Granular Per-Call Telemetry Storage
* Captured inside PostgreSQL table `live_calls` and `evaluation_history`:
  - `metrics` column (JSONB):
    ```json
    {
      "latency_ms": {
        "dsp": 42.5,
        "stt": 850.2,
        "gis": 28.1,
        "db_mqtt": 14.3,
        "total": 935.1
      },
      "stt_confidence": 0.94,
      "gis_match_type": "EXACT_PARCEL",
      "time_to_kiosk_sec": 1.2
    }
    ```

### B. SQL Aggregation Views
* Fast analytical queries for time-windowed rollups (Last 24 Hours, 7 Days, 30 Days, 90 Days, All-Time):
  - Average latency by stage
  - Accuracy & verification percentage
  - Hall call distribution

---

## 3. Frontend Visualization & Reporting

1. **In-App Performance Analytics HUD (`frontend/src/components/admin/SystemMetricsPanel.jsx`)**:
   - Interactive date range selectors (7D, 30D, 90D, All).
   - Turnout time impact gauges, call volume breakdowns, and hall utilization charts.
2. **Executive Presentation Export**:
   - One-click export of executive summary reports (Markdown/PDF) formatted specifically for Chiefs, Station Captains, and City Management.
3. **Live Latency Waterfall & MLOps Curve**:
   - Real-time visual waterfall showing millisecond sub-stage latency for recent dispatches.
