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

## Antigravity-specific: sub-agent delegation

Claude Code's delegation model is `CLAUDE.md` §4. This section covers only Antigravity's
`invoke_subagent`, which has no Claude Code equivalent.

**The project is in a feature freeze. Delegation is narrowed accordingly.**

1. **Delegate mechanical work**: bulk file edits, test runners, log parsing, tile
   downloads. These have a defined output and a verifiable end.
2. **Do not fan out research.** No explorer/challenger/auditor/victory-auditor chains.
   Their purpose is to find more, and during a freeze finding more is the failure mode,
   not the goal. A previous run of that pattern produced 68 agent working directories and
   2.6 MB of reports; it was archived out of the repository on 2026-08-30 because
   everything of substance in it had already been committed as code or a briefing.
3. **A sub-agent returns a decision, not a report.** Cap it: finding, `file:line`,
   recommended action, confidence. A 50 KB report is a context cost paid twice — once to
   write it, once to read it.
4. **Model tier allocation**:
   * `flash_lite` — deterministic test runners (`feed_recorded_call.py`, `pytest`),
     mechanical renames, dead-code and import pruning, log parsing, linting.
   * `flash` — feature engineering, database migrations, shapefile ingestion, React
     component decomposition, tile pre-caching, API routes.
   * `pro` — DSP STFT/FFT harmonic filter maths, OSRM Lua profile maths, LoRA quantization
     analysis, concurrency deadlock diagnosis.
5. **Anything discovered that is not already a punch-list item** goes to
   [`docs/post_freeze_backlog.md`](docs/post_freeze_backlog.md) as one line and is not
   investigated — unless it is crew-visible (§7.1: *if this is wrong, can crews tell?*),
   which is promoted immediately.
6. **Skill lookup**: `.claude/skills/` before drafting any implementation plan.
