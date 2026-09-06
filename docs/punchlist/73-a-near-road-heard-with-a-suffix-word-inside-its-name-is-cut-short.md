# Punch list #73 — A near road heard with a suffix word inside its name is cut short

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🗣️ Parser, near roads |
| **Blocks** | — |
| **Origin** | Live call DISP-2026-5317C5, 2026-09-06 16:39 PDT, seen by the operator on the kiosk |

[← punch list index](../debug_and_qa_punchlist.md)

---

> **Status**: ✅ **Closed 2026-09-06 — the trailing-junk strip now cuts at the last suffix word
> instead of the first (`31c51ee`); the whole-corpus stored-transcript run is unchanged and
> the live call keeps both roads.**

**Seen.** 2573 Diamond Cres, medical aid. The banner read *NEAR A Gate (as heard)*. The
dispatcher said *near Agate Place and Topaz Court*; both are on the map beside the pin.

**Cause.** The STT heard *Agate Place* as *a gate place*, and *Gate* is a street suffix
(Windsor Gate). `clean_location_text`'s trailing-junk strip — meant to turn *Burlington Drive
105* into *Burlington Drive* — cut at the **first** suffix word it found, so *a gate place and
topas crt* became *a gate*, and Topaz Court was gone before the near-road resolver ever saw
it. The resolver then had *A Gate* against the roads within 400 m and, rightly, matched
nothing. Round 2 (*a gate place and topaz court*) went the same way.

**Fix.** The strip cuts at the last suffix word whose remainder holds no further suffix word:
a suffix followed by text with another suffix in it is a street name, not junk. The same
change handles *1234 st laurence street* without the `known_streets` list that was added for
it on 2026-09-02. Five tests in `backend/tests/test_location_clean_trailing.py`, the live
transcript among them.

**Measured.** Whole corpus, stored transcripts, `harness_chain.py --skip-stt`, before
(`f2c01a3`) and after (`31c51ee`): identical — place ok 90.1 %, wrong address 133, near roads
exact 30 / partial 4 / wrong 0. Nothing in the verified corpus had this shape; the live call
does. With the fix the parser yields *A Gate Pl* and *Topas Crt*, which the near-road resolver
matches by spelling to Agate Place and Topaz Court within 400 m and marks *(?)*.

**Live after the next agent restart**; the operator picks the moment.
