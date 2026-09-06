"""Phase 1 publishes the placed parcel's zone as the map grid; phase 2 takes the spoken one.

Punch list #72. On 448 recordings replayed in the listener's own chunks, the grid in the chunk
that trips the completion check was the model's completion on 314: at 16-19 s the dispatcher
has not reached the grid, and the model finishes the sentence. The parcel's own zone
(public.parcels.zone_id) agrees with the announced grid on 96.3 % of exact placements, so a
preliminary payload takes that and says so; the final payload takes the spoken grid.

The transcript below is DISP-2026-3E1426's 19-second chunk as the model wrote it on
2026-09-05: real address, completed talk group, completed grid 68. The call's real grid is 82.
Needs the kiosk database (DATABASE_URL); skipped otherwise. Read-only against it.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cfr_dispatch  # noqa: E402,F401
from cfr_dispatch.config import UNITS_VOCABULARY  # noqa: E402
from cfr_dispatch.parser import sanitize_transcript, split_rounds, parse_dispatch_announcement  # noqa: E402
from cfr_dispatch.pipeline.payload_builder import build_dispatch_payload  # noqa: E402
from cfr_dispatch.pipeline.review_flags import GRID_MISMATCH, NO_MAP_GRID  # noqa: E402
from gis_service import CoquitlamDataValidator  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL.startswith("postgres"),
                                reason="needs the kiosk database: set DATABASE_URL")

CHUNK_19S = ("coquitlam medic 1 respond emergency medical aid back pain 3080 lincoln avenue number 2507 "
             "near westwood street and westwood street and westwood street and westwood street "
             "use talk group 10 combined response coquitlam map grid 68")
# DISP-2026-33D8C2, the cut structure fire: no parcel behind "166 coquitlam".
CUT_FIRE = ("coquitlam engine 1 engine 4 engine 2 rescue 2 quint 5 car 8 respond emergency structure fire "
            "166 coquitlam map grid 68")


@pytest.fixture(scope="module")
def validator():
    return CoquitlamDataValidator(database_url=DATABASE_URL)


def candidates(raw):
    san = sanitize_transcript(raw)
    cands = []
    for seg in split_rounds(san, UNITS_VOCABULARY):
        if len(seg.split()) > 2:
            cands.extend(parse_dispatch_announcement(seg, UNITS_VOCABULARY))
    return san, cands


def parcel_zone(validator, address_prefix):
    from sqlalchemy import text
    with validator.engine.connect() as conn:
        row = conn.execute(text("SELECT zone_id FROM public.parcels WHERE upper(address) LIKE :a ORDER BY id LIMIT 1"),
                           {"a": address_prefix.upper() + "%"}).fetchone()
    assert row and row[0], address_prefix
    return str(row[0])


def test_preliminary_grid_is_the_parcels_zone_not_the_chunks(validator):
    san, cands = candidates(CHUNK_19S)
    assert next(c.map_grid for c in cands if c.map_grid) == "68"  # what the chunk says
    payload, _ = build_dispatch_payload("TEST", CHUNK_19S, san, cands, validator, UNITS_VOCABULARY,
                                        preliminary=True)
    target = payload["target"]
    assert target["address"] == "3080 Lincoln Ave"
    assert target["map_grid"] == parcel_zone(validator, "3080 LINCOLN AVE")
    assert target["map_grid_source"] == "parcel-zone"
    assert target["map_grid"] != "68"


def test_final_grid_is_the_spoken_one(validator):
    san, cands = candidates(CHUNK_19S)
    payload, _ = build_dispatch_payload("TEST", CHUNK_19S, san, cands, validator, UNITS_VOCABULARY)
    target = payload["target"]
    assert target["map_grid"] == "68" and target["map_grid_source"] == "announced"


def test_no_parcel_means_no_preliminary_grid(validator):
    san, cands = candidates(CUT_FIRE)
    payload, _ = build_dispatch_payload("TEST", CUT_FIRE, san, cands, validator, UNITS_VOCABULARY,
                                        preliminary=True)
    target = payload["target"]
    assert target["map_grid"] is None and target["map_grid_source"] is None
    assert NO_MAP_GRID in target["review_flags"]
    assert GRID_MISMATCH not in target["review_flags"]
