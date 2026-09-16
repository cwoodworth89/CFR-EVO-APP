# Municipal 511, Coquitlam: every current record, 2026-09-16

For the operator, to decide whether any kind of record should be filtered out of the kiosk. **Nothing has been filtered.** Prepared by `gis-spatial-engineer` for punch-list #91, piece B.

## Where this came from

- **One pull of the live feed**, 2026-09-16 20:39 UTC, with the operator's permission. It used the same URLs the kiosk's hourly sync uses: the Coquitlam page, then the 13 data files it lists (14 requests; the estimate given beforehand was 2–4, but the page lists 13 files). Two more requests read the site's script bundles, also with permission. Registered in [`../external_calls.md`](../external_calls.md) Part B.
- **The data files are not Coquitlam's alone.** They hold every Transnomis client, about 6,500 issues including Florida roads. The kiosk keeps a record only when its geometry intersects `public.city_boundary` and touches a `public.zones` polygon (`backend/api/closure_spatial.py`). This list applies **exactly those two tests**, run as one read-only query against the kiosk's PostGIS. A loose box around Coquitlam cut the query size first; all 84 geometries filed under the City of Coquitlam fell inside it.
- **Labels are the vendor's own.** `RoadClosureType` is a single power of two. The site's `Framework.min.js` maps each value to its label (table below). Every value seen here is one bit, and the kiosk and the vendor both read the highest bit.
- **"Tier as served today"** is what `road_closure_service.py` gives it now: 262144 → NO ACCESS; 65536, 32768, 16384, or "road closed" / "full closure" in the text → ACCESS ONLY; anything else → N/A. **That mapping is not changed here.** It is the operator's to rule on after reading this.
- **Shown vs ended.** A record whose end date has passed is stored inactive and not served, so 7 past-end ("overdue") records are listed separately below. **Cross-check:** the kiosk served 71 municipal closures after its 20:08 UTC sync; this pull, 31 minutes later, has 71 current ones in Coquitlam's zones.

## Counts: 71 current and served, 7 past their end date, 13 dropped by the spatial tests

| Vendor label | Value | Records | Tier as served today |
|:--|--:|--:|:--|
| Lane(s) Closed | 32 | 46 | N/A (null) ×46 |
| Unknown | 0 | 10 | N/A (null) ×10 |
| No / Minimal Traffic Impact | 2 | 9 | N/A (null) ×9 |
| Alternating Traffic | 2048 | 2 | ACCESS_ONLY (text rule) ×1; N/A (null) ×1 |
| Road Closed - Local Traffic Only | 16384 | 1 | ACCESS_ONLY ×1 |
| Sidewalk Closure | 8 | 1 | N/A (null) ×1 |
| Road Closed - Emergency Access Only | 65536 | 1 | ACCESS_ONLY ×1 |
| Road Closed - No Emergency Access | 262144 | 1 | NO_ACCESS ×1 |

**Every record has a geometry.** Sources: City of Coquitlam 71. **No record has a headline**, so the kiosk card title falls back to the location. Every record uses the same construction map icon.

## Questions for the operator

1. **Filters.** The candidates are Sidewalk Closure (1), No / Minimal Traffic Impact (9) and Unknown (10). Lane(s) Closed is the largest group (46).
2. **"Emergency Access Unspecified" (32768): the vendor contradicts itself.** Its **legend** shares one icon with "No Emergency Access". Its **map overlay code** (`GetRoadClosureOverlayIcon`) draws 32768 with the *With Emergency Access* icon. Our code serves it as ACCESS ONLY. None in Coquitlam today, but the next one will pick one reading.
3. **Tiers the ruling has not covered yet.** Today these are N/A: Lane(s) Closed (46), Alternating Traffic (2), Road Closed - One Direction (0), Intermittently Blocked (0). Their DriveBC counterparts are CAUTION under the operator's DriveBC ruling (SOME_LANES_CLOSED, SINGLE_LANE_ALTERNATING, CLOSED in one direction). Road Closed - Local Traffic Only (16384) is served as ACCESS ONLY. "Local traffic only" is not the vendor's "Emergency Access Only".
4. **The text rule.** "road closed" / "full closure" in the description raises any record to ACCESS ONLY. Today it fires on 1 record, an Alternating Traffic record whose note reads "full closure dec 5".
5. **6 records the City of Coquitlam filed itself are dropped** by the kiosk's spatial tests (last table). They sit on streets at or near the city edge (North Rd, Westwood St, Victoria Dr) or, for Balmoral Dr, inside the city but in no response zone. Why each one falls outside was not checked. Whether the City's own records should be kept regardless of the boundary test is a ruling, not a fix; the list is here so it can be made.

## Value → label (vendor source), with our tier today

| Value | Label | Our tier today | Seen in Coquitlam |
|--:|:--|:--|--:|
| 0 | Unknown | N/A | 10 |
| 1 | Detour | N/A | 0 |
| 2 | No / Minimal Traffic Impact | N/A | 9 |
| 4 | Shoulder Closure | N/A | 0 |
| 8 | Sidewalk Closure | N/A | 1 |
| 16 | Bike Lane Closure | N/A | 0 |
| 32 | Lane(s) Closed | N/A | 46 |
| 64 | Bus Lane Closure | N/A | 0 |
| 128 | HOV Lane Closure | N/A | 0 |
| 256 | Left Turn Closure | N/A | 0 |
| 512 | Right Turn Closure | N/A | 0 |
| 1024 | Buffer Lane Closure | N/A | 0 |
| 2048 | Alternating Traffic | N/A | 2 |
| 4096 | Opposite Side Lane Open | N/A | 0 |
| 8192 | Road Closed - One Direction | N/A | 0 |
| 16384 | Road Closed - Local Traffic Only | ACCESS_ONLY | 1 |
| 32768 | Road Closed - Emergency Access Unspecified | ACCESS_ONLY | 0 |
| 65536 | Road Closed - Emergency Access Only | ACCESS_ONLY | 1 |
| 131072 | Intermittently Blocked | N/A | 0 |
| 262144 | Road Closed - No Emergency Access | NO_ACCESS | 1 |

## Records shown on the kiosk, grouped by label

### Lane(s) Closed (46)

| Feed id | Location | Tier today | Headline | Description | Start | End | Geometry | Flags |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| `muni_4\|72102673\|8096_0` | 1184 Inlet | N/A (null) | -- | -- | 2025-11-13 | 2026-10-04 | Point (1 pts) | -- |
| `muni_4\|78054038\|8096_0` | 1960 Winslow | N/A (null) | -- | -- | 2026-08-24 | 2026-09-23 | Point (1 pts) | -- |
| `muni_4\|76417825\|8096_0` | 225 North Rd (161 m) | N/A (null) | -- | -- | 2026-06-02 | 2026-09-25 | Line (3 pts) | -- |
| `muni_4\|78054973\|8096_0` | 267 Blue Mtn | N/A (null) | -- | -- | 2026-08-19 | 2026-09-19 | Point (1 pts) | -- |
| `muni_4\|72946926\|8096_0` | 3409 Galloway | N/A (null) | -- | -- | 2026-01-09 | 2026-09-30 | Point (1 pts) | -- |
| `muni_4\|66272773\|8096_0` | 3507 Hall | N/A (null) | -- | -- | 2026-04-02 | 2026-09-26 | Point (1 pts) | -- |
| `muni_4\|73244502\|8096_0` | 3630 Harper | N/A (null) | -- | -- | 2026-01-26 | 2026-10-04 | Point (1 pts) | -- |
| `muni_4\|73587211\|8096_0` | 618 Tyndall - on Claremont | N/A (null) | -- | -- | 2026-02-12 | 2026-09-26 | Point (1 pts) | -- |
| `muni_4\|76489415\|8096_0` | 622 Smith (191 m) | N/A (null) | -- | -- | 2026-06-01 | 2026-10-01 | Line (5 pts) | -- |
| `muni_4\|76236684\|8096_0` | 636 Claremont | N/A (null) | -- | -- | 2026-05-19 | 2026-09-20 | Point (1 pts) | -- |
| `muni_4\|65919587\|8096_0` | 636 Tyndall | N/A (null) | -- | -- | 2024-12-13 | 2026-09-19 | Point (1 pts) | -- |
| `muni_4\|76989911\|8096_0` | 753 Edgar | N/A (null) | -- | -- | 2026-06-29 | 2026-09-19 | Point (1 pts) | -- |
| `muni_4\|77671463\|8096_0` | Admiral Crt 94 m west of Palmdale St | N/A (null) | -- | -- | 2026-07-27 | 2026-09-22 | Point (1 pts) | -- |
| `muni_4\|78323171\|8096_0` | Aspen St at Foster Ave | N/A (null) | -- | -- | 2026-09-09 | 2026-09-27 | Point (1 pts) | -- |
| `muni_4\|74544118\|8096_0` | Cedar Dr 324 m southwest of Gilleys Trail | N/A (null) | -- | -- | 2026-03-16 | 2026-09-26 | Point (1 pts) | -- |
| `muni_4\|78231834\|8096_0` | Clarke Rd at Chapman Ave | N/A (null) | -- | -- | 2026-09-14 | 2026-09-18 | Point (1 pts) | -- |
| `muni_4\|78355987\|8096_0` | Como Lake Ave from 73 m east of Emerson St to Hailey St (1.14 km) | N/A (null) | -- | -- | 2026-09-14 | 2026-09-26 | Line (4 pts) | -- |
| `muni_4\|78054260\|8096_0` | Como Lake Ave from Blue Mountain St to Poirier St (2.50 km) | N/A (null) | -- | -- | 2026-09-09 | 2026-09-27 | Line (3 pts) | -- |
| `muni_4\|78355989\|8096_0` | Como Lake Ave from Lillian St to Schoolhouse St (605 m) | N/A (null) | -- | -- | 2026-09-14 | 2026-09-26 | Line (3 pts) | -- |
| `muni_4\|78251224\|8096_0` | Cottonwood Ave 32 m east of Whiting Way | N/A (null) | -- | -- | 2026-09-08 | 2026-09-23 | Point (1 pts) | -- |
| `muni_4\|78356465\|8096_0` | David Ave 264 m east of Lansdowne Dr | N/A (null) | -- | -- | 2026-09-15 | 2026-09-17 | Point (1 pts) | -- |
| `muni_4\|78323159\|8096_0` | David Ave 49 m southeast of Silver Springs Blvd | N/A (null) | -- | -- | 2026-09-21 | 2026-09-23 | Point (1 pts) | planned |
| `muni_4\|78356464\|8096_0` | David Ave 98 m west of Glenbrook St | N/A (null) | -- | -- | 2026-09-16 | 2026-09-17 | Point (1 pts) | -- |
| `muni_4\|77760318\|8096_0` | Daybreak Ave at Spuraway Ave | N/A (null) | -- | -- | 2026-08-04 | 2026-09-30 | Point (1 pts) | -- |
| `muni_4\|77074763\|8096_0` | Dewdney Trunk Rd from Locarno Dr to Mariner Way (264 m) | N/A (null) | -- | TRAFFIC ALERT – Starting Wednesday, July 8, at 7:00 a.m., Dewdney Trunk Road will be closed to eastbound traffic at Barnet Highway, except f | 2026-07-08 | 2026-10-09 | Line (3 pts) | -- |
| `muni_4\|78411530\|8096_0` | Dogwood St at Grover Ave | N/A (null) | -- | -- | 2026-09-15 | 2026-09-30 | Point (1 pts) | -- |
| `muni_4\|78214635\|8096_0` | Ducklow St 25 m north of Smith Ave | N/A (null) | -- | -- | 2026-09-07 | 2026-09-19 | Point (1 pts) | -- |
| `muni_4\|78119593\|8096_0` | Dunlop St 51 m north of Alderson Ave | N/A (null) | -- | -- | 2026-08-24 | 2026-10-03 | Point (1 pts) | -- |
| `muni_4\|77556422\|8096_0` | Gatensbury St from Summit Dr to Willow Way (96 m) | N/A (null) | -- | -- | 2026-07-20 | 2026-10-01 | Line (2 pts) | -- |
| `muni_4\|78398743\|8096_0` | Gilroy Pl at Chapman Ave | N/A (null) | -- | -- | 2026-09-14 | 2026-09-28 | Point (1 pts) | -- |
| `muni_4\|77760459\|8096_0` | Heffley Cres 44 m east of Obelisk Way | N/A (null) | -- | -- | 2026-08-10 | 2026-09-26 | Point (1 pts) | -- |
| `muni_4\|78231835\|8096_0` | Hosmer Crt 27 m north of Dewdney Trunk Rd | N/A (null) | -- | -- | 2026-09-14 | 2026-09-18 | Point (1 pts) | -- |
| `muni_4\|78413110\|8096_0` | Johnson St at David Ave | N/A (null) | -- | -- | 2026-09-17 | 2026-09-29 | Point (1 pts) | planned |
| `muni_4\|78416400\|8096_0` | Kemsley Ave 58 m east of Gardena Dr | N/A (null) | -- | 588 Harrison | 2026-09-16 | 2026-09-30 | Point (1 pts) | -- |
| `muni_4\|78339845\|8096_0` | King Edward St 56 m north of Woolridge St | N/A (null) | -- | -- | 2026-09-16 | 2026-09-16 | Point (1 pts) | -- |
| `muni_4\|78061597\|8096_0` | Lea Ave at Dogwood St | N/A (null) | -- | -- | 2026-08-31 | 2026-09-26 | Point (1 pts) | -- |
| `muni_4\|78306997\|8096_0` | Lougheed Hwy from 42 m east of King Edward St to 94 m west of Woolridge St (327 m) | N/A (null) | -- | -- | 2026-10-01 | 2026-10-01 | Line (2 pts) | planned |
| `muni_4\|78428051\|8096_0` | Marmont St at Brunette Ave | N/A (null) | -- | 1051 James | 2026-09-21 | 2026-10-03 | Point (1 pts) | planned |
| `muni_4\|78339847\|8096_0` | North Rd at Delestre Ave | N/A (null) | -- | -- | 2026-09-16 | 2026-09-16 | Point (1 pts) | -- |
| `muni_4\|78231836\|8096_0` | Pipeline Rd 105 m northeast of Galette Ave | N/A (null) | -- | -- | 2026-09-12 | 2026-09-18 | Point (1 pts) | -- |
| `muni_4\|77287502\|8096_0` | Pipeline Rd; David to Gabriola (136 m) | N/A (null) | -- | -- | 2026-07-13 | 2026-09-20 | Line (3 pts) | -- |
| `muni_4\|77474316\|8096_0` | Quarry Rd 62 m east of Calgary Dr | N/A (null) | -- | -- | 2026-07-22 | 2026-09-27 | Point (1 pts) | -- |
| `muni_4\|78251740\|8096_0` | Sydney Ave 116 m west of Guilby St | N/A (null) | -- | -- | 2026-09-10 | 2026-09-25 | Point (1 pts) | -- |
| `muni_4\|78131839\|8096_0` | Tyndall St 72 m north of Como Lake Ave | N/A (null) | -- | 618 Tyndall | 2026-08-31 | 2026-09-26 | Point (1 pts) | -- |
| `muni_4\|78427934\|8096_0` | United Blvd at King Edward St | N/A (null) | -- | 2 King Edward | 2026-09-21 | 2026-09-26 | Point (1 pts) | planned |
| `muni_4\|78356466\|8096_0` | Woolridge St 182 m west of private driveway | N/A (null) | -- | -- | 2026-09-17 | 2026-09-18 | Point (1 pts) | planned |

### Unknown (10)

| Feed id | Location | Tier today | Headline | Description | Start | End | Geometry | Flags |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| `muni_4\|78123170\|8096_0` | -- | N/A (null) | -- | Oversize/Overweight transport | 2026-09-14 | 2026-09-17 | Line (19 pts) | -- |
| `muni_4\|72028720\|8096_0` | -- | N/A (null) | -- | -- | 2025-11-13 | 2026-09-27 | Line (2 pts) | -- |
| `muni_4\|78099541\|8096_0` | Alderson Ave at Marmont St | N/A (null) | -- | -- | 2026-09-14 | 2026-09-18 | Point (1 pts) | -- |
| `muni_4\|76015825\|8096_0` | Guilby St from Grayson Ave to 49 m north of Alderson Ave (51 m) | N/A (null) | -- | -- | 2026-05-15 | 2026-10-02 | Line (2 pts) | -- |
| `muni_4\|78401046\|8096_0` | Johnson St at David Ave | N/A (null) | -- | -- | 2026-09-17 | 2026-09-19 | Point (1 pts) | planned |
| `muni_4\|73244500\|8096_0` | Mitchell St from 84 m south of Harper Rd to 103 m north of Sheffield Ave (150 m) | N/A (null) | -- | -- | 2026-01-26 | 2026-10-04 | Line (3 pts) | -- |
| `muni_4\|73244500\|8096_1` | Sheffield Ave at Lofting St | N/A (null) | -- | -- | 2026-01-26 | 2026-10-04 | Point (1 pts) | -- |
| `muni_4\|77887030\|8096_0` | Sheffield Ave at Lofting St | N/A (null) | -- | -- | 2026-08-10 | 2026-10-04 | Point (1 pts) | -- |
| `muni_4\|72028712\|8096_0` | Smith Ave at Marshall St | N/A (null) | -- | -- | 2025-11-10 | 2026-09-27 | Point (1 pts) | -- |
| `muni_4\|76686350\|8096_0` | Victoria Dr 314 m north of Cedar Dr | N/A (null) | -- | -- | 2026-06-12 | 2026-09-19 | Point (1 pts) | -- |

### No / Minimal Traffic Impact (9)

| Feed id | Location | Tier today | Headline | Description | Start | End | Geometry | Flags |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| `muni_4\|77309531\|8096_0` | 602 Clarke | N/A (null) | -- | -- | 2026-07-17 | 2026-09-25 | Point (1 pts) | -- |
| `muni_4\|73001054\|8096_0` | 803 North Rd | N/A (null) | -- | -- | 2026-01-12 | 2026-09-19 | Point (1 pts) | -- |
| `muni_4\|73381788\|8096_0` | 820 Dogwood - on Lea | N/A (null) | -- | -- | 2026-02-04 | 2026-09-29 | Point (1 pts) | -- |
| `muni_4\|77430648\|8096_0` | 955 Robinson - Laneway | N/A (null) | -- | -- | 2026-07-20 | 2026-09-25 | Point (1 pts) | -- |
| `muni_4\|77990928\|8096_0` | David Ave 126 m east of Princeton Ave | N/A (null) | -- | Truck access to the site | 2026-08-17 | 2026-09-26 | Point (1 pts) | -- |
| `muni_4\|78132252\|8096_0` | Don Moore Dr from 77 m east of Toronto St to 39 m northwest of Soball St (89 m) | N/A (null) | -- | -- | 2026-08-31 | 2026-09-26 | Line (3 pts) | -- |
| `muni_4\|77430271\|8096_0` | Dunlop St 50 m south of Sunset Ave, to Sunset Ave, to Guilby St (194 m) | N/A (null) | -- | -- | 2026-08-17 | 2026-09-19 | Line (4 pts) | -- |
| `muni_4\|78411531\|8096_0` | Eastwood St 36 m south of Guildford Way | N/A (null) | -- | 1190 Eastwood | 2026-09-21 | 2026-09-25 | Point (1 pts) | planned |
| `muni_4\|78395652\|8096_0` | Queenston Ave 27 m east of Paquette St | N/A (null) | -- | 1385 Paquette | 2026-09-14 | 2026-09-26 | Point (1 pts) | -- |

### Alternating Traffic (2)

| Feed id | Location | Tier today | Headline | Description | Start | End | Geometry | Flags |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| `muni_4\|64629084\|8096_0` | 675 North Rd (121 m) | ACCESS_ONLY (text rule) | -- | 5515441 - full closure dec 5 | 2024-10-01 | 2026-09-19 | Line (2 pts) | -- |
| `muni_4\|77852917\|8096_0` | Glen Dr 97 m east of Johnson St | N/A (null) | -- | -- | 2026-08-10 | 2026-09-23 | Point (1 pts) | -- |

### Road Closed - Local Traffic Only (1)

| Feed id | Location | Tier today | Headline | Description | Start | End | Geometry | Flags |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| `muni_4\|78356339\|8096_0` | Casey St from Cartier Ave to Brunette Ave (95 m) | ACCESS_ONLY | -- | -- | 2026-09-14 | 2026-09-27 | Line (2 pts) | -- |

### Sidewalk Closure (1)

| Feed id | Location | Tier today | Headline | Description | Start | End | Geometry | Flags |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| `muni_4\|72946922\|8096_0` | Victoria Dr from 339 m northeast of Mars St to 52 m west of Mars St (262 m) | N/A (null) | -- | -- | 2026-01-09 | 2026-09-22 | Line (3 pts) | -- |

### Road Closed - Emergency Access Only (1)

| Feed id | Location | Tier today | Headline | Description | Start | End | Geometry | Flags |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| `muni_4\|76165595\|8096_0` | Laval Sq from Laval St to Cartier Ave (93 m) | ACCESS_ONLY | -- | This closure is related to the ongoing development and will be in place for the duration of the project as per encroachment agreement, with  | 2026-05-19 | -- | Line (4 pts) | -- |

### Road Closed - No Emergency Access (1)

| Feed id | Location | Tier today | Headline | Description | Start | End | Geometry | Flags |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| `muni_4\|77112426\|8096_0` | Sproule Ave from end of road to Grant St (132 m) | NO_ACCESS | -- | -- | 2026-07-06 | 2026-10-03 | Line (3 pts) | -- |

## Past their end date (in Coquitlam, stored inactive, not served)

| Feed id | Location | Label | Tier if it were served | Start | End |
|:--|:--|:--|:--|:--|:--|
| `muni_4\|78132255\|8096_0` | Austin Ave at Schoolhouse St | Lane(s) Closed | N/A (null) | 2026-09-02 | 2026-09-05 |
| `muni_4\|78133876\|8096_0` | Harper Rd at Mitchell St | Lane(s) Closed | N/A (null) | 2026-08-28 | 2026-09-11 |
| `muni_4\|78136053\|8096_0` | El Camino Dr 73 m south of Sharpewood Pl | Lane(s) Closed | N/A (null) | 2026-09-01 | 2026-09-14 |
| `muni_4\|73744738\|8096_0` | Mariner Way; Dewdney to Barnet | Lane(s) Closed | N/A (null) | 2026-03-03 | 2026-09-12 |
| `muni_4\|77180704\|8096_0` | 1500 Coast Meridian | Lane(s) Closed | N/A (null) | 2026-07-13 | 2026-09-11 |
| `muni_4\|77599832\|8096_0` | Cape Horn Ave 68 m west of United Blvd | Lane(s) Closed | N/A (null) | 2026-07-29 | 2026-09-13 |
| `muni_4\|78134540\|8096_0` | Leeder St 88 m south of Rogers Ave | No / Minimal Traffic Impact | N/A (null) | 2026-09-01 | 2026-09-16 |

## Dropped by the kiosk's spatial tests (not served), for completeness

| Feed id | Source | Location | Label | Why dropped |
|:--|:--|:--|:--|:--|
| `muni_4\|78131841\|8096_0` | City of Coquitlam | North Rd 64 m north of Rochester St | Lane(s) Closed | outside the city boundary |
| `muni_4\|78132259\|8096_0` | City of Coquitlam | Balmoral Dr 96 m south of Guildford Dr | Lane(s) Closed | inside the city but in no response zone |
| `muni_4\|78323174\|8096_0` | City of Coquitlam | Westwood St at Gordon Ave | Lane(s) Closed | outside the city boundary |
| `muni_4\|78341457\|8096_0` | City of Coquitlam | Victoria Dr 37 m east of Mitchell St | Lane(s) Closed | outside the city boundary |
| `muni_4\|78395658\|8096_0` | City of Coquitlam | North Rd 88 m south of Foster Ave | Lane(s) Closed | outside the city boundary |
| `muni_4\|78427933\|8096_0` | City of Coquitlam | North Rd 77 m south of Foster Ave | Lane(s) Closed | inside the city but in no response zone |
| `muni_4\|78054283\|8099_0` | BC MOTI Gateway | Highway 7 | Unknown | outside the city boundary |
| `muni_4\|78370948\|8099_0` | BC MOTI Gateway | Highway 17 | Unknown | outside the city boundary |
| `muni_4\|78370949\|8099_0` | BC MOTI Gateway | Highway 17 | Unknown | outside the city boundary |
| `muni_4\|78370957\|8099_0` | BC MOTI Gateway | Pattullo Bridge at Front St | Lane(s) Closed | outside the city boundary |
| `muni_4\|77458316\|8099_0` | BC MOTI Gateway | Mary Hill Bypass at Mary Hill Bypass Onramp | Lane(s) Closed | inside the city but in no response zone |
| `muni_4\|77458317\|8099_0` | BC MOTI Gateway | Queensborough Bridge at River Dr | Lane(s) Closed | outside the city boundary |
| `muni_4\|77458540\|8099_0` | BC MOTI Gateway | Howes St at Boyd St | Lane(s) Closed | outside the city boundary |
