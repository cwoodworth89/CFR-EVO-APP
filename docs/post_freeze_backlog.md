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
| 2026-08-31 | Reading `agent_onboarding.md` during onboarding | `agent_onboarding.md` §5 "Toggling Speech-to-Text Engines" tells you to set `STT_ENGINE=google` in `backend/.env` and restart. That does nothing — `STT_ENGINE` is a hardcoded constant in `backend/cfr_dispatch/config/cloud.py:7`, never read from env. The procedure is inert, and it contradicts both the same file's own domain map and CLAUDE.md §1 (no cloud STT). `backend/.env.example:9` and `:14` imply the same env-configurability. |
