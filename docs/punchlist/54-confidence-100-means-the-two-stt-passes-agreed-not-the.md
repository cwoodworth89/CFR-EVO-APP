# Punch list #54 — Confidence 100 means "the two STT passes agreed", not "the location is right"

| | |
|:--|:--|
| **Status** | SUPERSEDED |
| **Severity** | crew-visible |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L4017 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 54. Confidence 100 means "the two STT passes agreed", not "the location is right"
> **Status**: 🟡 **Superseded by operator ruling, 2026-08-30 — the confidence score is being
> scrapped entirely, not recalibrated.** Warnings move to the amber banner / flag model (§5).
> The measurement below stands as the reason, and as the baseline any replacement signal has to
> beat. Supersedes punch-list #32, which asked for recalibration.
>
> **Operator ruling (CLAUDE.md §6.3 tier 4 — the operator is the authority):** a single number
> conflating transcription agreement with location correctness is not fixable by choosing a
> better number. There will be **no numeric confidence shown to crews**. A location is either
> resolved, or it carries an explicit warning saying what is uncertain and why.
>
> This is the same conclusion the project already reached for response codes: an unparsed value
> is `NULL`, never a guess, and the honest unknown beats the plausible number (§6.1).
>
> Original finding follows. Operator hypothesis 2026-08-30, confirmed against 510 records the
> same day.

**The operator's question:** *"If Whisper fails to hear the right street name twice, and they
both agree with the misheard term, that scores 100%? Shouldn't the failure come at the geocoder
level?"*

Yes to the first. And the geocoder **does** already fail correctly — Phase 2 overwrites it.

**Mechanism.** Phase 2's only cross-check is string equality on the address:

```python
addresses_match = (p1_addr == p2_addr) and (p1_addr != "")
...
update_payload = {"verify_location": False, "confidence_score": 100.0, ...}
```

Agreement between two Whisper passes is a statement about **transcription consistency**. It is
written into `confidence_score`, which the kiosk presents as confidence in the **location**. A
street misheard the same way twice agrees with itself perfectly.

The geocoder had already said otherwise. It sets `resolution_note`, returns its own confidence,
and sets `is_ambiguous` for a non-exact match. Phase 2 discards all three and stamps `100.0`.

**Measured, `public.dispatches`, 510 records with a target:**

| | |
|:--|--:|
| Carrying `confidence_score = 100` | 389 |
| …operator later corrected the address | **55 (14%)** |
| …rated `FAILED` | 15 |
| …carrying a `resolution_note` — the geocoder saying it could not resolve | **11** |

Four of those eleven, verbatim:

| Dispatch | Stored address | What the geocoder said | Rating |
|:--|:--|:--|:--|
| `E6522C` | Lougheed Hwy & Westwood St | *"'Westwood St And Loheed Hwy' does not match any intersection in the road network"* | OPERATIONAL |
| `298EC2` | Dunkirk Ave & Gabriola Dr | *"'Dunkirk Avenue And Gabriela Dr' does not match any intersection in the road network"* | PENDING |
| `B19172` | Parkway Blvd | *"19999 Parkway Blvd could not be placed on this street. Showing the midpoint"* | **FAILED** |
| `C6165A` | 3062 Lougheed Hwy | *"has no parcel in City of Coquitlam records. Position estimated along the road"* | OPERATIONAL |

`E6522C` is exactly the case the operator described: **"Loheed"** was misheard consistently in
both rounds, the rounds agreed, and 100 was written over the geocoder's explicit statement that
the junction does not exist.

**A second finding, found while measuring this.** `is_ambiguous` is **never persisted** —
**0 of 510** records have the key in `target`, though `requested_address` reaches 12. The
geocoder computes ambiguity and it is dropped before storage. The CLAUDE.md §5 candidate-selector
banner keys off `is_ambiguous`, so it cannot fire from a stored record; whether it works on the
live MQTT payload is unverified.

#### The shape of a fix — not implemented, needs a decision

The principle: **round agreement should raise trust in the transcript, never in the location.**
They are different claims and only one of them is being measured.

* Phase 2 should **not raise** `confidence_score` above what the geocoder itself asserted.
  Carry the geocoder's number through; let agreement confirm the *transcript*.
* Where `resolution_note` is set, confidence must reflect the approximation — a location the
  geocoder says it could not place is not a 100 under any reading (§6.1).
* Persist `is_ambiguous` so the operator-facing selector can fire.
* Consider a separate, honestly-named field for what Phase 2 actually measured — round
  agreement — rather than overloading one number with two meanings.

**Do not simply lower the number to something invented.** Punch-list #32 records that confidence
is uncalibrated in both directions: score 100 was wrong on 8% of reviewed calls while the 81–89
band was flawless. Any replacement needs to be checked against the ratings corpus, not chosen
because it looks more cautious.

---
