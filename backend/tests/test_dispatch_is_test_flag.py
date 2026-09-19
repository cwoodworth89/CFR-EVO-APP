"""`is_test` reaches the stored dispatch row (2026-09-19).

The pipeline has sent `is_test` at the top level of the create payload since the flag
existed (cfr_dispatch/pipeline/payload_builder.py:496), but DispatchCreateSchema had no such
field, so Pydantic dropped it silently. Measured on the kiosk 2026-09-19: 0 of 700 rows carry
the key, so no corpus figure could exclude a test dispatch -- while CLAUDE.md 6.5 says genuine
pipeline test dispatches are marked with exactly this flag.

It lands in `target`, not a column: SUMMARY_TARGET_KEYS already names it and
frontend/src/utils/dispatchModel.js:122 already reads `record.is_test ?? target.is_test`.

No database: the route functions are exercised with a MagicMock session, as in
test_dispatch_summary.py, so this runs anywhere without touching DATABASE_URL (the kiosk).
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.api.models import LiveCallModel  # noqa: E402
from backend.api.schemas import DispatchCreateSchema, DispatchUpdateSchema  # noqa: E402
from backend.api.routers.dispatches import (  # noqa: E402
    SUMMARY_TARGET_KEYS,
    create_or_upsert_dispatch,
    serialize_call,
    serialize_call_summary,
    update_dispatch,
    _settle_is_test,
)

DISPATCH_ID = "DISP-2026-TEST01"


def _db(existing=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing
    return db


def _create(**body):
    """POST /api/dispatches with no row present, returning the serialized record."""
    payload = DispatchCreateSchema(**{"dispatch_id": DISPATCH_ID, **body})
    with patch("backend.api.routers.dispatches.publish_mqtt_event"):
        return create_or_upsert_dispatch(payload, db=_db())


def _patch(existing, **body):
    """PATCH /api/dispatches/{id} against `existing`, returning the serialized record."""
    payload = DispatchUpdateSchema(**body)
    with patch("backend.api.routers.dispatches.publish_mqtt_event"):
        return update_dispatch(DISPATCH_ID, payload, db=_db(existing))


def _row(**over):
    """A stored row, as phase 1 left it."""
    base = dict(
        id=7, dispatch_id=DISPATCH_ID, timestamp=None, incident_type="Medical Aid",
        responding_units=["E1"], routing_metrics=[], raw_transcript="Coquitlam engine one",
        target={"address": "1145 Heffley Cres", "review_flags": [], "is_test": True},
    )
    base.update(over)
    return LiveCallModel(**base)


class TestIsTestReachesTheRow(unittest.TestCase):
    def test_there_is_no_is_test_column(self):
        """Why it goes in `target`: the model has no attribute to set, and the live table has
        no such column (information_schema, kiosk, 2026-09-19). _settle_is_test must therefore
        pop the key -- LiveCallModel(**data) would raise on an unexpected kwarg."""
        self.assertFalse(hasattr(LiveCallModel, "is_test"))

    def test_true_round_trips_into_target_and_out_of_both_served_shapes(self):
        served = _create(is_test=True, target={"address": "1145 Heffley Cres"})
        self.assertIs(served["target"]["is_test"], True)
        # The address it arrived with is still there: the flag is merged, not substituted.
        self.assertEqual(served["target"]["address"], "1145 Heffley Cres")
        # Not promoted to the top level -- there is no column, and dispatchModel.js reads
        # `record.is_test ?? target.is_test`.
        self.assertNotIn("is_test", {k: v for k, v in served.items() if k != "target"})

        # Both shapes the API serves carry it (GET /api/dispatches, summary and full).
        row = _row(target=served["target"])
        self.assertIs(serialize_call(row)["target"]["is_test"], True)
        self.assertIs(serialize_call_summary(row)["target"]["is_test"], True)

    def test_summary_rows_carry_it_because_the_review_table_reads_it(self):
        self.assertIn("is_test", SUMMARY_TARGET_KEYS)

    def test_false_is_a_value_and_is_stored(self):
        """A real dispatch is is_test=False. That is a measurement, not an absence: the
        pipeline said so, and a corpus figure needs it to count the call as genuine."""
        served = _create(is_test=False, target={"address": "1145 Heffley Cres"})
        self.assertIn("is_test", served["target"])
        self.assertIs(served["target"]["is_test"], False)

    def test_absent_stores_nothing_rather_than_a_fabricated_false(self):
        """Every caller other than the pipeline sends no is_test. CLAUDE.md 6.1: an unknown
        stays unknown, so the key must be missing, not False."""
        served = _create(target={"address": "1145 Heffley Cres"})
        self.assertNotIn("is_test", served["target"])

    def test_explicit_null_stores_nothing_either(self):
        served = _create(is_test=None, target={"address": "1145 Heffley Cres"})
        self.assertNotIn("is_test", served["target"])

    def test_a_create_with_no_target_still_records_the_flag(self):
        """INTEGRATION_PAYLOAD_OPTION == 1 sends `address` instead of `target`
        (payload_builder.py:506). The flag still has to land somewhere."""
        data = {"dispatch_id": DISPATCH_ID, "is_test": True}
        _settle_is_test(data, None)
        self.assertEqual(data["target"], {"is_test": True})

    def test_phase_2_correction_cannot_erase_the_flag(self):
        """The regression this guards: phase 2's correction replaces `target` wholesale
        (payload_builder.py:509, phase2.py:527) with one build_dispatch_payload just built,
        which knows nothing of is_test. Folding on the way in puts the flag into the
        replacement, so the correction carries it instead of dropping it."""
        stored = _row()
        replacement = {"address": "1963 Lougheed Hwy", "review_flags": ["ADDRESS_CORRECTED"]}
        served = _patch(stored, is_test=True, target=replacement, verify_location=False)
        self.assertIs(served["target"]["is_test"], True)
        self.assertEqual(served["target"]["address"], "1963 Lougheed Hwy")

    def test_an_update_without_a_target_merges_into_the_stored_one(self):
        """Phase 2's non-correction branches send is_test with no target (phase2.py:557, 572).
        The stored target's other keys must survive."""
        stored = _row(target={"address": "1145 Heffley Cres", "review_flags": ["GRID_MISMATCH"]})
        served = _patch(stored, is_test=True, verify_location=True)
        self.assertIs(served["target"]["is_test"], True)
        self.assertEqual(served["target"]["review_flags"], ["GRID_MISMATCH"])
        self.assertEqual(served["target"]["address"], "1145 Heffley Cres")

    def test_an_update_that_is_silent_on_the_flag_leaves_it_alone(self):
        """An operator saving a review must not clear a call's test marking."""
        stored = _row(target={"address": "1145 Heffley Cres", "is_test": True})
        served = _patch(stored, quality_rating="GOOD")
        self.assertIs(served["target"]["is_test"], True)

    def test_the_fold_does_not_mutate_the_stored_target_in_place(self):
        """SQLAlchemy does not track in-place changes to a JSON column: the fold must hand
        back a new dict or the write is silently lost."""
        stored_target = {"address": "1145 Heffley Cres"}
        data = {"is_test": True}
        _settle_is_test(data, _row(target=stored_target))
        self.assertNotIn("is_test", stored_target)
        self.assertIs(data["target"]["is_test"], True)
        self.assertIsNot(data["target"], stored_target)


class TestEveryPhase2UpdateShapePreservesIt(unittest.TestCase):
    """Phase 2 sends four different UPDATE shapes and only three name `is_test`.

    The fourth is the common one. Audit on 3096dbc6: the agreement branch (phase2.py:387 --
    phase 1 and phase 2 agreeing on the address, the normal outcome) replaces `target`
    wholesale and sends no `is_test`, because its replacement is a spread of the phase-1
    target held in the worker's memory (phase2.py:313, worker.py:65), which never carried
    the flag. Folding a top-level flag is therefore not enough: the API has to carry a
    stored one across any `target` replacement that does not name it.

    Each shape below is transcribed from the call site named in its comment.
    """

    def _phase_1_created_a_test_dispatch(self):
        """POST as phase 1 sends it (payload_builder.py:487-509), returning the stored row."""
        served = _create(
            is_test=True,
            incident_type="*TEST* Medical Aid",
            responding_units=["E1"],
            raw_transcript="Coquitlam engine one",
            sanitized_transcript="Coquitlam engine one",
            verify_location=False,
            target={"address": "1145 Heffley Cres", "lat": 49.28, "lng": -122.79,
                    "map_grid": "68", "review_flags": [], "review_flag_count": 0},
        )
        self.assertIs(served["target"]["is_test"], True, "phase 1 create must store the flag")
        return _row(target=served["target"])

    def test_agreement_branch_the_common_path_keeps_the_flag(self):
        """phase2.py:371-387. No `is_test`, and `target` replaced wholesale. This is the one
        that erased it: every cleanly-geocoded test dispatch went through here."""
        stored = self._phase_1_created_a_test_dispatch()
        # target_payload as phase2.py:313 builds it: a spread of the phase-1 target with
        # phase 2's answers over it. Note there is no is_test key anywhere in this PATCH.
        replacement = {"address": "1145 Heffley Cres", "lat": 49.28, "lng": -122.79,
                       "x_street_1": "Austin Ave", "x_street_2": None, "map_grid": "68",
                       "map_grid_source": "parcel", "radio_channel": "TAC2",
                       "routing_metrics": [{"unit": "E1", "eta_minutes": 4}],
                       "review_flags": [], "review_flag_count": 0}
        served = _patch(
            stored,
            verify_location=False, audio_url="/api/audio/x.wav", audio_duration=28.4,
            raw_transcript="Coquitlam engine one", sanitized_transcript="Coquitlam engine one",
            incident_type="*TEST* Medical Aid", responding_units=["E1"],
            routing_metrics=replacement["routing_metrics"], target=replacement,
        )
        self.assertIs(served["target"]["is_test"], True)
        # Phase 2's own answers still win -- preserving one key must not resurrect the rest.
        self.assertEqual(served["target"]["radio_channel"], "TAC2")
        self.assertEqual(served["target"]["x_street_1"], "Austin Ave")

    def test_correction_branch_keeps_the_flag(self):
        """phase2.py:512-527. Sends is_test AND replaces target."""
        stored = self._phase_1_created_a_test_dispatch()
        replacement = {"address": "1963 Lougheed Hwy", "lat": 49.25, "lng": -122.88,
                       "review_flags": ["ADDRESS_CORRECTED"], "review_flag_count": 1}
        served = _patch(
            stored,
            verify_location=False, audio_url="/api/audio/x.wav", audio_duration=28.4,
            raw_transcript="Coquitlam engine one", sanitized_transcript="corrected",
            incident_type="*TEST* Medical Aid", responding_units=["E1"], is_test=True,
            routing_metrics=[], target=replacement,
        )
        self.assertIs(served["target"]["is_test"], True)
        self.assertEqual(served["target"]["address"], "1963 Lougheed Hwy")

    def test_geocode_failed_branch_keeps_the_flag(self):
        """phase2.py:553-558. Sends is_test, no target."""
        stored = self._phase_1_created_a_test_dispatch()
        served = _patch(
            stored,
            verify_location=True, audio_url="/api/audio/x.wav", audio_duration=28.4,
            raw_transcript="Coquitlam engine one", sanitized_transcript="full", is_test=True,
        )
        self.assertIs(served["target"]["is_test"], True)
        self.assertEqual(served["target"]["address"], "1145 Heffley Cres")

    def test_no_candidate_branch_keeps_the_flag(self):
        """phase2.py:568-573. Sends is_test, no target."""
        stored = self._phase_1_created_a_test_dispatch()
        served = _patch(
            stored,
            verify_location=False, audio_url="/api/audio/x.wav", audio_duration=28.4,
            raw_transcript="Coquitlam engine one", sanitized_transcript="full", is_test=True,
        )
        self.assertIs(served["target"]["is_test"], True)

    def test_a_genuine_call_is_not_turned_into_a_test_by_the_carry_forward(self):
        """The carry-forward must preserve False as faithfully as True, and must not invent
        a key on a row that never had one."""
        genuine = _row(target={"address": "1145 Heffley Cres", "is_test": False})
        served = _patch(genuine, target={"address": "1145 Heffley Cres", "map_grid": "68"})
        self.assertIs(served["target"]["is_test"], False)

        unmarked = _row(target={"address": "1145 Heffley Cres"})
        served = _patch(unmarked, target={"address": "1145 Heffley Cres", "map_grid": "68"})
        self.assertNotIn("is_test", served["target"])

    def test_an_incoming_target_that_names_the_flag_wins_over_the_stored_one(self):
        """Precedence: a replacement carrying its own answer is not overruled by history."""
        stored = _row(target={"address": "1145 Heffley Cres", "is_test": True})
        served = _patch(stored, target={"address": "1145 Heffley Cres", "is_test": False})
        self.assertIs(served["target"]["is_test"], False)


if __name__ == "__main__":
    unittest.main()
