# The OSRM profile that built the kiosk's routing graph

**Held**: [`car.lua`](car.lua) and [`lib/`](lib/), copied verbatim on 2026-09-08 from `/opt/`
inside the running `cfr_osrm` container. This is the text every routing-profile change cites
by line (CLAUDE.md §7.3a): what OSRM does with a road is what this file says, not what its
name suggests. Nothing here has been modified; the md5 sums below are the check.

| | |
|:--|:--|
| Image | `ghcr.io/project-osrm/osrm-backend:latest`, id `sha256:3ac496ff8fd7e1af53846179d73d06a97f719c8ad2217d008ed868942398665c`, created 2026-08-01T09:26:32Z |
| Version | `osrm-routed --version` → `v26.8.0` (`/opt/OSRM_GITSHA` in the image is empty) |
| Copied with | `docker cp cfr_osrm:/opt/car.lua` and `docker cp cfr_osrm:/opt/lib`, 2026-09-08 |
| Graph | kiosk `backend/data/osrm/vancouver.osrm.*`, every file written 2026-08-14 00:05 PDT; the container's first log line is 07:15:43 UTC the same morning |

```
db4f09652994b1a24389de0f0a6b7719  car.lua
9f87eeaad9a9fadb7d29e99a36aa79ea  lib/access.lua
f51b5340d6132d39a2c43780c809a930  lib/destination.lua
1e52ac35de32022b445208c7bb0fe145  lib/guidance.lua
a4ec83163249c9c8ca36adc43c7658cc  lib/maxspeed.lua
4844871ab24269ac56f4de7d25271de8  lib/measure.lua
29beef094bfda2d03b304597fd53e6c9  lib/obstacles.lua
bdb98c53098e0642a06a7692c8056c05  lib/pprint.lua
bbd48c876a97742e1daac4139b5a755a  lib/profile_debugger.lua
897e5c371ccc698d74996fbd67764979  lib/relations.lua
0638037d900af334719fb78294285723  lib/sequence.lua
aceeaa443acce8c531b025760fdaed0b  lib/set.lua
4e4e1fef8762c56baaf5572bc67526ac  lib/tags.lua
3e656b4a2db68abca73659afcc966ae1  lib/traffic_signal.lua
847641893395b68e9640ff0514c10d08  lib/utils.lua
e7a9e6439845ea9efe7ea4e318217af4  lib/way_handlers.lua
```

## Why we believe this text built the graph

The compose file names no profile and no build script exists in the repository, the shell
history or on the kiosk's disk; the container that ran `osrm-extract` was removed. The
evidence is therefore circumstantial, and it is listed so the next person can weigh it:

1. **The graph was built by this OSRM version.** `vancouver.osrm.properties` is a tar
   archive; its member `osrm_fingerprint.meta` reads `4f 53 52 4f 1a 08 00` — `OSRO` then
   26, 8, 0 — the fingerprint of v26.8.0, the version in the image.
2. **The recorded profile properties are car.lua's.** The `/common/properties` member
   carries the weight name `routability` and the class names `motorway`, `restricted`,
   `tunnel`, `ferry`, `toll` (car.lua lines 21 and 147–149), together with the integer 200 and
   the double 50.0 that `u_turn_penalty = 20` (stored in deciseconds) and
   `max_speed_for_map_matching = 180/3.6` would produce (lines 19 and 27). The shipped
   `bicycle.lua` (`cyclability`) and `foot.lua` (`duration`) produce neither. The byte layout
   of that block is from recollection of OSRM's `profile_properties.hpp` and has **not** been
   checked against the v26.8.0 source (§7.3); the strings are unambiguous, the numbers are not.
3. **Nothing else is there to have been used.** `find /home/tcfire -name '*.lua'` returns
   nothing outside the container; `docker ps -a` shows no build container; the graph files
   are ten minutes older than the container's first start.

**What this does not prove**: an edited copy of `car.lua` with a different speed table would
leave the properties block unchanged. The one check that settles it is a rebuild from this
vendored text with the same image, comparing `vancouver.osrm.enw` and `vancouver.osrm.geometry`
byte for byte against the kiosk's. Do that at the first deliberate rebuild and record the
result here (§7.6).

Re-verify at any time, on the kiosk:

```bash
docker exec cfr_osrm osrm-routed --version
docker exec cfr_osrm md5sum /opt/car.lua
docker exec cfr_osrm sh -c 'head -c 520 /data/vancouver.osrm.properties | tail -c 8 | od -A n -t x1'
```

## The extract the graph was cut from

`backend/data/osrm/vancouver.osm.pbf`, 64,138,175 bytes, written 2026-08-14 00:05 PDT, git-ignored
and shared with the basemap stream. Read with pyosmium on the kiosk, 2026-09-08:

| Header field | Value |
|:--|:--|
| `writingprogram` | `https://download.BBBike.org` — a BBBike custom extract |
| `osmosis_replication_timestamp` | `2026-08-07T23:00:00Z` — the age of the map data |
| bounding box | lon −123.307 … −122.668, lat 48.999 … 49.416 (the City is lon −122.92 … −122.70, lat 49.20 … 49.39) |

`vancouver.osrm.timestamp` on the kiosk is empty even though the header carries a
timestamp. Not explained; recorded (§7.7).

## What the text decides, for the work ahead

Facts from the file, with the line that says so. None of these has been changed, and none
should be without the operator or a measurement (standards index, *Apparatus routing profile*).

* **The weight is `routability`** (line 21): the route minimises duration plus the penalties
  below, not distance. Lines 575–586 in `process_turn` show the alternatives.
* **Speed by highway tag, km/h** (lines 169–188): motorway 90, motorway_link 45, trunk 85,
  trunk_link 40, primary 65, primary_link 30, secondary 55, secondary_link 25, tertiary 40,
  tertiary_link 20, unclassified 25, residential 25, living_street 10, service 15. A `maxspeed`
  tag caps these ([`lib/maxspeed.lua`](lib/maxspeed.lua) lines 5–17 take the minimum). Implicit
  limits default to urban 50 / rural 90 (lines 306–311); the exception table has `ca-on:rural`
  (line 326) and no British Columbia entry.
* **Turn costs**: `turn_penalty = 7.5` s shaped by `turn_bias = 1.075` (lines 37–39, applied at
  lines 564–566), `u_turn_penalty = 20` s (line 27, applied at line 570),
  `side_road_multiplier = 0.8` (line 36), `lane_markings_penalty = 0.75` (line 44),
  `priority_penalty = 0.7` (line 51).
* **Service roads are halved**: `service_penalties` alley, parking, parking_aisle, driveway,
  drive-through 0.5 (lines 191–198); gates and lift gates cost 60 s (lines 200–203).
* **The vehicle is a car**: height 2.0 m, width 1.9 m, length 4.8 m, weight 2,000 kg
  (lines 54–59). [`lib/way_handlers.lua`](lib/way_handlers.lua) lines 524–580 drop a way whose
  `maxheight`, `maxwidth` or `maxweight` is below these, and keep every way above them. A
  pumper or a ladder is not a car; the department's apparatus dimensions are for the operator
  to supply (§7.2), and because they decide which roads disappear from the graph they are
  operational values (§6.3).
* **Emergency-only ways are excluded.** `access_tag_blacklist` contains `emergency` (line 96)
  and `emergency_vehicle` (line 103); `service_tag_forbidden` contains `emergency_access`
  (lines 137–139). A way tagged for emergency vehicles only is unroutable for the car. How many
  such ways lie inside the City is a measurement on the extract (pyosmium, kiosk), not yet made.
* **Turn restrictions are obeyed** (`use_turn_restrictions = true`, line 29) and
  `continue_straight_at_waypoint = true` (line 28) affects via points only; production routes
  two points. Whether an apparatus responding emergency should be routed through a posted turn
  restriction is a question for the operator, not a setting to flip.

Punch-list #1 and the routing brief ([`../../briefs/osrm_routing_agent.md`](../../briefs/osrm_routing_agent.md))
carry the work; the standards index ([`../README.md`](../README.md)) carries the status.
