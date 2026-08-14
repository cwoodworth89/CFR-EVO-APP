## 2026-08-14T00:00:27Z
You are Worker M1 Fix 3 Specialist.

Your assigned working directory is: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1_fix3\`

Read the verbatim user request from: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`
Read Challenger 1 Recheck 2's report: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\challenger_m1_1_recheck2\handoff.md` and test script `.agents/challenger_m1_1_recheck2/test_adversarial_recheck2.py`.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Mission: Fix the order of `s.strip(' ,.-')` and unit suffix regex in `_clean_streetview_address` inside `backend/api/server.py`.

Tasks:
1. In `backend/api/server.py` function `_clean_streetview_address`:
   - Strip leading/trailing whitespace and punctuation (`s = s.strip(' ,.-')`) BEFORE matching unit suffix regex.
   - Also allow optional trailing punctuation/whitespace in the unit regex itself: `re.sub(r'[,\-\s]+\s*(?:UNIT|APT|STE|SUITE|#)\.?\s*#?\s*\d+[\w-]*[,\-\s]*$', '', s)`.
   - Strip trailing punctuation again after all unit and city regexes.
2. Run test suites:
   - `python .agents/challenger_m1_1_recheck2/test_adversarial_recheck2.py`
   - `python .agents/challenger_m1_1_recheck/test_adversarial_recheck.py`
   - `python .agents/challenger_m1_1/stress_test_m1.py`
   - `python backend/tests/test_parcels_and_streetview_api.py`
   Verify 100% test pass.

Write report in `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1_fix3\changes.md` and handoff report in `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1_fix3\handoff.md`. Send a summary message when complete.
