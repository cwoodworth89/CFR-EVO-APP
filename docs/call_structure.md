# Coquitlam Dispatch Call Structure & Parsing

This document defines the exact template and structure used by the computerized dispatcher to announce incoming calls, and explains how the Python agent splits, segments, and validates this information.

---

## 🧭 Exact Dispatch Call Template

The dispatch system announces calls over the radio using a highly structured, repeatable format. The general structure of an announcement is:

```text
Coquitlam [Units]. Respond [Priority], [Incident Type], [Address] [Subaddress / Business]. Near [Cross Street 1] and [Cross Street 2], Use Talk Group [Channel] Coquitlam, Map Grid [Grid]
```

### Example Announcement
> *"Coquitlam Engine 2, Engine 3, Rescue 2. Respond Emergency, Alarm Activated - High Risk, 1189 Eastwood Street Unit 105. Near Primrose Lane and Guildford Way, Use Talk Group 10 Combined Response Coquitlam, Map Grid 84"*

---

## 🛠️ Segmented Parser Filters (Template-Aligned Segmentation)

The parser in [parser.py](../backend/cfr_dispatch/parser.py) maps this template directly to separate data fields using anchor keywords:

| Segment Name | Sample Value | Anchor Keyword / Split logic |
| :--- | :--- | :--- |
| **Units** | `Engine 2, Engine 3, Rescue 2` | Precedes the `respond` keyword |
| **Priority** | `Emergency` | Follows `respond` (e.g. `respond emergency` / `respond routine`) |
| **Incident Type** | `Alarm Activated - High Risk` | Extracted via lookup matching against [call_types.txt](../backend/data/vocabulary/call_types.txt) |
| **Address** | `1189 Eastwood Street` | Extracted from text following Incident Type up to `near` / `cross roads` |
| **Subaddress / Business** | `Unit 105` / `Save-on-Foods` | Extracted following main address (or preceding house numbers for businesses) before cross roads |
| **Cross Streets** | `Primrose Lane and Guildford Way` | Captured between `near` / `cross roads` and `use talk group` anchors |
| **Radio Channel** | `Talk Group 10 Combined Response` | Extracted after `use talk group` anchor, verified against [radio_channels.txt](../backend/data/vocabulary/radio_channels.txt) |
| **Map Grid** | `84` | Captured after `map grid` / `math grade` anchors |

---

## 🏢 Subaddress & Business Name Parsing

Subaddresses (unit numbers, apartment numbers, suite numbers) and business names are automatically parsed and separated:
- **Subaddress Extractor**: Identifies unit markers (`Unit`, `Apt`, `Suite`, `Room`, `Bldg`, `Bay`) or trailing unit digits following street suffixes (e.g., `1252 Town Centre Blvd 125`).
- **Business Name Extractor**: Detects leading business names preceding house numbers (e.g., `Save-on-Foods 1205 Pinetree Way`).
- **Geocoder Cleanliness**: The subaddress / business segment is isolated under `target.subaddress` and stripped from the primary address string before geocoding against Coquitlam GIS shapefiles.
- **Stage 3 Reconstruction**: The subaddress is automatically re-assembled into the reconstructed template text for high-fidelity review.

---

## 🏥 Riverview Hospital Station Overrides

For dispatches on the Riverview Hospital grounds referencing historic stations or wards (e.g., `Station 15`, `Station 37`, `Riverview Station 15`, `Brookside`, `Centrale`, `Crease Clinic`):
- The local geocoder in [geocoder.py](../services/gis/src/gis_service/geocoder.py) intercepts station patterns.
- Returns exact Riverview coordinates (`49.245830, -122.805330`) and labels the match as `"Station [Number], Riverview Hospital (2601 Lougheed Hwy)"`.

---

## 🎙️ Common Transcription Phonetic Corrections

To ensure the template splits and segments correctly, the sanitizer automatically cleans up common audio-to-text homophones before parsing:

* **Coquitlam**: Maps `"coquina"`, `"colquitt loom"`, `"quick loma"` to `"coquitlam"`.
* **Quint**: Maps `"queens"` followed by a number (e.g., `"queens 5"`) to `"quint 5"` (avoiding street names like *Queens Road*).
* **Respond**: Maps `"respondents"`, `"responder"`, `"respawn"` to `"respond"` so that the priority splits line up correctly.
* **Talk Group 10**: Maps `"Combined Response Coquitlam"` to `"Talk Group 10 Combined Response Coquitlam"`.

---

## 📡 Notification Push Payloads & Call Category Formats

The python agent pushes notification payloads to `ntfy.sh` to trigger instant audio playback and maps-navigation shortcuts on Android handsets. The push payload structure is tailored to the geocoded quality of the parsed location.

### 1. Known Good Address Category
- **Condition**: Exact parcel match found in Coquitlam shapefiles.
- **Ntfy Title**: `Dispatch: [Incident Type]` (e.g., *Dispatch: Medical*)
- **Ntfy Tags**: `fire_engine,rotating_light`
- **Click Action URL**: Launches Google Maps search with exact address (e.g., `https://www.google.com/maps/search/?api=1&query=3030+Gordon+Ave,+Coquitlam,+BC`).
- **Ntfy Body Text**:
  ```text
  📍 Address: 3030 Gordon Ave
  🚒 Units: E1, L1
  🗺️ Map Grid: 42
  📻 Channel: 10
  📝 Transcript: coquitlam engine 1...
  ```

### 2. Approximate / Unmapped Address Category
- **Condition**: Street name recognized, but specific house number is missing from the local GIS shapefiles.
- **Ntfy Title**: `Dispatch: [Incident Type]`
- **Ntfy Tags**: `fire_engine,rotating_light`
- **Click Action URL**: Uses parsed approximate address, letting Google Maps handle fuzzy geocoding (e.g., `https://www.google.com/maps/search/?api=1&query=3080+Gordon+Ave,+Coquitlam,+BC`).
- **Ntfy Body Text**:
  ```text
  📍 Address: 3080 Gordon Ave (Street Midpoint / Approx)
  🚒 Units: E1, E2
  🗺️ Map Grid: 42
  📻 Channel: 10
  📝 Transcript: coquitlam engine 1...
  ```

### 3. Strict Intersection Category
- **Condition**: Two street names connected by "and" / "at" / "&".
- **Ntfy Title**: `Dispatch: [Incident Type]`
- **Ntfy Tags**: `fire_engine,rotating_light`
- **Click Action URL**: Google Maps query of the intersection (e.g., `https://www.google.com/maps/search/?api=1&query=Gordon+Ave+%26+Christmas+Way,+Coquitlam,+BC`).
- **Ntfy Body Text**:
  ```text
  📍 Address: Gordon Ave & Christmas Way
  🚒 Units: E1, R1
  🗺️ Map Grid: 42
  📻 Channel: 10
  📝 Transcript: coquitlam engine 1...
  ```

### 4. Confidential / Sensitive Placeholder Category
- **Condition**: Dispatcher broadcasts generic confidential instructions (e.g., *"contact dispatch for location information"*).
- **Ntfy Title**: `Dispatch: Confidential`
- **Ntfy Tags**: `fire_engine,warning`
- **Click Action URL**: *(No URL sent to prevent mapping errors)*
- **Ntfy Body Text**:
  ```text
  📍 Address: Contact dispatch for location information
  🚒 Units: E1
  🗺️ Map Grid: 42
  📻 Channel: 10
  📝 Transcript: contact dispatch for location info...
  ```

### 5. Phase 2 Corrections / Updates
- **Condition**: Human reviewer submits verified corrections or Phase 2 completes processing.
- **Ntfy Title**: `[CORRECTION] Dispatch: [Incident Type]`
- **Ntfy Tags**: `fire_engine,repeat`
- **Click Action URL**: Direct coordinates/address search.
- **Ntfy Body Text**:
  ```text
  📍 Address: [Verified Address]
  🚒 Units: [Verified Units]
  🗺️ Map Grid: [Verified Grid]
  📻 Channel: [Verified Talk Group]
  📝 Transcript: Location/units updated in Phase 2 processing.
  ```

---

## 💾 Supabase Realtime Payload Schema

Updates pushed via Supabase Realtime use a standardized json object layout for the React frontend client:

*   **`live_calls` Table Schema**:
    *   `dispatch_id` (Text): Unique alphanumeric index (`DISP-[Year]-[HEX]`).
    *   `incident_type` (Text): Parsed or verified incident category.
    *   `responding_units` (Array): Array of active units (e.g., `["E1", "L1"]`).
    *   `raw_transcript` / `sanitized_transcript` (Text): Text representations.
    *   `audio_url` (Text): Direct Supabase storage link.
    *   `verify_location` (Boolean): Boolean flag. `true` triggers visual map warnings.
    *   `target` (JSONB): Structured geocoding parameters:
        ```json
        {
          "address": "3030 Gordon Ave",
          "subaddress": "Unit 204",
          "lat": 49.282138,
          "lng": -122.791240,
          "map_grid": "42",
          "radio_channel": "10",
          "tone_name": "Engine Tone"
        }
        ```
