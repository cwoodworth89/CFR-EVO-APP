# Briefing: the roads import drops 45 streets that 1,918 parcels are addressed on

**Written 2026-08-23 for the parser/GIS audit agent.** Punch-list item **#42**.
You have reportedly reached the same conclusion independently — this adds the measurements,
so you can skip re-deriving them.

---

## The filter

`backend/scripts/import_gis_data.py`, `step2_import_roads` (~`:228`):

```python
status = props.get("STATUS")
if status and str(status).strip().upper() != "OPERATING":
    continue
```

**The import is faithful — nothing leaks.** The arithmetic reconciles exactly, so this is a
deliberate filter, not a bug in the loader:

| | |
|:--|--:|
| `road_centre_lines.geojson` features | 3,456 |
| Dropped, `STATUS != 'OPERATING'` | **242** |
| Dropped, missing `FULLNAME` | 0 |
| Expected in `public.roads` | 3,214 |
| **Actual `public.roads` rows** | **3,214** ✅ |

The 242 are **170 `PRIVATE`, 71 `MOT`, 1 `METRO`**. `public.roads` contains exactly one
distinct `status` value: `OPERATING`.

---

## What is actually missing

**68 named roads exist *only* as non-OPERATING segments — they are absent entirely, not
thinned.** Confirmed against the database:

| Road | Source segments | Rows in `public.roads` |
|:--|:--|--:|
| `Highway #1` (Trans-Canada) | 7 MOT, 0 OPERATING | **0** |
| `Mary Hill By-Pass Road` | 4 MOT, 0 OPERATING | **0** |

Roads that survive but lose segments: `Lougheed Highway` 8 of 45 gone, `United Boulevard`
6 of 22, **`Highway Ramp` 41 of 44**.

**The residential side is the operational problem.** Cross-referencing
`public.parcels.street` against `public.roads.roadname`:

| | |
|:--|--:|
| Distinct streets in `public.parcels` | 997 |
| **Streets with no matching road** | **45** |
| **Parcels addressed on those streets** | **1,918** |

| Street | Parcels |
|:--|--:|
| Princess | **568** |
| Silver Springs | **359** |
| Riverbend | 227 |
| Whisper | 193 |
| Bluff | 63 |
| River | 60 |
| Bow | 55 |
| Flynn | 50 |

Verified present in the source and flagged `PRIVATE`: `Princess Crescent (PRIV)`,
`Silver Springs Boulevard`, `Riverbend Drive`, `Whisper Way`, `Oxbow Way (PRIV)`,
`Parkland Drive (Private)`.

These are strata roads. **Crews still respond to them** — `2980 Princess Cres` is already in
the dispatch corpus.

---

## What breaks, and what does not

**Still works**: direct address geocoding. `public.parcels` holds these addresses with
coordinates, so a plain address lookup resolves normally. That is why this has stayed
invisible.

**Does not work** — anything derived from road geometry:

* **`public.intersections`** is derived from `public.roads`, so no junction involving these
  streets can exist. A dispatch announcing *"Princess Cres and \<cross street\>"* has nothing
  to match.
* **"near \<road\> and \<road\>"** matching on the announced cross streets.
* **Cross-street validation** and street-name vocabulary.

---

## Recommendation

**Do not simply delete the filter.** `STATUS` is meaningful municipal data — MOT segments are
provincial highways and PRIVATE are strata roads, and they may warrant different routing or
display treatment. Deleting the filter would silently promote all of them to equal footing,
which is the opposite mistake.

**Import all statuses and keep the `status` column populated**, letting each consumer decide.
`public.roads.status` already exists and currently holds one value for every row — that
flattening is the tell that a real distinction was discarded at import rather than preserved.

Consequences to plan for:

1. **`public.intersections` must be re-derived** (`backend/scripts/derive_intersections.py`)
   after the re-import, since it reads `public.roads`.
2. **The geocoder's street vocabulary changes** — 45 new street names become resolvable.
   Worth diffing against the real dispatch corpus the way the intersection rebuild was, per
   the pattern in `docs/review_status_handoff.md`.
3. Decide explicitly whether private/MOT roads should be **routable**, **matchable for
   intersections**, or **display-only**. That is a §7.2 domain decision, not a coding choice —
   raise it with the operator rather than picking a default.

---

## Reproducing the measurements

`road_centre_lines.geojson` is git-ignored; it is at
`backend/data/staging/road_centre_lines.geojson` locally. GDAL/fiona are **not** installed on
the dev machine, so shapefiles need `backend/scripts/read_dbf.py` (added 2026-08-23) rather
than geopandas. The GeoJSON itself parses with plain `json`.

Parcel/road cross-reference, run against the kiosk database:

```sql
WITH pstreets AS (
  SELECT trim(street) AS street, count(*) AS parcels
  FROM public.parcels WHERE street IS NOT NULL AND trim(street) <> ''
  GROUP BY 1
)
SELECT street, parcels FROM pstreets p
WHERE NOT EXISTS (
  SELECT 1 FROM public.roads r WHERE upper(trim(r.roadname)) = upper(p.street))
ORDER BY parcels DESC;
```
