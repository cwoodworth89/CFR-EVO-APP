#!/usr/bin/env python3
"""Score the geocoder against the human-verified dispatch corpus.

Replays the *stored* parsed address for each verified dispatch back through the live
Geocoder, records which resolution step answered, and diffs the result against the
operator's `verified_address`.

Why this exists
---------------
`public.dispatches` holds paired ground truth: what the system concluded (`target`)
alongside what a human confirmed was true (`verified_*`). That pairing can score the
geocoder, not just STT word error rate. (`confidence_score` used to be read here too; it was
dropped 2026-08-29, punch-list #45, and the "stored confidence on wrong streets" summary went
with it on 2026-09-03 when the query started failing.)

This does NOT synthesise dispatches (CLAUDE.md 6.5) -- every row replayed is a real
historical record. It is read-only: no INSERT/UPDATE, and nothing is published to MQTT.

Which step answered is captured by wrapping the resolver methods rather than by reading
the code, because the step ladder in Geocoder.get_coordinates falls through on None and
the answering step is not otherwise recorded anywhere.

Usage
-----
    # one call, full step-by-step trace
    python tools/trace_geocode_corpus.py --dispatch-id DISP-2026-156DCF

    # whole verified corpus, summary + per-call CSV
    python tools/trace_geocode_corpus.py --all --csv /tmp/geocode_corpus.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter

import _repo  # noqa: F401  tools/_repo.py puts backend/ and services/*/src on sys.path

from sqlalchemy import create_engine, text  # noqa: E402

from gis_service.geocoder import CoquitlamDataValidator  # noqa: E402
from gis_service.address_resolver import AddressResolver  # noqa: E402
from gis_service.intersection_resolver import IntersectionResolver  # noqa: E402

TRACED = [
    (AddressResolver, "resolve_exact", "1-exact"),
    (AddressResolver, "resolve_block", "3-block"),
    (AddressResolver, "resolve_x_street_narrow", "4-x-street"),
    (AddressResolver, "resolve_nearest_civic", "4b-nearest-civic"),
    (AddressResolver, "resolve_street_centroid", "5-street-centroid"),
    (AddressResolver, "resolve_road_centroid", "6-road-centroid"),
    (IntersectionResolver, "resolve_candidates", "2-intersection"),
]

SUFFIX = {
    "AVENUE": "AVE", "STREET": "ST", "ROAD": "RD", "DRIVE": "DR", "PLACE": "PL",
    "COURT": "CRT", "CT": "CRT", "CRESCENT": "CRES", "BOULEVARD": "BLVD",
    "HIGHWAY": "HWY", "LANE": "LN", "SQUARE": "SQ",
}


def install_tracer():
    """Wrap each resolver so we learn which one produced the answer.

    Records every step *attempted* and what it returned, so a call that falls through
    several steps shows the whole ladder rather than only the winner.
    """
    log = []

    def wrap(cls, name, label):
        original = getattr(cls, name)

        def traced(self, *a, **kw):
            result = original(self, *a, **kw)
            log.append({
                "step": label,
                "args": [repr(x) for x in a],
                "hit": result is not None,
                "address": (result or {}).get("address"),
                "confidence": (result or {}).get("confidence"),
                "is_ambiguous": (result or {}).get("is_ambiguous"),
                "note": (result or {}).get("resolution_note"),
            })
            return result

        traced.__name__ = name
        setattr(cls, name, traced)

    for cls, name, label in TRACED:
        wrap(cls, name, label)
    return log


def norm(s):
    """Compare addresses the way an operator reads them, not byte-for-byte.

    Drops the ", Coquitlam, BC V3B 0M1, Canada" locality tail that older geocoder
    versions appended. The operator never typed it into verified_address, so keeping
    it would score a string-formatting difference as a wrong location.
    """
    if not s:
        return ""
    t = re.sub(r"\s+", " ", s).strip().upper()
    t = t.split(",")[0].strip()
    return t


def is_intersection(s):
    return bool(re.search(r"\s(?:&|AND)\s", norm(s)))


def canon_intersection(s):
    """Order-independent key for an intersection.

    "CHRISTMAS WAY & GORDON AVE" and "GORDON AVE & CHRISTMAS WAY" are the same
    junction; dispatch and the operator write the legs in whichever order they were
    spoken. Comparing them positionally reports a match as a defect.
    """
    legs = [p.strip() for p in re.split(r"\s(?:&|AND)\s", norm(s)) if p.strip()]
    return " & ".join(sorted(" ".join(SUFFIX.get(w, w) for w in leg.split())
                             for leg in legs))


def street_of(s):
    """Street portion only -- drops the house number and any trailing unit."""
    t = norm(s)
    # \b\s* not \s+ : a bare house number ("1550") has no trailing space, and must
    # still reduce to an empty street so it buckets as no-street rather than as a
    # street literally named "1550".
    t = re.sub(r"^\d+\b\s*", "", t)
    t = re.sub(r"\s+\d+[A-Z]?$", "", t)
    t = re.sub(r"\s*\(.*\)$", "", t)
    return t.strip()


def canon(s):
    """Collapse suffix spelling so 'Carmelo Avenue' and 'Carmelo Ave' compare equal."""
    return " ".join(SUFFIX.get(w, w) for w in street_of(s).split())


def classify(sys_addr, true_addr):
    """Bucket a system address against the operator-verified one.

    exact / cosmetic are the same place; every other bucket is a defect. The
    house-number test must run *before* the suffix-canonicalising comparison, or a
    right-street/wrong-number result ("307 Glen Dr" for "3007 Glen Dr") is absorbed
    into "cosmetic" and disappears from the count.
    """
    if norm(sys_addr) == norm(true_addr):
        return "exact"
    if not norm(sys_addr):
        return "unresolved"

    # Intersections compare as unordered pairs, before any house-number logic --
    # a junction has no house number and the leg order carries no meaning.
    if is_intersection(sys_addr) and is_intersection(true_addr):
        return "cosmetic" if canon_intersection(sys_addr) == canon_intersection(true_addr) \
            else "wrong-street"
    if is_intersection(sys_addr) != is_intersection(true_addr):
        # One side is a junction and the other a civic address: a real disagreement
        # about what kind of place this is, not a formatting difference.
        return "wrong-street"

    hn_s = re.match(r"^(\d+)", norm(sys_addr))
    hn_t = re.match(r"^(\d+)", norm(true_addr))
    same_street = canon(sys_addr) == canon(true_addr)

    if same_street and hn_s and hn_t and hn_s.group(1) != hn_t.group(1):
        return "house-number"
    if same_street:
        return "cosmetic"
    # A house number with no street name at all: the pipeline emitted a fragment.
    # Distinct from wrong-street because nothing was mismatched -- the street was lost.
    if not street_of(sys_addr):
        return "no-street"
    return "wrong-street"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dispatch-id")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--csv")
    ap.add_argument("--probe", help=(
        "Geocode this literal address string and print the step ladder. Use for the "
        "text the PARSER produced, which is not what the record stores: the stored "
        "target.address is the geocoder's own answer, so replaying it only shows that "
        "the answer round-trips, never how it was arrived at."))
    args = ap.parse_args()

    db = os.environ.get("DATABASE_URL")
    if not db:
        print("DATABASE_URL is not set. Without it this would report nothing rather "
              "than failing loudly, which is the trap the handoff describes.",
              file=sys.stderr)
        return 2

    engine = create_engine(db)

    if args.probe:
        log = install_tracer()
        geo = CoquitlamDataValidator(database_url=db)
        result = geo.get_coordinates(args.probe)
        print("  probe   : %r" % args.probe)
        print("  result  : %r conf=%s ambiguous=%s\n"
              % ((result or {}).get("address"), (result or {}).get("confidence"),
                 (result or {}).get("is_ambiguous")))
        print("  step ladder (in call order):")
        for e in log:
            print("    [%s] %-18s args=%s" % ("HIT " if e["hit"] else "miss",
                                              e["step"], e["args"]))
            if e["hit"]:
                print("           -> address=%r conf=%s ambiguous=%s note=%r"
                      % (e["address"], e["confidence"], e["is_ambiguous"], e["note"]))
        return 0

    if args.dispatch_id:
        where, params = "dispatch_id = :did", {"did": args.dispatch_id}
    else:
        where, params = ("verified_address IS NOT NULL "
                         "AND btrim(verified_address) <> ''"), {}

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT dispatch_id, raw_transcript, verified_address, "
            "       target->>'address'      AS sys_addr, "
            "       target->>'map_grid'     AS sys_grid, "
            "       target->>'intersection' AS sys_intersection, "
            "       target->>'lat'          AS lat "
            "FROM public.dispatches "
            f"WHERE {where} "
            "ORDER BY dispatch_id"
        ), params).mappings().fetchall()

    print("Replaying %d record(s) from the verified corpus.\n" % len(rows))

    log = install_tracer()
    geo = CoquitlamDataValidator(database_url=db)

    buckets = Counter()
    step_by_kind = Counter()
    out = []

    for r in rows:
        log.clear()
        # Replay the address the pipeline actually recorded. The transcript -> address
        # parse is a separate stage with its own ground truth (raw vs verified
        # transcript) and is scored separately; mixing them would hide which stage failed.
        probe = r["sys_addr"]
        try:
            result = geo.get_coordinates(probe, target_map_grid=r["sys_grid"])
        except Exception as e:  # a crash is a finding, not a reason to stop the sweep
            result = None
            log.append({"step": "EXCEPTION", "args": [], "hit": False, "address": str(e),
                        "confidence": None, "is_ambiguous": None, "note": None})

        answering = next((e["step"] for e in log if e["hit"]), "none")
        kind = classify(r["sys_addr"], r["verified_address"])
        buckets[kind] += 1
        step_by_kind[(kind, answering)] += 1

        out.append({
            "dispatch_id": r["dispatch_id"],
            "kind": kind,
            "answering_step": answering,
            "system_address": r["sys_addr"],
            "verified_address": r["verified_address"],
            "replay_address": (result or {}).get("address"),
            "replay_confidence": (result or {}).get("confidence"),
            "replay_ambiguous": (result or {}).get("is_ambiguous"),
        })

        if args.dispatch_id:
            print("  dispatch      : %s" % r["dispatch_id"])
            print("  probe address : %r" % probe)
            print("  verified      : %r" % r["verified_address"])
            print("  classification: %s\n" % kind)
            print("  step ladder (in call order):")
            for e in log:
                mark = "HIT " if e["hit"] else "miss"
                print("    [%s] %-18s args=%s" % (mark, e["step"], e["args"]))
                if e["hit"]:
                    print("           -> address=%r conf=%s ambiguous=%s note=%r"
                          % (e["address"], e["confidence"], e["is_ambiguous"], e["note"]))
            print()

    if not args.dispatch_id:
        total = sum(buckets.values()) or 1
        print("Address outcome across the verified corpus")
        print("-" * 48)
        for k in ("exact", "cosmetic", "house-number", "wrong-street", "no-street", "unresolved"):
            n = buckets.get(k, 0)
            print("  %-14s %4d  %5.1f%%" % (k, n, 100.0 * n / total))
        print("  %-14s %4d" % ("TOTAL", sum(buckets.values())))

        print("\nWhich step answered, for the calls that were wrong:")
        for (kind, step), n in sorted(step_by_kind.items(), key=lambda kv: -kv[1]):
            if kind in ("wrong-street", "house-number", "no-street"):
                print("  %-13s via %-18s %3d" % (kind, step, n))

    if args.csv and out:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
        print("\nPer-call detail written to %s" % args.csv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
