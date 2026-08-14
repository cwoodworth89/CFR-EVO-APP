# Challenge Report — Milestone 1 (Recheck 2)

## Challenge Summary

**Overall risk assessment**: HIGH

During empirical re-testing of Worker M1 Fix 2's implementation of address normalization (`_clean_streetview_address` in `backend/api/server.py`), an empirical flaw was discovered: when an input address contains trailing commas, trailing periods, trailing dashes, or trailing whitespace following a unit suffix (e.g., `"3030 Gordon Ave, Suite 500-X,"` or `"3030 Gordon Ave, Unit 101,"`), the unit suffix regex anchor `$` fails to match. As a result, the unit suffix is **not** stripped, and the cleaned address retains the unit specifier (e.g., `"3030 GORDON AVE, SUITE 500-X"`).

This violates Requirement 1 and Requirement 2 of the prompt:
1. Trailing commas must be stripped cleanly.
2. Unit suffixes (`Unit #101`, `Ste. 101`, `Apt 202`, `Suite 500-X`) must clean down to the canonical street address (`3030 GORDON AVE`).

---

## Challenges

### [High] Challenge 1: Unit Suffix Cleaning Fails When Input Has Trailing Punctuation or Whitespace

- **Assumption challenged**: Worker M1 Fix 2 assumed that calling `s = s.strip(' ,.-')` at line 569 (after line 568 unit suffix regex `re.sub(r'[,\-\s]+\s*(?:UNIT|APT|STE|SUITE|#)\.?\s*#?\s*\d+[\w-]*$', '', s)`) would clean trailing punctuation properly.
- **Attack scenario**:
  An incoming address format or CAD dispatch payload arrives with trailing punctuation or trailing whitespace after a unit suffix, such as:
  - `"3030 Gordon Ave, Suite 500-X,"` (trailing comma)
  - `"3030 Gordon Ave, Unit 101,"` (trailing comma)
  - `"3030 Gordon Ave, Ste. 101,"` (trailing comma)
  - `"3030 Gordon Ave, Apt 202,"` (trailing comma)
  - `"3030 Gordon Ave, #101,"` (trailing comma)
  - `"3030 Gordon Ave, Suite 500-X."` (trailing period)
  - `"3030 Gordon Ave, Suite 500-X   "` (trailing spaces)

  When line 568 executes, `$` attempts to match the end of string `s`. Because `s` ends with `,` or `.` or ` `, `\d+[\w-]*$` fails to match. Line 568 leaves the unit untouched. Line 569 then strips the trailing comma/space, resulting in `'3030 GORDON AVE, SUITE 500-X'` instead of `'3030 GORDON AVE'`.
- **Blast radius**: Addresses containing trailing punctuation/whitespace after unit suffixes fail to resolve to the canonical parcel record in PostgreSQL `parcels`, causing parcel lookup misses and duplicate database records for unit variations.
- **Mitigation**:
  In `_clean_streetview_address` in `backend/api/server.py`:
  Strip trailing whitespace and punctuation `s = s.strip(' ,.-')` **before** executing regex pattern matching on unit suffixes (or incorporate optional trailing punctuation/whitespace `[,\-\s]*$` into the suffix regex).

---

## Stress Test Results

| Test Scenario / Suite | Expected Behavior | Actual Behavior | Result |
| --- | --- | --- | --- |
| `python .agents/challenger_m1_1_recheck/test_adversarial_recheck.py` | 100% pass on standard unit variants | All 12 variants passed, empty address rejected, 50 workers concurrency passed | **PASS** |
| `python .agents/challenger_m1_1/stress_test_m1.py` | 8/8 tests pass | 8/8 tests passed | **PASS** |
| `python backend/tests/test_parcels_and_streetview_api.py` | All API and model tests pass | All tests passed | **PASS** |
| `3030 Gordon Ave, Suite 500-X` | Clean to `3030 GORDON AVE` | Cleaned to `3030 GORDON AVE` | **PASS** |
| `3030 Gordon Ave, Unit 101` | Clean to `3030 GORDON AVE` | Cleaned to `3030 GORDON AVE` | **PASS** |
| `3030 Gordon Ave, Suite 500-X,` (Trailing comma) | Clean to `3030 GORDON AVE` | Cleaned to `3030 GORDON AVE, SUITE 500-X` | **FAIL** |
| `3030 Gordon Ave, Unit 101,` (Trailing comma) | Clean to `3030 GORDON AVE` | Cleaned to `3030 GORDON AVE, UNIT 101` | **FAIL** |
| `3030 Gordon Ave, Ste. 101,` (Trailing comma) | Clean to `3030 GORDON AVE` | Cleaned to `3030 GORDON AVE, STE. 101` | **FAIL** |
| `3030 Gordon Ave, Apt 202,` (Trailing comma) | Clean to `3030 GORDON AVE` | Cleaned to `3030 GORDON AVE, APT 202` | **FAIL** |
| `3030 Gordon Ave, #101,` (Trailing comma) | Clean to `3030 GORDON AVE` | Cleaned to `3030 GORDON AVE, #101` | **FAIL** |
| `3030 Gordon Ave, Suite 500-X.` (Trailing period) | Clean to `3030 GORDON AVE` | Cleaned to `3030 GORDON AVE, SUITE 500-X` | **FAIL** |
| `3030 Gordon Ave, Suite 500-X   ` (Trailing spaces) | Clean to `3030 GORDON AVE` | Cleaned to `3030 GORDON AVE, SUITE 500-X` | **FAIL** |
| High-concurrency upserts (50 workers) | 0 errors, DB row count = 1 | 50/50 succeeded, DB row count = 1 | **PASS** |

---

## Unchallenged Areas

- Front-end Street View camera orientation tracking (`heading`, `pitch`, `fov`): verified working in prior runs; out of scope for backend address normalization fix.
