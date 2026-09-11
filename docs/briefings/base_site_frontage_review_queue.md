# Base_site frontage review queue — punch list #77

**Generated 2026-09-10** from the kiosk database. Machine-produced; no figure here was typed by hand.

When the resolver switches to the `base_site` row as the master row for a multi-parcel
address, the default destination becomes that row's `front_lat`/`front_lng`. These are the
**71 sites where that point moves 25 m or more.**

## What the shift is, and is not

It is **not** lost frontage work. `build_base_site_rows` sets no front point; it is
`backfill_parcel_frontage` that snaps every row — base rows included — to the street its
address names, using the same constrained-road lookup
(`roads.roadname = parcels.street`, `ST_ClosestPoint` against the polygon) that took
misplacements to zero on 2026-08-31.

The difference is the **polygon it snaps from**:

| | |
|:--|:--|
| Today's point | frontage of **one arbitrary lot** — whichever of the site's rows has the lowest `id` |
| New point | frontage of the **whole property** — `ST_Union` of its members |

Today's value was never curated. It is the answer for a lot nobody chose. The new value is
deterministic and corresponds to the address — but on a spread-out split lot,
`ST_ClosestPoint` against a large union can land on the nearest corner of the property
rather than at the addressed building. **That is what this list is for.**

## How to work it

Open the address in **Explore** with admin unlocked, and compare the new point against the
site. If it is wrong, **set an arrival point on it**. Do not try to restore the old
coordinate — `front_lat` is recomputed for every row on every parcel import, so a copied
value reverts silently at the next run. `entrance_lat` is excluded from both the INSERT and
the `ON CONFLICT` set (`test_parcel_import_entrance.py` enforces it) and is the only value
that survives the pipeline.

## Scope

| Shift | Sites | |
|:--|--:|:--|
| No change (<1 m) | **1,543** | not listed |
| 1–24 m | 57 | not listed — within frontage noise |
| **25 m and over** | **71** | **listed below** |
| — of those, over 200 m | 6 | the first six rows |

Total base_site rows: 1,671. **92% do not move at all.**

---

| Address | City rows | Shift | New point (lat, lng) | Current point (lat, lng) | base_id | Checked |
|:--|--:|--:|:--|:--|--:|:--|
| 2885 Lansdowne Dr | 3 | 397 m | 49.296047, -122.811684 | 49.292505, -122.811053 | 201345 |  |
| 1735 Hampton Dr | 2 | 388 m | 49.312098, -122.784079 | 49.308653, -122.783250 | 201120 |  |
| 25 Braid St | 2 | 248 m | 49.228506, -122.876399 | 49.226275, -122.876404 | 201268 |  |
| 2040 Pipeline Rd | 2 | 226 m | 49.340480, -122.772412 | 49.338474, -122.771947 | 201181 |  |
| 2050 Pipeline Rd | 14 | 226 m | 49.340480, -122.772412 | 49.338474, -122.771947 | 201187 |  |
| 2215 Dawes Hill Rd | 2 | 213 m | 49.235986, -122.832204 | 49.236867, -122.829611 | 201235 |  |
| 1038 Corona Cres | 2 | 194 m | 49.272679, -122.828837 | 49.270991, -122.829519 | 200660 |  |
| 150 Schoolhouse St | 2 | 190 m | 49.234981, -122.852548 | 49.236688, -122.852524 | 201082 |  |
| 4455 Oliver Rd | 2 | 169 m | 49.293041, -122.705169 | 49.293053, -122.702839 | 201660 |  |
| 1460 Coast Meridian Rd | 3 | 169 m | 49.303670, -122.755819 | 49.302149, -122.755851 | 201068 |  |
| 4375 Oliver Rd | 2 | 169 m | 49.293041, -122.705169 | 49.293053, -122.702839 | 201651 |  |
| 3379 Gislason Ave | 2 | 168 m | 49.289287, -122.755294 | 49.289297, -122.752986 | 201538 |  |
| 3000 Riverbend Dr | 258 | 161 m | 49.261572, -122.795318 | 49.262262, -122.793374 | 201421 |  |
| 4908 Quarry Rd | 4 | 144 m | 49.324989, -122.673725 | 49.325910, -122.672328 | 201674 |  |
| 1480 Marguerite St | 6 | 144 m | 49.303495, -122.759454 | 49.304689, -122.760211 | 201073 |  |
| 502 Lougheed Hwy | 2 | 142 m | 49.251828, -122.800797 | 49.250600, -122.801327 | 201688 |  |
| 4900 Quarry Rd | 4 | 139 m | 49.324919, -122.673832 | 49.325805, -122.672488 | 201673 |  |
| 1630 Parkway Blvd | 3 | 133 m | 49.305583, -122.805909 | 49.304646, -122.807038 | 201103 |  |
| 3438 Galloway Ave | 3 | 123 m | 49.294885, -122.748850 | 49.294877, -122.750536 | 201571 |  |
| 4916 Quarry Rd | 3 | 122 m | 49.325134, -122.673519 | 49.325910, -122.672328 | 201676 |  |
| 2495 Cape Horn Ave | 2 | 111 m | 49.238980, -122.823825 | 49.238961, -122.825346 | 201267 |  |
| 3430 Harper Rd | 2 | 99 m | 49.303579, -122.747994 | 49.303985, -122.749210 | 201564 |  |
| 1491 Johnson St | 3 | 95 m | 49.300958, -122.794855 | 49.301032, -122.793560 | 201079 |  |
| 1401 Collins Rd | 2 | 94 m | 49.298598, -122.761466 | 49.299446, -122.761452 | 201042 |  |
| 2975 Panorama Dr | 4 | 94 m | 49.298930, -122.803591 | 49.298572, -122.804757 | 201389 |  |
| 1016 Howie Ave | 360 | 87 m | 49.250590, -122.865720 | 49.250605, -122.866921 | 200619 |  |
| 439 North Rd | 3 | 85 m | 49.247054, -122.892659 | 49.247820, -122.892694 | 201654 |  |
| 435 North Rd | 66 | 85 m | 49.247054, -122.892659 | 49.247820, -122.892694 | 201649 |  |
| 455 North Rd | 3 | 85 m | 49.247054, -122.892659 | 49.247820, -122.892694 | 201666 |  |
| 2501 Como Lake Ave | 9 | 84 m | 49.263229, -122.823403 | 49.263223, -122.822244 | 201271 |  |
| 2777 Barnet Hwy | 2 | 79 m | 49.277771, -122.805161 | 49.277845, -122.806246 | 201326 |  |
| 1550 Eagle Mountain Dr | 2 | 78 m | 49.304523, -122.814527 | 49.303956, -122.815164 | 201091 |  |
| 925 Sherwood Ave | 16 | 78 m | 49.235854, -122.871187 | 49.235843, -122.872263 | 202156 |  |
| 2865 Glen Dr | 84 | 75 m | 49.282752, -122.804565 | 49.282748, -122.803538 | 201337 |  |
| 580 Clarke Rd | 4 | 73 m | 49.263224, -122.887974 | 49.262761, -122.888676 | 201779 |  |
| 1355 Pinetree Way | 2 | 72 m | 49.294876, -122.788466 | 49.295276, -122.787682 | 201014 |  |
| 1378 Purcell Dr | 13 | 69 m | 49.295592, -122.784287 | 49.295162, -122.784969 | 201026 |  |
| 885 Baker Dr | 6 | 69 m | 49.269191, -122.825069 | 49.268609, -122.824744 | 202118 |  |
| 1800 Austin Ave | 52 | 65 m | 49.248619, -122.844095 | 49.249001, -122.843428 | 201131 |  |
| 2635 Hawser Ave | 2 | 60 m | 49.270868, -122.815992 | 49.270864, -122.815169 | 201292 |  |
| 210 Lebleu St | 47 | 59 m | 49.238287, -122.867529 | 49.237757, -122.867532 | 201197 |  |
| 3338 David Ave | 2 | 52 m | 49.292951, -122.761499 | 49.292948, -122.760780 | 201532 |  |
| 575 Nathan Pl | 2 | 45 m | 49.253242, -122.857729 | 49.253244, -122.857107 | 201771 |  |
| 540 Rochester Ave | 142 | 43 m | 49.245479, -122.888970 | 49.245483, -122.889554 | 201726 |  |
| 542 Rochester Ave | 128 | 43 m | 49.245479, -122.888970 | 49.245483, -122.889554 | 201729 |  |
| 1101 Austin Ave | 2 | 40 m | 49.249044, -122.862028 | 49.249039, -122.861475 | 200742 |  |
| 3393 Darwin Ave | 6 | 40 m | 49.287537, -122.754097 | 49.287535, -122.754647 | 201545 |  |
| 1040 Howie Ave | 220 | 40 m | 49.250569, -122.864246 | 49.250576, -122.864799 | 200665 |  |
| 1109 Austin Ave | 2 | 40 m | 49.249044, -122.862028 | 49.249039, -122.861475 | 200752 |  |
| 3459 Wilkie Ave | 24 | 39 m | 49.286667, -122.746885 | 49.286663, -122.747420 | 201585 |  |
| 1930 Brunette Ave | 3 | 37 m | 49.231611, -122.840748 | 49.231908, -122.840966 | 201141 |  |
| 837 Lougheed Hwy | 2 | 36 m | 49.237238, -122.874468 | 49.237140, -122.873994 | 202102 |  |
| 3030 Lincoln Ave | 58 | 35 m | 49.279070, -122.791199 | 49.279007, -122.791677 | 201436 |  |
| 1470 Southview St | 2 | 34 m | 49.303992, -122.754026 | 49.304269, -122.753819 | 201071 |  |
| 3441 Roxton Ave | 6 | 34 m | 49.288472, -122.748424 | 49.288465, -122.748889 | 201575 |  |
| 1132 Dufferin St | 37 | 33 m | 49.279190, -122.804044 | 49.278896, -122.804034 | 200790 |  |
| 100 Schoolhouse St | 32 | 33 m | 49.233821, -122.852558 | 49.234116, -122.852553 | 200581 |  |
| 1391 Gilleys Trail | 3 | 32 m | 49.297153, -122.716736 | 49.297441, -122.716670 | 201033 |  |
| 1380 Woolridge St | 4 | 32 m | 49.232072, -122.854863 | 49.232185, -122.855261 | 201028 |  |
| 3427 Roxton Ave | 7 | 30 m | 49.288452, -122.751319 | 49.288450, -122.751735 | 201563 |  |
| 3419 Roxton Ave | 6 | 30 m | 49.288446, -122.752434 | 49.288444, -122.752851 | 201560 |  |
| 3423 Roxton Ave | 6 | 30 m | 49.288449, -122.751916 | 49.288447, -122.752332 | 201562 |  |
| 3411 Roxton Ave | 8 | 30 m | 49.288444, -122.754791 | 49.288443, -122.754376 | 201556 |  |
| 2689 Guildford Way | 4 | 29 m | 49.283859, -122.811608 | 49.283622, -122.811788 | 201309 |  |
| 555 Cottonwood Ave | 225 | 28 m | 49.258846, -122.889572 | 49.258840, -122.889191 | 201750 |  |
| 490 Mariner Way | 4 | 27 m | 49.242019, -122.815999 | 49.241814, -122.816209 | 201671 |  |
| 1029 Ridgeway Ave | 2 | 27 m | 49.249677, -122.865444 | 49.249671, -122.865073 | 200646 |  |
| 1031 Ridgeway Ave | 2 | 27 m | 49.249677, -122.865444 | 49.249671, -122.865073 | 200651 |  |
| 1570 Pipeline Rd | 3 | 26 m | 49.311920, -122.772350 | 49.312129, -122.772184 | 201094 |  |
| 166 Warrick St | 2 | 26 m | 49.234204, -122.831414 | 49.234396, -122.831220 | 201109 |  |
| 1053 Rochester Ave | 2 | 25 m | 49.245327, -122.863314 | 49.245324, -122.862966 | 200702 |  |

