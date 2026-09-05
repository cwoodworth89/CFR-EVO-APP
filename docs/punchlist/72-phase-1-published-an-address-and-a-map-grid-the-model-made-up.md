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

### Measured on the round-1 holdout, 2026-09-05 (`tools/harness_phase1.py`, `e0d4ded`)

44 recordings replayed in the listener's own chunks (10 s, then every 3 s) through the live STT
settings, the parser and the real completion check; 37 of the 44 have a verified grid.

| | Published in phase 1 | Median at | Grid right | Grid wrong | Address exact / wrong street |
|:--|--:|--:|--:|--:|:--|
| **Today (baseline)** | 44 of 44 | 19 s | 10 | **26** | 32 / 4 |
| A, location gate | 44 | 19 s | 9 | 24 | 32 / 2, 5 withheld |
| B, two chunks agree | 38 | 25 s | 24 | 8 | 30 / 3 |
| C, talk group in front | 44 | 19 s | 9 | 22 | 32 / 4, 7 withheld |

**Seven grids in ten are wrong when phase 1 publishes.** Nineteen of the 26 are the number 68,
the model's habitual completion; the rest are other completions (38, 82, 96, 81, 55). The
mechanism is structural: the check requires a grid, phase 1 passes at 16-19 s, and the
dispatcher reaches the grid at 25-35 s, so the grid in the chunk is the model's whenever the
check fires. Phase 2 corrects it about a minute later; the kiosk shows the wrong zone until then.

The address is a different story: it is spoken early, and 32 of 44 are exact at the baseline
chunk. Rule A removes two of the four wrong streets and the one bare street by withholding five
locations, which is what the Tier 1 card is for.

Rule B is better than the baseline and not good enough: eight wrong grids survive, because a
completion that has settled ("map grid 68" three chunks running on DISP-2026-3E1426) is as
stable as speech. Rule C is useless: the model completes the talk-group clause too.

### What follows

No rule on the transcript text can tell a settled completion from speech. Two honest options
remain, and the operator's rule decides between them:

1. **Phase 1 publishes no map grid.** Units, incident and the address (behind rule A) go out
   at 16-19 s as today; the zone appears with phase 2, about a minute later. Zero fabricated
   grids by construction. The grid must also stop being passed to the geocoder's street
   narrowing in phase 1, where a completed grid can pick the wrong street.
2. **Word timestamps.** faster-whisper can return per-word times; a completion's words are
   expected to pile up at the end of the audio while spoken words spread over it. Untested;
   a hypothesis for the simulator, not a plan.

Option 1 is a small change in `phase1.py` and `payload_builder.py`, measurable with this tool
and reversible. The full-corpus run of the simulator is in `evaluation_history` for the record.

### Related

#70 (the restart that stopped phase 2), #63 (the same completion behaviour in pauses),
#12 (the decision to label a fallback pin rather than suppress it, which is what put the
Coquitlam Ave centroid on the map for a structure fire; the operator's rule above reopens
that question for phase 1).
