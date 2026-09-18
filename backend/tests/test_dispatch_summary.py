"""The review list's summary rows and the lean evaluations list (2026-09-18).

No database: the serialisers and the evaluations route are exercised on stand-in rows, so
this runs anywhere without touching DATABASE_URL (which points at the kiosk).
"""
import os
import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.api.routers.dispatches import serialize_call, serialize_call_summary, SUMMARY_TARGET_KEYS  # noqa: E402
from backend.api.routers.evaluations import get_evaluations  # noqa: E402


def _call(**over):
    base = dict(
        id=7, dispatch_id="DISP-2026-TEST01", timestamp=datetime(2026, 9, 17, 3, 0, tzinfo=timezone.utc),
        incident_type="Medical Aid", responding_units=["E1", "M1"], routing_metrics=[{"unit": "E1", "eta_minutes": 4}],
        target={
            "address": "1145 Heffley Cres", "map_coords_accurate": True, "tone_name": "Engine",
            "review_flags": ["GRID_MISMATCH"], "review_flag_count": 1,
            "rings": [[[1, 2], [3, 4], [5, 6]]], "routing_metrics": [{"unit": "E1"}], "review_notes": "long notes",
        },
        raw_transcript="Coquitlam engine one", sanitized_transcript="sanitized", verified_transcript="verified",
        verify_location=False, origins=["1"], audio_url="/recordings/x.wav", audio_duration=41.5,
        verified_address="1145 Heffley Cres", verified_incident=None, verified_units=["E1"],
        verified_map_grid="68", verified_talkgroup=None, verified_response_type="routine",
        verified_x_street_1=None, verified_x_street_2=None, feedback_submitted=True,
        quality_rating="GOOD", model_updated=False, review_notes=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


class TestDispatchSummary(unittest.TestCase):
    def test_summary_carries_what_the_table_reads_and_drops_the_weight(self):
        s = serialize_call_summary(_call())
        self.assertTrue(s["summary"])
        for key in ("id", "dispatch_id", "timestamp", "incident_type", "responding_units", "raw_transcript",
                    "verified_address", "verified_units", "verified_map_grid", "verified_response_type",
                    "feedback_submitted", "quality_rating", "model_updated"):
            self.assertIn(key, s)
        for gone in ("routing_metrics", "sanitized_transcript", "verified_transcript", "origins",
                     "created_at", "audio_url", "audio_duration"):
            self.assertNotIn(gone, s)
        # Empty optional fields are left out, not sent as null.
        for empty in ("verified_incident", "verified_talkgroup", "verified_x_street_1", "verified_x_street_2"):
            self.assertNotIn(empty, s)
        # model_updated False is a value, not an empty: it is sent.
        self.assertIs(s["model_updated"], False)
        self.assertEqual(set(s["target"]), set(SUMMARY_TARGET_KEYS) & set(_call().target))
        self.assertNotIn("rings", s["target"])
        self.assertEqual(s["target"]["review_flags"], ["GRID_MISMATCH"])

    def test_full_record_is_unchanged_and_not_marked_summary(self):
        f = serialize_call(_call())
        self.assertNotIn("summary", f)
        self.assertIn("rings", f["target"])
        self.assertEqual(f["sanitized_transcript"], "sanitized")

    def test_summary_survives_a_null_target(self):
        self.assertEqual(serialize_call_summary(_call(target=None))["target"], {})

    def test_evaluations_summary_drops_metrics_only(self):
        row = SimpleNamespace(
            id=1, created_at=datetime(2026, 9, 5, tzinfo=timezone.utc), model_version="base", total_samples=10,
            wer=4.2, cer=1.1, perfect_percent=50.0, operational_percent=80.0, failed_percent=5.0, stage="stt",
            git_hash="abc", period_start=None, period_end=None, metrics={"big": [1] * 100}, notes="n",
        )
        db = MagicMock()
        db.query.return_value.order_by.return_value.all.return_value = [row]
        full = get_evaluations(summary=False, db=db)
        lean = get_evaluations(summary=True, db=db)
        self.assertIn("metrics", full[0])
        self.assertNotIn("metrics", lean[0])
        self.assertEqual({k: v for k, v in full[0].items() if k != "metrics"}, lean[0])


if __name__ == "__main__":
    unittest.main()
