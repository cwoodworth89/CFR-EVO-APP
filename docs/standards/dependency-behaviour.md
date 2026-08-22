# Verified Dependency Behaviour

Companion to [`README.md`](README.md). That file covers **domain standards** — what the
fire service and the GIS world specify. This file covers **library semantics** — what the
code we depend on actually does, as opposed to what its API name suggests.

Both categories caused real defects in the 2026-08-21/22 review, but the library ones were
more dangerous, because a domain gap feels like a gap while a library assumption feels
like knowledge.

## The pattern: the API name is not the contract

Every library defect found so far had the same shape — **the name described the intent,
not the behaviour**, and the code was written against the name.

| Called | The name implies | It actually does |
|:--|:--|:--|
| `hotwords=` | these words are boosted | keeps the first 223 tokens, silently discards the rest |
| `token_set_ratio` | a similarity ratio | returns **100** when one token set is a subset of the other |
| `ST_Contains` | the point is in the polygon | excludes the boundary, so a point on a zone edge is *not* contained |

None of these are bugs in the libraries. All are documented or evident in source. The
defect was on our side: **we trusted the name.**

## Rule

Before an operational decision rests on a library function's behaviour, verify it against
the **installed source of the pinned version** or that version's documentation — and
record it here. For a pinned dependency the installed source is authoritative and beats
recollection (CLAUDE.md §7.3).

Cheapest reliable check: write the two-line probe that demonstrates the behaviour, run it,
and paste the output here. `token_set_ratio('LOUGHEED HWY', 'ALDERSON AVE & LOUGHEED HWY')`
→ `100` took ten seconds to run and would have prevented a 4.3 km routing error.

## Verified behaviours

### faster-whisper 1.2.1 — `hotwords` is truncated, head-first

`faster_whisper/transcribe.py`, `TranscriptionOptions.get_prompt`:

```python
if len(hotwords_tokens) >= self.max_length // 2:
    hotwords_tokens = hotwords_tokens[: self.max_length // 2 - 1]
```

* `max_length` is **448** for the loaded model, so the cap is **223 tokens**.
* The **head** is kept (`[:n]`), so ordering of the hotword list is the whole policy.
* Truncation is silent — no warning, no return value, no exception.
* `initial_prompt` is a separate budget (it becomes `previous_tokens`, capped the same
  way), so the two do not compete.

**Consequence when unverified**: 1,173 alphabetically-ordered entries were supplied; 61
survived; the list ended at "Archworth Avenue"; every arterial in Coquitlam received no
biasing at all. Punch-list #18.

### thefuzz 0.22.1 (rapidfuzz 3.14.5) — `token_set_ratio` and the subset trap

```
token_set_ratio('LOUGHEED HWY', 'ALDERSON AVE & LOUGHEED HWY')  -> 100
```

`token_set_ratio` compares the *set intersection* against the differences, so when one
string's tokens are a subset of the other's it scores a perfect match regardless of how
much extra the longer string contains.

* Use `fuzz.ratio` when the two strings are meant to be the *same* thing.
* Never use `token_set_ratio` where one operand may be a fragment of the other.

**Also measured, and more fundamental**: for Coquitlam street names there is **no safe
similarity threshold at all**. Across all 1,079 road names, genuinely different streets
score `HAMBER CRT`/`AMBER CRT` **96**, `WESTWOOD ST`/`EASTWOOD ST` **93**,
`BURKE MOUNTAIN ST`/`BLUE MOUNTAIN ST` **93** — while corrections worth making score
`TASIS→TAHSIS` **95** and `JOHNSON→JOHNSTON` **98**. The populations overlap, so fuzzy
matching may **suggest** but must never **substitute**. Punch-list #15.

### PostGIS 3.4 — `ST_Contains` excludes the boundary

`ST_Contains(A, B)` is false when B lies on A's boundary; `ST_Intersects` is true.

Emergency response zone polygons are bounded **by the road network**, so every road
intersection sits exactly on a zone boundary. Using `ST_Contains` to find "which zone is
this junction in" returns NULL for them.

**Consequence when unverified**: 155 of 1,784 intersections had no map grid, and five
different containment queries across the codebase disagreed with each other. Now
consolidated into `public.zone_for_point()`. Punch-list #13.

### PostGIS 3.4 — `ST_ClusterDBSCAN` with `minpoints := 1` produces no noise

```
3 input points (2 close, 1 far), eps := 0.0002, minpoints := 1
-> 3 rows, 3 non-null cluster ids, 0 NULL, 2 distinct clusters
```

With `minpoints := 1` every point is its own core point, so nothing is classified as noise
and no row comes back with a NULL cluster id. `derive_intersections.py` relies on this: a
junction represented by a single centreline node must still become a cluster of one rather
than being dropped.

Verified 2026-08-22. Had it returned NULL for isolated points, single-node junctions would
have silently vanished from `public.intersections`.

### PostGIS 3.4 — `ST_LineMerge` signals failure through geometry type

```
disjoint parts  -> ST_MultiLineString (2 parts)
touching parts  -> ST_LineString      (1 part)
```

`ST_LineMerge` joins parts that share endpoints and leaves the rest alone, so a collection
that cannot be merged into a single line comes back as a `MultiLineString`. The geometry
type is therefore a reliable test for "did this merge".

`derive_intersections.py` uses `ST_LineInterpolatePoint` (which requires a `LineString`)
only when the merge yields `ST_LineString`, and falls back to `ST_PointOnSurface`
otherwise. Verified 2026-08-22 — the discrimination is correct.

This is also the shape of an earlier live defect: block interpolation had never worked
because `public.roads.geom` is `MULTILINESTRING` and `ST_LineInterpolatePoint` requires
`LINESTRING`, so step 3 of the geocoder cascade threw on every call and silently fell
through to coarser steps.

## Unverified — assumptions still resting on names

Recorded so they are visible (§7.5). None of these have been checked.

* **OSRM** — whether `distance`/`duration` in the response are affected by the profile's
  `weight` versus being true metres/seconds. Punch-list #1 depends on this and the profile
  has not been tuned.
* **Silero VAD** (`vad_filter=True` in `transcriber.py`) — what it removes, and whether it
  can clip the leading tones or the first unit name of a dispatch.
