# Punch list #90 — A road closure with no coordinates is drawn at a hardcoded point near Coquitlam Centre

| | |
|:--|:--|
| **Status** | BUILT — backend `e3009d6a`, frontend `2978da7e`; **not deployed.** Latent: falsifier run on the kiosk, 177 rows, 0 null, 0 malformed, so nothing on screen changes until a bad feed record arrives |
| **Severity** | 🔴 crew-visible — a closure marker where there is no closure looks like every other closure marker |
| **Area** | ⚙️ API · 🗺️ Map |
| **Origin** | Found by `gis-spatial-engineer` while building #89, out of its scope; verified by lead against the working tree the same day |
| **Related** | #89 · CLAUDE.md §5 (no silent coordinate fallbacks) · §6.1 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

`backend/api/routers/road_closures.py:134`:

```python
raw_coords = r.coordinates or [49.28, -122.80]
```

and the same pair again at `:138`, in the `except` that catches an unparseable value. A
closure record with missing or malformed coordinates is returned to the kiosk **at a fixed
point near Coquitlam Centre**, and the map draws it there as an ordinary closure marker. No
comment names where the pair came from (§6.3), and the kiosk cannot tell it from a real
location (§6.1). CLAUDE.md §5 forbids exactly this: coordinates that are null, NaN or 0 must
propagate as unresolved, never be replaced by a default.

## What it should do

Return the closure with `coordinates: null` (or omit it from the map payload) and let the
sidebar list it without a marker. A closure the crew can read about but not see on the map is
a correct unknown; a marker at the wrong place is a defect.

## Falsifier

Query `public.road_closures` for rows with `coordinates IS NULL` or a value that fails to
parse. If there are none today, the defect is latent; it still goes, because the next bad
feed record makes it live.

## Log

| Date | Event |
|:--|:--|
| 2026-09-16 | Found by `gis-spatial-engineer` during #89, verified by lead, promoted straight to the list under §7.1. Not built; no owner yet |
| 2026-09-16 | **Backend fixed, `e3009d6a`**, on the operator's direct word in the GIS chat ("hardcoded failsafes concern me, it needs to fail loudly"). The pair is gone from both places; `_parse_closure_point` (`routers/road_closures.py:~93`) returns `None` for missing, wrong arity, non-numeric, NaN, infinite or 0 (§5 treats null, NaN and 0 alike). The closure still goes out, with `"coordinates": null`, and each one is logged at ERROR with its id and the stored value. Test in `backend/tests/test_road_closures_cache.py`: six bad values → all null, none equal the old pair, every id logged; road closure tests 10/10. **Falsifier run on the kiosk:** 177 rows, 0 null, 0 malformed — latent, nothing on screen changes today. Not deployed. **Consumer side found by GIS:** `RightSidebar.jsx:248` calls `map.flyTo(closure.coordinates, …)` unguarded, so a null now throws in the click handler and the tap does nothing; `RoadClosureMarker.jsx:41` already handles null. Sent to `frontend-kiosk-architect`. GIS also listed the other invented defaults in the same two files — the severity pair is crew-visible — opened as #91, not built |
| 2026-09-16 | **Frontend built, `2978da7e`**, `RightSidebar.jsx` only. `closureMapPoint` (`:21`) picks the tap target in the marker's order — own coordinates, else the polyline's first point, else `null` — and is stricter than the marker: both numbers must parse finite, so NaN is rejected too. The click handler (`:268`) returns on `null`; the card shows `⚠️ NO MAP LOCATION IN FEED RECORD` (`:329`) and loses its hover and pointer styling so it no longer looks tappable. No tooltip, no placeholder coordinate. Verified: `lint:crash` and `build` clean; the helper run against seven record shapes, three return a point and four return `null`. **Not seen rendered** — no null-coordinate closure exists on the kiosk and none was fabricated (§6.5) |
