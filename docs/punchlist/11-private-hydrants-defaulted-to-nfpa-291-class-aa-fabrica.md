# Punch list #11 — Private hydrants defaulted to NFPA 291 class AA — fabricated flow rating

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🚰 Hydrant Data |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L499 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 11. Private hydrants defaulted to NFPA 291 class AA — fabricated flow rating
> **Status**: ✅ **Closed 2026-08-21 — fixed, re-synced and verified end to end**
> (commits `7b684eb`, `4122628`). All three required steps were completed and each was
> checked independently:
>
> | Required step | Verification | Result |
> |:--|:--|:--|
> | 1. Remove the `or "AA"` default | `sync_hydrants.py:77` | now `"flowClass": attribs.get("flow_class")` ✅ |
> | 2. Re-sync — a code fix alone changes nothing | `public.hydrants` on the kiosk | **853 of 3,390** rows carry `flow_class IS NULL` ✅ |
> | 3. Explicit unknown rendering | hydrant layer | renders `⚠️ UNRATED`, distinct from all four NFPA colours ✅ |
>
> Step 2 is the one that mattered and it is the one that is easy to skip: the fabricated
> values lived in cached data, not in code. **853 unrated hydrants** is the direct
> counterpart of the 462 + 68 + 9 + 8 = 547 non-OPERATING AA rows plus the OPERATING
> unrated remainder — they now read as unknown instead of as the best available supply.
>
> The stale `frontend/public/data/hydrants.json` cache was deleted rather than
> regenerated; the kiosk now reads `/api/hydrants` from `public.hydrants`, so there is one
> source and no cache to drift.
>
> The `sync_hydrants.py:77` fix carries a provenance comment (`:72`) explaining why the
> default was dangerous, per §6.3.

**Historical record of the defect (as originally found):**

`backend/scripts/sync_hydrants.py:80` substituted the highest flow class when the
municipal source had none:

```python
"flowClass": attribs.get("flow_class") or "AA",
```

`backend/scripts/update_gis_data.py:207` does the same lookup honestly:

```python
"flowClass": attribs.get("flow_class") or "",
```

The two scripts disagree, and the fabricating one produced the cached data.

Distribution in the since-deleted `frontend/public/data/hydrants.json` (3,387 hydrants),
which is what made the default visible:

| status | AA | A | B | C |
|:--|--:|--:|--:|--:|
| OPERATING | 2322 | 333 | 123 | 60 |
| **PRIVATE** | **462** | 2 | 0 | 0 |
| OPERATING NON-TCA | 68 | 0 | 0 | 0 |
| NOT READY | 9 | 0 | 0 | 0 |
| METRO | 8 | 0 | 0 | 0 |

OPERATING shows a real spread (≈82% AA). PRIVATE is **99.6% AA**, and NON-TCA, NOT READY
and METRO are **100% AA**. That pattern is a default, not a measurement — consistent with
the operator's report that private hydrants have no recorded flow value.

**The direction of the error matters.** Under NFPA 291, AA is the *highest* class
(light blue, 1500+ GPM). Defaulting unknown hydrants to AA tells crews an unrated
hydrant is the best available supply. For a working fire that is the most dangerous
possible substitution — the opposite of failing safe, and a direct CLAUDE.md §6.1
violation.

**Fix**: `flow_class` should propagate as null and render as an explicit unknown
(grey/unclassified marker, "flow not rated"), never as a colour-coded class. Requires:
1. Change the `or "AA"` default in `sync_hydrants.py`.
2. Re-sync hydrant data — the cached JSON already carries the fabricated values, so a
   code fix alone changes nothing.
3. Give the kiosk hydrant layer an explicit unknown rendering, distinct from all four
   NFPA colours.

---

## 🧭 Geocoder Honesty Gaps
