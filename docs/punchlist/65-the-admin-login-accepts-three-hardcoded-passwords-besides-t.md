# Punch list #65 — The admin login accepts three hardcoded passwords besides the configured one

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | hygiene |
| **Area** | 🔐 API |
| **Blocks** | 0 |
| **Origin** | Found 2026-09-05 while scrubbing two plaintext copies of the kiosk password out of the tree |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 65. `auth.py` takes any of four passwords, and its 401 message tells you the default

> **Status**: ✅ **Closed 2026-09-05 — one password, from `ADMIN_PASSWORD`, wired through compose; the operator chose the value (`2c7c051`).** *(Opened as: ⚪ Open — the operator's decision, because fixing it changes the password the > running kiosk accepts. Not crew-visible: the admin console answers only to localhost and the > Tailscale network (`is_allowed_network`), and one person uses the kiosk.)*

### What the code does

`backend/api/routers/auth.py` (`login`) reads `ADMIN_PASSWORD` from the environment with
`"rescue"` as the default, then accepts the request if the password is *any* of
`[expected_pass, "rescue", "cfr2026", "admin"]`. Setting `ADMIN_PASSWORD` therefore adds a
password; it never removes the three literals. The 401 response ends *"Default password is
'rescue'."*

The kiosk's `backend/.env` sets neither `ADMIN_PASSWORD` nor `ADMIN_USERNAME` (checked
2026-09-05), so the default is the live password.

### What was done on 2026-09-05

The two plaintext copies outside `auth.py` are gone. The `kiosk-remote-ops` runbook piped the
sudo password into `docker exec`, which never needed it: `tcfire` is in the `docker` group.
`backend/tests/test_api_routers.py` logged in with the literal; it now reads `ADMIN_PASSWORD`
from the environment and skips when it is unset. `auth.py` accepts whatever the environment
holds, so any value serves the test.

### Proposed fix, for the operator

1. Put `ADMIN_PASSWORD=<new value>` in the kiosk's `backend/.env`.
2. In `auth.py`, accept only `expected_pass`; exit at startup when `ADMIN_PASSWORD` is unset,
   the way `database.py` does for `DATABASE_URL` (#61); drop the default from the 401 text.
3. `docker compose up -d --build api` (the API image bakes the code in; a restart is not enough).

Step 2 before step 1 locks the operator out of the admin console, which is why this is filed
rather than done. Choosing the value is the operator's.

### Closed 2026-09-05

`auth.py` accepts `ADMIN_PASSWORD` and nothing else; unset answers 503 *not configured* with
a log line, and the 401 no longer names a default. The test refuses the three old literals.

Found on the way: **the API container never read `backend/.env`.** Compose interpolates
`${...}` from the shell or a root `.env`, and `.dockerignore` keeps every `.env` out of the
image, so the value the punch list said to set there could never have reached the API; the
"rescue" that worked was the code's fallback. `docker-compose.yml` now passes
`ADMIN_PASSWORD: ${ADMIN_PASSWORD:-}` with a comment, and the value lives in the kiosk's
root `.env` (git-ignored), moved out of `backend/.env` so there is one copy.

Verified on the rebuilt container: the configured password 200, `cfr2026` and `admin` 401,
body `Invalid username or password.`

**Addendum, 2026-09-09.** The frontend half was still open: `apiClient.getSession` logged
every browser in by itself with `rescue` written into the source, so the backend fix above
gated nothing in practice. Removed with the admin unlock (`ux_notes.md` §3). The token
signing key had the same shape, a literal default in `auth.py` and in compose, now
`${JWT_SECRET:-}` from the root `.env` beside `ADMIN_PASSWORD`; unset answers 503 the same
way. Every token issued under the old literal was invalidated by the change.
