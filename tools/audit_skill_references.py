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
    python tools/audit_skill_references.py
    python tools/audit_skill_references.py --skills-dir .claude/skills
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


def audit_scripts(scripts_dir: str) -> int:
    """Check backend/scripts/README.md against what is actually in the directory.

    Why this exists
    ---------------
    The previous README documented 8 of 51 scripts, and one of those 8 --
    `create_adaptation_resources.py` -- had been deleted. Its description explained how to
    load vocabulary into Google Cloud Speech-to-Text, a dependency CLAUDE.md §1 forbids. So
    the one artefact whose job was telling you what these scripts are covered 16% of them and
    was actively wrong about part of that.

    Grouping files into folders does not fix this: a folder records a guess about lifecycle
    made once, and says nothing when the guess stops being true. A check does.

    Two directions, both of which matter:
      * a script with no row -- undocumented, so nobody knows whether it is live or spent
      * a row naming no script -- documentation of something that no longer exists, which is
        worse, because it reads as current

    Subdirectories such as oneshot/ are deliberately NOT scanned. They are provenance.
    """
    readme = os.path.join(scripts_dir, "README.md")
    if not os.path.isfile(readme):
        print("no README.md in %s" % scripts_dir, file=sys.stderr)
        return 2

    text = io.open(readme, encoding="utf-8", errors="replace").read()
    documented = set(re.findall(r"^\|\s`([^`]+)`\s\|", text, re.M))
    on_disk = {f for f in os.listdir(scripts_dir)
               if os.path.isfile(os.path.join(scripts_dir, f)) and f != "README.md"}

    undocumented = sorted(on_disk - documented)
    phantom = sorted(documented - on_disk)

    for f in undocumented:
        print("UNDOCUMENTED  %s" % f)
    for f in phantom:
        print("MISSING       %s  (README describes it; it is not there)" % f)

    print()
    print("%d scripts, %d documented, %d undocumented, %d described but absent."
          % (len(on_disk), len(documented & on_disk), len(undocumented), len(phantom)))
    if undocumented or phantom:
        print("A row per script, and a script per row. Neither direction is optional.")
        return 1
    print("README and directory agree.")
    return 0


LINK = re.compile(r"\]\((?!https?://|file://|mailto:|#)([^)\s]+?)\)")
# An explicit, per-file exemption naming the path it excuses:
#
#     <!-- audit-ok: backend/data/vocabulary/custom_places.json -- records a deletion -->
#
# This replaces a word-spotting rule that skipped any paragraph containing "deleted",
# "removed" and similar. That rule was written to handle 28 findings; once the genuinely
# stale references were fixed there were 8 left, seven of which say "deleted" or "does not
# exist" in the sentence itself. A guess is not worth keeping to save eight comments -- and
# the guess could go quiet on a real finding that happened to share a paragraph with an
# unrelated deletion. An exemption should be a statement, not an inference.
AUDIT_OK = re.compile(r"<!--\s*audit-ok:\s*([^\s]+)")
_IGNORE_CACHE: dict[str, bool] = {}


def _git_ignored(repo: str, target: str) -> bool:
    """True if git ignores the path -- kiosk-only data dirs are absent here by design."""
    if target in _IGNORE_CACHE:
        return _IGNORE_CACHE[target]
    # Both forms: a directory-only rule such as `frontend/public/recordings/` does not match
    # the same path written without its trailing slash when the path is absent from disk.
    candidates = [target, target.rstrip("/") + "/"]
    ignored = False
    try:
        for c in candidates:
            rc = subprocess.run(["git", "check-ignore", "-q", c], cwd=repo,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
            if rc == 0:
                ignored = True
                break
    except Exception:
        ignored = False
    _IGNORE_CACHE[target] = ignored
    return ignored

BACKTICK_PATH = re.compile(r"`((?:backend|frontend|services|docs|scripts|tools|\.claude|\.githooks)/[A-Za-z0-9_./-]+)`")
FENCE = re.compile(r"```.*?```", re.S)


def audit_docs(docs_dir: str) -> int:
    """Check that documentation does not point at files which are not there.

    Why this exists
    ---------------
    Two things rotted repeatedly and neither announced itself:

      * **Relative links.** Splitting the punch list into `docs/punchlist/` moved every item
        one directory deeper without rewriting the links inside them. 34 links were silently
        broken for most of a day, and were found only because someone thought to look.
      * **Paths named in prose.** Deleting a document or moving a script leaves every sentence
        that mentions it reading as though it is still there.

    Nothing catches either at commit time, and neither breaks a test. A reader discovers them
    one at a time, by following a link into nothing.

    Both checks skip fenced code blocks: an example command may legitimately name a path that
    does not exist yet, and flagging those would train people to ignore the output.

    Two more exclusions, for the same reason -- a check people learn to ignore is worse than
    no check, because it costs attention and returns nothing:

      * **Git-ignored paths.** `backend/data/`, model caches and audio corpora are real on the
        kiosk and absent here by design (CLAUDE.md §3.6). Their absence proves nothing.
      * **Paths the sentence itself says are gone.** A closed punch-list item describing the
        file a defect used to live in is CORRECT documentation, not rot. `custom_places.json`
        was deliberately deleted and item #7 exists to record that. The signal is a past-tense
        or removal word in the same line -- which is how this project already writes them.
    """
    broken_links, broken_paths, scanned = [], [], 0
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # tools/.. is the repository root

    for root, _dirs, files in os.walk(docs_dir):
        for f in files:
            if not f.endswith(".md"):
                continue
            p = os.path.join(root, f)
            scanned += 1
            text = io.open(p, encoding="utf-8", errors="replace").read()
            prose = FENCE.sub("", text)
            # Read the exemptions BEFORE stripping fences, so a marker is findable wherever
            # it was written. Scope is the file: a path excused here is excused throughout it.
            exempt = set(AUDIT_OK.findall(text))

            for m in LINK.finditer(prose):
                target = m.group(1).split(":")[0].split("#")[0]
                if not target:
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(root, target))):
                    broken_links.append((p, m.group(1)))

            for m in BACKTICK_PATH.finditer(prose):
                target = m.group(1)
                if os.path.exists(os.path.join(repo, target)):
                    continue
                if _git_ignored(repo, target):
                    continue
                if target in exempt:
                    continue
                broken_paths.append((p, target))

    for p, t in broken_links:
        print("BROKEN LINK   %s -> %s" % (p, t))
    for p, t in broken_paths:
        print("MISSING PATH  %s names `%s`" % (p, t))

    print()
    print("%d markdown files scanned. %d broken links, %d prose paths naming nothing."
          % (scanned, len(broken_links), len(broken_paths)))
    if broken_links or broken_paths:
        print("A link into nothing is discovered one reader at a time. Fix or delete it.")
        return 1
    print("Every link resolves and every path named in prose exists.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir", default=".claude/skills")
    ap.add_argument("--docs", action="store_true",
                    help="audit documentation for broken links and paths naming nothing")
    ap.add_argument("--docs-dir", default="docs")
    ap.add_argument("--scripts", action="store_true",
                    help="audit backend/scripts/README.md against the directory instead")
    ap.add_argument("--scripts-dir", default="backend/scripts")
    args = ap.parse_args()

    if args.scripts:
        return audit_scripts(args.scripts_dir)

    if args.docs:
        return audit_docs(args.docs_dir)

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
