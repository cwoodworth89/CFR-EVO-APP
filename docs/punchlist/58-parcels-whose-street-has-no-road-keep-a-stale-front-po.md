# Punch list #58 — Parcels whose street has no road keep a stale front point on a different street

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | Found 2026-08-31 while verifying #38 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 58. A front point that survived the fix, still pointing at the wrong street

> **Status**: ⚠️ **Open — found and measured 2026-08-31 against the running database.**

The #38 fix constrains frontage to the addressed street. Its road lookup is a
`CROSS JOIN LATERAL` that returns no row when no road carries that street name, so the
`UPDATE` never touches those parcels — and they **keep whatever the old any-road algorithm
computed**.

| | |
|:--|--:|
| Parcels with a front point not on their named road | **56** |
| — no road of that name exists (this item) | **56** |
| — road exists but point is elsewhere | 0 |

So 56 parcels carry an arrival point on a street that is not theirs, left frozen rather than
recomputed. It is not a large number, but it is the **§6.1 failure exactly**: a plausible
wrong value where an explicit unknown belongs. A crew routed to one of these is sent to a
different street, and nothing on the kiosk says so.

**These are the orphan-street parcels from #42** — `Pinecone Burke` (28), `Deer's Leap` (15),
`Coronation` (7), `Fremont` (6), plus survey notations that were never streets
(`Power Line`, `N/O Quarry`, `E/O Pipeline`). The City publishes no road centreline for them,
so there is no correct front point to compute.

#### Fix direction

Set `front_lat`/`front_lng` to **NULL** where no road of the addressed street name exists,
rather than leaving the stale value. That surfaces as the Tier 1 amber card
(`⚠️ LOCATION UNRESOLVED`) instead of routing confidently to the wrong street. The parcel
still geocodes — `centroid_lat/lng` is unaffected — so the map still shows the property.

These 56 are also the natural first entries in the **#49** operator entrance queue: they are
precisely the properties where no automatic answer exists and a human must set the arrival
point.

**Requires**: a small change to `backfill_parcel_frontage` (a second statement nulling the
unmatched set) and a re-run. Confirm with the operator first — it changes what the kiosk
shows for those 56 addresses.
