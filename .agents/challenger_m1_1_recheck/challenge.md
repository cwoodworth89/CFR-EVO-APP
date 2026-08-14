# Adversarial Challenge Report — Milestone 1 Re-check (Backend PostgreSQL & REST Overhaul)

## Challenge Summary

**Overall risk assessment**: MEDIUM

Empirical re-testing confirmed that Worker M1 Fix resolved the primary HTTP 500 concurrency race condition and empty address input validation defects. However, adversarial edge case mining revealed remaining address normalization regex defects where trailing unit suffixes after commas (`3030 Gordon Ave, Suite 500-X`, `3030 Gordon Ave, #303`), compound unit prefixes (`Unit #101`), unit abbreviation variants (`Ste 101`), and dotted unit prefixes (`Apt. 202`) leave dangling punctuation or unstripped unit text, causing property parcel lookups to fail (`Found: False`).

---

## Challenges

### [Medium] Challenge 1: Dangling Comma in Trailing Unit Suffix Normalization (`3030 Gordon Ave, Suite 500-X`, `3030 Gordon Ave, #303`)
- **Assumption challenged**: Trailing unit regex cleanly removes unit suffixes regardless of whether comma punctuation precedes or follows whitespace.
- **Attack scenario**: Dispatch feed or user search query with comma-separated trailing units (e.g., `3030 Gordon Ave, Suite 500-X` or `3030 Gordon Ave, #303`).
- **Blast radius**: `_clean_streetview_address` in `backend/api/server.py` strips `Suite 500-X` but leaves a trailing comma (`3030 GORDON AVE,`). `lookup_parcel` queries PostgreSQL for `3030 GORDON AVE,` (and ILIKE `%3030 GORDON AVE,%`), which fails to match canonical DB record `3030 GORDON AVE`, returning `{"found": False}`.
- **Mitigation**: Update trailing unit regex in `server.py` line 568 to match leading punctuation, or trim trailing punctuation after substitution:
  `s = re.sub(r'[,\-\s]+\s*(UNIT|APT|SUITE|STE|#)\s*\d+[\w-]*$', '', s, flags=re.IGNORECASE)` followed by `s = s.strip(' ,-')`.

### [Low] Challenge 2: Regex Gaps for Compound (`Unit #101`), Dotted (`Apt. 202`), and Abbreviated (`Ste 101`) Unit Prefixes
- **Assumption challenged**: `_clean_streetview_address` handles real-world CAD unit prefixes with dots, `#` symbols, or `STE` abbreviations.
- **Attack scenario**: Inputs containing `Unit #101, 3030 Gordon Ave`, `Apt. 202 - 3030 Gordon Ave`, or `Ste 101, 3030 Gordon Ave`.
- **Blast radius**: `_clean_streetview_address` in `backend/api/server.py` line 567 fails to strip unit prefixes, producing `UNIT #101, 3030 GORDON AVE`, `APT. 202 - 3030 GORDON AVE`, and `STE 101, 3030 GORDON AVE`, causing `lookup_parcel` to return `{"found": False}`.
- **Mitigation**: Update prefix regex in `server.py` to handle optional dots, `#` symbols, and `STE` keyword:
  `s = re.sub(r'^(UNIT|APT|SUITE|STE|#)\.?\s*(#\s*)?\d+[\w-]*[,\-\s]+', '', s, flags=re.IGNORECASE)`.

---

## Stress Test Results

| Test Scenario | Expected Behavior | Actual Behavior | Pass/Fail |
|---|---|---|---|
| **Parallel Concurrent Upserts (10 Workers)** | 10 parallel threads upserting a new property handle DB conflicts gracefully | All 10/10 workers succeeded; DB rollback & update fallback prevented HTTP 500 (`IntegrityError`) | **PASS** |
| **High-Concurrency Stress (50 Workers)** | 50 parallel threads upserting different address variants for a new property | All 50/50 workers succeeded; atomic row count = 1 | **PASS** |
| **Empty & Whitespace Address Rejection** | `""`, `"   "`, `"\t\n  "`, `"   COQUITLAM, BC   "` return HTTP 400 | All invalid address payloads rejected with HTTP 400 Bad Request | **PASS** |
| **Standard Unit Prefix & Suffix Cleaning** | `Unit 101 3030 Gordon Ave`, `Unit 101, 3030 Gordon Ave`, `Apt 202 - 3030 Gordon Ave`, `3030 Gordon Ave Unit 101` clean to `3030 GORDON AVE` | Cleaned to `3030 GORDON AVE`; lookup returned `found: True` | **PASS** |
| **Trailing Unit Suffix with Comma** (`3030 Gordon Ave, Suite 500-X`, `3030 Gordon Ave, #303`) | Clean to `3030 GORDON AVE`; lookup resolves canonical parcel | Cleaned to `3030 GORDON AVE,` (dangling comma); lookup returned `found: False` | **FAIL** |
| **Compound / Dotted / Abbreviated Unit Prefixes** (`Unit #101`, `Apt. 202`, `Ste 101`) | Strip unit prefix; lookup resolves canonical parcel | Failed to strip prefix (`UNIT #101, 3030 GORDON AVE`); lookup returned `found: False` | **FAIL** |

---

## Unchallenged Areas

- **PostgreSQL 16 High-Volume Database Load**: Executed using local SQLAlchemy session bindings; multi-gigabyte production DB load not tested locally.
- **Frontend HUD WebGL Component**: UI visual components are handled in frontend suite.
