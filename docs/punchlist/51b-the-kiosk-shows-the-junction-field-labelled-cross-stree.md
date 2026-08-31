# Punch list #51b — The kiosk shows the junction field labelled "cross streets", and never reads the real one

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3744 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 51. The kiosk shows the junction field labelled "cross streets", and never reads the real one
> **Status**: 🔴 **Open — genuine display defect, but NOT the cause of the ratings regression.**
> Found 2026-08-29 while auditing XStreets representation end to end.
>
> ⚠️ **Correction, same day.** This entry first claimed to be the cause of the PERFECT-rating
> collapse. It is not, and the error is recorded rather than overwritten. The operator rates
> **the reconstructed transcript in the review panel against the audio** — not the kiosk
> dispatch display. The regression is the transcript, tracked below and fixed in `703173c`;
> the kiosk display gap described in this entry is real but separate and was never what the
> ratings measured.

#### The regression was the transcript, not this

Both symptoms share one upstream cause — the pipeline stopped overloading `intersection` with
the near roads, which was correct — but they surface in different places and only the transcript
one drove the ratings.

`reconstruct_template_transcript` reaches the near clause two ways: `cross_street_1/2`, or
failing that `elif dispatch.intersection`. While `intersection` was overloaded, the second path
fired and the clause appeared. When that stopped, nothing replaced it, because **both
`DispatchData` copies in `phase2.py` omitted `cross_street_1/2`** — and Phase 2's
`sanitized_transcript` overwrites the one `payload_builder` built correctly.

Measured on house-number calls where the dispatcher announced "near", against the operator's own
rating:

| Week | Calls announcing "near" | Clause kept in transcript | **PERFECT** |
|:--|--:|--:|--:|
| Jul 20 | 56 | 96.4% | 57.1% |
| Jul 27 | 66 | 59.1% | 46.8% |
| Aug 3 | 42 | 85.7% | 62.7% |
| Aug 10 | 52 | **96.2%** | **65.3%** |
| Aug 17 | 58 | 55.2% | 38.4% |
| Aug 24 | 44 | **2.3%** | **16.1%** |

The two columns move together week for week, including the Jul 27 dip in both. **Fixed in
`703173c`**, verified against the real `DISP-2026-9E8BF5` payload:

```
before: ...2653 sandstone crescent, use talk group 10 combined response coquitlam, map grid 73
after:  ...2653 sandstone crescent, near sandstown court and nunes creek drive, use talk
        group 10 combined response coquitlam, map grid 73
```

Not yet deployed to the kiosk at time of writing; backend changes need `cfr-agent` restarted.

#### The display gap this entry is actually about

The same upstream change moved the near roads out of `intersection` on the kiosk path too. The
kiosk reads `intersection` and nothing else, so it stopped showing them there as well — a real
defect, just not the one being rated:

| Week | House-address calls announcing "near" | `intersection` overloaded with them | Carried in `cross_streets` |
|:--|--:|--:|--:|
| Jul 20 | 56 | 56 | 0 |
| Aug 3 | 42 | 42 | 0 |
| Aug 10 | 52 | **52** | 0 |
| Aug 17 | 58 | 31 | 1 |
| Aug 24 | 44 | **0** | 43 |

**The near roads were always displayed through `intersection`.** Until mid-August the pipeline
overloaded that field with them, and the kiosk reads `intersection` — so they appeared, and calls
rated PERFECT. The 2026-08-21 geocoder work **correctly** stopped overloading it, and
`cross_streets` **correctly** began carrying them. Both changes were right. But nothing taught the
kiosk to read the new field, so the data moved into a column the UI has never mapped and vanished
from the display.

The migration and the ratings collapse track each other exactly, in opposite directions. This is
the display half of punch-list #35: that entry fixed the *pipeline* dropping `cross_streets`; the
*frontend* was never updated to read them.

**No dispatch data is lost today** — `target.cross_streets` is populated on 43 of 44 recent
qualifying calls. The kiosk simply does not render it, and the operator correctly reads that as
the system having got worse.

> **On attribution.** These calls span many development sessions and deploys, so the week
> boundaries above track **when code reached the kiosk**, not when it was committed. The claim
> here is only that the field migration and the ratings collapse coincide — which the per-call
> counts show directly, independent of any commit. Nothing here says a change was wrong; the two
> pipeline changes were both improvements, and the defect is the frontend that was never brought
> along.

**Two different things share one operator-facing label.**
[`config/models.py:14-16`](../backend/cfr_dispatch/config/models.py:14) draws the distinction
deliberately, and the parser honours it
([`announcement.py:173-175`](../backend/cfr_dispatch/parser/announcement.py:173) makes them
mutually exclusive):

* `intersection` — **the address itself is a junction** (`Gordon Ave and Christmas Way`)
* `cross_street_1` / `_2` — **a house address plus nearby streets** (`2653 Sandstown Crescent,
  near Sandstown Court & Nunes Creek Drive`)

Operationally these are not the same. The first is where the crew is going; the second is how
they confirm they are on the right block. The printed run sheet labels the second "XStreets:",
which is why that is the name used through the codebase
([`geocoder.py:139-152`](../services/gis/src/gis_service/geocoder.py:139)).

**What the kiosk does.** [`dispatchModel.js:56`](../frontend/src/utils/dispatchModel.js:56) maps
`intersection` and nothing else — **`cross_streets` is not in the frontend model at all** and no
component reads it. Then
[`ActiveAlertBanner.jsx:11`](../frontend/src/components/hud/ActiveAlertBanner.jsx:11) labels
`intersection` to the operator as **`'cross streets'`**.

So the crew sees the *junction* field under the *XStreets* label, while the actual announced
cross streets travel all the way to the kiosk in `target.cross_streets` and are dropped at
render. This is the same defect as the transcript one fixed in `phase2.py` — carried data
discarded at the last step — but on the display path.

**Measured, kiosk database 2026-08-29:**

| | |
|:--|--:|
| Dispatches with `target.cross_streets` populated | 71 |
| Ever rendered on the kiosk | **0** |
| Recent qualifying calls carrying them | 43 / 44 |
| `target.cross_streets` stored as a JSON array | 71 / 71 |
| `target.intersection` using ` and ` | 222 / 222 |

**Storage is not the problem.** The parser keeps two fields, `public.intersections` keeps two
columns, and `target.cross_streets` is a proper array on every record that has one. The value is
only flattened into a string for `target.intersection` and for the reconstructed transcript.

#### What the UX needs

1. **Add `cross_streets` to `dispatchModel.js`** so it reaches components at all.
2. **Two distinct slots on the alert banner** — the junction (or civic address) as the
   destination, and XStreets as a separate confirmation line. Do not merge them: a house-address
   call has both, and they mean different things.
3. **Relabel** `intersection` in `UPDATE_FIELD_LABELS` to something that is not "cross streets"
   — it is the incident location when the call is a junction.
4. **Show nothing rather than something wrong** when `cross_streets` is empty (§6.1). Most calls
   have no XStreets and the slot should simply be absent.

**Related and already fixed:** the same fields were omitted from the `DispatchData` copies in
`phase2.py`, which dropped them from the reconstructed transcript. Fixed 2026-08-29; this entry
is the remaining display half.


---
