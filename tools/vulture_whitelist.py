"""Whitelist for `vulture`: names it reports as unused that something it cannot see uses.

Run:
    .venv/Scripts/vulture backend services tools tools/vulture_whitelist.py --min-confidence 80

At 80 % confidence and above this list makes the report empty (2026-09-05). Each entry names
the real user. Add one only with that line; a name nothing uses is removed, not listed. The
2026-09-05 sweep removed thirteen such names, and one removal broke the geocoder: the
`has_block_indicator` field was written by a constructor call in its own file and never read,
which vulture reports as unused. Run the tests after every removal.

Below 80 % the report is mostly route handlers, ORM columns and dataclass fields, which the
framework reads by name; it is not whitelisted and not a to-do list.
"""

# The three arguments Python passes to a context manager's __exit__
# (backend/cfr_dispatch/pipeline/models.py).
exc_type
exc_val
exc_tb

# `import cfr_dispatch` is for its side effect: backend/cfr_dispatch/__init__.py puts the
# sibling services on sys.path (CLAUDE.md §2). Tests and tools import it and never name it again.
cfr_dispatch

# backend/api/server.py re-exports the router functions so the tests can import them from one
# place; test_road_closures_cache.py imports this one for that reason.
trigger_road_closure_sync
