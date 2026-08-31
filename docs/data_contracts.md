# Canonical Data Contracts & Payloads

> [!CAUTION]
> **Stale 2026-08-30. This file calls itself "the single source of truth" and is not.**
> Last substantive update 2026-08-08. It still documents `confidence_score`, which was
> **retired** and replaced with named review flags (punch-list **#45b**, closed 2026-08-30) —
> the whole point of that change being that a single number conflated "the two STT passes
> agreed" with "the location is right" (**#54**).
>
> Other fields have moved since: the operator-verified fields were promoted out of `target`
> JSON into columns (`bfc6bd0`), and numeric response codes were deleted rather than renamed.
>
> **The schema is the contract.** Read the migrations under `backend/migrations/` and the
> models in `backend/api/`. Treat every payload below as unverified until checked against
> them.

This document serves as the **single source of truth** for all dispatch data structures, database schemas, REST API contracts, and real-time MQTT message payloads across **CFR EVO**.

---

## 1. Primary Dispatch Object Contract (Option 2 Polygon Standard)

All backend pipeline stages, database records, MQTT broadcasts, and frontend state conform to this structure:

```json
{
  "dispatch_id": "DISP-2026-1793D9",
  "incident_type": "Structure Fire",
  "responding_units": ["E1", "L1", "R1"],
  "timestamp": "2026-08-08T18:14:02.123456-07:00",
  "raw_transcript": "coquitlam Engine one ladder one rescue one respond emergency structure fire at 2648 sandstone crescent map grid one eighteen",
  "sanitized_transcript": "coquitlam engine 1 ladder 1 rescue 1 respond emergency structure fire at 2648 sandstone crescent map grid 118",
  "verified_transcript": null,
  "confidence_score": 100.0,
  "verify_location": false,
  "audio_url": "/api/audio/DISP-2026-1793D9.wav",
  "audio_duration": 28.4,
  "target": {
    "address": "2648 Sandstone Cres",
    "subaddress": null,
    "intersection": null,
    "lat": 49.297236,
    "lng": -122.818381,
    "rings": [
      [
        [-122.818730, 49.297308],
        [-122.818648, 49.297350],
        [-122.818508, 49.297423],
        [-122.818420, 49.297425],
        [-122.818018, 49.297236],
        [-122.818281, 49.297050],
        [-122.818353, 49.296999],
        [-122.818730, 49.297308]
      ]
    ],
    "map_grid": "118",
    "radio_channel": "Tac 1",
    "tone_name": "Engine Tone, Rescue Tone",
    "captured_tones": ["Engine Tone", "Rescue Tone"]
  },
  "feedback_submitted": false,
  "verified_address": null,
  "feedback_notes": null
}
```

---

## 2. Field Definitions & Types

| Field | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| **`dispatch_id`** | `String` | No | Unique ID formatted as `DISP-YYYY-HEX6` (e.g. `DISP-2026-1793D9`). |
| **`incident_type`** | `String` | No | Standard incident category (e.g. `Structure Fire`, `Medical Aid`, `Vehicle Fire`). |
| **`responding_units`** | `List[String]` | No | Abbreviated unit codes (e.g. `["E1", "L1", "Q5"]`). |
| **`timestamp`** | `ISO8601 String`| No | Local timestamp with timezone offset (`YYYY-MM-DDTHH:MM:SS-07:00`). |
| **`confidence_score`** | `Float` | No | Overall confidence percentage (`0.0` to `100.0`). |
| **`verify_location`** | `Boolean` | No | Flag set to `true` when confidence is `<90%` or geocoding failed. |
| **`target.address`** | `String` | No | Cleaned, normalized street address. |
| **`target.lat`** | `Float` | Yes | WGS84 Latitude coordinate (`None` if geocoding failed). |
| **`target.lng`** | `Float` | Yes | WGS84 Longitude coordinate (`None` if geocoding failed). |
| **`target.rings`** | `List[List[List[Float]]]` | No | GeoJSON-compatible parcel polygon coordinates `[[ [lng, lat], ... ]]`. |
| **`target.map_grid`** | `String` | Yes | 1..134 Emergency Response Zone grid number. |
| **`target.radio_channel`**| `String` | Yes | Tactical radio channel (e.g. `Tac 1`, `Tac 2`). |
| **`target.captured_tones`**| `List[String]` | Yes | Array of spotted apparatus tone names. |

---

## 3. PostgreSQL Database Schema (`dispatches` Table)

```sql
CREATE TABLE IF NOT EXISTS dispatches (
    id SERIAL PRIMARY KEY,
    dispatch_id VARCHAR(64) UNIQUE NOT NULL,
    incident_type VARCHAR(128) NOT NULL,
    responding_units JSONB DEFAULT '[]'::jsonb,
    timestamp TIMESTAMPTZ NOT NULL,
    raw_transcript TEXT,
    sanitized_transcript TEXT,
    verified_transcript TEXT,
    confidence_score REAL DEFAULT 0.0,
    verify_location BOOLEAN DEFAULT FALSE,
    audio_url VARCHAR(512),
    audio_duration REAL DEFAULT 0.0,
    target JSONB NOT NULL,
    feedback_submitted BOOLEAN DEFAULT FALSE,
    verified_address VARCHAR(256),
    feedback_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dispatches_dispatch_id ON dispatches(dispatch_id);
CREATE INDEX IF NOT EXISTS idx_dispatches_created_at ON dispatches(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dispatches_verify_location ON dispatches(verify_location);
```

---

## 4. Mosquitto MQTT Real-Time Broadcast Contract

* **Broker**: Mosquitto (`localhost:1883` TCP / `ws://localhost:9001` WebSockets)
* **Topic**: `cfr/dispatches`

### Message Envelope:
```json
{
  "eventType": "INSERT", 
  "new": { ...dispatch_payload... }
}
```
* **Event Types**:
  * `INSERT`: Broadcast by Phase 1 (<15s) or single-phase dispatch.
  * `UPDATE`: Broadcast by Phase 2 (verified / corrected) or when HITL feedback is submitted.
  * `DELETE`: Broadcast if a test dispatch is purged.

---

## 5. HITL Feedback API Contract

### Request: `POST /api/dispatches/{dispatch_id}/feedback`
```json
{
  "verified_address": "2648 Sandstone Cres",
  "verified_transcript": "coquitlam engine 1 ladder 1 respond structure fire 2648 sandstone crescent map grid 118",
  "feedback_notes": "Dispatcher spoke fast; system originally missed unit R1."
}
```
* **Effect**: Updates PostgreSQL record (`feedback_submitted = true`, `verify_location = false`, `confidence_score = 100.0`), re-broadcasts MQTT `UPDATE` event, and promotes the corrected street to the Whisper STT dynamic bias cache.
