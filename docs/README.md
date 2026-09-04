# Documentation map

Start here if you are new. This page says what each document is for and which ones describe
the system as it runs today. The rules for anyone working on the code, person or agent, are in
[`CLAUDE.md`](../CLAUDE.md); this page is the reading order.

## What runs in production, and what only helps development

CFR EVO is one program that runs unattended on a fire-hall kiosk, plus a set of tools that
people use to build, check, and maintain it. The two are kept apart by directory and, inside
`backend/scripts/`, by the sections of its README.

| Area | Production: runs on the kiosk, on its own | Development and testing: a person runs it |
|:--|:--|:--|
| Dispatch agent | `backend/cfr_dispatch/`, `backend/main.py`, the `cfr-agent` systemd unit | `backend/tests/`; `backend/scripts/` sections *QA harnesses*, *STT / MLOps*, *Ad-hoc inspection*, and `oneshot/` |
| API and database | `backend/api/` (Docker), `backend/migrations/` | `backend/scripts/audit_*.py`, `trace_geocode_corpus.py` |
| Sibling services | `services/gis`, `services/audio_analysis`, `services/dispatch_notifications`, `services/mosquitto` | |
| Display | `frontend/`, built once and served by nginx on the kiosk | `npm run lint:crash`, `npm run build` |
| Operator maintenance, run occasionally by a person | `backend/scripts/` sections *Scheduled and routine* (one is in the kiosk crontab), *Municipal data ingest*, *Tiles* | |
| Top-level `scripts/` | | dev-environment installers and `analyze_historical_tones.py`, the tone backtest |

Moving the development tools into their own top-level tree is on
[`post_freeze_backlog.md`](post_freeze_backlog.md), not done: `backup_db.sh` is pinned in the
kiosk crontab by absolute path, most scripts find the package from their own file position, and
fourteen runbooks cite script paths. Until then, the divide is in the READMEs, not the tree.

## 1. Start here

- [`PROJECT_PURPOSE_AND_HISTORY.md`](PROJECT_PURPOSE_AND_HISTORY.md): why this exists, for a reader who has never been inside a fire hall.
- [`../README.md`](../README.md): what the system is and how the pieces fit.
- [`../PROJECT.md`](../PROJECT.md): feature inventory, milestones, interface contracts.
- [`agent_onboarding.md`](agent_onboarding.md): the working guide for anyone touching the code. Commands, SSH to the kiosk, the audio quirk that costs people an hour.

## 2. How it works, as it runs today

- [`call_structure.md`](call_structure.md): what a Coquitlam dispatch broadcast sounds like and how the parser reads it.
- [`architecture/database_and_datastores.md`](architecture/database_and_datastores.md): every table and file the system reads. Two dated corrections at the top; the rest is current.
- [`external_calls.md`](external_calls.md): every code path that leaves the building's network. Nothing is added without an operator ruling.
- [`city_gis_data_register.md`](city_gis_data_register.md): open questions for the City's GIS team about their data.
- [`standards/README.md`](standards/README.md): which published standard governs which number. [`standards/dependency-behaviour.md`](standards/dependency-behaviour.md): what the libraries actually do, checked against their source, where the name suggested otherwise.
- [`privacy.md`](privacy.md): how audio is handled and what is kept.
- [`ntfy_server_access_and_qr_spec.md`](ntfy_server_access_and_qr_spec.md): the push-notification server and how a phone subscribes.
- [`hardware_specification.md`](hardware_specification.md), [`laptop_kiosk_setup.md`](laptop_kiosk_setup.md): the kiosk that exists. Deployment design for more halls is deferred until the code is stable (operator ruling 2026-09-03).

## 3. Operating it

The runbooks are the skills in [`../.claude/skills/`](../.claude/skills), one folder per task,
each `SKILL.md` readable on its own. Two procedures live here instead because they carry their
own history: [`briefings/database_backup_runbook.md`](briefings/database_backup_runbook.md) and
[`briefings/tile_recrawl_runbook.md`](briefings/tile_recrawl_runbook.md).

## 4. Quality and testing

- [`review_status_handoff.md`](review_status_handoff.md): system state and open items in priority order. Read this before debugging anything.
- [`debug_and_qa_punchlist.md`](debug_and_qa_punchlist.md): the open-defect index. One file per item under `punchlist/`; closed items are listed in `punchlist/_closed.md`.
- [`post_freeze_backlog.md`](post_freeze_backlog.md): things found during the freeze that are recorded but not being worked.
- [`qa_harnesses.md`](qa_harnesses.md): how a change is measured against real historical dispatches. There is no synthetic test corpus by rule (`CLAUDE.md` §6.5).
- [`test_procedures.md`](test_procedures.md): the test procedures that exist and the ones that were retired.

## 5. Decisions and history

Read these to learn why something is the way it is. They are not descriptions of current code
unless they say so at the top.

- `briefings/`: one decision or investigation per file. Snapping to the addressed street, base-site rows, the PA tone discriminator, retiring the confidence score, persisting the response type, the roads status filter, which cross-round disagreements matter, how a recording becomes a Whisper training pair, the review of the Valhalla proposal, and the two audits ([2026-08-30 skills](briefings/skills_audit_2026-08-30.md), [2026-09-03 staleness](briefings/staleness_audit_2026-09-03.md)).
- Handoffs, each a snapshot at a date: [`parser_audit_handoff.md`](parser_audit_handoff.md), [`arrival_point_handoff.md`](arrival_point_handoff.md), [`qa_handoff_2026-08-30.md`](qa_handoff_2026-08-30.md), [`qa_handoff_2026-08-31.md`](qa_handoff_2026-08-31.md).
- [`development_freeze_summary.md`](development_freeze_summary.md): the state at the v1.0.0 freeze on 2026-08-20. Sections 3 and 4 are kept current; the phase narrative is historical.
- [`decomposition_plan.md`](decomposition_plan.md): the module-by-module review plan from 2026-08-21, with what landed marked.
- [`milestones.md`](milestones.md): the roadmap as it stood. Some milestones describe features since removed, such as the recruit training simulator.
- [`emergency_routing_gis_parcels_standard.md`](emergency_routing_gis_parcels_standard.md): an unadopted routing proposal, kept together with the review that rejected it.
- [`architecture/unified_map_surface.md`](architecture/unified_map_surface.md): a design proposal for the map layers.

## 6. Ideas

- [`PROJECT_IDEAS.md`](PROJECT_IDEAS.md): the feature backlog and loose ideas.
- [`dispatch_integration_options.md`](dispatch_integration_options.md): how the Locution PrimeAlert dispatch system could be read passively.

## Files here that are not documents

- `cfr_whisper_colab_fine_tuning.ipynb`: the Colab notebook for Whisper fine-tuning; the `stt-mlops-backtest` skill is the procedure around it.
- `complex_sites_for_review.csv`: the entrance-point review queue export, produced by `backend/scripts/export_complex_sites_for_review.sql` (punch-list #49).

## Removed, on purpose

A document that described a system no longer run is deleted rather than kept with a warning
banner (operator ruling 2026-09-04). Git history has them. `gis_endpoints.md` and the
local-stack/DSP walkthrough went on 2026-09-04; eight others on 2026-08-30. Unadopted
proposals are the exception and stay, with their review attached, because a rejected design
that is visible cannot be proposed a second time by accident.

<!-- audit-ok: docs/gis_endpoints.md -- deleted 2026-09-04; this section records it -->
