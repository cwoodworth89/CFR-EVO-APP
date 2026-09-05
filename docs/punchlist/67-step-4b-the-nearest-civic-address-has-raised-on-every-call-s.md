# Punch list #67 — Step 4b, the nearest civic address, has raised on every call since the parcel column rename

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🗺️ Geocoding |
| **Blocks** | 0 |
| **Origin** | Found 2026-09-05 by a traceback printed during the hotword holdout run of `tools/harness_chain.py` |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 67. The statement said `centroid_lat`; the code asked the row for `lat`

> **Status**: ✅ **Closed 2026-09-05 — fixed in `56a68a5`, live-schema test added, measured on the
> corpus.** Crew-visible: a dispatched number the City does not have was placed at the street
> centroid with no note, when the nearest civic address with a "Verify on arrival" note was
> the designed answer.

### What happened

`resolve_nearest_civic` in `services/gis/src/gis_service/address_resolver.py` selects
`p.centroid_lat, p.centroid_lng` and then reads `row['lat']` and `row['lng']`. SQLAlchemy
raises `NoSuchColumnError`, the step's own `except` logs it and returns `None`, and the ladder
falls through to the street centroid. It has done that on every call since `be0e7bf`
(2026-08-30) renamed the parcel columns. #62 was the same rename missed in step 5; this is the
second statement, found six days later by the same route: a harness run printed the traceback.

The evidence was already in every harness row recorded today: no `resolved_by` count ever
showed `4b-nearest-civic`. Nobody read it that way until the traceback named the column.

### Measured

Stored-transcript replay of the 303 verified calls since 2026-08-01 (`--skip-stt`), before
(`8b962b8`, 06:48) and after (`56a68a5`):

| | Before | After |
|:--|--:|--:|
| Resolved by step 4b, nearest civic | 0 | 2 |
| Resolved by step 5, street centroid | 5 | 3 |
| Place bucket *approximate* | 7 | 5 |
| Place bucket *house-number* | 0 | 2 |

The two are `2905 Lougheed Hwy` (DISP-2026-997FB0) and `2929 Lougheed Hwy` (DISP-2026-10A8DC),
both in #64's table as numbers the City's address layer lacks. Each now routes to
`2950 Lougheed Hwy`, the nearest civic number in the block, at confidence 70 with the
substitution note, instead of the average of every parcel on Lougheed Highway at confidence
50 with no note. The 0 m distance in the harness says nothing here: the verified address
resolves the same way.

### Fix and test

The two reads now name the columns the statement selects. The remaining `row['lat']` reads in
the resolver were checked: every other statement aliases `AS lat`.
`test_address_resolver_db.py::test_nearest_civic_statement_is_valid_against_the_live_schema`
picks a house number the City does not have, one above a real parcel in the same 100-block,
and runs the step against the kiosk database beside the two #62 tests.
