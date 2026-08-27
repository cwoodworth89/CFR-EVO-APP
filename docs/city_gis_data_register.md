# Register: open questions for the City of Coquitlam GIS team

**Started 2026-08-26.** One place for authoritative-data gaps that we cannot fix ourselves,
because the fix belongs in the municipal source rather than in our code (CLAUDE.md §6.2).

Until now these were scattered through `docs/debug_and_qa_punchlist.md` mixed in with code
defects, which made them easy to lose and impossible to hand to anyone at the City as a
list.

## How to use this

* **Every entry must be measured, not suspected.** Include the query or file check that
  produced it, so the City is given evidence rather than an impression.
* **Rule out our own bugs first.** A name we fail to match is far more often our
  normalization than their data — see the Deer's Leap entry below, which looked exactly
  like a missing street and was an apostrophe. An item goes to the City only after we have
  checked the source file and our own matching.
* **Record the workaround.** What the system does today in the absence of an answer, so
  nobody assumes the gap is unhandled.
* **Nothing here is fixed by inventing data.** No hand-entered parcels, roads, or
  coordinates. That is what `custom_places` did, with script-generated coordinates up to
  1.8 km off, and it was removed for it. An unanswered question stays visible.

Status values: **OPEN** (needs the City), **ANSWERED**, **OURS** (turned out to be our
defect — kept so the finding is not re-raised), **WONTFIX**.

---

## 1. `Chartwell Rd` — one address, three street names

**Status: OPEN.** Punch-list #47. Raised by the operator from `DISP-2026-EC4501`.

| Source | Street name |
|:--|:--|
| Dispatch audio, per the operator | Chartwell **Rd** |
| STT transcript | Chartwell **Grove** |
| City cadastre (`parcels`, `road_names`) | Chartwell **Green** |

`public.road_names` holds exactly two Chartwell streets — `Chartwell Green` and
`Chartwell Lane (PRIV)`. There is no `Chartwell Rd`, `Road`, or `Grove` anywhere in
`road_names` or `parcels`. House number 3305 is valid and unique on Chartwell Green
(49.317006, -122.787520).

**Ask:** Is Chartwell Green signed, or historically known, as Chartwell Rd? Dispatch is
announcing a name the cadastre does not contain, which suggests CAD and cadastre disagree.

**Workaround:** the system resolves to `3305 Chartwell Green` — the correct location per the
only authoritative source. Crews are routed correctly. The call scores as an address
mismatch in our harness only because ground truth follows the audio.

---

## 2. `627 / 629 / 631 Cottonwood Ave` — a run of missing odd numbers

**Status: OPEN.** Punch-list #41. Raised when the operator could not find 629 in search.

723 parcels match `%Cottonwood%`; **zero** match `629 Cottonwood%`. The neighbours exist and
the gap is three consecutive odd numbers on one side:

```
... 620, 622, 625, 628, [627, 629, 631 MISSING], 633, 635, 637, 639 ...
```

**Ask:** Are 627/629/631 Cottonwood Ave currently addressable properties? A run of three
consecutive odd numbers suggests a real-world cause — lot consolidation, redevelopment,
renumbering — at least as strongly as an export gap.

**Workaround:** the address does not resolve and surfaces as the amber Tier 1 card. Honest,
but the crew gets no location.

**Not yet done our side:** confirm whether they are present in the source `Addresses.shp`.
Until that check is run this could still be an import defect rather than a City gap.

---

## 3. `Coronation Cres` and `Fremont St` — addressed parcels with no road centreline

**Status: OPEN.** Found 2026-08-26.

| Street | Parcels | Inside city | Has map grid | In `roads` | In `road_names` |
|:--|--:|:--|:--|:--|:--|
| Coronation Cres | 7 | yes | yes | **no** | **no** |
| Fremont St | 6 | yes | yes | **no** | **no** |

Both are inside the city boundary and carry map grids, so they are Coquitlam addresses. They
appear in `Addresses.shp` but in neither road layer, under any spelling — checked with
`LIKE '%CORONATION%'` and `%FREMONT%` against both tables.

**Ask:** Should these streets exist in the road centre line file? If they are private, they
carry no `PRIVATE` marker in `road_names` the way others do.

**Workaround:** addresses resolve from the parcel, so crews reach them. What fails is
anything derived from road geometry — block interpolation, and these can never appear as an
XStreet or form an intersection.

---

## 4. `Lougheed Highway` address ranges skip the 2700–2900 block

**Status: OPEN.** Found 2026-08-23, re-confirmed after the full road re-import.

All 45 Lougheed Highway segments are present and all carry address ranges — this is **not** a
missing-segment problem. The ranges themselves have a hole:

```
... 1301-1395 ... 1400 -> 2601 ... 2601-2665 -> 2950/2991 -> 3000-3064
                        ^gap^            ^gap^
                    2561 lands here   2915 lands here
```

Zero segments have a range covering 2915. Two real dispatches landed in these holes:
`DISP-2026-66CAF4` (2915 Lougheed) and `DISP-2026-99F8C4` (2561 Lougheed).

**Ask:** Are the `LEFTBEGIN` / `RIGHTBEGIN` ranges on Lougheed Highway complete? Highway
addresses are where motor-vehicle incidents happen, so gaps there are costly.

**Workaround:** nearest-civic substitution within the same hundred-block — 2915 routes to
2950 Lougheed (35 numbers off), amber-flagged with the substitution stated. Approximate but
honest.

---

## 5. Highway addresses absent from `parcels`

**Status: OPEN.** Related to #4 but a separate layer.

`2915 Lougheed Hwy`, `2911 Lougheed Hwy`, `2561 Lougheed Hwy` and `2925 Barnet Hwy` do not
exist in `public.parcels` at all, though all four were dispatched to.

**Ask:** How are highway-frontage addresses maintained? They appear to be addressed by CAD
but not present in the cadastral address file.

---

## 6. Emergency response zones do not tile the city

**Status: OPEN.** Measured 2026-08-26.

`ST_Difference` of the city boundary against the union of all 134 zone polygons leaves
**0.29 km² uncovered**, of 129.71 km² total (0.22%).

Concretely, two road junctions inside the city resolve to no map grid:

| Junction | Distance to nearest zone | Nearest zone |
|:--|--:|:--|
| Lincoln Ave & Oxford St | 19.8 m | grid 99 |
| Lincoln Ave & Shaughnessy St | 9.1 m | grid 99 |

No other zone lies within 120 m of either, so both unambiguously belong to **grid 99** — the
polygon edge does not quite reach the road.

**Every one of the 65,401 parcels resolves to a grid**, so no property is affected. This is
limited to derived road junctions.

**Ask:** Should the zone polygons tile the city boundary exactly? If the slivers are
intentional, is there a rule for assigning a point that falls in one?

**Workaround:** `zone_for_point()` returns NULL and the grid renders as unknown. We
deliberately do **not** snap to the nearest zone — that would be inventing a grid assignment
(§6.1).

---

## 7. `STATUS` in the road centre line file records ownership, not state

**Status: OPEN — clarification rather than a defect.**

The complete domain across 3,456 features is `OPERATING` (3,214), `PRIVATE` (170),
`MOT` (71), `METRO` (1). There is **no `CLOSED`, `PROPOSED`, or `ABANDONED` value**. All four
describe who owns or has jurisdiction over the road; none describes whether it is in service.

The field name cost us real data: our import filtered `STATUS != 'OPERATING'`, reading it as
"not in service", and silently dropped 242 segments including 45 streets that 1,918 parcels
are addressed on. Fixed 2026-08-26 (punch-list #42).

**Ask:** Is there a separate attribute recording road lifecycle — under construction, closed,
decommissioned? If a road were permanently closed, how would that be represented?

---

## 8. Private-road markers in `road_names` are inconsistent

**Status: OPEN.** Found 2026-08-23.

`public.road_names` marks private roads two different ways — `Princess Crescent (PRIV)` and
`Parkland Drive (Private)` — and some roads flagged `PRIVATE` in the centreline file carry no
marker at all in `road_names`: `Silver Springs Boulevard` (359 parcels), `Riverbend Drive`
(227), `Whisper Way` (193).

**Ask:** Is the parenthetical marker in `road_names` maintained, or is `STATUS` in the
centreline file the authority? We currently treat the centreline file as authoritative.

---

## 9. Five road segments with no name at all

**Status: OPEN — low priority.**

Five features in the centreline file have neither `FULLNAME` nor `ROADNAME`, all
`STATUS=PRIVATE`, four of them `CLASS=PRIV`. They are skipped at import because nothing can
match them by name.

**Ask:** Are these intentionally unnamed (internal strata drives), or is the name missing?

---

## 10. Parcels addressed to park land and landmarks

**Status: OPEN — probably not a defect, worth confirming.**

Some parcels carry a "street" that is a place rather than a road, all inside the city and all
with map grids:

| Street | Parcels | Example |
|:--|--:|:--|
| Pinecone Burke Mtn | 28 | `100 Pinecone Burke Mtn` |
| Addington Pt | 1 | `Addington Pt` |
| Taft Ave | 1 | `Taft Ave` |
| Trans Canada Hwy | 1 | `Trans Canada Hwy` |

Others in the same class have no street type at all: `Fraser River`, `Munro Creek`,
`Deboville Slough`, `Railroad`, `Power Line Rd`, `E/O Pipeline Rd`, `N/O Quarry Rd`,
`S.E. Quarry Rd`.

**Ask:** Are these addressable locations a crew could be dispatched to, or cadastral
bookkeeping for non-addressable land?

---

## Closed items

### `Deer's Leap Pl` — OURS, not a City gap

**Status: OURS.** Found and resolved 2026-08-26.

15 parcels are addressed to `DEER'S LEAP` with no matching road, which looked exactly like
items 3 and 5 above. The road **does** exist: `Deers Leap Place`, 3 segments in
`public.roads`.

The parcels spell it with an **apostrophe** and the road layer does not. Our matching is
exact on the street name, so it fails. This is our normalization gap, not a City data gap,
and it must not be raised with them.

Recorded here because it is the strongest argument for the "rule out our own bugs first" rule
at the top of this document — the shape was identical to a genuine missing street.

**Follow-up on our side:** apostrophe handling in street normalization. Not yet done.
