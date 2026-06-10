# Coquitlam Dispatch Call Structure & Parsing

This document defines the exact template and structure used by the computerized dispatcher to announce incoming calls, and explains how the Python agent splits and segments this information.

---

## 🧭 Exact Dispatch Call Template

The dispatch system announces calls over the radio using a highly structured, repeatable format. The general structure of an announcement is:

```text
Coquitlam [Units]. Respond [Priority], [Incident Type], [Address]. Near [Cross Street 1] and [Cross Street 2], Use Talk Group [Channel] Coquitlam, Map Grid [Grid]
```

### Example Announcement
> *"Coquitlam Engine 2, Engine 3, Rescue 2. Respond Emergency, Alarm Activated - High Risk, 1189 Eastwood Street. Near Primrose Lane and Guildford Way, Use Talk Group 6 Coquitlam, Map Grid 84"*

---

## 🛠️ Segmented Parser Filters (Template-Aligned Segmentation)

The parser in [parser.py](file:///C:/Users/curti/Documents/GitHub/CFR-EVO-APP/agent/cfr_dispatch/parser.py) maps this template directly to separate data fields using anchor keywords:

| Segment Name | Sample Value | Anchor Keyword / Split logic |
| :--- | :--- | :--- |
| **Units** | `Engine 2, Engine 3, Rescue 2` | Precedes the `respond` keyword |
| **Priority** | `Emergency` | Follows `respond` (e.g. `respond emergency` / `respond routine`) |
| **Incident Type** | `Alarm Activated - High Risk` | Extracted via lookup matching against [call_types.txt](file:///C:/Users/curti/Documents/GitHub/CFR-EVO-APP/agent/data/vocabulary/call_types.txt) |
| **Address** | `1189 Eastwood Street` | Extracted from the text following the Incident Type, up to the `near` keyword |
| **Cross Streets** | `Primrose Lane and Guildford Way` | Captured between the `near` / `cross roads` and `use talk group` anchors |
| **Radio Channel** | `Talk Group 6 Coquitlam` | Extracted after the `use talk group` anchor |
| **Map Grid** | `84` | Captured after the `map grid` / `math grade` anchors |

---

## 🎙️ Common Transcription Phonetic Corrections

To ensure the template splits and segments correctly, the sanitizer automatically cleans up common audio-to-text homophones before parsing:

* **Coquitlam**: Maps `"coquina"`, `"colquitt loom"`, `"quick loma"` to `"coquitlam"`.
* **Quint**: Maps `"queens"` followed by a number (e.g., `"queens 5"`) to `"quint 5"` (avoiding street names like *Queens Road*).
* **Respond**: Maps `"respondents"`, `"responder"`, `"respawn"` to `"respond"` so that the priority splits line up correctly.
