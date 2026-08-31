# Punch list #10 — Three test modules have never run in review

| | |
|:--|:--|
| **Status** | OPEN |
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
