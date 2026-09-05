"""Shared plumbing for the corpus harnesses: database, git hash, date range, JSON baselines,
the evaluation_history record, and the two scoring helpers every harness needs.

The stage harnesses each answer one question over the same corpus of reviewed dispatches:

    backtest_parser_corpus.py   stored transcript -> parser        -> verified fields
    trace_geocode_corpus.py     stored parser output -> geocoder   -> verified address
    harness_chain.py            recording -> STT -> parser -> geocoder -> everything at once

What they share lives here, so that "before" and "after" mean the same thing in all three:

    --since / --until   the slice of the corpus replayed (ISO dates; --until is exclusive)
    --limit N           at most N calls, in corpus order
    --json PATH         write this run's summary, to be a --baseline later
    --baseline PATH     print every number that moved against a saved summary
    --record            write one row to public.evaluation_history: stage, git hash, period,
                        model, metrics, notes. tools/harness_history.py shows the trend.
    --notes TEXT        stored with the record: what changed, why you ran it

Operator ruling 2026-09-04: the production database is the test database. Every harness
reads it through DATABASE_URL, from the environment or backend/.env, and --record writes to
it. No harness is ever pointed at anything else.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys

from _repo import BACKEND, ROOT
from sqlalchemy import create_engine, text


# ---------------------------------------------------------------------------- environment
def _load_backend_env() -> None:
    """Put backend/.env into os.environ for keys not already set, the way cfr_dispatch does
    on import. Done here so a harness that never imports cfr_dispatch (and so never loads
    PortAudio) still finds DATABASE_URL over SSH."""
    env_path = os.path.join(str(BACKEND), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_backend_env()


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgres://")):
        sys.exit("DATABASE_URL is not set (environment or backend/.env) or is not Postgres. "
                 "Refusing to run: the harness would score nothing and call it a result "
                 "(CLAUDE.md 6.1).")
    return url


def git_hash() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def git_dirty() -> bool:
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                             cwd=str(ROOT), capture_output=True, text=True, check=True).stdout
        return bool(out.strip())
    except Exception:
        return False


# ----------------------------------------------------------------------------- arguments
def add_common_args(ap) -> None:
    ap.add_argument("--since", help="ISO date lower bound on the dispatch timestamp, e.g. 2026-08-01")
    ap.add_argument("--until", help="ISO date upper bound (exclusive)")
    ap.add_argument("--limit", type=int, help="replay at most N calls, in corpus order")
    ap.add_argument("--json", help="write this run's summary here, for use as --baseline later")
    ap.add_argument("--baseline", help="print every number that moved against a summary written by --json")
    ap.add_argument("--record", action="store_true",
                    help="write one row to public.evaluation_history (stage, git hash, period, metrics)")
    ap.add_argument("--notes", help="free text stored with --record: what changed, why you ran it")


def date_where(args, column: str = "timestamp"):
    """SQL fragments and bind parameters for --since / --until."""
    where, params = [], {}
    if getattr(args, "since", None):
        where.append(f"{column} >= :since")
        params["since"] = args.since
    if getattr(args, "until", None):
        where.append(f"{column} < :until")
        params["until"] = args.until
    return where, params


def month_of(ts) -> str:
    return ts.strftime("%Y-%m")


# ------------------------------------------------------------------------------- scoring
def wer(reference: str, hypothesis: str) -> float:
    """Word error rate: word-level Levenshtein distance divided by reference length. The same
    definition as backtest_regression.calculate_wer, restated so that the chain harness does
    not import a 460-line training script for fifteen lines."""
    ref, hyp = (reference or "").split(), (hypothesis or "").split()
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1] / len(ref)


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    """Great-circle distance in metres on a sphere of radius 6,371,008.8 m, the IUGG mean
    Earth radius. Over a 20 km city the spherical approximation errs by far less than a
    parcel width, which is the resolution these distances are read at."""
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def pct(n: float, d: float):
    return round(100.0 * n / d, 1) if d else None


def quantile(values, q: float):
    """Nearest-rank quantile of a list; None when empty."""
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(q * (len(s) - 1)))]


# ------------------------------------------------------------------------- json baselines
def save_summary(path: str, summary: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)
    print(f"\nsummary written to {path}")


def load_summary(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def diff_summaries(current: dict, baseline: dict, title: str = "CHANGE VS BASELINE") -> None:
    """Print every number that moved, walking nested dicts. Direction is the reader's to
    judge: each harness names its defect buckets, and a WRONG count going down is good while
    an EXACT count going down is not."""
    lines = []

    def walk(cur, base, prefix):
        for k in sorted(set(cur or {}) | set(base or {})):
            c = (cur or {}).get(k)
            b = (base or {}).get(k)
            if isinstance(c, dict) or isinstance(b, dict):
                walk(c if isinstance(c, dict) else {}, b if isinstance(b, dict) else {}, prefix + str(k) + ".")
            elif isinstance(c, (int, float)) or isinstance(b, (int, float)):
                if c != b:
                    fmt = lambda v: "-" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))
                    delta = "" if c is None or b is None else f"{c - b:+.3f}" if isinstance(c - b, float) else f"{c - b:+d}"
                    lines.append(f"  {prefix + str(k):<42} {fmt(b):>9} -> {fmt(c):<9} {delta}")

    walk(current, baseline, "")
    print(f"\n{title} (every number that moved)")
    print("\n".join(lines) if lines else "  nothing moved")


# -------------------------------------------------------------------------------- record
def record_run(*, stage: str, n: int, args, metrics: dict, model_version: str,
               period=None, wer_pct=None, headline: str | None = None) -> None:
    """One row in public.evaluation_history. `metrics` is the harness's own summary as JSON;
    `headline` is the one line harness_history.py prints for the run."""
    engine = create_engine(database_url())
    metrics = dict(metrics)
    if headline:
        metrics["headline"] = headline
    notes = getattr(args, "notes", None)
    if git_dirty():
        notes = (notes + "; " if notes else "") + "working tree had uncommitted changes"
    gh = git_hash()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO public.evaluation_history "
            "(model_version, total_samples, wer, stage, git_hash, period_start, period_end, metrics, notes) "
            "VALUES (:mv, :n, :wer, :stage, :gh, :ps, :pe, CAST(:metrics AS jsonb), :notes)"),
            {"mv": model_version, "n": int(n),
             "wer": None if wer_pct is None else round(float(wer_pct), 2),
             "stage": stage, "gh": gh,
             "ps": period[0] if period else None, "pe": period[1] if period else None,
             "metrics": json.dumps(metrics, default=str), "notes": notes})
    engine.dispose()
    print(f"\nrecorded: stage={stage} git={gh} model={model_version} n={n} -> public.evaluation_history")
