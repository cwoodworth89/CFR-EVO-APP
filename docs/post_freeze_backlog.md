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
| 2026-08-31 | Verifying the kiosk was in sync after the session's deploys | `backend/dispatch.log.2026-06-11` and `.2026-06-19` are **tracked in git** — 1.2 MB of rotated dispatch logs. `.gitignore` already carries `*.log` and `*.log*`, but those rules do not apply to files already tracked, so the pattern looks like it covers them and does not. `git rm --cached` both. They also make `git grep` return hits from June for identifiers that no longer exist, which is how they surfaced. |
