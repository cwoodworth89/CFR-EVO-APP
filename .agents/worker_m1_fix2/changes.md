# Code Changes — Worker M1 Fix 2

## Files Modified

### `backend/api/server.py`
Modified function `_clean_streetview_address(addr: str) -> str`:

1. **Updated Unit Prefix Regex**:
   - Expanded prefix regex pattern from `^(UNIT|APT|SUITE|#)\s*\d+[\w-]*[,\-\s]+` to `^\s*(?:UNIT|APT|STE|SUITE|#)\.?\s*#?\s*\d+[\w-]*[,\-\s]+`.
   - Added support for `STE` unit abbreviation (e.g. `Ste 101`).
   - Added support for optional periods after keywords (e.g. `Apt. 202`, `Ste. 101`).
   - Added support for optional hashes after keywords (e.g. `Unit #101`, `Ste #101`).

2. **Updated Unit Suffix Regex**:
   - Updated suffix regex pattern from `\s+[,\-]?\s*(UNIT|APT|SUITE|#)\s*\d+[\w-]*$` to `[,\-\s]+\s*(?:UNIT|APT|STE|SUITE|#)\.?\s*#?\s*\d+[\w-]*$`.
   - Replaced pattern to correctly capture preceding separator (comma, dash, whitespace) before the unit keyword (e.g. `3030 Gordon Ave, Suite 500-X` and `3030 Gordon Ave, #303`).

3. **Added Trailing Punctuation Stripping**:
   - Added `s = s.strip(' ,.-')` immediately following unit and city stripping.
   - Updated final return value to `return s.strip(' ,.-')`.
   - Ensures that trailing commas, dashes, periods, or whitespace left behind after unit or city stripping (such as `,` in `3030 Gordon Ave, Suite 500-X`) are completely removed, returning exact string `'3030 GORDON AVE'`.

## Test Results

1. **`python .agents/challenger_m1_1_recheck/test_adversarial_recheck.py`**:
   - Status: **EXTENDED ADVERSARIAL STATUS: ALL PASSED**
   - Test A1 (Complex Unit & Separator Variants): All 12 variants passed 100%.
   - Test A2 (Empty & Whitespace Address Rejection): All 5 invalid address inputs rejected with HTTP 400.
   - Test A3 (High-Concurrency Stress): 50 concurrent workers succeeded cleanly with 0 errors.

2. **`python .agents/challenger_m1_1/stress_test_m1.py`**:
   - Status: **SUMMARY: 8 PASSED, 0 FAILED out of 8 tests.**

3. **`python backend/tests/test_parcels_and_streetview_api.py`**:
   - Status: **[SUCCESS] ALL MILESTONE 1 TESTS PASSED SUCCESSFULLY!**
