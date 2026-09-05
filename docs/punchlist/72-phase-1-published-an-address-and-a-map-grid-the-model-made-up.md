# Punch list #72 — Phase 1 published an address and a map grid the model made up to finish a cut chunk

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🎙️ Dispatch Pipeline |
| **Blocks** | 0 |
| **Origin** | DISP-2026-33D8C2, the 2026-09-05 11:41 structure fire (#70); the operator asked which fields were heard and which were guesses |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 72. The completion trigger fired on the model's own "map grid 68", 23 seconds in

> **Status**: 🔴 **Open — the operator's rule is stated: unknown beats a guess.** Crew-visible: a
> structure fire went to the kiosk with a pin, a grid and six ETAs, none of which came from
> the broadcast.

### What the audio contained, and what the kiosk showed

Phase 1 transcribes the capture in growing chunks (10 s, 13 s, 16 s …) and publishes a
preliminary payload as soon as `is_round_1_complete_check` passes. At 11:41:40, 23 seconds
after the tones, the chunk read:

```
coquitlam engine 1 engine 4 engine 2 rescue 2 quint 5 car 8 respond emergency structure fire
166 coquitlam map grid 68
```

The model in service was fine-tuned on transcripts that all end in *"coquitlam map grid N"*,
so when a chunk ends mid-sentence it finishes the sentence. The check found units, a call
type and a grid between 1 and 134, and published. Field by field:

| Field on the kiosk | Value | Source |
|:--|:--|:--|
| Tones | Chief Tone | measured (DSP) |
| Units | E1 E4 E2 R2 Q5 C8 | heard, in the first 23 s |
| Response | emergency | heard |
| Incident | Structure Fire | heard |
| House number | 166 | **the model's completion; no evidence it was spoken** |
| Map grid | 68 | **the model's completion; it is also what satisfied the trigger** |
| Address | Coquitlam (street centroid of Coquitlam Ave) | **the geocoder's fallback on "166 Coquitlam"**, labelled with the approximate banner |
| Coordinates, six routes and ETAs | 49.2501, −122.7992; 7 to 11 min | **derived from that centroid** |
| Talk group, near roads | unknown | correctly null; flagged NO_TALK_GROUP |

Phase 2, which would have replaced all of it from the full recording, never ran: the agent
was restarted at 11:42:07 (#70). On any other day it would have corrected the payload
about a minute later; the crew would still have seen the guess first.

### The rule, from the operator

*"I'd rather have unknown than guesses."* A phase-1 payload may carry what was heard and
must show the Tier 1 card for what was not.

### Two ways to make phase 1 honour it, to be measured before either is built

1. **Template order.** The announcement always puts the address between the incident type
   and the grid (`docs/call_structure.md`). A chunk whose text goes from the incident type
   to *"coquitlam map grid"* with nothing that parses as a civic address or an intersection
   in between has not reached the address yet; the grid in it is a completion. Do not
   publish a location or a grid from it.
2. **Stability across chunks.** Real speech persists from one chunk to the next; the
   model's completions change. Publish an address or a grid only when two consecutive
   chunks agree on it.

The measurement, before choosing: replay every recording in the corpus truncated at 20, 25
and 30 seconds through phase 1 and count how often the trigger fires with a grid or an
address that is not in the verified transcript. `tools/harness_chain.py` has no truncation
option yet; that is the first piece of work.

### Related

#70 (the restart that stopped phase 2), #63 (the same completion behaviour in pauses),
#12 (the decision to label a fallback pin rather than suppress it, which is what put the
Coquitlam Ave centroid on the map for a structure fire; the operator's rule above reopens
that question for phase 1).
