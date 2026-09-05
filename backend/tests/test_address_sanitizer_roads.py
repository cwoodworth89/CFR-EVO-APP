"""The kiosk's address sanitizer must not damage a City road name.

`frontend/src/utils/addressUtils.js` (`sanitizeAddress`) strips unit designators ("UNIT 105",
"#5", "Bay 4") from a parsed address before the kiosk uses it as the parcel and Street View
lookup key. A parity check on 2026-09-05 found it stripping the street instead: "1550 United
Blvd" became "1550 Blvd" and "1332 Steeple Dr" became "1332 Dr", because the keyword match had
no word boundary ("UNIT|ed", "STE|eple"). 18 of the City's 1,079 road names were affected
(punch list #66).

The first test runs the real JavaScript with node on the addresses that were wrong that day.
The second runs every name in `public.road_names` through it, so it needs the kiosk database
(DATABASE_URL) as well; both skip without node. Operator ruling 2026-09-04: the production
database is the test database, read-only here.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
JS = REPO / "frontend" / "src" / "utils" / "addressUtils.js"
NODE = shutil.which("node")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

RUNNER = """
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const { sanitizeAddress } = await import(pathToFileURL(process.argv[2]).href);
const inputs = JSON.parse(readFileSync(process.argv[3], 'utf8'));
process.stdout.write(JSON.stringify(inputs.map(sanitizeAddress)));
"""

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not on PATH; the sanitizer is JavaScript")


def sanitize_all(values):
    """Run the kiosk's sanitizeAddress over `values` in one node process."""
    with tempfile.TemporaryDirectory() as d:
        runner = Path(d) / "run.mjs"
        data = Path(d) / "in.json"
        runner.write_text(RUNNER, encoding="utf-8")
        data.write_text(json.dumps(values), encoding="utf-8")
        out = subprocess.run([NODE, str(runner), str(JS), str(data)],
                             capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


# Real strings from the dispatch corpus (parser output and the verified column), 2026-09-05.
CORPUS_CASES = {
    "1050 United Blvd": "1050 United Blvd",
    "1550 United Blvd": "1550 United Blvd",
    "39 United Blvd": "39 United Blvd",
    "1332 Steeple Dr": "1332 Steeple Dr",
    "2575 Steeple Crt": "2575 Steeple Crt",
    "5 Coquitlam Ave #5": "5 Coquitlam Ave",
    "1131 Dufferin St 204D": "1131 Dufferin St",
    "2929 Barnet Hwy 2112": "2929 Barnet Hwy",
    "Christmas Way And Westwood St": "Christmas Way & Westwood St",
    "105-3000 Riverbend Dr": "3000 Riverbend Dr",  # the function's own documented example
}


def test_corpus_addresses_keep_their_street():
    got = sanitize_all(list(CORPUS_CASES))
    assert dict(zip(CORPUS_CASES, got)) == CORPUS_CASES


@pytest.mark.skipif(not DATABASE_URL.startswith("postgres"), reason="DATABASE_URL not set")
def test_every_city_road_name_survives():
    from sqlalchemy import create_engine, text
    with create_engine(DATABASE_URL).connect() as conn:
        names = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT road_name FROM public.road_names "
            "WHERE road_name IS NOT NULL AND road_name <> '' ORDER BY 1"))]
    assert len(names) > 1000, "public.road_names should hold the City's ~1,079 road names"
    inputs = [f"1234 {n}" for n in names]
    damaged = {n for n, v, s in zip(names, inputs, sanitize_all(inputs)) if s != v}
    # "Highway #1" is the one road name that reads as a unit ("#1"). It is never a civic-address
    # street, and the '#' rule is what strips "5 Coquitlam Ave #5" correctly.
    assert damaged == {"Highway #1"}, sorted(damaged)
