"""The call type comes from the incident slot of the announcement, never from the unit list (#34a).

Rescue and Hazmat 1/2/3 are call types and apparatus names. When the STT mangles the incident
phrase, "rescue 2" in the unit list used to become the incident at full score: DISP-2026-A19179,
an alarm call shown as Rescue. Pure: a fixed call-type list, no aliases, the unit types passed in.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cfr_dispatch.parser.call_types import match_incident_type, incident_search_text  # noqa: E402

CALL_TYPES = ["Rescue", "Hazmat 1", "Hazmat 2", "Hazmat 2 - Moderate Risk", "Hazmat 3",
              "Alarm Activated - High Risk", "Alarm Activated", "Medical Aid - Overdose", "Stove Fire"]
UNITS = ["Engine", "Ladder", "Rescue", "Quint", "Car", "Medic", "Hazmat", "Hazmat Tender", "Squad"]

# DISP-2026-A19179 as the STT wrote it: the incident phrase collapsed into "respondents".
MANGLED = ("coquitlam engine 1 engine 2 rescue 2 respondents way near glen drive and atlantic avenue "
           "use talk group 5 coquitlam map grid 86")


def match(text):
    return match_incident_type(text, CALL_TYPES, aliases={}, units_vocabulary=UNITS)


def test_a_unit_named_rescue_is_not_an_incident():
    assert match(MANGLED) == "Unknown Incident"


def test_a_real_rescue_call_is_still_a_rescue():
    assert match("coquitlam engine 1 rescue 2 respond emergency rescue 3030 gordon avenue "
                 "near christmas way use talk group 10") == "Rescue"


def test_a_hazmat_incident_keeps_its_qualifier():
    assert match("coquitlam engine 3 hazmat 3 hazmat tender 3 quint 5 respond emergency hazmat 2 "
                 "moderate risk 4522 port mann bridge use talk group") == "Hazmat 2 - Moderate Risk"


def test_hazmat_units_alone_are_not_a_hazmat_incident():
    assert match("coquitlam hazmat 3 hazmat tender 3 respondents 1234 pinetree way") == "Unknown Incident"


def test_the_search_text_starts_after_respond():
    assert incident_search_text("coquitlam rescue 2 respond emergency stove fire 12 elm st", UNITS).strip() \
        == "stove fire 12 elm st"
    assert "rescue 2" not in incident_search_text("coquitlam rescue 2 respondents stove fire 12 elm st", UNITS)
    assert "stove fire" in incident_search_text("coquitlam rescue 2 respondents stove fire 12 elm st", UNITS)
