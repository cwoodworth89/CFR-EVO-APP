# Punch list #58 — Parcels whose street has no road keep a stale front point on a different street

| | |
|:--|:--|
| **Status** | CLOSED |
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

---

## 58 (closed). Cleared, and the code no longer leaves them behind

> **Status**: ✅ **Closed 2026-08-31.** Fixed in code and applied to the running kiosk
> database, verified by re-query rather than assumed (§6.6).

**Code** (`9570eb8`): `backfill_parcel_frontage` now explicitly nulls `front_lat`/`front_lng`
for any parcel whose addressed street has no road in `public.roads`, instead of skipping them
and leaving the previous any-road value in place. The existing note claimed they already
"surface as an approximate location rather than a confident wrong one" — that was the intent,
not the behaviour.

**Data**, applied 2026-08-31:

| | |
|:--|--:|
| Parcels with a front point, before | 65,401 |
| Stale rows cleared | **56** |
| Parcels with a front point, after | **65,345** |
| Stale rows remaining | **0** |
| `entrance_lat` values touched | **0** |

65,401 − 56 = 65,345, which matches the count exactly. Those 56 now report an unknown arrival
point — the Tier 1 amber card — rather than routing confidently to a street they are not on.

The 16 streets involved are their own explanation: `Power Line`, `N/O Quarry`, `S.E. Quarry`,
`S.E./O Quarry` and `E/O Pipeline` are survey notations; `Fraser River`, `Munro Creek`,
`Deboville Slough`, `Railroad` and `Trans Canada` are geographic features; `Pinecone Burke`,
`Coronation`, `Fremont`, `Taft`, `Addington` and `Coquitlam` are names the City publishes no
centreline for.

`Deer's Leap` dropped out of the set: the apostrophe stripping added with the street filter
now matches it to the road layer's `Deers Leap`.

These 56 are the natural first entries in the **#49** entrance queue — the properties where
no automatic answer exists and a human must set the arrival point.
