"""Cross-round agreement reporting.

The module reports; it never picks a winner. These pin both halves of that: real
disagreements are caught, and cosmetic transcription variance is not reported as one.
"""
import unittest

from cfr_dispatch.config.models import DispatchData
from cfr_dispatch.pipeline.round_comparison import (
    AGREE, DISAGREE, SINGLE, ABSENT,
    compare_observations, observations_from_rounds, normalize_location_text,
    same_value, same_location_text, source_for_round,
)


def cand(**kw):
    kw.setdefault("raw_text", "")
    return DispatchData(**kw)


class TestLocationNormalisation(unittest.TestCase):
    """Unnormalised diffs overstate error -- 30.2% measured vs 16.8% real
    (docs/arrival_point_handoff.md). Two transcriptions rendering "Ave" and "Avenue"
    are not in disagreement about anything operational."""

    def test_suffix_variants_fold_together(self):
        self.assertTrue(same_location_text("2653 Sandstone Cres", "2653 Sandstone Crescent"))
        self.assertTrue(same_location_text("1123 Westwood St", "1123 Westwood Street"))
        self.assertTrue(same_location_text("Anson Ave", "Anson Avenue"))

    def test_punctuation_and_case_fold(self):
        self.assertTrue(same_location_text("1123 Westwood St.", "1123 westwood st"))

    def test_intersection_order_is_not_a_disagreement(self):
        # public.intersections stores alphabetically; the dispatcher says it either way.
        self.assertTrue(same_location_text("Gordon Ave and Christmas Way",
                                           "Christmas Way & Gordon Ave"))

    def test_a_different_house_number_is_still_a_disagreement(self):
        self.assertFalse(same_location_text("29883 Robson Dr", "2983 Robson Dr"))

    def test_a_different_street_is_still_a_disagreement(self):
        self.assertFalse(same_location_text("3100 Osada Ave", "3100 Ozeita Ave"))
        self.assertFalse(same_location_text("2735 Barnet Hwy", "2735 Varnette Hwy"))


class TestSameValueMirrorsFrontend(unittest.TestCase):
    """Deliberately mirrors sameValue in frontend/src/utils/dispatchModel.js so the
    backend and the kiosk cannot disagree about what counts as a change."""

    def test_none_and_empty_are_both_absent(self):
        self.assertTrue(same_value(None, ""))
        self.assertTrue(same_value("", None))

    def test_numeric_strings_compare_numerically(self):
        self.assertTrue(same_value("82", 82))

    def test_sequence_order_is_significant(self):
        # responding_units order is the dispatch order and the kiosk preserves it.
        self.assertFalse(same_value(["E1", "R2"], ["R2", "E1"]))
        self.assertTrue(same_value(["E1", "R2"], ["E1", "R2"]))


class TestVerdicts(unittest.TestCase):

    def test_rounds_agreeing_is_agree(self):
        c = compare_observations([
            ("p2r1", cand(address="1123 Westwood St")),
            ("p2r2", cand(address="1123 Westwood Street")),
        ])
        self.assertEqual(c.fields["address"].verdict, AGREE)
        self.assertEqual(c.disagreements, [])

    def test_rounds_differing_is_disagree_and_keeps_both_values(self):
        c = compare_observations([
            ("p2r1", cand(address="29883 Robson Dr")),
            ("p2r2", cand(address="2983 Robson Dr")),
        ])
        f = c.fields["address"]
        self.assertEqual(f.verdict, DISAGREE)
        self.assertTrue(f.is_flagged)
        # Both survive -- the operator decides, the module does not.
        self.assertEqual(set(f.values.values()), {"29883 Robson Dr", "2983 Robson Dr"})

    def test_one_source_only_is_single_not_agree(self):
        """Absence of a disagreement is not evidence of agreement."""
        c = compare_observations([
            ("p2r1", cand(address="1123 Westwood St", map_grid="82")),
            ("p2r2", cand(address="1123 Westwood St")),
        ])
        self.assertEqual(c.fields["map_grid"].verdict, SINGLE)
        self.assertFalse(c.fields["map_grid"].is_flagged)
        self.assertIn("map_grid", [f.name for f in c.uncorroborated])

    def test_no_source_has_it_is_absent(self):
        c = compare_observations([("p2r1", cand(address="1123 Westwood St"))])
        self.assertEqual(c.fields["subaddress"].verdict, ABSENT)

    def test_single_round_has_no_second_observation(self):
        c = compare_observations([("p2r1", cand(address="1123 Westwood St"))])
        self.assertFalse(c.has_second_observation)

    def test_x_streets_are_positional_not_a_set(self):
        """Operator ruling 2026-08-30: the announcement is
        [address] NEAR [x_street_1] AND [x_street_2], so position is part of what
        was said. This asserted AGREE on a swapped pair when written -- sorting the
        pair was my inference and it was wrong.
        """
        c = compare_observations([
            ("p2r1", cand(address="1123 Westwood St",
                          x_street_1="Anson Ave", x_street_2="Lincoln Ave")),
            ("p2r2", cand(address="1123 Westwood St",
                          x_street_1="Lincoln Avenue", x_street_2="Anson Avenue")),
        ])
        self.assertEqual(c.fields["x_streets"].verdict, DISAGREE)

    def test_same_x_streets_in_the_same_order_agree(self):
        c = compare_observations([
            ("p2r1", cand(address="X", x_street_1="Anson Ave", x_street_2="Lincoln Ave")),
            ("p2r2", cand(address="X", x_street_1="Anson Avenue", x_street_2="Lincoln Avenue")),
        ])
        self.assertEqual(c.fields["x_streets"].verdict, AGREE)

    def test_an_omitted_first_x_street_is_not_back_filled(self):
        """Either may be omitted. A round naming only the second must not read as
        agreeing with a round naming only the first."""
        c = compare_observations([
            ("p2r1", cand(address="X", x_street_1="Anson Ave")),
            ("p2r2", cand(address="X", x_street_2="Anson Ave")),
        ])
        self.assertEqual(c.fields["x_streets"].verdict, DISAGREE)

    def test_a_genuinely_different_cross_street_disagrees(self):
        c = compare_observations([
            ("p2r1", cand(address="X", x_street_1="Anson Ave", x_street_2="Lincoln Ave")),
            ("p2r2", cand(address="X", x_street_1="Anson Ave", x_street_2="Dawes Hill Rd")),
        ])
        self.assertEqual(c.fields["x_streets"].verdict, DISAGREE)

    def test_empty_input_is_not_an_error(self):
        c = compare_observations([])
        self.assertFalse(c.has_second_observation)
        self.assertEqual(c.disagreements, [])


class TestObservationAssembly(unittest.TestCase):

    def test_phase_1_and_each_round_become_sources(self):
        obs = observations_from_rounds(
            cand(address="1123 Westwood St"),
            [[cand(address="1123 Westwood St")], [cand(address="1123 Westwood St")]],
        )
        self.assertEqual([s for s, _ in obs], ["p1", "p2r1", "p2r2"])

    def test_a_round_with_no_located_candidate_is_skipped_but_labels_do_not_renumber(self):
        """Round 1 parsed no address; the surviving observation is still labelled p2r2.

        The label says which round it came from, so a later reader can tell "round 2
        only" from "round 1 only". Renumbering would erase that.
        """
        obs = observations_from_rounds(None, [[cand(units="Engine 1")],
                                              [cand(address="1123 Westwood St")]])
        self.assertEqual([s for s, _ in obs], ["p2r2"])

    def test_round_labels_are_one_based(self):
        self.assertEqual(source_for_round(0), "p2r1")
        self.assertEqual(source_for_round(1), "p2r2")


if __name__ == "__main__":
    unittest.main()
