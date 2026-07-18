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
