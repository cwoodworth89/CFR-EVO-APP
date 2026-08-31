"""The parcel import must never write `entrance_lat` / `entrance_lng`.

Those hold the OPERATOR-VERIFIED way in, recorded by a company officer, and
`address_resolver` ranks them above everything else:

    entrance  ->  front  ->  centroid

The import used to seed them from the parcel CENTROID on INSERT. A newly loaded
parcel therefore resolved to the worst of the three positions while presenting as
though a human had verified it -- the good computed front point was skipped, and
`entrance_set_by` / `entrance_set_at` / `entrance_note` were all NULL with nothing
checking them. On 177 parcels the centroid is not even inside the parcel.

This survived because the invariant was held by a COMMENT, and the comment was
attached to the wrong function: it sat above `backfill_parcel_frontage`, which
genuinely never writes entrance, while the INSERT 200 lines below did.
So it is asserted here instead (punch-list #50).

These tests read the scripts as text rather than running an import, deliberately:
the defect is in the SQL and the bound parameters, both of which are statically
checkable, and neither requires a database. A live import is the trial run, not
the regression guard.
"""
import io
import os
import re
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = {
    "production": os.path.join(REPO, "backend", "scripts", "import_parcels.py"),
    # import_parcels_PROPOSED.py was deleted 2026-08-31 -- the Boundary-Edge
    # Decomposition proposal was not adopted, so there is no second script to guard.
}


def source(name):
    return io.open(SCRIPTS[name], encoding="utf-8", errors="replace").read()


def insert_statement(text):
    """The INSERT INTO public.parcels (...) VALUES (...) block, columns and binds."""
    m = re.search(r"INSERT INTO public\.parcels\s*\((.*?)\)\s*VALUES\s*\((.*?)\)\s*ON CONFLICT",
                  text, re.S | re.I)
    assert m, "could not locate the parcels INSERT ... VALUES ... ON CONFLICT block"
    return m.group(1), m.group(2)


class TestImportNeverWritesEntrance(unittest.TestCase):

    def test_entrance_is_not_an_insert_column(self):
        for name in SCRIPTS:
            with self.subTest(script=name):
                columns, _ = insert_statement(source(name))
                self.assertNotIn("entrance_lat", columns)
                self.assertNotIn("entrance_lng", columns)

    def test_entrance_is_not_a_bound_value(self):
        for name in SCRIPTS:
            with self.subTest(script=name):
                _, binds = insert_statement(source(name))
                self.assertNotIn(":entrance_lat", binds)
                self.assertNotIn(":entrance_lng", binds)

    def test_entrance_is_not_a_record_parameter(self):
        """The params dict must not carry the key at all -- an unbound column is
        SQL NULL, which is what the resolver needs to fall through to front."""
        for name in SCRIPTS:
            with self.subTest(script=name):
                self.assertNotRegex(source(name), r'"entrance_(lat|lng)"\s*:')

    def test_entrance_is_not_in_the_on_conflict_update(self):
        """Existing rows were always safe; this keeps them that way."""
        for name in SCRIPTS:
            with self.subTest(script=name):
                self.assertNotIn("entrance_lat = EXCLUDED", source(name))
                self.assertNotIn("entrance_lng = EXCLUDED", source(name))

    def test_the_column_still_exists_in_the_schema(self):
        """Not written by the import, but still a real column the UX will set.
        Guards against 'fixing' this by deleting the column."""
        for name in SCRIPTS:
            with self.subTest(script=name):
                text = source(name)
                self.assertIn("entrance_lat DOUBLE PRECISION", text)
                self.assertIn("entrance_lng DOUBLE PRECISION", text)

    def test_front_point_is_still_written(self):
        """The fix must not take the computed arrival point with it -- front_lat
        is what the resolver now falls through to."""
        for name in SCRIPTS:
            with self.subTest(script=name):
                columns, binds = insert_statement(source(name))
                self.assertIn("front_lat", columns)
                self.assertIn(":front_lat", binds)


if __name__ == "__main__":
    unittest.main()
