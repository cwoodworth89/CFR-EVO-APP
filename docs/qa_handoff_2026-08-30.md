# QA Handoff — 2026-08-30

**Read this first if you are picking up the QA/debugging thread.** Companion to
[`review_status_handoff.md`](./review_status_handoff.md), which is still correct on
architecture and environment; this covers what changed in the 2026-08-23 → 08-30 QA session
and what is still open.

The live work queue remains [`debug_and_qa_punchlist.md`](./debug_and_qa_punchlist.md), now an
index over [`docs/punchlist/`](./punchlist/) — **68 items, 35 open**.

---

## How this session worked, and how to keep working

The operator (Curtis — 15-year firefighter, the domain authority) reports issues from live
operation and review sessions. The standing mode was: **log it, characterise it read-only,
fix only when asked.** That held for most of the session and is a good default — but he
approves work directly and often, so ask rather than assume when a fix looks obvious.

**The single habit that produced every real finding: measure, do not infer.** Nearly every
defect below was found by a query or a probe, and several of my *own* confident explanations
were wrong and had to be withdrawn:

| I claimed | It actually was |
|:--|:--|
| Cadastral crawl is slow because the City's server is slow | Our own `RateLimiter`, pinned at exactly 5 req/s |
| 25% of high-confidence calls had corrected addresses | ~8%; the rest was suffix expansion I had not normalised |
| The 176k blank tiles are dead weight, purge them | 80% of the whole archive is blank by design; keeping them is correct |
| The tile gap was a crawl failure | A hardcoded bbox constant, matching my measured cut to 4 decimal places |

**Every one of those corrections is recorded in the punch list rather than overwritten.** Do
the same. A wrong conclusion stated confidently is the expensive failure here.

---

## What shipped this session

| Item | State |
|:--|:--|
| **#14** PA page leakage | ✅ **Enforcing.** 647 Hz discriminator, 25/25 on confirmed ground truth, 0 real dispatches affected |
| **#30/#31** `response_type` | ✅ Persisted; numeric codes deleted system-wide; UNKNOWN is its own amber state |
| **#33/#36** review form | ✅ Fabricated example placeholders and double-click autofill removed |
| **#34** phantom UPDATED badge | ✅ Only fires on a real visible change, and names the fields |
| **#39** review row | ✅ Verified values shown in amber bold, system hypothesis on hover |
| **#40** basemap gap | ✅ **Closed.** 28% of the city had no basemap above z16; re-crawled, verified |
| **#42** roads STATUS filter | ✅ Closed by another agent |
| **#43** blank-tile semantics | ✅ Documented; failure logging raised to WARNING |
| **#45** `confidence_score` → review flags | ✅ **Shipped and deployed** |
| **#46** 22 GB API image | ✅ **Closed.** 1.27 GB; 223 GB reclaimed |

### The two most consequential findings

**`response_type` was parsed, used, and then dropped before the database (#31).** Every
dispatch rendered *routine*, including all 343 emergency ones in the corpus. The parser was
fine; the value died in local scope in `payload_builder.py`.

**`confidence_score` was a metadata-completeness score labelled as confidence (#45).** The
geocoder's score minus 30 for no coordinates, 20 for no units, 15 for no grid, 15 for no talk
group. A correct address with an untranscribed talk group scored 85; a confidently *wrong*
address scored 100. Replaced by named flags in `target.review_flags`.

**Both are the same defect.** So is the bug the operator's question caught in my own
replacement — I wrote flags to the top level of the payload, where the API silently drops them,
so the feature was dead on arrival. **When a value seems missing, trace it end to end rather
than trusting that it is stored.**

---

## Open items, in the order I would take them

1. **#47 — basemap licensing.** *Operator decision, not a code task.* ~789k Carto and ~431k
   Esri tiles bulk-cached with nobody having read either provider's terms. No keys involved and
   nothing watermarked — the exposure is redistribution rights. The operator has asked for a
   high-level review of which map sources the system should use; that belongs here.
2. **#35 — Street View.** Blocked on one thing: **the kiosk browser console (F12) with a call
   active.** Key, build and WAN all verified good, so the API-key theory is dead. Fix the
   indistinguishable-failure problem regardless of cause.
3. **#30 — amber border trigger set.** Should be driven by the #45 flag list, *not* a second
   parallel mechanism. `RESPONSE_TYPE_UNKNOWN` already exists as a flag. Two independent
   notions of "needs attention" is the defect #45 removed.
4. **#37 — close button vs timer timeout.** Timeout → map; Close → previous screen.
   `dismissActiveCall` is shared by both paths, and `App.jsx:52-54` force-resets `returnMode`.
5. **#38 — parcel front points.** *Another agent has this.* Do not double-work.
6. **#44** stale-chunk kiosk crash → deferred to `PROJECT_IDEAS.md #10`.

---

## Things that will bite you

**Deploy order for schema changes: code first, then migrate.** I did it backwards and opened a
~40-minute window where the running API mapped a dropped column. Nothing arrived, but that was
luck.

**A frontend deploy is not finished until the kiosk tab is hard-reloaded** (`Ctrl+Shift+R`).
`npm run build` deletes the previous hashed chunks; an open tab then holds a stale
`index.html`. `KioskView` is lazy-loaded, so it fails **only when a call arrives**. This caused
a real crash mid-dispatch on 2026-08-29.

**Use explicit paths with `git add`, never `-A`.** Multiple agents work this repo
concurrently. I twice swept another agent's untracked files into my commits.

**`sudo systemctl restart cfr-agent` drops the audio listener ~10 s.** Ask first.

**A schema change needs `docker compose up -d --build api`.** Now fast (1.27 GB); it used to
stall ~10 minutes.

**Clean up background tasks.** I left six SSH polling loops running against the kiosk.

**Tailscale SSH lapses silently.** Always `timeout` your SSH commands.

**`XDG_RUNTIME_DIR=/run/user/1000`** for anything importing `cfr_dispatch` — or load config by
path, as `backfill_tone_spectra.py` does.

---

## Verified state at handoff

```
Backend tests      203 passed (+26 review-flag tests)
public.dispatches  513 rows, confidence_score column DROPPED
Tiles              4 archives, all Integrity: ok / journal_mode delete
API image          1.27 GB   |  Disk free 395 GB
cfr-agent          active, PA/hum rejection ENFORCING
Backup             cfr-critical-20260829-200615.sql.gz (verified, 507 dispatches)
```

**Watch for this**: any `REJECTED:` line in `backend/dispatch.log` naming a *real* dispatch
means the PA filter has a false positive. Revert is one flag
(`REJECT_NON_DISPATCH_ENFORCE = False` in `config/dsp.py`) plus a restart.

```bash
ssh tcfire@100.95.146.94 "grep 'REJECTED:' /home/tcfire/CFR-EVO-APP/backend/dispatch.log"
```

`flagged_dispatches` reads 0 until the first new call — existing rows were never scored. That
is expected, not a fault.

---

## Reference

Briefings written this session, all in `docs/briefings/`:
`pa_tone_discriminator.md` · `replace_confidence_with_flags.md` · `tile_recrawl_runbook.md` ·
`roads_status_filter.md` · `response_type_persistence.md`

New tooling: `backfill_tone_spectra.py` (reconstruct tone spectra from archived audio) ·
`read_dbf.py` (shapefile attributes without GDAL) · `export_tile_coverage.py`
