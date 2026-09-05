# Punch list #69 — A five-digit house number was routed on as if it were a civic number

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🗺️ Geocoding |
| **Blocks** | 0 |
| **Origin** | The Thor/four lead in `post_freeze_backlog.md` (2026-09-05), measured the same day at the operator's request |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 69. "300, zero, zero" became 30000 Lougheed Hwy, and the ladder tried to place 30000

> **Status**: ✅ **Closed 2026-09-05 — step 1b added in `d9dbfb2`, measured on the corpus, tests
> live and pure.** Crew-visible: ten calls in the corpus carried a number no parcel has and
> were placed on a cross-street section or not at all; every one of them now lands on the
> verified parcel.

### The source

No civic number in City of Coquitlam records has more than four digits: `public.parcels`
tops out at 6000 with zero five-digit rows, and the `public.roads` address ranges at 7351.
None of the 565 verified addresses in the corpus has five digits.

### Where five digits come from

Not the dispatcher. Only 4 of 565 raw transcripts contain a five-digit token; the rest are
the sanitiser reassembling the model's digit dictation, the same rule that turns
*"1, 3, 7, 8, Oxford"* into `1378 Oxford`:

| Heard | Became | Verified |
|:--|:--|:--|
| *"300, zero, zero, Lougheed"* | 30000 Lougheed Hwy | 3000 Lougheed Hwy |
| *"29, 8, 8, 3, Robson"* | 29883 Robson Dr | 2983 Robson Dr |
| *"33, 56, 4, court"* (*Thor* heard as *four*) | 33564 Crt | 3356 Thor Crt |
| *"routine 61300 pinetree way"* | 61300 Pinetree Way | 1300 Pinetree Way |

The sanitiser cannot tell these from a real number split across tokens. The parcel table can.

### What was built

`AddressResolver.resolve_overlong_house`, step 1b of the ladder, right after the exact match
fails. Every shorter reading of the number (`overlong_house_readings`: the surplus digit or
two removed, every way) goes through step 1 unchanged, so the street matching and the
map-grid and near-road narrowing all apply. The parcel table decides:

- exactly one reading exists on that street: that parcel, at the substitution tier (70,
  the tier `resolve_nearest_civic` gives its closest substitution), with a note that names
  the dispatched number and the parcel used;
- more than one: ambiguous, each reading a candidate, for the operator to choose on the map
  (CLAUDE.md §5; 29883 Robson Dr offers 2983 and 2988);
- none: the ladder continues as before. *"33564 Crt"* has no street to read against and
  stays unresolved; that pair is hotword coverage (#18).

### Measured

Stored-transcript replay, whole corpus (508 calls), `a0e7f04`: step 1b answered 10 calls,
all placed on the verified parcel at 0 m: 3000 Pinewood Ave, 1121 King Albert Ave, 2665 Cape
Horn Ave, 1145 Inlet St, 3000 Lougheed Hwy, 1178 Heffley Cres, 3098 Guildford Way, 3030 Gordon
Ave, 1300 Pinetree Way, 1457 Hockaday St. Since 2026-08-01, against the after-#67 row:

| Since 2026-08-01, n=303 | Before | After |
|:--|--:|--:|
| Placed exactly | 254 | 257 |
| Approximate (a section, no address) | 5 | 3 |
| Wrong street | 21 | 20 |
| Resolved by a cross-street section | 6 | 0 |
| Unresolved | 19 | 18 |
| Place ok | 90.7 % | 91.7 % |

The other six of the nine August calls were already reaching the right parcel through round
2 (#44a); step 1b now answers them from round 1 as well.

### The assumption, and the ruling

The step assumes CFR is never dispatched to a legitimate five-digit civic address. Port
Coquitlam, Port Moody, Burnaby and New Westminster are four-digit cities; Pitt Meadows,
Maple Ridge and Surrey are five-digit. **Operator ruling 2026-09-05:** dispatches outside the
city are one or two in the department's memory and are not handled. A real five-digit
address would only resolve here if a shorter reading of it existed on a Coquitlam street of
the same name, and would carry the note and the 70 tier; on Lougheed Hwy, the shared
arterial, no reading of 19xxx-24xxx exists (Coquitlam's Lougheed runs 502-3064). Falsifier:
a verified address with five digits.

### Found on the way

The harness attributed every step 1b answer to step 1, because the tracer logs a step after
it returns and step 1b runs step 1 inside it; the same ordering meant that with #44a
geocoding every round, the first hit could belong to a round not chosen. `winning_step` in
`harness_chain.py` now takes the last hit carrying the final address (`a0e7f04`). The two
rows recorded at `d9dbfb2` are annotated.

### Tests

`test_overlong_house_readings.py` pins the readings of the real numbers.
`test_address_resolver_db.py` runs 30000 Lougheed Hwy (one reading), 29883 Robson Dr
(ambiguous), 33564 Crt (nothing) and a four-digit number (not this step) against the kiosk
database. 234 tests pass.
