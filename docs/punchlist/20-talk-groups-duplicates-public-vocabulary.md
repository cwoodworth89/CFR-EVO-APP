# Punch list #20 — `TALK_GROUPS` duplicates `public.vocabulary`

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🧱 Duplicated & Unsourced Frontend Constants |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L877 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 20. `TALK_GROUPS` duplicates `public.vocabulary`
> **Status**: ⚠️ **Open — found 2026-08-22 during the MapBoard decomposition.**

`frontend/src/components/review/verificationConstants.js` hardcodes eight talk groups.
`public.vocabulary` category `radio_channel` holds **the same eight**, and is what the
dispatch parser matches against. They have already drifted in format:

| Database | Frontend |
|:--|:--|
| `Talk Group 5 Coquitlam` | `5` |
| `Talk Group 10 Combined Response Coquitlam` | `10 Combined Response` |

Same defect class as the street-suffix vocabulary moved into the database earlier the same
day: two hand-maintained lists of one fact, free to diverge, with nothing reporting it when
they do. The operator's HITL dropdown reads the hardcoded list while the parser reads the
database, so a talk group change corrects one and not the other.

**Fix**: serve `radio_channel` from the API and have the sidebar consume it, as the kiosk
already does for hydrants. Left in place rather than changed as a side effect of a lint
extraction; the constant now carries a comment saying so.
