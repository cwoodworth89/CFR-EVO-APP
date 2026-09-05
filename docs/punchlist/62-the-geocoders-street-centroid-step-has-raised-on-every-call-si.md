# Punch list #62 — The geocoder's street-centroid step has raised on every call since the `parcels.lat` rename

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🗺️ Geocoding |
| **Blocks** | 1 |
| **Origin** | Found 2026-09-05 by the first full run of `tools/harness_chain.py`: repeated `Error in street centroid fallback` lines in its log |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 62. Step 5 of the geocoder returned None on every call that reached it, for six days

> **Status**: ✅ **Closed 2026-09-05 — found and fixed the same day; the effect on outcomes is
> measured in the closing note.** *(Opened as: 🔴 Open — found 2026-09-05 by the chained
> harness, 24 occurrences by the 60 % mark of its first full run.)*

### What the code did

`services/gis/src/gis_service/address_resolver.py:698`, `resolve_street_centroid`, step 5 of the
ladder in `Geocoder.get_coordinates`:

```sql
SELECT AVG(lat) as avg_lat, AVG(lng) as avg_lng, COUNT(*) as cnt FROM public.parcels ...
```

`parcels.lat` / `lng` became `centroid_lat` / `centroid_lng` on 2026-08-30 (`be0e7bf`,
"rename parcels.lat/lng to centroid_lat/centroid_lng"). That commit touched this file and
missed this statement. Since then Postgres raised `UndefinedColumn` on it, the method's own
`except` logged the error and returned `None`, and the ladder fell through to step 6, the road
centreline centroid (confidence 45 instead of 50), or to unresolved.

**Crew-visible:** a call whose street exists in parcels but whose house number does not, the
case step 5 exists for, was placed on the road centreline or not placed at all, with nothing
telling anyone that a resolver had crashed. The failure was in the container log only.

### Why nothing caught it

* `backend/tests/test_geocoder_orchestrator.py` mocks every resolver. The suite passed, 203
  of 203, on 2026-09-04 with this statement broken.
* The 2026-09-03 staleness scan's migration check flagged `lat` with 337 code references marked
  "generic name, expect noise", and the noise was not read. A rename of a two-letter-word column
  is exactly the case that check cannot separate from prose.
* Running the code found it in the first hour. Same lesson as the closing note of #10: what
  catches this class is execution, not reading.

### Fix

`be0e7bf`'s missed statement now reads `AVG(centroid_lat)`, `AVG(centroid_lng)`, with a comment
naming the rename and this item. `backend/tests/test_address_resolver_db.py` runs the street-
and road-centroid statements against the live schema so the next rename cannot pass silently;
it picks the street with the most parcels rather than naming one.

### Verification, 2026-09-05

| Check | Result |
|:--|:--|
| `test_address_resolver_db.py` against the kiosk database, old statement | fails with `UndefinedColumn: column "lat" does not exist`, the log's exact error |
| Same test, fixed statement (`abf8180`) | 2 passed |
| `harness_chain.py --skip-stt --since 2026-08-01` after the fix, against the morning baseline (`eb0f801`) | outcome buckets identical on all 325 calls, and they had to be: steps 5 and 6 return the same address string and differ only in the point |
| Same run, which resolver answered (`8539894` added the metric) | **5 of 325 calls now answered by step 5**; every one of them raised and fell through before the fix |
| The full STT baseline, started before the fix on the old code | 56 `Error in street centroid fallback` lines by the 3,000-line mark: fresh transcripts reach step 5 far more often than stored ones, because a garbled street name fails every step above it |

The five calls are the case step 5 exists for, a real street with no usable house number: two on
United Blvd (verified `39 United Blvd`), two on Lougheed Hwy (`2905`, `2929`), one on Upper Harper
Rd (`4992`). Before the fix they were placed on the road centreline at confidence 45; now on the
average of the street's parcels at confidence 50, which is what the code always meant to do.

One thing the run exposed about the harness itself: those five read 0 m from the verified
address because the geocoder places the verified address by the same fallback, so the distance
was fallback-to-fallback. The harness now records which step placed the verified address too
and counts the ones the geocoder could not place exactly, so a 0 m is read with that beside it.
