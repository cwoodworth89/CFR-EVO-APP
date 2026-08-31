# CFR EVO: Review Status & Handoff

**Written 2026-08-23. Read this first if you are picking up the review in a new session.**

Supersedes the 2026-08-21 handoff. The earlier one is preserved in git history.

Companion documents:
* [`docs/debug_and_qa_punchlist.md`](./debug_and_qa_punchlist.md) — index over [`docs/punchlist/`](./punchlist/);
  **68 items, 35 open (22 crew-visible)**. The live work queue
* [`docs/arrival_point_handoff.md`](./arrival_point_handoff.md) — **GIS/geocoder workstream: parcel
  arrival points, the roads import fix, and the ~1,400-site review queue. Start there for that work.**
* [`docs/parser_audit_handoff.md`](./parser_audit_handoff.md) — **scoped handoff for the parser audit**; measured
  corpus baselines, the ground-truth corpus, and three traps. Start there if that is the task.
* [`docs/city_gis_data_register.md`](./city_gis_data_register.md) — **authoritative-data gaps for the City GIS team.** Anything the municipal source gets wrong belongs there, not in code.
* [`docs/standards/README.md`](./standards/README.md) — domain standards index (currently all gaps)
* [`docs/standards/dependency-behaviour.md`](./standards/dependency-behaviour.md) — **verified library semantics; read this before trusting any API name**
* [`docs/architecture/unified_map_surface.md`](./architecture/unified_map_surface.md) — frontend architecture, implemented
* [`CLAUDE.md`](../CLAUDE.md) — architectural rules. **§6 and §7 are the ones that matter.**

---

## Update, 2026-08-30 — XStreets, the two rounds, and the confidence ruling

The body of this document is from 2026-08-23 and remains accurate on system state and
environment. This section records what has changed since, so a new session starts current.

**Operator ruling: the confidence score is scrapped, not recalibrated.** Warnings move to
the amber banner / flag model (§5). No numeric confidence is shown to crews — a location is
either resolved or it carries an explicit warning naming what is uncertain. Punch-list #54
records the measurement behind it; #32 is superseded. The column is being removed in a
separate session.

**A quality regression was found and closed.** The operator's `quality_rating` showed PERFECT
falling 65.3% → 38.4% → 16.1% across three weeks while `FAILED` stayed flat — calls moving
PERFECT → OPERATIONAL, the signature of a *dropped field* rather than a wrong answer. Cause:
the announced "near" XStreets stopped reaching the reconstructed transcript that the operator
reviews against the audio. Both `DispatchData` copies in `phase2.py` omitted
`cross_street_1/2`; the clause had previously survived only because the pipeline was
overloading `intersection` with it. Fixed and deployed.

**Six defects fixed and verified** — see the punch-list section *"Session batch, 2026-08-29/30"*
for the full table with commits and verification: intersections reading back alphabetically,
XStreets missing from the transcript, `sanitize_transcript` deleting `&`, XStreets and
subaddress not coalescing across rounds, street-suffix doubling, and the entrance-seeding trap
(#50, logged not fixed).

**New and open:** #51 (the kiosk labels `intersection` "cross streets" and never reads
`target.cross_streets`), #53 (the agent makes a WAN call to huggingface.co on every start),
#56 (bring XStreets onto the address's resolution path — the fuzzy threshold of 75 is cleared
by a *different real Coquitlam street* for 938 of 1,079 names), #57 (latent candidate-level
parse bleed).

**Built but wired into nothing:** a cross-round comparator and its backtest harness
(`round_comparison.py`, `backtest_round_comparison.py`). Corpus-scored in
[`briefings/round_disagreement_signal.md`](./briefings/round_disagreement_signal.md): of eight
fields only **two** carry signal, five are noise, and two of those point the *wrong way*. The
flag also belongs **after** the geocoder, not at parse time — the geocoder resolves 79% of
parsed-stage disagreements, so flagging early would raise ~77 false alarms.

### The habit that mattered most this session

**Read the operator's `quality_rating` and `review_notes` before any derived metric.** An
inferred address-accuracy metric put the regression a week early and pointed at the wrong
subsystem. The ratings found it immediately. Curtis logs real mistakes there deliberately;
they are ground truth about what went wrong, and no query substitutes for them.

Two corrections from this session are recorded rather than overwritten, because both were
stated confidently before being checked: cross-street "parse bleed" was described as a live
defect and is not (#57), and three transcripts were called broken when the dispatcher had
genuinely said the intersection twice and the reconstruction was correct.

---

## Read this part even if you read nothing else

**Every serious defect found across two days of review was a missing or wrong *source*,
not a coding error.** None of them looked like bugs. They looked like working code:

| What it looked like | What it was |
|:--|:--|
| An intersections table | Pairs of houses within 40 m on differently-named streets |
| A fuzzy "did you mean" | A 4.3 km routing error at confidence 86 |
| A hydrant on the kiosk | Two string literals in the JSX, shown on **every** call |
| A vocabulary list | 96% silently discarded by a token cap |
| A quiet night on the logs | Logging that had stopped recording |

The habits that actually found these, in order of yield:

1. **Measure, don't infer.** Nearly every finding came from a query or a probe, not from
   reading. `token_set_ratio('LOUGHEED HWY', 'ALDERSON AVE & LOUGHEED HWY')` → `100` took
   ten seconds and would have prevented the routing error.
2. **The API name is not the contract** (CLAUDE.md §7.3a). Five defects had this exact
   shape. Check `dependency-behaviour.md` before relying on any library's behaviour.
3. **Verify against the real corpus.** The intersection rebuild was diffed against 24 real
   dispatches; the dispatch-model unification against 421 records with 0 mismatches. Both
   caught things reading would not have.
4. **A wrong conclusion stated confidently is the expensive failure.** Two of my own
   readings were wrong and had to be corrected in the docs (punch-list #25's root cause,
   and "only line 471 needs to change"). Both corrections are recorded rather than
   overwritten. Do the same.

---

## System state, 2026-08-23

Kiosk `tcfire@100.95.146.94`, HEAD `f9069fc` + settings commit. Agent restarted 06:52 and
running current code.

| | |
|:--|:--|
| Backend tests | **92 passed**, 0 failed |
| Frontend | build clean, `lint:crash` clean, src lint **7** (3 React Compiler bailouts, 4 hook-dep warnings) |
| `public.dispatches` | ~430 rows |
| `public.intersections` | **1,784** derived rows, 0 false pairs |
| Punch-list | **18 closed, 9 open** (see below) |

---

## What changed, by subsystem

### GIS / geocoding
* **`public.intersections` is derived from `public.roads` geometry** —
  `backend/scripts/derive_intersections.py`. It was previously built from *parcel
  proximity* and contained 3,086 rows whose streets never meet. 6,499 → 1,784.
* **One canonical zone lookup**: `public.zone_for_point()`. Five inconsistent
  `ST_Contains`/`ST_Intersects` queries existed; `ST_Contains` excludes boundaries and
  zone polygons are bounded *by roads*, so 155 intersections had no map grid.
* **Street suffixes moved to `public.vocabulary`** (`street_suffix`). Two hardcoded
  mappings disagreed — the table stored `SUNSET SQ` while the geocoder normalized to
  `SUNSET SQUARE`.
* **Fuzzy matching demoted to suggestion-only.** There is **no safe similarity threshold**
  for Coquitlam streets: `HAMBER`/`AMBER` score 96 while the corrections worth keeping
  score 95–98. Non-exact matches now return `is_ambiguous`.

### Dispatch pipeline
* **Worker logging fixed** — Python 3.14 changed multiprocessing's default start method to
  `forkserver`, so the worker stopped inheriting logging config and *all* pipeline INFO was
  discarded. This blocked one investigation entirely.
* **Worker supervised** — `worker_supervisor.py`, restart with a crash-loop ceiling.
* **Queue never blocks the listener** — `enqueue_dispatch_task`; a stalled worker used to
  deadlock the audio capture silently.
* **Phase 1 state in `public.dispatch_sessions`**, and recorded *before* broadcast.

### Frontend
* `MapBoard.jsx` **1,184 → ~560 lines**; layers extracted under `components/map/`.
* **One dispatch translation** (`utils/dispatchModel.js`). There were three, and the third
  silently dropped street-section fields on the live path.
* **Kiosk is idempotent on `dispatch_id`** — MQTT QoS 1 is *at-least-once*, so duplicate
  delivery is the contract, not a bug.

---

## Open items, in the order I would take them

1. **#19 — the five unreviewed fuzzy sites.** `address_resolver.py:44` and `:345` are the
   dangerous ones: same `token_set_ratio` subset trap as the intersection defect, but on
   the **main address path**, not just intersections. Highest remaining risk.
2. **#12 — geocoder steps 5/6 overwrite the result address with the requested one**, so a
   street centroid displays like an exact match. Step 4b shows the correct pattern.
3. **#20 / #21** — `TALK_GROUPS` duplicates `public.vocabulary`; the four rail crossings are
   hand-entered where §6.2 already names OSM `railway=level_crossing` as authoritative.
4. **#1 — OSRM profile tuning.** *Blocked*: needs the OSRM docs, and whether `distance`/
   `duration` reflect profile `weight` is unverified. Do not tune without that.
5. **#10, #14, #17, #22** — see the punch-list.

### The documentation pass (planned, not started)

The highest-leverage remaining work. `docs/standards/README.md` lists ten expected sources,
**all currently `NOT HELD`**. Two practical notes:

* **Dependency behaviour can be verified today, offline, from installed source.** That half
  has the better yield-per-effort and needs no procurement.
* **Domain standards need acquiring** — NFPA documents are licensed. Worth knowing before
  an agent burns time trying to fetch them.

Also unfinished: I audited all 15 skills for stale *paths and constants* and fixed three,
but **not** for described-behaviour that never existed — which is how
`kiosk-responsive-ergonomics` came to document an `isKioskMode` API that has never been in
the code. That audit needs reading each skill against the code it claims to describe.

---

## Environment notes

* The kiosk **is** the test machine. Nothing runs locally but standalone scripts.
* **Tailscale SSH lapses** and then hangs silently. If SSH stalls, that is why — the user
  must re-auth in a browser. Use `timeout` on SSH commands.
* Running the suite on the kiosk:
  ```
  set -a && . ./backend/.env && set +a
  export XDG_RUNTIME_DIR=/run/user/1000
  export DATABASE_URL=$(docker exec cfr_api printenv DATABASE_URL | sed 's/@postgres:/@localhost:/')
  PYTHONPATH=services/gis/src:backend .venv/bin/python -m pytest backend/tests \
    --ignore=backend/tests/test_database_integration.py \
    --ignore=backend/tests/test_listener.py \
    --ignore=backend/tests/test_keyword_spotter.py -q
  ```
  * `DATABASE_URL` is **not** in `backend/.env`. Without it `test_04` *skips* rather than
    passes, which reads as green.
  * `XDG_RUNTIME_DIR` is required — importing `cfr_dispatch` pulls in PortAudio.
  * There is no `python` on PATH; use `.venv/bin/python`.
* **A schema change needs `docker compose up -d --build api`, not `docker restart`.**
* Backend changes need `sudo systemctl restart cfr-agent`. **Ask first** — it briefly drops
  the audio listener, so a real call in that window is missed.
* Frontend changes need `npm run build` on the kiosk **and a hard reload** in the kiosk
  browser (`Ctrl+Shift+R`); it caches the old bundle otherwise.
* Do not run state-changing git commands on the kiosk. **Do not force-push** — I did twice
  and had to `reset --hard` the kiosk to recover. Commit fixups on top instead.

### Verifying the kiosk UI

The in-app browser's sandbox **blocks `ws://…:9001`**, so you cannot observe MQTT-driven
behaviour there. Options that work:

* `npm run preview -- --host 0.0.0.0 --port 4173` on the kiosk, then browse
  `http://100.95.146.94:4173` — good for layout and console, not for live dispatch.
* **Ask the user for a screenshot.** They have offered; it is the fastest way to close the
  loop on anything MQTT-driven, and it is how three defects were found.

### Replaying a dispatch safely

Per §6.5, replay a **real historical record** — never synthesise one. Publish to MQTT only,
with `is_test=True` and a `*TEST*` incident prefix; the kiosk then shows
*"SYSTEM TEST / DRILL — NOT A LIVE 911 CALL"*. This writes nothing to the database.
**It appears on the live station display, so ask first.**

---

## Verification harness worth reusing

`frontend/scripts/verify_dispatch_model.mjs` diffs the dispatch translation against a
**frozen copy** of the original over every record in the database (421, 0 mismatches). The
reference copy is deliberately not imported from the app — importing it would make the test
compare the function to itself and pass unconditionally.

That pattern — freeze the old behaviour, run both over the real corpus, diff — is the one
that gave real confidence. Reuse it for anything touching the dispatch path.
