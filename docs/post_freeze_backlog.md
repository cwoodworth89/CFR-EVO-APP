# Post-freeze backlog

Anything discovered **during the freeze** that is not already a punch list item goes here
as **one line**, and is not investigated until the freeze lifts.

This file exists to give the freeze an exit condition. The punch list grew to 68 items
because every hardening pass was also a discovery pass, and discovery has no natural end:
each item found under CLAUDE.md §7 ("find the source") legitimately produces two or three
more. That is correct behaviour for the system and the wrong behaviour for a freeze.

**The rule**: if it is not already in [`debug_and_qa_punchlist.md`](debug_and_qa_punchlist.md),
it does not get worked, characterized, or root-caused now. Write the line. Move on.

**The exception**: a 🔴 crew-visible defect — one that produces plausible wrong operational
output crews cannot detect — is promoted into the punch list immediately. That is the whole
reason the severity column exists.

| Date | Found while | One line |
|:--|:--|:--|
| 2026-08-31 | External call audit | 🔴 **Leaflet marker icons load from `raw.githubusercontent.com` + `cdnjs.cloudflare.com`** — offline, the gold *incident* marker and the blue candidate markers do not render, silently (a failed `<img>` is not a JS error). 6 sites across `BlockParcelPanel`, `PropertySatellitePanel`, `RouteOverviewPanel`. Vendor them into `frontend/public/`. See [`external_calls.md`](external_calls.md) §3.1. **Promotion candidate — awaiting operator call.** |
| 2026-08-31 | External call audit | Road closure daemon (`server.py:129`) hits `open511.gov.bc.ca` hourly and fails silently; the kiosk cannot tell a crew the closure list is stale. §6.1 question, not a coding fix. [`external_calls.md`](external_calls.md) §2.1. |
| 2026-08-31 | External call audit | `backend/.env` still exports `GOOGLE_APPLICATION_CREDENTIALS` for an orphaned GCP service-account key (live `private_key`, project `cfr-dispatch-mapping`). No code reads it; never committed; gitignored. Revocation is a Google console action. [`external_calls.md`](external_calls.md) §7. |
