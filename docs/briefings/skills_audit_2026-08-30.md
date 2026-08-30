# Skills audit — all 15, read against the code they claim to describe

**Date:** 2026-08-30
**Scope:** every `SKILL.md` in [`.claude/skills/`](../../.claude/skills)
**Why now:** a parser/QA team is being spun up and will load these first.

`docs/review_status_handoff.md` recorded this audit as unfinished: the 2026-08-23 pass checked
skills for stale **paths and constants** but never for **described behaviour that never
existed** — which is how `kiosk-responsive-ergonomics` came to document an `isKioskMode` API
that has never been in the code. This is that second pass.

---

## Method

Three passes, because the first two are cheap and the third is the one that finds things.

1. **Mechanical** — every backticked file path checked against `git ls-files`, every
   `public.<table>` against the live schema, every `symbol()` against the definitions in the
   tree. *Yield: almost nothing.* It flagged gitignored `.mbtiles` archives and data files,
   which are absent by design (CLAUDE.md §3.6). **A clean mechanical pass is not evidence a
   skill is correct.**
2. **Phantom identifiers** — every backticked identifier of 5+ characters checked against the
   **code only**, excluding other Markdown. Excluding docs matters: with `.md` included, every
   identifier "exists" somewhere and the check returns nothing.
3. **By hand** on what pass 2 flagged, plus the runnable commands.

---

## Findings

### 🔴 `hitl-log-analysis` — both core queries were broken and would not run

The worst of the set, and the one a parser team loads first.

| Referenced | Reality |
|:--|:--|
| `confidence_score` | **Column dropped** from `dispatches` by the operator ruling (#54) |
| `created_at` | **Never existed** on `dispatches` — the column is `timestamp` |
| `feedback_notes` | **Never existed** — the column is `review_notes` |
| `[Local GIS Check] Match FAILED` | **No such log tag** anywhere in the codebase |
| `backtest_parser.py --text "..."` | **The script takes no arguments** — no `argparse`, no `sys.argv`. The flag was silently ignored and the full corpus comparison ran instead |

Two of the three bad columns were wrong **the day the file was written**, not stale.

**And the gap that mattered most:** no skill in the entire set mentioned `quality_rating` or
`review_notes` — the operator's own per-call rating and notes. Those outperformed every derived
metric during this session: an inferred accuracy metric put a regression a week early and blamed
the wrong subsystem, while the ratings located it immediately.

**Fixed.** Triage now runs on `quality_rating` and `resolution_note`, a rating-trend query was
added with an explicit warning that the rated set is not a random sample, the phantom log tag is
struck through with the real alternative, and the four real harnesses are listed.

### 🔴 `road-closure-management` — documents a feature that does not exist

Describes a `closure_warnings` array attached to the dispatch payload by
`payload_builder`, produced by buffering the route corridor 100 m and intersecting active
closures — with a worked JSON example that reads as observed output.

`closure_warnings` **appears nowhere in the codebase**, and no corridor collision check runs.
Marked as a specification rather than behaviour.

### 🔴 `gis-spatial-analysis` §6 — an entire section with no data behind it

LiDAR point-cloud classification, overhead-obstruction flagging (`FLAG_OVERHEAD_OBSTRUCTION`),
WUI fuel-canopy density modelling, floodplain bare-earth mapping, apparatus grade penalties.

**There is no elevation, DEM, HGT or point-cloud data anywhere in the system**, and
`public.roads` has no grade, incline or elevation column. None of the analysis exists.

One claim is not merely unbuilt but **false as written**: §6.2 states *"the routing engine biases
against routes with >15% downhill gradients."* OSRM runs the **stock `driving` profile**, there
is no `.lua` file in the repository at all, and no elevation input exists. Nothing applies that
bias to anything.

This is the same content, with the same problem, as
`docs/emergency_routing_gis_parcels_standard.md` §3.5 — annotated there on 2026-08-29 for the
same reason. Two documents, one fabrication, reached independently.

### 🟠 `emergency-routing-engine` — documents an online Google routing mode

`departure_time`, `traffic_model`, and the Directions endpoint appear nowhere in the code, and
an online routing dependency is contrary to CLAUDE.md §1. Marked as a path considered and not
taken; all routing goes through the local OSRM container.

### 🟡 `performance-metrics-analytics` — one wrong identifier

Stage 4 named `t_publish`; the code uses `t_bcast`, recorded as `bcast_ms`. Corrected.

### ✅ Clean, or already self-correcting

`dispatch-pipeline-ops`, `e2e-dispatch-testing`, `gis-pipeline-sync`, `google-imagery-streetview`,
`kiosk-remote-ops`, `kiosk-ui-audit`, `local-stack-orchestrator`, `mbtiles-tile-server`,
`stt-mlops-backtest`.

**`kiosk-responsive-ergonomics` is the model for the rest.** It opens with a warning naming the
API it used to document that never existed, when that was found, and how it was corrected. My
phantom-identifier scan flagged `isKioskMode` in it — from inside its own correction notice.
That is what a repaired skill should look like.

---

## The pattern

Four of five defects are the same shape, and it is the shape CLAUDE.md §7 exists to prevent:
**a plausible design written in the present tense.** Not one reads as speculative. Each states
what the system does, in the voice of a runbook, for something nobody built.

They are more dangerous than stale paths. A wrong path fails loudly on the first command. A
described-but-absent feature fails silently — an agent reasons from it, produces work that
depends on it, and nothing contradicts them until a crew is affected.

The mechanical checks found **none** of these. Every one came from asking *"does the thing this
sentence describes actually exist?"* and then running a query.

---

## Recommendations

1. **Re-run the phantom-identifier scan in CI.** It is ~30 lines and found four of the five
   defects. Excluding `.md` from the corpus is the part that makes it work.
2. **Skills must cite, not restate.** `hitl-log-analysis` now points at `qa_harnesses.md` and
   `parser_audit_handoff.md` rather than paraphrasing them. A skill that restates a document
   becomes a second copy that drifts — which is how this set got here.
3. **A skill describing something unbuilt must say so in its own voice**, at the top of the
   section, in the present tense. `kiosk-responsive-ergonomics` shows the form.
4. **Nothing was deleted here.** Every unbuilt section is marked and kept, because a design
   someone thought worth writing is worth keeping visible — and because deleting it would hide
   that it was ever believed. Whether to keep or cut §6 of `gis-spatial-analysis` and the Google
   routing section is an operator call, not mine.

## What this audit did not cover

* **Prose accuracy** — procedures were checked for *existence* of what they name, not for
  whether the steps still work end to end. Running each runbook against the live kiosk is a
  separate exercise.
* **The `.claude/agents/` sub-agent definitions**, which were not in scope and have never had
  this treatment.
* **Whether each skill's `description:` triggers correctly**, which needs eval rather than
  reading.
