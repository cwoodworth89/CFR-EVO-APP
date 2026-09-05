"""The readings of a five- or six-digit house number, on the numbers the corpus produced.

No civic number in City of Coquitlam records has more than four digits (public.parcels max
6000, public.roads ranges max 7351, 2026-09-05). Step 1b of the geocoder ladder reads a longer
number every way the surplus digits could be removed and lets the parcel table decide; this
pins the readings themselves. No database.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cfr_dispatch  # noqa: F401,E402  puts the sibling services on sys.path (CLAUDE.md section 2)
from gis_service.address_resolver import overlong_house_readings  # noqa: E402


def test_readings_of_the_real_cases():
    assert overlong_house_readings("30000") == ["3000"]                       # "300, zero, zero"
    assert overlong_house_readings("33564") == ["3354", "3356", "3364", "3564"]  # "33, 56, 4, court"
    assert overlong_house_readings("29883") == ["2883", "2983", "2988", "9883"]  # "29, 8, 8, 3"
    assert overlong_house_readings("20003") == ["3", "2000", "2003"]         # leading zeros dropped
    assert overlong_house_readings("61300") == ["1300", "6100", "6130", "6300"]  # "routine 61300"


def test_six_digits_drop_two():
    assert "3000" in overlong_house_readings("300000")
    assert len(overlong_house_readings("123456")) == 15


def test_not_this_steps_business():
    assert overlong_house_readings("1300") == []
    assert overlong_house_readings("6000") == []
    assert overlong_house_readings("1234567") == []
    assert overlong_house_readings("12a45") == []
    assert overlong_house_readings("") == []
    assert overlong_house_readings(None) == []
