# Punch list #65 — The admin login accepts three hardcoded passwords besides the configured one

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | hygiene |
| **Area** | 🔐 API |
| **Blocks** | 0 |
| **Origin** | Found 2026-09-05 while scrubbing two plaintext copies of the kiosk password out of the tree |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 65. `auth.py` takes any of four passwords, and its 401 message tells you the default

> **Status**: ⚪ **Open — the operator's decision, because fixing it changes the password the
> running kiosk accepts.** Not crew-visible: the admin console answers only to localhost and the
> Tailscale network (`is_allowed_network`), and one person uses the kiosk.

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
