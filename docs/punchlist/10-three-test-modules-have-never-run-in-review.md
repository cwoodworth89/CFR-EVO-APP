# Punch list #10 — Three test modules have never run in review

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | hygiene |
| **Area** | 🧪 Test Suite Debt |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L485 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 10. Three test modules have never run in review
> **Status**: ⚠️ **Open — unchanged 2026-08-21.** No attempt was made to run them this pass;
> the missing dependencies have not been installed.

`test_database_integration`, `test_listener` and `test_keyword_spotter` were excluded all
session with `--ignore` because `librosa` (local) and `pvporcupine` (kiosk) are missing.
"72 passed" therefore does not represent the full suite. `pvporcupine` is a Picovoice
wake-word dependency that is not installed on the kiosk at all — worth deciding whether
that feature is live before keeping a test for it.

---

## 🚰 Hydrant Data

---

## 10 (closed). None of the three were tests

> **Status**: ✅ **Closed 2026-08-31.** The full suite now runs with no `--ignore` flags:
> **197 passed**.

The premise was inverted. These were not test modules missing their dependencies — they were
**scripts named `test_*`**, and pytest reported collection errors because an import failed,
not because coverage was absent.

Run on the kiosk with `XDG_RUNTIME_DIR=/run/user/1000` (where `geopandas` 1.1.3 and `librosa`
0.11.0 both exist), they collect cleanly and report **"no tests ran"**. Neither file contains
a single pytest function:

| File | Contents | Outcome |
|:--|:--|:--|
| `tests/test_database_integration.py` | 249-line harness, 0 test functions | **deleted** |
| `tests/test_listener.py` | 92-line audio diagnostic, 0 test functions | **deleted** |
| `tests/test_keyword_spotter.py` | wake-word exploration | **deleted** |

**All three were deleted rather than relocated**, and inspecting them is why. Each carried its
own copy of operational constants, already diverged from the live configuration:

* `test_listener.py` held `TONE_FINGERPRINTS` with five peaks per tone
  (`Chief: 429.69, 437.50, 445.31, 656.25, 664.06`) against the two the live
  `config/dsp.py` now uses (`Chief: 440, 660`) — **and no `PA Tone` entry at all**. The live
  config gained `"PA Tone": [595, 647]` on 2026-08-29. Run today it would report PA
  announcements as dispatches, which is punch-list **#14** exactly. That is not clutter; it is
  a diagnostic that reproduces a fixed defect and would convince its reader the fix had failed.
* `test_database_integration.py` held its own `STT_ENGINE`, an `ENABLE_GOOGLE_MAPS_FALLBACK`
  flag for a capability §1 forbids, duplicate shapefile paths and column names, and a
  `STREET_NAME_CONFIDENCE_THRESHOLD = 80` fuzzy cutoff (**#19a** territory). It validated
  against shapefiles directly — the pre-PostGIS architecture §1 eliminated.

A second copy of a tuned constant is worth less than nothing: it cannot be trusted, and it
misleads exactly the person who reached for a diagnostic because something already looked wrong.

So *"72 passed does not represent the full suite"* was the wrong worry. The suite was
complete; these three were never in it, and never could be. While they sat in `tests/` under a
`test_` name, every run showed collection errors and every reader concluded coverage was
missing.

**The keyword spotter is an abandoned direction, confirmed by the operator**: using
"Coquitlam" as a wake word was considered and **tone spotting was chosen instead**. The test
imported `pvporcupine` — installed nowhere, absent from `requirements.txt` — required a
`PICOVOICE_ACCESS_KEY` for a commercial cloud service that §1 forbids, listened on a live
microphone, and exercised no module in this repository; there is no keyword spotter. Deleted
with its 2,944-byte `map_grid_wakeword.ppn`, untouched since June 2025 and referenced by
nothing.

### Recorded so it is not re-proposed: crawling git history for doc drift

The question that led here was whether to mine commit messages for documentation that
contradicts the code. Three forms were tried on 2026-08-31:

| Approach | Findings | Real |
|:--|--:|--:|
| Backticked identifiers in `docs/` absent from the code corpus | 125 | ~3 |
| Column renames and drops parsed from `backend/migrations/*.sql`, old name still referenced | 5 | **0** |
| Commit prose compared against doc prose | not attempted — semantic, and a discovery amplifier during a freeze | — |

The identifier check cannot separate a stale symbol from a street name, a commit SHA, or
`Z_LEVEL` — which appears precisely *because* a document exists to record that it does not
exist. The migration check cannot handle **ordering**: `centroid_lat` reads as dropped because
one migration removed it as a duplicate and a later one recreated it by renaming `lat`. Both
are current columns.

**What actually caught this class was running code, not reading it.** Both casualties of the
`lat` → `centroid_lat` rename surfaced by execution — `pytest` found the `streetview.py` 500 in
80 seconds, and running the import found its own broken verifier. No static crawl would have
found either: `r.lat` is valid Python that fails only when the line executes.

<!-- audit-ok: backend/tests/test_database_integration.py -- deleted 2026-08-31 (5aa72e0); this item is the record -->
<!-- audit-ok: backend/tests/test_listener.py -- deleted 2026-08-31 (5aa72e0); this item is the record -->
<!-- audit-ok: backend/tests/test_keyword_spotter.py -- deleted 2026-08-31 (5aa72e0); this item is the record -->
