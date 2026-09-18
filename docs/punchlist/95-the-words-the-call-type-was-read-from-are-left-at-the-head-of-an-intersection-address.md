# Punch list #95 — The words the call type was read from are left at the head of an intersection address

| | |
|:--|:--|
| **Status** | **FIXED and RUNNING** — `f91bdedd` on the kiosk, `cfr-agent` restarted by the operator 2026-09-18 16:44 PDT; **the call itself re-recorded** with `tools/reparse_dispatch.py` (`75dfe724`) at 16:51 PDT: row 822 now carries David Ave & Genest Way at 49.29292 / −122.78590 and an E4 route. The three older calls stay as captured (operator). Not seen rendered; the next intersection call with a qualified incident is the live falsifier |
| **Severity** | 🔴 crew-visible — the kiosk showed LOCATION UNRESOLVED for a live wildland call whose intersection is in `public.intersections` |
| **Area** | 🎙️ Pipeline · sanitize / parser |
| **Origin** | Operator, 2026-09-18, live call `DISP-2026-A018E9` (E4, Wildland Fire – Smouldering, David Ave & Genest Way): "see why it failed to place the correct marker? I'm seeing smouldering getting heard twice? Duplicated?" |
| **Related** | #91 (the same "unknown is not a value" rule, for closures) · `backend/migrations/2026-09-11c` (the alias this rests on) · `docs/post_freeze_backlog.md` 2026-09-18 (the qualifier-window caveat) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

Raw transcript (STT, both rounds identical): *"coquitlam engine 4 respond routine wildland fire
smoldering david avenue and genest way near david avenue and genest way use talk group 5
coquitlam map grid 88"*. Heard right.

Sanitized: *"…wildland fire - smouldering, **smoldering** david avenue and genest way, near
**smoldering** david avenue and genest way…"*. `target.address` = "Smoldering David Avenue And
Genest Way", lat/lng null, no candidates. The display showed the amber Tier 1 card, correctly
for a null — the defect is upstream of it. "Twice" is not a duplicate: the raw text is the
two-round broadcast, and the sanitized line carries the word in the address *and* the near copy.

`DAVID AVE & GENEST WAY` is in `public.intersections` (49.29292, −122.78590, derived): the
geocoder had the answer and was handed a string it could not match.

## Root cause (pipeline-core-engineer, reproduced)

`backend/cfr_dispatch/parser/announcement.py:77–82` (pre-fix) isolated the address by a
substring loop over `CALL_TYPES` **canonical spellings only** — no aliases, no qualifier
naming — while the record's call type came from `match_incident_type` →
`_name_the_qualifier` (`call_types.py:88`, `:142`), which has both. With the STT writing
"smoldering", `"wildland fire smouldering"` was not in the text, the loop fell through to
`"wildland fire"`, and the address began one word early. The near segment did not fail on its
own: `announcement.py:171–174` copies the intersection legs to the cross streets and
`reconstruct_template_transcript` (`:417`) rebuilds "near" from the intersection.

Spelling was the trigger, not the cause: the live vocabulary carries the alias
(`Wildland Fire - Smouldering`, `metadata.aliases = ["Wildland Fire - Smoldering"]`, though
`backend/migrations/2026-09-11c` says none replaces it), so the call type resolved through it;
the address loop never consulted aliases. That migration's "verified by re-parsing" checked the
call type only. House-numbered calls were rescued by the pre-digit strip
(`announcement.py:93–100`, e.g. D36869), so **only intersection addresses were exposed**:
5EC6F0, FC1B29 and E9FD48 had lost theirs the same way.

## Fix — `f91bdedd`

- `call_types.py:142–186` — new `split_incident_type(segment, call_types, aliases)`: one
  decision, the same candidates and qualifier naming as `match_incident_type`; consumes the
  verbatim candidate (canonical or alias, longest first) plus the heard window a qualifier was
  named from; whole words, first occurrence (the old `replace` matched substrings and removed
  every occurrence).
- `announcement.py:72–81` — the loop replaced by that call; the no-match (digit split) branch
  unchanged.
- `backend/tests/test_call_type_span.py` — this transcript against the live vocabulary, plus
  pure cases with the alias present and absent.

After: `call_type="Wildland Fire - Smouldering"`, `intersection="David Avenue And Genest Way"`,
`x_street_1/2 = "David Avenue" / "Genest Way"`; reconstruction "…wildland fire - smouldering,
david avenue and genest way, near david avenue and genest way…". `local_geocode` against the
kiosk DB (read-only): old string → `None`; fixed string → `David Ave & Genest Way`,
49.29292 / −122.78590, confidence 100, one exact candidate — the kiosk would have had a marker.

## Verified / not verified

- Parser and sanitize suites, 14 files: 115 → **125 passed**.
- Parser backtest (`tools/backtest_parser_corpus.py`, 639 verified calls, run locally against
  the kiosk DB, before vs after): **address wrong 148 → 145**; incident, units, map grid,
  talkgroup unchanged. Exactly 4 cells moved, all address, all this class: 5EC6F0, E9FD48,
  FC1B29 WRONG → correct; B5B8DC WRONG → WRONG (its second street was lost by the STT).
  Address by month 70.7 → 71.2, 75.7 → 76.1, 88.5 → 89.3 %.
- The routing table sends a parser-fix confirmation to `stt-mlops-evaluator`; the engineer ran
  the same script over the same corpus, so lead did not spend a second start on a repeat.
- **Not running yet.** The sanitizer and parser run in the `cfr-agent` systemd unit
  (`backend/cfr_dispatch/worker.py:background_worker_loop`, via `phase1.py:114` /
  `phase2.py:178`); `backend/api` imports nothing from `cfr_dispatch.parser`, so **no api
  rebuild — agent restart only**, the operator's.
- Confidence high on the rule and the fix; **medium on the wider path**: it now takes a fuzzily
  named qualifier's window out of an intersection address. No regression on 639 calls, but a
  street word scoring ≥ 80 against a sibling qualifier is how it would go wrong. Backlogged.

## Log

| Date | Event |
|:--|:--|
| 2026-09-18 | Operator brought the call. Lead pulled the record, named the stage (sanitize: transcript right, address wrong), confirmed the intersection row exists, sent `pipeline-core-engineer` as a sub-agent. Reproduced, fixed `f91bdedd`, backtested; lead pushed. Awaiting the kiosk pull and the agent restart |
| 2026-09-18 | **Operator pulled and restarted the agent (16:44 PDT), then: "run the call through the pipeline and have it re-record to the database."** Same sub-agent wrote `tools/reparse_dispatch.py` (`75dfe724`, with its `tools/README.md` row): the worker's own path — `sanitize_transcript` → `split_rounds` → `parse_dispatch_announcement` → `build_dispatch_payload` with `worker.get_shared_validator()`, as `phase2.py:197–200` handles a call whose phase 1 was skipped, `captured_tones` carried from the stored target — then one direct `UPDATE … SET sanitized_transcript, incident_type, responding_units, target WHERE dispatch_id = %s RETURNING id`, rowcount checked. Direct SQL on purpose: `update_dispatch_record` is the API PATCH whose endpoint ends in `publish_mqtt_event("UPDATE")` (`dispatches.py:238`); `notification_service` never imported. Refuses (exit 3) when the re-parse has no coordinates; `--dry-run` rolls back. Run on the kiosk as tcfire from `backend/` in the unit's environment, dry then real: `WROTE id=822`, `run_at` 16:51:41 PDT. **Before → after:** `target.address` "Smoldering David Avenue And Genest Way" → "David Ave & Genest Way"; lat/lng null → 49.292922892751754 / −122.78590405415248; `x_street_1` "Smoldering David Avenue" → "David Avenue"; `x_streets_how` [unresolved, exact] → [exact, exact]; `sanitized_transcript` "…smoldering david avenue and genest way…" → "…david avenue & genest way, near david avenue and genest way…"; `incident_type` and `responding_units` unchanged; `target.routing_metrics` [] → E4 from Hall 4, OSRM 3.99 km, crow 3.16 km, ETA 5 min routine, snap 0.96 m; old target and the three old columns kept under `target.reparsed_from` with `run_at` and commit. **Untouched, confirmed by SELECT:** `raw_transcript`, `timestamp`, `audio_url`/`audio_duration` 43.84, `feedback_submitted` false, `quality_rating` PENDING, every `verified_*` null, `review_notes` null; one row for the id, table 693 rows, max id 822 — nothing created. **Operator on the three older calls (5EC6F0, E9FD48, FC1B29): "Leave them, we'll consider this dispatch the first time it's been fixed."** |
| 2026-09-18 | **One finding from the re-parse, backlogged, not crew-visible.** The geocoder set `review_flags` [LOCATION_SUBSTITUTED] with its own note: "1 junctions exist for this street pair; none of these junctions lie in map grid 88. Select the correct one." Lead measured: the junction is **0 m from both zone 86 and zone 88** — it sits on their shared boundary, and the grid test excludes the boundary (the `ST_Contains` behaviour already in `docs/standards/dependency-behaviour.md`, §7.3a). The dispatch's grid 88 is right; the flag is false. The marker and route are correct, so it stays a backlog line |
