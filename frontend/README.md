# CFR EVO — Frontend

React 19 + Vite kiosk client for the CFR EVO dispatch system. Renders the apparatus-bay
HUD, the Leaflet map surface, and the HITL review panel.

## Running it

The full stack runs on the **kiosk**, not locally (CLAUDE.md §3). The normal loop is edit
locally, push, then pull and build on the kiosk:

```bash
git add . && git commit -m "..." && git push origin main
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP && git pull && cd frontend && npm run build"
```

## Before you change anything here

| Topic | Read |
|:--|:--|
| Architecture and domain rules | [`CLAUDE.md`](../CLAUDE.md) — especially §5 (unresolved/out-of-bounds handling) and §6 (no fabricated data) |
| API and tile base URLs | [`src/apiClient.js`](src/apiClient.js) — **never** use relative paths or hardcoded `localhost`; remote kiosks over Tailscale will 404 |
| Display sizing and typography | `kiosk-responsive-ergonomics` skill in `.claude/skills/` |
| Map surface | [`docs/architecture/unified_map_surface.md`](../docs/architecture/unified_map_surface.md) |
| Open defects | [`docs/debug_and_qa_punchlist.md`](../docs/debug_and_qa_punchlist.md) |

## Lint

`npm run lint:crash` blocks commits touching `frontend/src/**` on the crash class only —
`no-undef` and use-before-declaration. Those compile cleanly through Vite and throw only at
runtime on the kiosk; `npm run build` does not catch them. `npm run lint` is advisory.
