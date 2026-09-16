# Punch list #90 — A road closure with no coordinates is drawn at a hardcoded point near Coquitlam Centre

| | |
|:--|:--|
| **Status** | OPEN — found 2026-09-16; not built |
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
