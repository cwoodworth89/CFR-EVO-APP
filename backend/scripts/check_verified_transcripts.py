# backend/scripts/check_verified_transcripts.py
"""Spell- and street-checks the operator's verified transcripts before they become labels.

Run before every Whisper training pass. prepare_training_clips.py calls it and refuses to
build a dataset while blocking issues exist (override: --skip-label-check).

WHY THIS EXISTS
---------------
On the 2026-09-02 holdout, two of six address failures were the LABEL being wrong, not the
model: the verified transcript said "Norbur Pl" where the authoritative street is Norbury Pl
(the model's "norbery" was closer to the truth than its own reference), and "eagle mountain
driveuse" ran two words together. A verified transcript is simultaneously the training label
and the scoring reference, so a typo in it is trained in and then scored as correct.

WHAT BLOCKS, AND WHAT ONLY ADVISES
----------------------------------
Blocking is reserved for the one thing crews drive to:

  BLOCK   the main address street is not a street the city has (public.roads), or a call
          tagged [PA] is still flagged for training.
  ADVISE  everything else -- a probable typo elsewhere in the text, a cross street the city
          does not have (schools, "Turning Lane", mall access roads are legitimate cross
          streets and are not roads), a house number with no parcel (new builds exist), a
          note mentioning a cut-off recording.

The first version of this script blocked on all of it and reported 216 issues across 186
calls, most of them "Turning Lane is not a road". A gate that fires on a third of the corpus
is a gate that gets bypassed. Every source here is authoritative or the corpus itself:
public.roads, public.vocabulary, public.parcels, and phrases attested in >= ATTESTED_MIN
distinct verified transcripts (typos recur rarely; real words and places recur constantly).

Read-only. Exit status 1 when blocking issues exist, so a runner stops before training.
"""
import os
import re
import sys
import difflib
import logging
import argparse
from collections import Counter, defaultdict

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import cfr_dispatch                      # _load_env() on import sets DATABASE_URL
from cfr_dispatch.parser import parse_dispatch_announcement, sanitize_transcript
from cfr_dispatch.config import UNITS_VOCABULARY

# A token or cross-street phrase seen in this many distinct verified transcripts is treated
# as real. Typos observed 2026-09-02 each appeared once; descriptors like "Turning Lane"
# appear in dozens. Chosen from that corpus shape, not tuned.
ATTESTED_MIN = 3

# difflib ratio at or above which an unknown token is reported as a probable typo. Observed
# typos: norbur/norbury 0.92, shepard/shepherd 0.93, kencal/kensal 0.91, probelm/problem
# 0.86, erxine/erskine 0.86. Business words that are NOT typos sat lower: hortons/morton
# 0.77, aquatic/traumatic 0.71. 0.80 keeps the first group and drops the second.
TYPO_RATIO = 0.80

# Spoken after round 2 on calls with no addressable location; not part of the call text.
ADDENDUM = re.compile(r"contact\s+dispatch\s+via\s+radio\s+for\s+location\s+information", re.I)

WORD = re.compile(r"[a-z][a-z'\-]*")


def _tokens(text):
    return WORD.findall((text or "").lower())


class Authority:
    """Everything the city and the vocabulary table vouch for."""

    def __init__(self, conn):
        from sqlalchemy import text as sql
        self.roads = set()
        self.suffixes = set()
        self.tokens = set()
        for (name, rtype) in conn.execute(sql("SELECT roadname, roadtype FROM public.roads")):
            if name:
                self.roads.add(name.strip().lower())
                self.tokens.update(_tokens(name))
            if rtype:
                self.suffixes.add(rtype.strip().lower())
                self.tokens.update(_tokens(rtype))
        self.descriptors = set()
        for (cat, term) in conn.execute(sql("SELECT category, term FROM public.vocabulary WHERE is_active")):
            t = (term or "").strip().lower()
            self.tokens.update(_tokens(t))
            if cat == "street_suffix":
                self.suffixes.add(t)
            elif cat == "xstreet_descriptor":
                self.descriptors.add(t)
        self.parcels = set()
        self.parcels_by_house = defaultdict(list)     # house -> [(street, type, zone)]
        for (h, s, t, z) in conn.execute(sql(
                "SELECT house, street, streettype, zone_id FROM public.parcels "
                "WHERE house IS NOT NULL AND street IS NOT NULL")):
            house, street = str(h).strip(), s.strip().lower()
            self.parcels.add((house, street))
            self.parcels_by_house[house].append((street, (t or "").strip(), str(z or "").strip()))
        self.parcel_streets = {s for (_, s) in self.parcels}
        self.road_list = sorted(self.roads)
        self.token_list = sorted(self.tokens)

    def parcel_candidates(self, house, street, grid):
        """Parcels with this house number whose street starts like the misspelt one.

        The road-name fuzzy match could not resolve 'beaty' (2026-09-02); house 1883 on a
        'be...' street had exactly one parcel, 1883 Beedie Pl, and it sat in the call's map
        grid. House number plus prefix plus zone is a far stronger key than spelling alone.
        Candidates in the verified grid's zone are listed first.
        """
        if not house or not street:
            return []
        prefix = street[:2]
        found = [(s, t, z) for (s, t, z) in self.parcels_by_house.get(house, [])
                 if s.startswith(prefix)]
        found.sort(key=lambda p: (p[2] != grid, p[0]))
        seen, out = set(), []
        for s, t, z in found:
            if (s, t) in seen:
                continue
            seen.add((s, t))
            out.append("%s %s %s%s" % (house, s.title(), t, (" (zone %s)" % z) if z else ""))
        return out

    def strip_suffix(self, name):
        """'como lake ave' -> 'como lake'; leaves 'the high' alone if 'high' is not a suffix."""
        words = (name or "").strip().lower().split()
        if len(words) > 1 and words[-1] in self.suffixes:
            words = words[:-1]
        return " ".join(words)


def flagged_calls(conn):
    from sqlalchemy import text as sql
    return conn.execute(sql(
        "SELECT dispatch_id, verified_transcript, "
        "       COALESCE(target->>'review_notes', review_notes) AS notes, "
        "       btrim(coalesce(verified_map_grid, '')) AS verified_grid "
        "FROM public.dispatches "
        "WHERE feedback_submitted AND verified_transcript IS NOT NULL "
        "AND btrim(verified_transcript) <> :e "
        "AND COALESCE((target->>:k)::boolean, TRUE) ORDER BY dispatch_id"),
        {"e": "", "k": "include_in_training"}).fetchall()


HOUSE_ADDR = re.compile(r"^(\d+)\s+(.+)$")


def parsed_location(auth, verified):
    """(house, main_street, [cross_street, ...], spoken_grid) as the production parser sees them."""
    try:
        cands = parse_dispatch_announcement(sanitize_transcript(verified), UNITS_VOCABULARY)
    except Exception:
        return None, None, [], ""
    c = cands[0] if cands else None
    if not c:
        return None, None, [], ""
    house = street = None
    m = HOUSE_ADDR.match((c.address or "").strip())
    if m:
        house, street = m.group(1), auth.strip_suffix(m.group(2))
    xs = []
    for raw in (getattr(c, "x_street_1", None), getattr(c, "x_street_2", None)):
        if raw and raw.strip():
            xs.append(raw.strip().lower())
    # The grid as spoken in the verified text, via the parser's own extraction (it also
    # rejects values outside MAP_GRIDS, so an unparseable grid comes back empty).
    grid = str(getattr(c, "map_grid", "") or "").strip()
    return house, street, xs, grid


def run_check(conn):
    """Returns (blocking_count, advisory_count, report_lines)."""
    rows = flagged_calls(conn)
    auth = Authority(conn)

    # One parse per transcript, reused for both the frequency pass and the checks.
    parsed = {}
    doc_freq, xs_freq = Counter(), Counter()
    for did, verified, _, _ in rows:
        clean = ADDENDUM.sub("", verified or "")
        parsed[did] = (clean,) + parsed_location(auth, clean)
        doc_freq.update(set(_tokens(clean)))
        xs_freq.update(set(auth.strip_suffix(x) for x in parsed[did][3]))
    attested_tokens = {t for t, n in doc_freq.items() if n >= ATTESTED_MIN}
    attested_xs = {p for p, n in xs_freq.items() if n >= ATTESTED_MIN}
    accept = auth.tokens | attested_tokens

    blocking = advisory = 0
    per_call = defaultdict(list)

    def block(did, msg):
        nonlocal blocking; blocking += 1; per_call[did].append(("BLOCK", msg))

    def advise(did, msg):
        nonlocal advisory; advisory += 1; per_call[did].append(("ADVISE", msg))

    for did, _, notes, verified_grid in rows:
        clean, house, street, xs, spoken_grid = parsed[did]
        n = notes or ""

        # Curation slips -- checked first, because they are what the operator checks first.
        # The include_in_training flag is the exclusion mechanism: the operator un-checks it
        # by hand for PA pages ([PA] in the note) and for cut-off recordings (operator,
        # 2026-09-02). A call carrying either signal but still flagged is a slip, and it is
        # reported ahead of any spelling issue because un-flagging it makes the spelling moot.
        if re.search(r"\[PA\]", n, re.I):
            block(did, "UN-FLAG: tagged [PA] in review notes but still flagged for training")
        elif re.search(r"cut ?off|truncat", n, re.I):
            block(did, "UN-FLAG: review note says the recording was cut off, still flagged for training")

        # Main address street -- the one blocking check. Crews drive to this.
        if street:
            if street not in auth.roads:
                near = difflib.get_close_matches(street, auth.road_list, n=1, cutoff=0.75)
                hints = []
                if near:
                    hints.append("did you mean '%s'?" % near[0])
                cands = auth.parcel_candidates(house, street, verified_grid or spoken_grid)
                if cands:
                    hints.append("parcel(s) with this number: " + "; ".join(cands[:3]))
                hint = (" -- " + " ".join(hints)) if hints else ""
                block(did, "address street '%s' is not in public.roads%s" % (street, hint))
            elif house and street in auth.parcel_streets and (house, street) not in auth.parcels:
                advise(did, "no parcel %s on %s (new build, or a wrong number?)" % (house, street))

        # Grid consistency: the grid spoken in the verified text against the verified grid
        # field. On DISP-2026-D00EC5 the transcript said 101 (right -- Beedie Pl is in 101)
        # while verified_map_grid said 10; the backtest scores map-grid SMMR against the
        # field, so a wrong field is a wrong reference. Advisory: the audio label is not
        # affected, and either side could be the one in error.
        if spoken_grid and verified_grid and spoken_grid != verified_grid:
            advise(did, "GRID: transcript says map grid %s, verified_map_grid says %s"
                        % (spoken_grid, verified_grid))

        # Cross streets: roads, descriptors ("Mall Access"), schools and anything the corpus
        # repeats are all legitimate. Only a rare one the city does not have is worth a look.
        for raw in xs:
            phrase = auth.strip_suffix(raw)
            if (phrase in auth.roads or raw in auth.descriptors or phrase in attested_xs
                    or "school" in phrase):
                continue
            near = difflib.get_close_matches(phrase, auth.road_list, n=1, cutoff=0.8)
            hint = (" -- did you mean '%s'?" % near[0]) if near else ""
            advise(did, "cross street '%s' is not in public.roads%s" % (raw, hint))

        # Probable typos anywhere in the text. Advisory: business and place names live here.
        for tok in sorted(set(_tokens(clean)) - accept):
            if len(tok) <= 2:
                continue
            near = difflib.get_close_matches(tok, auth.token_list, n=1, cutoff=TYPO_RATIO)
            if near:
                advise(did, "'%s' -- probable typo of '%s'" % (tok, near[0]))

    def rank(did):
        levels = [l for l, _ in per_call[did]]
        msgs = [m for _, m in per_call[did]]
        if any(m.startswith("UN-FLAG") for m in msgs):
            return (0, did)          # curation slips first
        if "BLOCK" in levels:
            return (1, did)          # then transcripts that need fixing
        return (2, did)              # then advisories

    unflag = sum(1 for d in per_call if any(m.startswith("UN-FLAG") for _, m in per_call[d]))
    fix = sum(1 for d in per_call
              if any(l == "BLOCK" and not m.startswith("UN-FLAG") for l, m in per_call[d]))

    lines = []
    for did in sorted(per_call, key=rank):
        lines.append(did)
        for level, msg in per_call[did]:
            lines.append("    %-6s %s" % (level, msg))
    lines.append("")
    grids = sum(1 for d in per_call for _, m in per_call[d] if m.startswith("GRID:"))
    lines.append("checked %d flagged transcripts: %d call(s) to UN-FLAG (PA / cut-off), "
                 "%d transcript(s) to FIX (main street not in the city), %d grid mismatch(es), "
                 "%d advisory line(s)" % (len(rows), unflag, fix, grids, advisory))
    return blocking, advisory, lines


def main():
    ap = argparse.ArgumentParser(description="Spell- and street-check verified transcripts before training.")
    ap.add_argument("--quiet", action="store_true", help="summary line only")
    ap.add_argument("--blocking-only", action="store_true", help="omit advisory lines")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    from sqlalchemy import create_engine
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL is not set; it is loaded from backend/.env by importing cfr_dispatch.")

    with create_engine(db_url).connect() as conn:
        blocking, advisory, lines = run_check(conn)
    if args.quiet:
        lines = lines[-1:]
    elif args.blocking_only:
        lines = [l for l in lines if not l.startswith("    ADVISE")]
    print("\n".join(lines))
    sys.exit(1 if blocking else 0)


if __name__ == "__main__":
    main()
