#!/usr/bin/env python3
"""Find identifiers a SKILL.md names that exist nowhere in the code.

Why this exists
---------------
`docs/review_status_handoff.md` recorded that the 2026-08-23 skill sweep checked paths and
constants but never checked **described behaviour that never existed** -- which is how
`kiosk-responsive-ergonomics` came to document an `isKioskMode` API that has never been in
the code. This is the cheap half of that second pass, and on 2026-08-30 it found four of the
five real defects across the 15 skills (see `docs/briefings/skills_audit_2026-08-30.md`).

What it can and cannot do
-------------------------
It proves an identifier is **absent**. It cannot prove a procedure is **correct** -- a skill
can name only real symbols and still describe a workflow that does not work. A clean run is
not evidence a skill is right; it only removes the cheapest class of error.

**Excluding Markdown from the corpus is the part that makes this work.** With `.md` included,
every identifier a skill mentions "exists" somewhere in the docs and the check returns
nothing at all. That was the first version, and it reported all clear on a file whose two
core SQL queries could not run.

Expect false positives, and read them rather than acting on the list:

* HTTP verbs, SQLite error codes and other external constants (`OPTIONS`, `SQLITE_CANTOPEN`)
  legitimately appear in no source file.
* An identifier quoted **inside a correction notice** flags too -- that is
  `kiosk-responsive-ergonomics` naming the phantom API it warns about.
* Gitignored data (`.mbtiles`, shapefiles, `.env`) is absent by design (CLAUDE.md §3.6).

Usage
-----
    python backend/scripts/audit_skill_references.py
    python backend/scripts/audit_skill_references.py --skills-dir .claude/skills
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys

# Live schema names and other identifiers that are real but live outside the source tree.
# Kept explicit so a reader can see exactly what is being excused.
KNOWN_GOOD = set("""
city_boundary dispatch_sessions dispatch_uploads dispatches evaluation_history hydrants
intersections parcels road_closures road_names roads streetview_overrides vocabulary zones
dispatch_id quality_rating review_notes verified_transcript verified_address verified_incident
verified_units feedback_submitted model_updated routing_metrics sanitized_transcript
raw_transcript verify_location audio_url audio_duration incident_type responding_units
resolution_note requested_address
OPTIONS SQLITE_CANTOPEN
""".split())

CODE_EXT = (".py", ".js", ".jsx", ".sql", ".yml", ".yaml", ".lua", ".sh", ".json", ".toml")
TOKEN = re.compile(r"`([A-Za-z_][A-Za-z0-9_]{4,})`")


def code_corpus() -> str:
    """Every tracked source file, concatenated. Markdown is deliberately excluded."""
    listed = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
    chunks = []
    for path in listed:
        if not path.endswith(CODE_EXT):
            continue
        try:
            chunks.append(io.open(path, encoding="utf-8", errors="replace").read())
        except OSError:
            continue
    return "\n".join(chunks)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir", default=".claude/skills")
    args = ap.parse_args()

    if not os.path.isdir(args.skills_dir):
        print("no such directory: %s" % args.skills_dir, file=sys.stderr)
        return 2

    blob = code_corpus()
    if not blob:
        print("code corpus is empty -- run from the repository root", file=sys.stderr)
        return 2

    names = sorted(d for d in os.listdir(args.skills_dir)
                   if os.path.isfile(os.path.join(args.skills_dir, d, "SKILL.md")))

    flagged = 0
    for name in names:
        path = os.path.join(args.skills_dir, name, "SKILL.md")
        text = io.open(path, encoding="utf-8", errors="replace").read()
        missing = [t for t in sorted(set(TOKEN.findall(text)))
                   if t not in KNOWN_GOOD and t not in blob]
        if missing:
            flagged += 1
            print("%s" % name)
            for t in missing:
                print("    %s" % t)

    print()
    print("%d of %d skills name an identifier absent from the code." % (flagged, len(names)))
    print("Read each one. Absence is not automatically a defect -- but every real defect")
    print("found on 2026-08-30 was in this list.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
