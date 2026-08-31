# Punch list #35b — "Near roads" stopped being recorded on 2026-08-21 — Phase 2 rebuilds `target` and drops `cross_streets`

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🔁 Batch follow-up, 2026-08-23 (operator screenshots + kiosk probes) |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2479 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 35. "Near roads" stopped being recorded on 2026-08-21 — Phase 2 rebuilds `target` and drops `cross_streets`
> **Status**: 🔴 **Open — live regression, found 2026-08-23.** Reported by the operator
> ("we've seemed to have dropped recording near roads completely") and **confirmed** against
> the kiosk database and the working tree. Root cause identified; no fix applied.

#### The regression is real and dated

| Date | Calls | Said "near" | `intersection` recorded |
|:--|--:|--:|--:|
| 2026-08-18 | 9 | 9 | 9 |
| 2026-08-19 | 8 | 7 | 7 |
| 2026-08-20 | 10 | 9 | **9** |
| **2026-08-21** | 10 | 6 | **1** |
| 2026-08-22 | 19 | 16 | **3** |
| 2026-08-23 | 13 | 12 | **1** |

The operator's own HITL notes track the changeover precisely: 2026-08-20 reads
*"Spelling mistakes for near roads"* and *"Misspelled one of the near roads"* — captured, just
misspelled. From 2026-08-21 the notes read *"Missed near roads"*.

#### It is NOT a parser failure

The parser still extracts the near roads correctly. Replaying `DISP-2026-ABD874` (2026-08-23)
through current code:

```
addr='3098 Guildford Quay'  cross_street_1='Eastwood Street'  cross_street_2='Pipeline Road Rd'
```

`build_dispatch_payload` also does the right thing, writing them at
[`payload_builder.py:203`](../../backend/cfr_dispatch/pipeline/payload_builder.py):

```python
target_cross_streets = [s for s in [cross_street_1, cross_street_2] if s]
...
"cross_streets": target_cross_streets
```

#### Root cause: Phase 2 rebuilds `target` from a hand-picked subset

[`phase2.py:190`](../../backend/cfr_dispatch/pipeline/phase2.py) and again at `:272` construct a
**new** `target_payload` rather than updating the existing one, then PATCH it over the record:

```python
target_payload = {
    "address": p1_address, "lat": ..., "lng": ..., "rings": ...,
    "map_grid": p2_grid, "radio_channel": p2_channel,
}
if p1_target.get("subaddress"):   target_payload["subaddress"] = ...
if p1_target.get("tone_name"):    target_payload["tone_name"] = ...
if p1_target.get("intersection"): target_payload["intersection"] = ...
```

`cross_streets` is not on the carry-forward list, so the PATCH **destroys** whatever Phase 1
wrote. Confirmed against stored records — the surviving key set matches this dict exactly:

```
address, lat, lng, map_grid, radio_channel, rings, subaddress, tone_name
```

`routing_metrics`, `location_type`, `resolution_note` and `requested_address` are lost the same
way. Only **4** dispatches in the entire corpus have ever carried a `cross_streets` key, and
only **1** has a non-empty one.

#### Why it surfaced on 2026-08-21 and not earlier

Two changes had to line up:

1. **Before 2026-08-21** the near roads rode in the `intersection` field, which *is* on the
   carry-forward list, so they survived — semantically wrong but functional:
   ```
   addr='1535 Parkway Blvd'  intersection='Salal Cresson and Sunridge'
   addr='2968 Glen Dr'       intersection='Pacific Street and The High St'
   ```
2. **On 2026-08-21** the geocoder work correctly stopped overloading `intersection` for civic
   addresses. `intersection` now means what it says — set only when the location genuinely
   *is* a junction (`'Barnet Hwy & Lougheed Hwy'`).

That fix was right. It exposed a latent defect: the field that *should* carry near roads was
already being thrown away, and nothing noticed because the wrong field was masking it.

**This is the shape worth remembering.** A correct fix in one module surfaced silent data loss
in another. The regression is not in the 08-21 change; it is in the Phase 2 rebuild, which has
been lossy since `cross_streets` was introduced (`0ec3061`, 2026-08-20).

#### Suggested fix, not applied

Merge into the existing target rather than replacing it — `{**p1_target, **updates}` — so a
field added to Phase 1 is not silently dropped by Phase 2. An explicit allowlist that must be
edited every time a field is added is the mechanism that produced this defect.

Operationally, near roads are how crews confirm they are on the right block, and the two-tier
warning of CLAUDE.md §5 does not cover a *silently missing* corroboration field.

---

---

## 35b (closed). The field was renamed, and the mechanism that dropped it was fixed

> **Status**: ✅ **Closed 2026-08-31.** Operator ruling: the XStreet rename made "near roads"
> obsolete. Verified against the running database rather than closed on the ruling alone
> (§6.6).

**Two things had to be true, and both are.**

**1. `cross_streets` is superseded, not broken.** It became `x_street_1` / `x_street_2` in the
XStreet rename. The legacy key appears on **zero** dispatches in the last seven days — it is
gone, not empty.

**2. The lossy Phase 2 rebuild is fixed.** Both construction sites in `phase2.py` now spread
the Phase 1 target first, which is exactly the merge this item recommended and did not apply:

```python
target_payload = {
    **p1_target,          # merge, not rebuild
    "address": p1_address,
    ...
}
```

That matters beyond this item. The same allowlist was also dropping `routing_metrics`,
`location_type`, `resolution_note` and `requested_address`. `resolution_note` is the field
**#12** was closed on today, so had the rebuild still been lossy that closure would have been
wrong. It survives — measured, not assumed.

**Recording is healthy.** `x_street_1` is now populated on *more* calls than say "near",
because XStreets come from the CAD announcement structure rather than that one word:

| Day | Calls | Said "near" | `x_street_1` | legacy `cross_streets` |
|:--|--:|--:|--:|--:|
| 2026-08-31 | 11 | 5 | **9** | 0 |
| 2026-08-30 | 11 | 6 | **9** | 0 |
| 2026-08-29 | 13 | 3 | **10** | 0 |
| 2026-08-28 | 12 | 6 | **9** | 0 |
| 2026-08-27 | 13 | 4 | **7** | 0 |

Against the regression this item recorded — **1 of 10** on 2026-08-21 and **1 of 13** on
2026-08-23.

**The lesson stays worth keeping**, and it is why the merge matters more than the rename: a
correct fix in the geocoder surfaced silent data loss in Phase 2 that had existed since
`cross_streets` was introduced. An explicit allowlist that must be edited every time a field
is added is the mechanism that produced the defect; a merge cannot fail the same way.
