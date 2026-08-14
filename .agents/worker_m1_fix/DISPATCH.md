## 2026-08-13T23:54:27Z
You are Worker M1 Fix Specialist.

Your assigned working directory is: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1_fix\`

Read the verbatim user request from: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\ORIGINAL_REQUEST.md`
Also read Challenger 1's feedback report: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\challenger_m1_1\handoff.md` and test script: `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\challenger_m1_1\stress_test_m1.py`.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Mission: Fix the 2 specific issues identified by Challenger 1 in `backend/api/server.py`.

Tasks:
1. **Address Normalization & Validation (`_clean_streetview_address`)**:
   - Return/raise HTTP 400 Bad Request if the input address is empty, whitespace-only, or cleans to an empty string.
   - Enhance unit cleaning regex to strip unit prefixes with punctuation (e.g., `Unit 101, 3030 Gordon Ave`, `Apt 202 - 3030 Gordon Ave`) and trailing unit suffixes (e.g., `3030 Gordon Ave Unit 101`) cleanly down to `3030 GORDON AVE`.

2. **Concurrency Race Condition Handling (`save_parcel_streetview` & `save_streetview_override`)**:
   - Wrap DB insert/upsert in `try...except IntegrityError:` with `db.rollback()` and fallback retry query for existing row update, preventing HTTP 500 when parallel threads upsert the same new address simultaneously.

3. **Verification**:
   - Run `python .agents/challenger_m1_1/stress_test_m1.py` and `python backend/tests/test_parcels_and_streetview_api.py`.
   - Ensure 100% pass across all test suites.

Write changes in `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1_fix\changes.md` and handoff report in `c:\Users\Curtis\Nextcloud\Documents\Projects\Coding\CFR-EVO-APP\.agents\worker_m1_fix\handoff.md`. Send a summary message when complete.
