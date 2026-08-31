# Punch list #43b — The 8 failed cadastral tiles, and what the "blank" tiles actually are

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🧾 Import Completeness Audit, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3348 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 43. The 8 failed cadastral tiles, and what the "blank" tiles actually are
> **Status**: ✅ **Closed 2026-08-27.** Both questions answered by measurement.

#### The 8 failures were transient

Re-ran the crawler; it found exactly 8 missing tiles and fetched all 8 with **zero failures**
in under a second. No pattern, no bad region — network noise across 153,102 requests over 8½
hours. Cadastral coverage is now provably complete:

```
archive tiles      : 606,946
inside coverage    : 430,801
grid expects       : 430,801
missing from grid  : 0
```

Archive re-finalized (`Integrity: ok`, `Journal Mode: delete`) and `cfr_tiles` restarted — the
retry had put it back into WAL mode, which would have broken the read-only mount if left.

**But the log could not say which 8 they were.** Every failure path in `fetch_tile` logged at
`logger.debug` while logging is configured at `INFO`, so the details were discarded and the run
reported a bare count. Identifying them required a re-run with `force=True` DEBUG logging.
That is the same defect as **#26**, one layer down: a count with no cause. It did not matter
here because the failures were transient — but a *systematic* failure over one region would
have produced an identical-looking log.

**Fixed**: the three retry-exhausted paths now log at `WARNING`.

#### Retraction: the "dead weight" claim about outside-coverage tiles was wrong

An earlier note called the 176,145 tiles outside the coverage polygon "dead weight" and
suggested purging them for space. **The operator questioned whether the City would even
produce cadastral data outside its own boundary. That instinct was right, and the reasoning
behind the purge suggestion was weak.**

Measured: all 176,145 are **exactly 885 bytes** — min, median and max identical. Decoded:

```
md5 = 72accbca6aa1edbf6fec07c32f2df94a
256x256, alpha min/max = 0/0, distinct pixels = 1
```

One fully transparent image, repeated. The City renders **nothing** beyond its cadastral
extent, so the coverage polygon is **not excluding any real data** — which was the question
worth asking.

Two comparable tiles at z18, both against the City's MapServer, for anyone re-checking this:

* **Outside**, 49.21984, −122.91985 → blank, 885 b
* **Inside**, 49.24316, −122.89238 → parcel lines and address labels, 9,415 b

`bbox` is EPSG:3857; the export URL pattern is in `MAPSERVER_EXPORT_URL`.

**And the space argument does not hold either.** There are **488,668** 885-byte blank tiles in
the whole archive — **80.5%** of 606,946 — of which only 176,145 are outside the polygon. So
**312,523 blanks are *inside* the city**, and that is entirely normal: at z20 a tile is ~30 m
across and parcels render as outlines, so tiles landing inside a lot, a park or the river have
nothing to draw. **Blank is not a proxy for "should not be there."**

The 176,145 outside tiles are ~150 MB of a 991 MB archive against 222 GB free, and they do
useful work: without them the tile server has no cached answer for a pan just past the boundary
and the frontend would paint its "no map data" hatch over Port Moody — reintroducing #40's
symptom at the edges.

**Recommendation reversed: leave them.** Recorded rather than quietly dropped, because the
original suggestion came from inferring purpose from file size instead of decoding one tile
(§7.1). The semantics are now an inline comment at the PNG-validation site so nobody
"optimises" blanks away later.

---
