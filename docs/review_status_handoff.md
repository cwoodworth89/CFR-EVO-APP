# CFR EVO: Multi-Phase Review — Status & Handoff

**Written 2026-08-21, at commit `9396ebb`. Punch-list reconciled 2026-08-21 at `0db0b75`.**
Read this first if you are picking up the review in a new session.

> [!NOTE]
> **The reconciliation found two live coordinate fabrications in `MapBoard.jsx`; both are
> now fixed** (punch-list #2, reopened and closed the same day). A dispatch with null
> coordinates was being rendered and routed as a valid incident at City Centre, and a road
> closure with no coordinate was being drawn across City Centre although the municipal feed
> never reported one. Null now propagates in both paths.

Companion documents:
* [`docs/decomposition_plan.md`](./decomposition_plan.md) — module-by-module plan, what is done, what remains
* [`docs/debug_and_qa_punchlist.md`](./debug_and_qa_punchlist.md) — 14 numbered open items
* [`docs/development_freeze_summary.md`](./development_freeze_summary.md) — Phases A–F, implementation record
* [`CLAUDE.md`](../CLAUDE.md) — architectural rules; **§6 was written this session**

---

## System status: green

Verified on the kiosk (`tcfire@100.95.146.94`) at 2026-08-21 21:51 PDT:

| Service | State |
|:--|:--|
| `cfr-agent` (audio listener) | active, stream open |
| `cfr_api` :8000 | 200 — `/api/dispatches`, `/api/hydrants`, `/api/road-closures` |
| `cfr_postgres` :5432 | healthy |
| `cfr_osrm` :5000 | 200 |
| `cfr_tiles` :8081 | 200 |
| `cfr_mosquitto` :9001 | healthy |
| `cfr_ntfy` :8080 | 200 |

11 dispatches captured in the last 24h. Zero geocoder errors since the block
interpolation fix. Local and kiosk trees are identical and clean.

---

## What changed this session — 32 commits

### Live defects fixed

1. **Kiosk would not boot.** `ReferenceError: loadingTraining is not defined`, left over
   from the training-mode removal. Plus three temporal-dead-zone bugs, one of which threw
   on *every new dispatch*. None were caught by `npm run build`.
2. **Every live MQTT dispatch arrived with null coordinates.** `useMqttListener.js` read
   `payload.eventType` / `payload.new` (Supabase field names) while the backend sends
   `event` / `payload`. Before this session the null silently became `49.2838, -122.7932`
   — Burlington & Pinetree — so **the kiosk routed every live call to a fixed point in
   Town Centre** and rendered it normally. Removing the coordinate fallback is what made
   it visible. Also meant Phase 2 UPDATE events queued as new calls.
3. **Block interpolation had never worked.** `public.roads.geom` is MULTILINESTRING;
   `ST_LineInterpolatePoint` requires LINESTRING and threw on every call. Step 3 of the
   geocoder cascade silently fell through to coarser steps. Now 3,214/3,214 resolve.
4. **ntfy pushes went to a stale topic.** `backend/.env` carried
   `NTFY_TOPIC=cfr-evo-dispatch-test`; the documented master topic `chief-master` had
   zero messages. Agent and API were also publishing to *different* topics.
5. **Private hydrants showed a fabricated NFPA 291 class.** `sync_hydrants.py` used
   `flow_class or "AA"` — AA being the *highest* class. 853 unrated hydrants were being
   presented to crews as the best available water supply. Now null, rendered `⚠️ UNRATED`.
6. **A dispatch was lost.** `DISP-2026-01DCBC` landed in an orphaned `live_calls` table
   after the rename because `docker restart` reuses the old image. Recovered.

### Fabricated data removed (CLAUDE.md §6)

`CLAUDE.md` §6 was written this session and is the rule the rest follows: **an unknown
reported as unknown is a correct answer; an unknown reported as a number is a defect.**

Removed: default coordinates (`49.2838`), a `'02:30'` ETA placeholder, `['SQ1','E1','L1']`
invented apparatus, `1.2 turns per km`, an EMTRAC rush-hour model, a blanket "downhill"
speed cap, rail-crossing detection by latitude threshold, `custom_places` coordinates up
to 1.8 km off, hardcoded destination overrides, and the `or "AA"` hydrant default.

Routing is now **stock OSRM** — its own `distance` and `duration`, no local physics.

### Architecture

* `public.live_calls` → `public.dispatches`
* Road closures: hand-rolled ray-casting → PostGIS `ST_Intersects`/`ST_Contains`
* Vocabulary: DB-only, no file fallback, fails loudly; `.txt` files deleted, seeded by migration
* Hydrants: new `public.hydrants` table + `/api/hydrants`; JSON deleted
* Audio: 8 storage locations → 2
* `parser.py` (1053 lines) → 6-module package; `DashboardHUD.jsx` (1083) → 5 components

### Guardrails added

* **Pre-commit lint guard** (`.githooks/pre-commit`) blocking only the crash class —
  `no-undef` and use-before-declaration. Proven against the exact bug that took the kiosk
  down: `npm run build` passes it, `lint:crash` blocks it. It caught two of my own
  mistakes during the session.
* Lint 92 → 22 (remaining are `react-refresh` and hook-dependency, non-crash).

---

## Corrections to earlier claims in this session

Recorded because they were stated in commit messages and are wrong:

* **"All 11 test failures are environmental."** False. Verified on the kiosk with PostGIS
  reachable and `librosa` present: identical 11 failures. The pre-existing half was
  verified by stashing; the environmental half was inferred. Real causes in punch-list #8.
* **"Splitting DashboardHUD clears the react-refresh warnings."** It cleared none — they
  were never in that file.
* **"6,488 of 6,499 intersections are unsupported."** Meaningless: the join used raw
  street strings, and `intersections` uses abbreviated suffixes while `roads` uses full
  words, so only 317 rows matched at all. Scope of the false-intersection problem is
  **unknown**, recorded as such in punch-list #9/#13.
* **"All hardcoded coordinate fallbacks have been removed frontend-wide."** False, and
  the most consequential of these corrections. **Two** were missed, both in
  `MapBoard.jsx` — the dispatch target at `:471` and the road closure marker at `:176`.
  Found by re-grepping for the constant rather than trusting the punch-list's ✅.
* **"Only line 471 needs to change."** Mine, from the reconciliation, and also wrong.
  I classified `:176` as an initial map view from a grep line number without reading the
  enclosing function; it was a second fabrication of the same class. **Identify the
  function a hit sits in before judging it** — three of the five `COQUITLAM_CENTER` uses
  in that file really are legitimate map-view defaults, which is exactly what makes the
  other two easy to wave through.
* **"`SatelliteMiniMap.jsx` deleted entirely."** It was removed from
  `VerificationSidebar.jsx` — the actual fix — but the component still exists under
  `components/hud/` and is used by `ActiveDispatchPanel.jsx`. The defect is genuinely
  gone (it early-returns on null coordinates); only the description was wrong.

### Reconciliation outcome (2026-08-21)

All 14 punch-list items were re-checked against the working tree and, where the item
touches data, the kiosk database. **Two items closed, one reopened, eleven confirmed
still open.**

| | Item | Change |
|:--|:--|:--|
| ✅ | #7 custom places | Closed — **obsolete**, the cascade step was deleted, not corrected |
| ✅ | #11 hydrant `or "AA"` | Closed — fixed **and re-synced**: 853/3,390 now null |
| ⚠️ | #2 coordinate fallbacks | **Reopened** — `MapBoard.jsx:471` survived the sweep |

Each status line now records what was actually checked, so `reported` and `confirmed`
stay distinguishable (§6.6).

**A trap worth knowing about before reading punch-list #6**: the `road_closures` table
currently shows 0 rows with `geom` and 103 with a null `hall_id`, which looks exactly
like the PostGIS rewrite failing. It is not. The last ingest ran 20 hours *before* the
`cfr_api` image was rebuilt, so every row predates the new code. The rewrite is confirmed
present in the running container; the first sync after the rebuild is still the first
real test.

---

## Where the review stands

| Phase | Status |
|:--|:--|
| Documentation reconciliation | ✅ done |
| Anti-fabrication rules (CLAUDE.md §6) | ✅ done |
| Stock OSRM baseline | ✅ done |
| Road closures → PostGIS | ✅ done |
| `DashboardHUD.jsx` split | ✅ done |
| `parser.py` split | ✅ done |
| Vocabulary → database | ✅ done |
| Hydrants → database + API | ✅ done |
| Audio store consolidation | ✅ done |
| **Remaining decomposition** | ⏳ `MapBoard.jsx`, `phase2.py`, review surfaces, `MapLayers.jsx` |
| Punch-list reconciliation | ✅ done (3 closed, 11 open) |
| `MapBoard.jsx` coordinate fabrications | ✅ fixed (both) |
| **Final phase: hardening & review** | ⏳ not started |

---

## Next steps

### Low-risk

1. **Helper extraction for `react-refresh`** — move non-component exports out of
   `MapLayers.jsx`, `ActiveAlertBanner.jsx`, `ReviewTable.jsx`, `VerificationSidebar.jsx`.
   Mechanical; clears 14 of the 22 remaining lint issues.
2. **Fix the stale tests** (punch-list #8). One test queries the dropped
   `public.landmarks` and aborts the transaction, cascading into ~6 others. Fixing that
   one likely clears most of the 11.

### Decomposition still open

3. `MapBoard.jsx` — 1155 lines, 52 hooks, densest state container left.
4. `phase2.py` — 464 lines in 3 functions; review with `phase1.py` for duplicated
   broadcast logic.
5. `DispatchReview` + `ReviewTable` + `VerificationSidebar` as one coupled review module.
6. `destructive_parser.py` divergence review — **deferred from the parser split, still open.**

### Final phase — code hardening and review

7. **PA page leakage** (punch-list #14). PA announcements carrying apparatus tones are
   captured as dispatches. Operator is tagging accidental captures with `[PA]` in the HITL
   review notes; once a corpus exists, pull their audio from
   `backend/audio_files/recordings/` by dispatch_id and fingerprint against it.
   Most promising fix: post-transcription retraction — a real dispatch yields units,
   address and map grid under the Locution template; a PA page parses to nothing.
8. **Maintenance/sync script conformance pass** (decomposition plan §4.2). Eleven scripts
   unaudited. Every one reviewed so far carried a real defect. Three questions each:
   does it read/write a file a database table now owns; does it default a missing source
   value; is it destructive on re-run.
9. **`public.intersections` integrity** (punch-list #9/#13). One confirmed false
   intersection; scope unknown. Consider deriving intersections from `public.roads` via
   `ST_Intersects` so false entries become structurally impossible.
10. **Steps 5/6 honesty gap** (punch-list #12) — they overwrite the result address with
    the *requested* address, so a street centroid displays like an exact match. The new
    step 4b shows the correct pattern.
11. **Hook-dependency lint** (7 issues) — needs per-case judgement, changes runtime
    behaviour, do not bulk-edit.
12. **CFR route configuration feature** (PROJECT_IDEAS #6) — blocked on sourcing apparatus
    speeds. Department policy is recorded as offsets from the posted limit (light +10–20,
    general +0–10, heavy 0–+5), which pairs with `public.roads.speed`.

### Verification still owed

13. **Road closure ingest** (punch-list #6) has not been observed through the new PostGIS
    path. Commands and pass criteria are in the punch-list.
14. **Three test modules have never run in review** — `test_database_integration`,
    `test_listener`, `test_keyword_spotter`. "72 passed" is not the full suite.

---

## Environment notes for the next session

* The kiosk **is** the test machine; nothing runs locally but standalone scripts.
* Tailscale SSH needs periodic browser re-auth; commands hang silently when it lapses.
* Running the suite on the kiosk needs:
  `set -a && . ./backend/.env && set +a && export XDG_RUNTIME_DIR=/run/user/1000 && PYTHONPATH=services/gis/src:backend`
* `DATABASE_URL` is not in `backend/.env`; take it from the `cfr_api` container and swap
  `@postgres:` for `@localhost:` when running host-side scripts.
* **A schema change needs `docker compose up -d --build api`, not `docker restart`.**
  A restart reuses the old image — that is how a dispatch was lost this session.
* Do not run state-changing git commands on the kiosk.
