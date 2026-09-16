# Punch list #91 — Road closure fields the feed did not send are filled with invented values, including the access level

| | |
|:--|:--|
| **Status** | OPEN — found 2026-09-16; not built; needs the operator's ruling on each default |
| **Severity** | 🔴 crew-visible — crews read the access level off a severity the feed never sent |
| **Area** | ⚙️ API · 🖥️ Kiosk |
| **Origin** | Found by `gis-spatial-engineer` while fixing #90 ("hardcoded failsafes concern me, it needs to fail loudly" — operator, 2026-09-16); every line verified by lead against the working tree at `e3009d6a` |
| **Related** | #89 · #90 · CLAUDE.md §6.1 (no default incident type, no placeholder that reads as real data) · §6.3 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

#90 removed one invented value — a coordinate. The same two files fill every other gap the
feeds leave with a value that reads as real. The two that set the **access level** matter
most, and they default in **opposite directions**:

| Where | Default | What a crew sees |
|:--|:--|:--|
| `backend/api/road_closure_service.py:243` | `(evt.get('severity') or 'MINOR')` — an unknown DriveBC severity becomes MINOR | A closure of unknown severity is filed as **CAUTION**, the mildest tier |
| `backend/api/routers/road_closures.py:175` | `r.closure_type or "FULL_CLOSURE"` — an unknown stored type is served as a full closure | The same unknown, one step later, is drawn as **NO_ACCESS**, the most severe |

Neither carries a source (§6.3). Which one a crew sees depends on which field happened to be
empty. Both are the "default incident type" §6.1 names outright.

The rest, same defect, lower stakes:

| Where | Default |
|:--|:--|
| `routers/road_closures.py:177` | `r.description or "Active traffic event."` |
| `road_closure_service.py:278` | street name `or "Regional Corridor"` |
| `road_closure_service.py:282` | headline `or "TRAFFIC ALERT"` |
| `road_closure_service.py:367` | municipal location `or "Local Road"` |
| `road_closure_service.py:369` | description `or "Local road construction or restriction."` |
| `road_closure_service.py:277` | `closure_id` falls back to `f"db_{len(raw_notices)}"` when the feed sends no id — the same id can be produced on a later sync for a different closure and **overwrite it** |

## What it should do

An unknown severity is an unknown, not a tier: propagate `null`, and let the sidebar and the
marker show a closure whose access level is **not stated** — distinct from CAUTION, ACCESS
ONLY and NO ACCESS — rather than pick one. Text fields render as absent (`--`), not as prose
that reads as a description. A record with no id from the feed gets an id derived from the
record (source + stable fields), never from the position in the list.

## Operator rulings needed

1. Unknown severity: a fourth visible state, or drop the record from the map and keep it in
   the sidebar list only?
2. Text placeholders: blank, or omit the card field?
3. The `db_{n}` id: derive from content, or refuse the record and log it?

## Falsifier

`SELECT count(*) FROM public.road_closures WHERE closure_type IS NULL OR description IS NULL
OR street_name IS NULL OR headline IS NULL OR closure_id LIKE 'db_%';` — if zero today, the
defect is latent like #90 was; it still goes, for the same reason.

## Log

| Date | Event |
|:--|:--|
| 2026-09-16 | Found by `gis-spatial-engineer` during #90, out of its scope, not built. Verified by lead line by line. Promoted under §7.1: the severity pair is crew-visible. Rulings above are the operator's |
