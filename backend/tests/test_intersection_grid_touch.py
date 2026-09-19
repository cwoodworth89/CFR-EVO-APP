"""Punch list #96: an announced map grid matches a junction on a zone line.

Zone lines run along roads, so a junction is on two or more zones as a rule: 584 of 1,994
junctions lie within 1 m of two or more (kiosk, 2026-09-19). Each candidate now carries
`grids` (every zone within geocoder.ZONE_TOUCH_M, 5 m) beside its single `grid`
(public.zone_for_point). The announced grid filters by touch and ranks by containment.

The shapes below are the kiosk's own values for these street pairs on 2026-09-19 (the
`grid` / `grids` the cache loader now produces), not invented geometry.
"""
from gis_service.intersection_resolver import IntersectionResolver


def _cand(name, ix, grid, grids, lat=49.28, lng=-122.80):
    return {"name": name, "lat": lat, "lng": lng + ix * 0.001, "grid": grid, "grids": grids,
            "description": name, "candidate_index": ix, "match_type": "exact"}


R = IntersectionResolver({}, 80)


def test_the_a018e9_junction_matches_either_grid_it_lies_on():
    # DISP-2026-A018E9, David Ave & Genest Way, announced 88. The junction is on the 86/88 line;
    # zone_for_point answers 86. Before #96: "none of these junctions lie in map grid 88".
    david_genest = [_cand("David Ave & Genest Way", 0, "86", ["86", "88"])]
    for grid in ("88", "86", "Grid 88"):
        res = R.resolve_candidates(list(david_genest), target_map_grid=grid)
        assert res["is_ambiguous"] is False, grid
        assert res["resolution_note"] is None, grid


def test_a_double_crossing_inside_one_zone_is_unchanged():
    # Baker Dr & Sumpter Dr: both junctions inside 40 only. The grid never told them apart.
    baker = [_cand("Baker Dr & Sumpter Dr", 0, "40", ["40"]),
             _cand("Baker Dr & Sumpter Dr", 1, "40", ["40"])]
    res = R.resolve_candidates(list(baker), target_map_grid="40")
    assert res["is_ambiguous"] is True
    assert len(res["candidates"]) == 2
    assert "map grid" not in (res["resolution_note"] or "")


def test_a_boundary_overlap_pair_on_the_shared_grid_resolves_to_the_contained_junction():
    # Briarcliffe Dr & Lansdowne Dr: #0 inside 72, #1 on the 71/72 line (zone_for_point 71).
    briar = [_cand("Briarcliffe Dr & Lansdowne Dr", 0, "72", ["72"]),
             _cand("Briarcliffe Dr & Lansdowne Dr", 1, "71", ["71", "72"])]
    res = R.resolve_candidates(list(briar), target_map_grid="72")
    assert (res["is_ambiguous"], res["lng"]) == (False, briar[0]["lng"])
    res = R.resolve_candidates(list(briar), target_map_grid="71")
    assert (res["is_ambiguous"], res["lng"]) == (False, briar[1]["lng"])


def test_two_junctions_on_the_same_line_keep_resolving_as_they_did():
    # Cypress St & Foster Ave: both within 5 m of 37 and 38; zone_for_point says 37 and 38.
    # Before #96 each grid resolved automatically; a plain touch filter would make both a
    # selector. The containment rank keeps them automatic.
    cypress = [_cand("Cypress St & Foster Ave", 0, "37", ["37", "38"]),
               _cand("Cypress St & Foster Ave", 1, "38", ["37", "38"])]
    for grid, ix in (("37", 0), ("38", 1)):
        res = R.resolve_candidates(list(cypress), target_map_grid=grid)
        assert (res["is_ambiguous"], res["lng"]) == (False, cypress[ix]["lng"]), grid


def test_a_grid_only_one_junction_touches_now_resolves_instead_of_raising_the_note():
    # Lansdowne Dr & Steeple Dr, announced 72: only #1 touches 72 (zone_for_point 71).
    steeple = [_cand("Lansdowne Dr & Steeple Dr", 0, "71", ["71"]),
               _cand("Lansdowne Dr & Steeple Dr", 1, "71", ["71", "72"])]
    res = R.resolve_candidates(list(steeple), target_map_grid="72")
    assert (res["is_ambiguous"], res["lng"], res["resolution_note"]) == (False, steeple[1]["lng"], None)


def test_a_junction_strictly_inside_one_zone_with_a_wrong_grid_is_still_noted():
    christmas = [_cand("Christmas Way & Westwood St", 0, "62", ["62"])]
    res = R.resolve_candidates(list(christmas), target_map_grid="61")
    assert res["is_ambiguous"] is True
    assert "none of these junctions lie in map grid 61" in res["resolution_note"]


def test_a_candidate_without_grids_behaves_as_before():
    # A cache built before #96 carries only `grid`; the single grid still matches.
    old = [_cand("Old Shape Rd & Test St", 0, "12", None)]
    assert R.resolve_candidates(list(old), target_map_grid="12")["is_ambiguous"] is False
    assert "map grid 13" in R.resolve_candidates(list(old), target_map_grid="13")["resolution_note"]
