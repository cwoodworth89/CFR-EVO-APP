# CFR EVO: Workspace & Architectural Rules

> [!IMPORTANT]
> **This file is a pointer, not the rules.** The canonical, actively maintained rules for
> CFR EVO live in [`CLAUDE.md`](./CLAUDE.md). Read that file — it covers offline
> architecture, sibling import paths, kiosk deployment, address normalization, and the two
> rules that matter most here: **§6 (no fabricated data, no unsourced constants)** and
> **§7 (start from the source of record)**.

## There is one rules file, and this is not it

The full duplicate ruleset was collapsed to this pointer on 2026-08-20 to stop two copies
of the same rules drifting apart.

The directory-local `backend/GEMINI.md`, `frontend/GEMINI.md` and `services/gis/GEMINI.md`
were missed in that pass and drifted for three weeks. They were **deleted on 2026-08-30**
after an audit found each one mandating behaviour the code had already removed:

* `services/gis/GEMINI.md` required a hardcoded Riverview Hospital coordinate override —
  removed from `geocoder.py`, which cites **§6.2** as the reason. It also gave rules for
  `shapefile_loader.py`, a file that no longer exists.
* `backend/GEMINI.md` presented `FREQUENCY_TOLERANCE_HZ = 8` as what *separates* PA chimes
  from engine tones. `config/dsp.py` says the opposite in its own comments: Engine's 600 Hz
  sits 5 Hz from PA's 595 Hz, **inside** that tolerance, so the two are not separable on it.
  595 Hz is "a liability, not a signature"; the real discriminator is 647 Hz.
* `frontend/GEMINI.md` required review-form audio auto-play, deliberately removed under
  punch-list `#19b`.

Do not recreate them. If a rule is specific enough to belong beside the code, it belongs
**in** the code with its provenance attached (§6.3), where it cannot drift out of sight.

## Where the real answers are

| Looking for | Read |
|:--|:--|
| Architecture, domain rules, deployment | [`CLAUDE.md`](./CLAUDE.md) |
| What governs an operational value | [`docs/standards/README.md`](docs/standards/README.md) |
| What a library actually does vs. its name | [`docs/standards/dependency-behaviour.md`](docs/standards/dependency-behaviour.md) |
| Open defects | [`docs/debug_and_qa_punchlist.md`](docs/debug_and_qa_punchlist.md) — index, one file per item |
| Runbooks | `.claude/skills/` — the single canonical location |

---

Antigravity is no longer used on this project (operator ruling 2026-09-03) and its
delegation section was removed. Claude Code's delegation model is `CLAUDE.md` §4.

<!-- audit-ok: backend/GEMINI.md -- deleted 2026-08-30; this file records why -->
<!-- audit-ok: frontend/GEMINI.md -- deleted 2026-08-30; this file records why -->
<!-- audit-ok: services/gis/GEMINI.md -- deleted 2026-08-30; this file records why -->
