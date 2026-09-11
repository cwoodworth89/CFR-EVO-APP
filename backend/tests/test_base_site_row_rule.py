"""One address means one row, and that row is the property's `base_site` row.

`public.parcels` is one row per ADDRESS, not per parcel. A multi-parcel property returns
many rows for the same address and neither key picks between them: 43,842 rows (62 %) share
a `gis_id` with a different address, and 2,170 addresses are themselves duplicated.

So *something* has to choose, and until 2026-09-10 each caller chose for itself. The entrance
save, the console lookup, the Street View override and the dispatch resolver each built the
same four-condition OR and took `.first()` with no ordering. They disagreed, silently:

    resolver  ->  "2929 Barnet Hwy 2112"   (lowest id of 236 rows)
    lookup    ->  whichever row came back first
    entrance  ->  an arbitrary member of the gis_id group

The operator's Coquitlam Centre arrival point was answered 200 OK and written to a suite row,
while the dispatched address kept none. Saved, and never read (punch-list #77).

The fix is not four corrected copies -- that is the same defect waiting to happen on the
fifth caller. It is ONE rule, `parcels._address_row`, that every address -> row lookup goes
through, ordering `is_base_site` first. These tests guard that:

    1. the column is visible to the ORM at all (it was not, which is how this began),
    2. the resolver's SQL orders by it,
    3. no router reintroduces a private address lookup beside the shared one.

Read as source rather than run against a database, in the idiom of
`test_parcel_import_entrance.py`: the invariant is in the SQL and the ORDER BY, both
statically checkable. The live check belongs on the kiosk, where the data is.
"""
import io
import os
import re
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

SOURCES = {
    "models": os.path.join(REPO, "backend", "api", "models.py"),
    "parcels": os.path.join(REPO, "backend", "api", "routers", "parcels.py"),
    "streetview": os.path.join(REPO, "backend", "api", "routers", "streetview.py"),
    "resolver": os.path.join(REPO, "services", "gis", "src", "gis_service", "address_resolver.py"),
}

# The two functions in parcels.py that are ALLOWED to name the address columns directly.
# `_address_row` is the shared rule itself. `_entrance_target` must see every matching row
# to refuse an ambiguous write with a 409, so it cannot delegate to a single-row helper.
ADDRESS_LOOKUP_OWNERS = {"_address_row", "_entrance_target"}


def source(name):
    return io.open(SOURCES[name], encoding="utf-8", errors="replace").read()


def top_level_functions(text):
    """{name: body} for module-level `def`s, so a pattern can be attributed to one."""
    starts = [(m.start(), m.group(1)) for m in re.finditer(r"^def (\w+)\(", text, re.M)]
    out = {}
    for i, (pos, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        out[name] = text[pos:end]
    return out


class TestBaseSiteColumnIsVisible(unittest.TestCase):
    def test_parcel_model_declares_is_base_site(self):
        """The column existed in Postgres from 2026-08-31 and was absent from the ORM, so
        every SQLAlchemy lookup was blind to it and could not have preferred it even in
        principle. That absence is the root of #77."""
        self.assertRegex(
            source("models"),
            r"is_base_site\s*=\s*Column\(Boolean",
            "ParcelModel must declare is_base_site or no ORM path can order by it",
        )


class TestSharedRowRule(unittest.TestCase):
    def test_address_row_orders_base_site_first(self):
        body = top_level_functions(source("parcels"))["_address_row"]
        self.assertIn(
            "_BASE_SITE_FIRST", body,
            "_address_row must apply the canonical ordering, not an ad-hoc one",
        )
        self.assertRegex(
            source("parcels"),
            r"_BASE_SITE_FIRST\s*=\s*\(\s*ParcelModel\.is_base_site\.desc\(\)",
            "the canonical ordering must put is_base_site first",
        )

    def test_address_row_is_ordered_before_every_first(self):
        """An unordered `.first()` over a multi-row address match is the defect itself."""
        body = top_level_functions(source("parcels"))["_address_row"]
        for call in re.findall(r"db\.query\(ParcelModel\)(.*?)\.first\(\)", body, re.S):
            self.assertIn(
                ".order_by(", call,
                "every address lookup must be ordered before .first(); an unordered "
                "one returns an arbitrary row of the property",
            )

    def test_no_router_reintroduces_a_private_address_lookup(self):
        """The guard that matters. Correcting four copies leaves a fifth free to drift;
        this fails the moment a new endpoint builds its own address OR."""
        for module in ("parcels", "streetview"):
            for name, body in top_level_functions(source(module)).items():
                if name in ADDRESS_LOOKUP_OWNERS:
                    continue
                self.assertNotIn(
                    "ParcelModel.address_normalized ==", body,
                    f"{module}.{name} builds its own address lookup; call "
                    f"_address_row instead so it cannot disagree with the resolver (#77)",
                )

    def test_every_address_query_anywhere_in_the_routers_is_ordered(self):
        """The miss of 2026-09-10, and the reason this test is broader than the one above.

        `test_no_router_reintroduces_a_private_address_lookup` looks for
        `ParcelModel.address_normalized ==`. `search_parcels` matches with `ilike`, so it was
        never examined -- and it had no ORDER BY at all. Explore's autocomplete therefore
        returned City row 131890 above base row 200859 for "1176 Lansdowne", the operator set
        an arrival point on the base row, came back through the search onto the City row and
        saw an empty field: *"1176 got set, and then it lost it"*.

        Any query filtering on an address column, in any router, must order its results --
        `.first()` and a `.limit()`ed list are equally arbitrary without it. Scans the whole
        router directory rather than a fixed list so a new endpoint is covered on the day it
        is written.
        """
        router_dir = os.path.join(REPO, "backend", "api", "routers")
        checked = 0
        for fname in sorted(os.listdir(router_dir)):
            if not fname.endswith(".py"):
                continue
            text = io.open(os.path.join(router_dir, fname), encoding="utf-8",
                           errors="replace").read()
            for name, body in top_level_functions(text).items():
                if name in ADDRESS_LOOKUP_OWNERS:
                    continue
                if not re.search(r"ParcelModel\.address(_normalized)?\b", body):
                    continue
                if "db.query(ParcelModel)" not in body:
                    continue
                checked += 1
                self.assertIn(
                    ".order_by(", body,
                    f"{fname}::{name} filters parcels by address without an ORDER BY. "
                    f"Which row comes back is then arbitrary, and the row the operator "
                    f"writes to stops matching the row they are shown (#77). Apply "
                    f"_BASE_SITE_FIRST.",
                )
        self.assertGreater(checked, 0, "the scan matched nothing; the pattern has drifted")

    def test_search_results_can_distinguish_the_base_row(self):
        """Two rows are addressed exactly `1176 Lansdowne Dr` — 200859 and 131890 — both with
        a null unit. Ordering puts the base row first, but a list that does not say which is
        which leaves the operator picking between identical-looking entries."""
        body = top_level_functions(source("parcels"))["search_parcels"]
        self.assertIn('"is_base_site": p.is_base_site', body,
                      "search results must expose which row speaks for the property")

    def test_entrance_target_prefers_the_base_site_row(self):
        """Two rows are addressed exactly `2929 Barnet Hwy`. One is the base_site row, and
        that is not an ambiguity to refuse -- it is the answer."""
        body = top_level_functions(source("parcels"))["_entrance_target"]
        self.assertRegex(
            body, r"r\.is_base_site",
            "_entrance_target must recognise the base_site row before raising 409",
        )


class TestResolverOrdersBaseSiteFirst(unittest.TestCase):
    def test_resolve_exact_selects_and_orders_by_is_base_site(self):
        text = source("resolver")
        order = re.search(r"ORDER BY\s+is_base_site DESC,\s*street,\s*streettype,\s*id", text)
        self.assertIsNotNone(
            order,
            "resolve_exact must order base_site first; ordered by id alone it resolves "
            "2929 Barnet Hwy to suite 2112 and never reads the property's arrival point",
        )
        self.assertRegex(
            text, r"zone_id,\s*is_base_site",
            "the column has to be SELECTed for the ORDER BY to be meaningful to callers",
        )

    def test_single_parcel_addresses_are_untouched(self):
        """Guards the claim the change rests on: the ordering only re-ranks rows that are
        already tied, so the 26,531 addresses with no base_site row keep the row they had.
        Asserted as the comment that states it, because the behaviour itself is a database
        property and is checked on the kiosk."""
        self.assertIn(
            "have no such row and are unaffected", source("resolver"),
            "the blast radius of the ordering change must be stated where it is made",
        )


if __name__ == "__main__":
    unittest.main()
