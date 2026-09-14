# Punch list #84 — `KNOWN_BUILDINGS`: eight hand-coded buildings override console pins, three of them wrong

| | |
|:--|:--|
| **Status** | OPEN — operator ruling 2026-09-13: remove it; not built |
| **Severity** | 🔴 crew-visible — on the **console** (workstation). The dispatch display does not use it. |
| **Area** | 🖥️ Console · 🗺️ Location data |
| **Origin** | Noticed during the #82 data-source review, 2026-09-13. Operator: *"I feel like I didn't make that."* |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What it is

`frontend/src/components/MapConstants.js` exports `KNOWN_BUILDINGS`: eight entries, each a name,
an address, aliases, and coordinates, commented *"Pre-configured building names, exact tower
footprints, and verified front-entrance routing access points"* and *"Exact West Tower Footprint
for 2968 Glen Dr"*. None of it cites a source.

It arrived in commit `51026b4`, 2026-07-26 22:55, *"add KNOWN_BUILDINGS registry with Grand
Central 2 front entrance routing on Glen Dr"*. Every commit in this repository carries the
operator's git identity, so git cannot say whether a person or an agent session wrote it; the
operator does not recall making it.

## What it does

`enrichAddressWithBuilding` (`frontend/src/components/map/mapGeometry.js`) runs on **every console
target**, including a live dispatch arriving on the console (`MapBoard.jsx` `updateTargetAddress`):
when the address contains a building's name, address or alias, the target's **coordinates and
address text are replaced** with the list's. The match is a substring test, so `2978 Glen Dr 1001`
matches `2978 GLEN` and loses its unit. The console address search also lists the entries
(`LeftSidebar.jsx`).

## Measured against the City's lots, 2026-09-13

| Entry | Address | Its point |
|:--|:--|:--|
| Grand Central 1 | 2978 Glen Dr | **107 m from its lot, on another lot** (1200 Glen Pine Crt / 2975–2979 Glen Dr) |
| Grand Central 3 | 2975 Atlantic Ave | **60 m from its lot, on the Mura lot** (2980 Atlantic Ave); identical coordinates to Mura's |
| Obelisk | 1178 Pinetree Way | **no such address in City records**; the point is on 1188 Pinetree Way |
| Grand Central 2 | 2968 Glen Dr | 20 m from its lot, on the street |
| 1386 Coast Meridian Rd | 1386 Coast Meridian Rd | 21 m from its lot, on the street |
| Celadon (Windsor Gate) | 3102 Windsor Gate | inside its lot |
| Mura | 2980 Atlantic Ave | inside its lot |
| Coquitlam Town Centre Park | 1299 Pinetree Way | inside its lot |

None of the eight has an operator-set arrival point (#49).

## The change (operator ruling 2026-09-13)

Delete `KNOWN_BUILDINGS` and the override in `enrichAddressWithBuilding`, and the search's use of
it; the console then shows the City lot or the geocoder's answer, as the dispatch display already
does. A building whose entrance matters gets an **operator-set arrival point** on its base-site
row (#49), attributed and dated — the mechanism that exists for exactly this. It is the same class
of data `custom_places` was removed for (#7): hand-entered coordinates with nobody behind them.
