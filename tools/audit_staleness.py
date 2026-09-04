#!/usr/bin/env python3
"""Deterministic staleness scan: things the tree says exist that do not, and vice versa.

Why this exists
---------------
The 2026-09-03 audit (`docs/briefings/staleness_audit_2026-09-03.md`) found that the rot in
this repository is concentrated in references, not code: an `.env.example` naming a variable
the client never reads, a script selecting a column a migration dropped, skill descriptions
advertising a routing mode nothing calls, 32 links to one developer's absolute path. None of
that is visible to a test suite. All of it is visible to a cross-reference.

Relation to `audit_skill_references.py`
---------------------------------------
That script already checks skills for phantom identifiers and docs for dangling paths
(`--docs`), and honours `<!-- audit-ok: path -- why -->` exemptions. This one honours the same
markers and adds checks the older one does not have: schema objects removed by a migration but
still named in code, modules and components nothing imports, frontend and pipeline API calls
against the backend route table, container and service names against `docker-compose.yml`,
environment variables read by code against what compose declares, punch-list header status
against the body status line, `file://` links, and document age. **The overlap is deliberate
debt**: folding these checks into the older script and deleting this one is on
`docs/post_freeze_backlog.md`. Do not add a third.

What it cannot do
-----------------
It proves a name is absent. It cannot tell whether a paragraph describes behaviour the code
no longer has. Every finding is a candidate to read, not a defect to act on; the migration
check in particular cannot see ordering (a column dropped and then recreated by rename reads as
dropped), and generic column names (`lat`, `id`) match everything.

Usage
-----
    python tools/audit_staleness.py                  # writes staleness_scan.md
    python tools/audit_staleness.py --out report.md
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict


def sh(*args: str) -> str:
    return subprocess.check_output(list(args), text=True)


def read(path: str) -> str:
    try:
        return io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


TEXT_EXT = (".md", ".py", ".js", ".jsx", ".sql", ".yml", ".yaml", ".sh", ".ps1", ".json",
            ".toml", ".txt", ".html", ".css", ".example", ".gitignore", ".lua", ".conf",
            ".cfg", ".ini")
# Paths that are absent from a checkout by design: kiosk-only data, models, library sources.
IGNORED_PREFIXES = ("backend/models/", "backend/data/", "frontend/.env", "backend/.env",
                    "venv/", ".venv/", "etc/", "var/", "tmp/", "transformers/",
                    "faster_whisper/", "node_modules/", "frontend/public/data/", "archive/",
                    "dist/")
AUDIT_OK = re.compile(r"<!--\s*audit-ok:\s*([^\s]+)")
# Fenced code is output or an example, not a claim about the tree; both checkers skip it.
FENCE = re.compile(r"```.*?```", re.S)
LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")


def prose(text: str) -> str:
    """Blank out fenced blocks but keep their line count so reported line numbers stay right."""
    return FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
TICK = re.compile(r"`([^`\n]+)`")
PATHISH = re.compile(r"^\.?[A-Za-z0-9_./\-]+\.[A-Za-z0-9]{1,5}$")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="staleness_scan.md", help="Markdown report path")
    args = ap.parse_args()

    tracked = [f for f in sh("git", "ls-files").split("\n") if f]
    tset = set(tracked)
    head = sh("git", "log", "-1", "--format=%h %as").strip()
    text_files = [f for f in tracked
                  if f.endswith(TEXT_EXT) or os.path.basename(f) == "Dockerfile"]
    contents = {f: read(f) for f in text_files}
    md = [f for f in tracked if f.endswith(".md")]
    py = [f for f in tracked if f.endswith(".py")]
    fe = [f for f in tracked
          if f.startswith("frontend/src/") and f.endswith((".js", ".jsx", ".css"))]

    out: list[str] = []
    summary: list[str] = []

    def H(t: str) -> None:
        out.append(f"\n## {t}\n")

    def P(t: str = "") -> None:
        out.append(t)

    # ---- last-touched date per file, one git call ---------------------------------------
    last: dict[str, str] = {}
    cur = None
    for line in sh("git", "log", "--name-only", "--format=%as").split("\n"):
        if re.match(r"^\d{4}-\d{2}-\d{2}$", line):
            cur = line
        elif line.strip() and cur and line not in last:
            last[line] = cur

    # ======================================================================================
    H("A. Dangling file paths referenced from markdown")
    P("Honours `<!-- audit-ok: path -- why -->` per file, as `audit_skill_references.py` does.\n")

    def resolves(c: str, d: str) -> bool:
        if c in tset or os.path.exists(c):
            return True
        rel = os.path.normpath(os.path.join(d, c)).replace(os.sep, "/")
        if rel in tset or os.path.exists(rel):
            return True
        if os.path.isdir(c) or os.path.isdir(rel):
            return True
        suf = "/" + c.lstrip("./")
        return any(t.endswith(suf) for t in tracked)

    dangling: dict[str, list] = defaultdict(list)
    total = 0
    for f in md:
        d = os.path.dirname(f)
        excused = set(AUDIT_OK.findall(contents[f]))
        for ln, line in enumerate(prose(contents[f]).split("\n"), 1):
            for c in LINK.findall(line) + TICK.findall(line):
                c = c.strip().strip("`")
                c = re.sub(r":\d+(-\d+)?$", "", c)
                if c.startswith("./"):
                    c = c[2:]
                if c.startswith(("http", "mailto", "<", "$", "-")):
                    continue
                if "/" not in c and not c.startswith(("CLAUDE", "GEMINI", "PROJECT", "README")):
                    continue
                if not PATHISH.match(c) or "YYYY" in c:
                    continue
                total += 1
                if c.lstrip("/").startswith(IGNORED_PREFIXES):
                    continue
                if any(c == e or c.endswith("/" + e.lstrip("./")) or e.endswith("/" + c.lstrip("./"))
                       for e in excused):
                    continue
                if resolves(c, d):
                    continue
                dangling[f].append((ln, c))
    n = sum(len(v) for v in dangling.values())
    P(f"Checked {total} path-like references. **{n} dangling across {len(dangling)} docs.**\n")
    summary.append(f"A dangling paths: {n} in {len(dangling)} docs (of {total} checked)")
    for f, items in sorted(dangling.items(), key=lambda kv: -len(kv[1])):
        P(f"- `{f}` (last touched {last.get(f, '?')})")
        seen = set()
        for ln, c in items:
            if c in seen:
                continue
            seen.add(c)
            P(f"    - L{ln} `{c}`")

    # ======================================================================================
    H("B. Schema objects dropped or renamed by migrations, still referenced in code")
    P("Cannot see ordering: a column dropped and then recreated by a later rename reads as dropped.\n")
    mig = [f for f in tracked if f.startswith("backend/migrations/") and f.endswith(".sql")]
    dead = []
    for f in mig:
        c = contents.get(f, "")
        for m in re.finditer(r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:\w+\.)?(\w+)\s+DROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?(\w+)", c, re.I):
            dead.append((m.group(2), f"column of {m.group(1)}", f))
        for m in re.finditer(r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:\w+\.)?(\w+)\s+RENAME\s+COLUMN\s+(\w+)\s+TO\s+(\w+)", c, re.I):
            dead.append((m.group(2), f"column of {m.group(1)} -> {m.group(3)}", f))
        for m in re.finditer(r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:\w+\.)?(\w+)\s+RENAME\s+TO\s+(\w+)", c, re.I):
            dead.append((m.group(1), f"table -> {m.group(2)}", f))
        for m in re.finditer(r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:\w+\.)?(\w+)", c, re.I):
            dead.append((m.group(1), "table", f))
        for m in re.finditer(r"DROP\s+(?:FUNCTION|VIEW|MATERIALIZED\s+VIEW)\s+(?:IF\s+EXISTS\s+)?(?:\w+\.)?(\w+)", c, re.I):
            dead.append((m.group(1), "function/view", f))
    code_files = [f for f in text_files if f.endswith((".py", ".js", ".jsx", ".sql"))
                  and f not in mig and f != "backend/api/init_db.sql"]
    generic = {"lat", "lng", "lon", "id", "name", "type", "data", "status", "value", "geom", "x", "y"}
    seen_dead = set()
    b_hits = 0
    for old, kind, f in dead:
        if (old, kind) in seen_dead:
            continue
        seen_dead.add((old, kind))
        hits = []
        for g in code_files:
            for ln, line in enumerate(contents[g].split("\n"), 1):
                if re.search(r"\b" + re.escape(old) + r"\b", line):
                    hits.append((g, ln, line.strip()[:110]))
        flag = " (generic name, expect noise)" if old.lower() in generic else ""
        if hits and not flag:
            b_hits += 1
        P(f"- **`{old}`** — {kind} — `{os.path.basename(f)}`: {len(hits)} code references{flag}")
        for g, ln, line in hits[:8]:
            P(f"    - `{g}:{ln}` `{line}`")
        if len(hits) > 8:
            P(f"    - … {len(hits) - 8} more")
    init = contents.get("backend/api/init_db.sql", "")
    P("\n**init_db.sql still defines objects a later migration removed or renamed:**")
    for old, kind, f in dead:
        if re.search(r"\b" + re.escape(old) + r"\b", init):
            P(f"- `{old}` ({kind}) appears in init_db.sql; migration `{os.path.basename(f)}` changed it")
    summary.append(f"B dropped/renamed schema names with non-generic code hits: {b_hits}")

    # ======================================================================================
    H("C. Python modules nothing imports")
    py_code = {f: contents[f] for f in py}
    entry = {"server", "main", "conftest", "__main__", "setup"}
    orph_none, orph_ext = [], []
    for f in py:
        base = os.path.basename(f)
        stem = base[:-3]
        if base == "__init__.py" or stem in entry:
            continue
        if "/tests/" in f or "/scripts/" in f or f.startswith("tools/") or stem.startswith("test_"):
            continue
        pat = re.compile(r"^\s*(?:from\s+[\w.]*\b" + re.escape(stem) + r"\b\s+import|import\s+[\w.]*\b"
                         + re.escape(stem) + r"\b|from\s+[\w.]+\s+import\s+[^\n]*\b" + re.escape(stem) + r"\b)", re.M)
        importers = [g for g, c in py_code.items() if g != f and pat.search(c)]
        if importers:
            continue
        others = [g for g, c in contents.items()
                  if g != f and not g.endswith((".py", ".md")) and base in c]
        docs = [g for g in md if base in contents[g]]
        (orph_ext if others else orph_none).append((f, others, docs))
    P(f"**{len(orph_none)} modules with no importer and no non-doc reference (compose, Dockerfile, shell):**")
    for f, others, docs in orph_none:
        note = " — mentioned only in docs: " + ", ".join(docs[:3]) if docs else " — mentioned nowhere"
        P(f"- `{f}` (last touched {last.get(f, '?')}){note}")
    P(f"\n**{len(orph_ext)} modules with no importer but referenced from compose/Dockerfile/shell (probably entrypoints):**")
    for f, others, docs in orph_ext:
        P(f"- `{f}` ← {', '.join(others[:3])}")
    summary.append(f"C orphan python modules: {len(orph_none)}")

    H("D. Scripts, tests, and shell/PS files referenced from nothing")
    P("Tests are discovered by pytest and `oneshot/` scripts are provenance; both are expected here.\n")
    script_like = [f for f in tracked if ("/scripts/" in f or f.startswith("tools/") or "/tests/" in f
                                          or f.endswith((".sh", ".ps1")) or os.path.basename(f).startswith("test_"))]
    d_n = 0
    for f in script_like:
        base = os.path.basename(f)
        refs = [g for g, c in contents.items() if g != f and base in c]
        if not refs:
            d_n += 1
            P(f"- `{f}` (last touched {last.get(f, '?')})")
    summary.append(f"D unreferenced scripts/tests: {d_n}")

    # ======================================================================================
    H("E. Frontend source files nothing imports")
    fe_code = {f: contents[f] for f in fe}
    e_n = 0
    for f in fe:
        base = os.path.basename(f)
        stem = re.sub(r"\.(jsx?|css)$", "", base)
        if base in ("main.jsx", "App.jsx", "index.jsx"):
            continue
        pat = re.compile(r"""(?:from|import)\s*\(?\s*['"][^'"]*/""" + re.escape(stem) + r"""(?:\.jsx?|\.css)?['"]""")
        importers = [g for g, c in fe_code.items() if g != f and pat.search(c)]
        if not importers:
            e_n += 1
            html_ref = base in contents.get("frontend/index.html", "")
            P(f"- `{f}` (last touched {last.get(f, '?')}){' — referenced from index.html' if html_ref else ''}")
    summary.append(f"E orphan frontend files: {e_n}")

    # ======================================================================================
    H("F. API endpoints: frontend and pipeline calls vs backend routes")
    routes = []
    for f in py:
        if not f.startswith("backend/api/"):
            continue
        c = contents[f]
        prefix = ""
        m = re.search(r"APIRouter\(([^)]*)\)", c, re.S)
        if m:
            pm = re.search(r"prefix\s*=\s*[\"']([^\"']+)", m.group(1))
            if pm:
                prefix = pm.group(1)
        for dm in re.finditer(r"@(?:router|app)\.(get|post|put|delete|patch|websocket)\(\s*[\"']([^\"']*)", c):
            routes.append((dm.group(1).upper(), (prefix + dm.group(2)) or "/", f))

    def segs(p: str) -> list[str]:
        return [s for s in p.strip("/").split("/") if s]

    def seg_match(call: str, route: str) -> bool:
        a, b = segs(call), segs(route)
        if len(a) != len(b):
            return False
        return all(x == y or x.startswith("{") or y.startswith("{") for x, y in zip(a, b))

    def norm_call(p: str) -> str:
        i = p.find("${")
        if i >= 0:
            p = p[:i].rstrip("/") + "/{p}"
        return re.sub(r"[`\"')\]},;]+$", "", p)

    calls: dict[str, set] = defaultdict(set)
    for f, c in fe_code.items():
        for m in re.finditer(r"\$\{API_BASE_URL\}(/[^`\"'\s?]+)", c):
            calls[norm_call(m.group(1))].add(f)
    for f, c in py_code.items():
        if f.startswith("backend/api/"):
            continue
        for m in re.finditer(r"[\"'`][^\"'`\n]*?(/api/[A-Za-z0-9_/{}.-]+)", c):
            calls[norm_call(m.group(1))].add(f)
    P(f"Backend routes found: {len(routes)}. Distinct call paths found in frontend + pipeline: {len(calls)}.\n")
    P("**Calls with no matching backend route:**")
    matched = set()
    f_n = 0
    for call, files in sorted(calls.items()):
        hits = [r for r in routes if seg_match(call, r[1])]
        for r in hits:
            matched.add(r[1])
        if not hits:
            f_n += 1
            P(f"- `{call}` ← {', '.join(sorted(files))}")
    P("\n**Backend routes no frontend or pipeline code calls (may be curl/ops-only; informational):**")
    for meth, path, f in sorted(routes, key=lambda r: r[1]):
        if path not in matched:
            P(f"- `{meth} {path}` — `{f}`")
    summary.append(f"F calls with no route: {f_n}")

    H("G. `/api/...` paths mentioned in docs and skills that match no backend route")
    P("File paths that happen to contain `/api/` (e.g. `backend/api/server.py`) are noise here.\n")
    doc_calls: dict[str, set] = defaultdict(set)
    for f in md:
        for ln, line in enumerate(contents[f].split("\n"), 1):
            for m in re.finditer(r"(/api/[A-Za-z0-9_/{}<>:.-]+)", line):
                p = re.sub(r"[.,;:)\]]+$", "", m.group(1))
                p = re.sub(r"<[^>]+>|:\w+", "{p}", p)
                doc_calls[p].add(f"{f}:{ln}")
    for p, locs in sorted(doc_calls.items()):
        if not any(seg_match(p, r[1]) for r in routes):
            P(f"- `{p}` ← {', '.join(sorted(locs)[:4])}{' …' if len(locs) > 4 else ''}")

    # ======================================================================================
    H("H. Docker service / container names in docs and skills vs docker-compose.yml")
    compose = contents.get("docker-compose.yml", "")
    svc = set(re.findall(r"^  ([a-z_\-]+):\s*$", compose, re.M))
    cnames = set(re.findall(r"container_name:\s*(\S+)", compose))
    P(f"compose services: {sorted(svc)}; container names: {sorted(cnames)}\n")
    bad: dict[str, set] = defaultdict(set)
    known_prefixes = ("cfr_dispatch", "cfr-dispatch", "cfr-evo", "cfr_evo", "cfr-postgres", "cfr-docker",
                      "cfr-mapping", "cfr-agent", "cfr-full", "cfr-critical", "cfr-backups", "cfr-model",
                      "cfr-audio", "cfr_user")
    for f in md + [f for f in text_files if f.endswith((".sh", ".ps1"))]:
        c = prose(contents[f]) if f.endswith(".md") else contents[f]
        for m in re.finditer(r"\bcfr[_-][a-z_\-]+\b", c):
            name = m.group(0)
            if name not in cnames and name not in svc and not name.startswith(known_prefixes):
                bad[name].add(f)
        for m in re.finditer(r"docker\s+compose\s+(?:-f\s+\S+\s+)?(?:restart|up|down|logs|exec|build|stop|start|run)\s+(?:-[a-z-]+\s+)*([a-z_\-]+)", c):
            name = m.group(1)
            if name not in svc and name not in ("-d", "d", "-v", "v", "build"):
                bad["compose svc: " + name].add(f)
        for m in re.finditer(r"docker\s+(?:exec|logs|restart|stop|start|inspect)\s+(?:-[a-z]+\s+)*([a-z_\-]+)", c):
            name = m.group(1)
            if name not in cnames and name.startswith("cfr"):
                bad["docker cmd: " + name].add(f)
    for name, files in sorted(bad.items()):
        P(f"- `{name}` ← {', '.join(sorted(files)[:5])}")
    if not bad:
        P("- none")
    summary.append(f"H unknown container/service names: {len(bad)}")

    # ======================================================================================
    H("I. Environment variables: code vs compose")
    P("`.env` files are git-ignored and have no template in the tree (2026-09-03); compose is the only declaration checked.\n")
    used: dict[str, set] = defaultdict(set)
    for f, c in py_code.items():
        for m in re.finditer(r"os\.(?:getenv|environ\.get)\(\s*[\"'](\w+)|os\.environ\[\s*[\"'](\w+)", c):
            used[m.group(1) or m.group(2)].add(f)
    for f, c in fe_code.items():
        for m in re.finditer(r"import\.meta\.env\.(\w+)", c):
            used[m.group(1)].add(f)
    declared: dict[str, set] = defaultdict(set)
    for m in re.finditer(r"^\s+-?\s*([A-Z][A-Z0-9_]+)[=:]", compose, re.M):
        declared[m.group(1)].add("docker-compose.yml")
    P("**Read by code, not declared in compose (must come from `.env` on the host):**")
    for v in sorted(set(used) - set(declared)):
        P(f"- `{v}` ← {', '.join(sorted(used[v])[:3])}")
    P("\n**Declared in compose, read by no code:**")
    for v in sorted(set(declared) - set(used)):
        P(f"- `{v}` ← {', '.join(sorted(declared[v]))}")

    # ======================================================================================
    H("J. SQL files referenced from no doc, script, or compose")
    j_n = 0
    for f in [t for t in tracked if t.endswith(".sql")]:
        base = os.path.basename(f)
        refs = [g for g, c in contents.items() if g != f and base in c]
        if not refs:
            j_n += 1
            P(f"- `{f}` (last touched {last.get(f, '?')})")
    summary.append(f"J unreferenced SQL files: {j_n}")

    # ======================================================================================
    H("K. Punch list: header status vs body status, and index coverage")
    pl = sorted(f for f in md if f.startswith("docs/punchlist/") and os.path.basename(f)[0].isdigit())
    statuses: Counter = Counter()
    disagree = []
    for f in pl:
        c = contents[f]
        hm = re.search(r"\|\s*\*\*Status\*\*\s*\|\s*([^|\n]+?)\s*\|", c)
        bm = re.search(r">\s*\*\*Status\*\*\s*:?\s*(.+)", c)
        h = hm.group(1).strip() if hm else "?"
        b = bm.group(1).strip() if bm else ""
        statuses[h.split()[0].upper() if h != "?" else "?"] += 1
        hw, bw = h.upper(), b.upper()
        if b and (("CLOSED" in hw and "OPEN" in bw and "CLOSED" not in bw)
                  or ("OPEN" in hw and "CLOSED" in bw and "OPEN" not in bw)):
            disagree.append((f, h, b[:90]))
    P(f"Header status counts: {dict(statuses)}\n")
    P(f"**{len(disagree)} items where the header table and the body status line disagree:**")
    for f, h, b in disagree:
        P(f"- `{f}`: header **{h}** / body `{b}`")
    idx = contents.get("docs/debug_and_qa_punchlist.md", "") + contents.get("docs/punchlist/_closed.md", "")
    linked = {"docs/punchlist/" + m for m in re.findall(r"\]\((?:\./)?(?:punchlist/)?([0-9][^)#]*\.md)", idx)}
    P("\n**Punch-list files linked from neither the index nor `_closed.md`:**")
    for f in pl:
        if f not in linked:
            P(f"- `{f}`")
    summary.append(f"K punch-list status disagreements: {len(disagree)}")

    # ======================================================================================
    H("L. Docs no other doc links to (orphan documents)")
    inbound: dict[str, set] = defaultdict(set)
    for f in md:
        d = os.path.dirname(f)
        for m in re.finditer(r"\]\(([^)\s#]+\.md)(?:#[^)]*)?\)", contents[f]):
            t = m.group(1)
            if t.startswith("http"):
                continue
            if t.startswith("./"):
                t = t[2:]
            for c in (t, os.path.normpath(os.path.join(d, t)).replace(os.sep, "/")):
                if c in tset:
                    inbound[c].add(f)
            suf = "/" + t.lstrip("./")
            for tt in md:
                if tt.endswith(suf):
                    inbound[tt].add(f)
        for m in re.finditer(r"`([^`\n]+\.md)`", contents[f]):
            t = m.group(1).lstrip("./")
            for tt in md:
                if tt == t or tt.endswith("/" + t):
                    inbound[tt].add(f)
    roots = {"CLAUDE.md", "GEMINI.md", "README.md", "PROJECT.md"}
    orphan_docs = [f for f in md if f not in inbound and f not in roots and not f.startswith(".claude/")]
    P(f"**{len(orphan_docs)} of {len(md)} markdown files have no inbound link from another doc:**")
    for f in sorted(orphan_docs, key=lambda x: last.get(x, "")):
        P(f"- `{f}` (last touched {last.get(f, '?')}, {len(contents[f].splitlines())} lines)")
    summary.append(f"L orphan docs: {len(orphan_docs)}")

    # ======================================================================================
    H("M. Skill and agent names referenced that do not exist")
    skills = {os.path.basename(os.path.dirname(f)) for f in tracked if f.startswith(".claude/skills/")}
    agents = {os.path.basename(f)[:-3] for f in tracked if f.startswith(".claude/agents/")}
    badref: dict[str, set] = defaultdict(set)
    for f in md:
        c = contents[f]
        for m in re.finditer(r"skills/([a-z0-9][a-z0-9\-]+)", c):
            if m.group(1) not in skills:
                badref["skill dir: " + m.group(1)].add(f)
        for m in re.finditer(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`\s+skill", c):
            if m.group(1) not in skills:
                badref["skill: " + m.group(1)].add(f)
        for m in re.finditer(r"agents/([a-z0-9][a-z0-9\-]+)\.md", c):
            if m.group(1) not in agents:
                badref["agent: " + m.group(1)].add(f)
    for k, files in sorted(badref.items()):
        P(f"- `{k}` ← {', '.join(sorted(files)[:4])}")
    if not badref:
        P("- none")

    # ======================================================================================
    H("N. Machine-specific `file://` links")
    n_n = 0
    for f in md:
        for ln, line in enumerate(prose(contents[f]).split("\n"), 1):
            for m in re.finditer(r"file:///[^)\s]+", line):
                n_n += 1
                P(f"- `{f}:{ln}` `{m.group(0)[:90]}`")
    if not n_n:
        P("- none")
    summary.append(f"N file:// links: {n_n}")

    # ======================================================================================
    H("O. Documentation age")
    ages = sorted(((last.get(f, "?"), f) for f in md), key=lambda x: x[0])
    buckets = Counter(a[:7] for a, _ in ages)
    P(f"Last-touched month distribution: {dict(sorted(buckets.items()))}\n")
    P("**Oldest 20 docs by last commit:**")
    for a, f in ages[:20]:
        P(f"- {a} `{f}`")

    header = (f"# Staleness scan — deterministic checks\n\nGenerated from the working tree at `{head}` by "
              f"`tools/audit_staleness.py`. Every item is a mechanical cross-reference; none is a "
              f"judgement call. Read each one: generic names and migration ordering produce false positives, "
              f"and they are marked where the script can tell.\n")
    io.open(args.out, "w", encoding="utf-8", newline="\n").write(header + "\n".join(out) + "\n")
    print(f"wrote {args.out} ({head})")
    for s in summary:
        print("  " + s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
