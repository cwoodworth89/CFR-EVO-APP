---
name: e2e-dispatch-testing
description: Operational runbook and test harness for executing full-system and targeted dispatch tests, validating MQTT/Ntfy delivery, enforcing *TEST* safeguards, and cleaning up test artifacts.
---

# End-to-End Dispatch Testing & QA Harness

This skill defines procedures for executing simulated dispatch audio tests, distinguishing between full system tests and targeted component tests, and maintaining database/audio cleanliness.

---

## 1. Test Execution Modes & Command Matrix

| Test Objective | Command Syntax | MQTT Kiosk | Ntfy Phones | DB Persistence | Audio File Saved |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Full System Test** *(Station + Phones)* | `python backend/scripts/feed_recorded_call.py <wav_path> [tone]` | **ON** (`*TEST*`) | **ON** (`*TEST*`) | **YES** (`is_test=True`) | **NO** (In-memory only) |
| **Targeted Unit / DSP Test** | `python backend/scripts/feed_recorded_call.py <wav_path> --omit-mqtt --omit-ntfy --omit-db` | **OFF** | **OFF** | **OFF** | **NO** |
| **Silent Integration Test** *(DB only)* | `python backend/scripts/feed_recorded_call.py <wav_path> --omit-mqtt --omit-ntfy` | **OFF** | **OFF** | **YES** | **NO** |
| **Live Operational Replay** *(Caution)* | `python backend/scripts/feed_recorded_call.py <wav_path> --production` | **ON** | **ON** | **YES** | **NO** |
| **Automated Benchmark Suite** | `python backend/tests/run_test_suite.py` | **OFF** | **OFF** | **OFF** | **OFF** |

---

## 2. Standard Curated Test Audio Suite (`backend/tests/test_calls/`)

Use only verified line-in recordings from `backend/tests/test_calls/`:

* `structure_fire_1st_alarm.wav`: 1st Alarm Multi-Engine (`E1, E2, E4, R2, L1, C6` @ Westwood St & Gordon Ave, Grid 68)
* `mvi_engine_rescue.wav`: Standard MVI Assignment (`E1, R2` @ Panorama Dr & Johnson St, Grid 78)
* `vehicle_fire_port_mann_quint5.wav`: Major Vehicle Incident with Quint 5 (`E2, R2, Q5, C5` @ Port Mann Bridge, Grid 52)
* `alarm_high_risk_care_facility.wav`: Care Facility High Risk (`E1, E4, R2` @ 1131 Dufferin St, Grid 81)
* `gas_leak_pinetree_secondary.wav`: Commercial Hazmat (`E1` @ 3000 Pinewood Ave, Grid 85)
* `medical_cardiac_arrest_superstore.wav`: Medical Cardiac (`M1` @ 3000 Lougheed Hwy, Grid 68)
* `wildland_fire_smoldering.wav`: Wildland Smoldering (`L1` @ Westwood St & Lincoln Ave, Grid 82)

---

## 3. Remote Server Testing Protocol (Tailscale SSH)

When executing tests against the real server (`tcfire@100.95.146.94`):

```bash
# 1. Full system test with *TEST* broadcast to station and phones
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && XDG_RUNTIME_DIR=/run/user/1000 .venv/bin/python backend/scripts/feed_recorded_call.py /home/tcfire/CFR-EVO-APP/backend/tests/test_calls/structure_fire_1st_alarm.wav 'Structure Fire Tone'"

# 2. Targeted test (no MQTT / no phone push / no DB entry)
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && XDG_RUNTIME_DIR=/run/user/1000 .venv/bin/python backend/scripts/feed_recorded_call.py /home/tcfire/CFR-EVO-APP/backend/tests/test_calls/mvi_engine_rescue.wav 'Motor Vehicle Incident' --omit-mqtt --omit-ntfy --omit-db"
```

---

## 4. Post-Test Cleanup Protocol

Always clean up temporary test dispatches after full system test sessions:

```bash
# 1. Remove test records from PostgreSQL dispatches table
ssh tcfire@100.95.146.94 "docker exec cfr_postgres psql -U cfr_user -d cfr_dispatch -c \"DELETE FROM dispatches WHERE target->>'is_test' = 'true' OR dispatch_id LIKE 'DISP-TEST-%';\""

# 2. Verify latest operational call
ssh tcfire@100.95.146.94 "docker exec cfr_postgres psql -U cfr_user -d cfr_dispatch -c 'SELECT id, dispatch_id, incident_type, timestamp FROM dispatches ORDER BY id DESC LIMIT 3;'"
```
