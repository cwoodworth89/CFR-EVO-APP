# Punch list #64 — Sixteen dispatched civic numbers are absent from the City's address layer

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🗺️ Geocoding |
| **Blocks** | 1 |
| **Origin** | Found 2026-09-05 by `tools/harness_chain.py`: 22 verified addresses the geocoder could not place exactly |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 64. The dispatcher says a number the City's address layer does not have

> **Status**: 🔴 **Open — a data question for the City (`city_gis_data_register.md` #14), not a
> code defect.** Crew-visible: the kiosk places these on the block or the street, and a crew
> cannot tell that from a parcel.

### Evidence

Of 303 verified addresses since 2026-08-01, the geocoder places 254 exactly and 27 at an
intersection the operator verified as such. The other 22 it places by block (11), street
centroid (5), or not at all (6). The 16 civic numbers among them were checked against
`Addresses.shp` (69,708 rows, the City's own file the parcel import reads) on 2026-09-05:
**none of the 16 is in it.** The import did not drop them; the City does not have them.

| Call | Dispatched and verified | Placed by | Nearest numbers the City has on that street |
|:--|:--|:--|:--|
| DISP-2026-EB9DED | 2833 David Ave | block | 2910, 2925, 2980 |
| DISP-2026-DD939E | 1550 United Blvd | block | 1555, 1539, 1500 |
| DISP-2026-F48EB0 | 4000 Quarry Rd | block | 4141, 4201, 4250 |
| DISP-2026-85DEE7 | 3990 Quarry Rd | block | 4141, 4201, 3748 |
| DISP-2026-F2BF59 | 1734 Eagle Mountain Dr | block | 1735 |
| DISP-2026-EE163B | 1414 Pinetree Way | block | 1413, 1415, 1417 |
| DISP-2026-798FAE | 1101 Pinetree Way | block | 1140 |
| DISP-2026-4C8501 | 1290 Pipeline Rd | block | 1291, 1289, 1287 |
| DISP-2026-87A819 | 629 Cottonwood Ave | block | 628, 633, 625 (punch-list #41) |
| DISP-2026-C6165A | 3062 Lougheed Hwy | block | 3064, 3051, 3025 |
| DISP-2026-49F0E5 | 1378 Oxford St | block | 1377, 1380, 1381 |
| DISP-2026-1CEEA2, 874CDE | 39 United Blvd | street centroid | 995 (nothing below 995) |
| DISP-2026-997FB0 | 2905 Lougheed Hwy | street centroid | 2950, 2991 |
| DISP-2026-10A8DC | 2929 Lougheed Hwy | street centroid | 2950, 2991 |
| DISP-2026-7D227A | 4992 Upper Harper Rd | street centroid | 5000 (the only parcel) |
| DISP-2026-D00EC5 | 1883 Beaty Pl | nothing | no street of that name in `roads` either |

The six the geocoder cannot place at all are a different class and stay out of this item:
`4522 Port Mann Bridge`, `Eagle Mountain Park` and a Lougheed on-ramp are named places, not
civic addresses (backlog: named places); `Pinetree Way` alone is a bare street; `Unknown
Location` is correct as verified; `1883 Beaty Pl` is either outside Coquitlam or a typo in the
verified column.

### What this means

Block placement is the best the data allows for the eleven, and the harness's *approximate*
bucket (classify v2, 2026-09-05) now counts them as what they are rather than as the same
place. The fix is upstream: ask the City whether these numbers exist in a layer the open
data does not carry (large sites, strata, recent assignments), and until then the
entrance-point queue (#49) is where a person pins them.

Register entry: `docs/city_gis_data_register.md` §14.

**Later on 2026-09-05 (#67):** step 4b, the nearest civic address, had been raising on every
call since 2026-08-30. With it answering again, `2905` and `2929 Lougheed Hwy` route to
`2950 Lougheed Hwy` with the substitution note instead of the street centroid. The other
three street-centroid placements (`39 United Blvd` twice, `4992 Upper Harper Rd`) still fall
through: their nearest numbers are in another 100-block, which step 4b refuses by design.
