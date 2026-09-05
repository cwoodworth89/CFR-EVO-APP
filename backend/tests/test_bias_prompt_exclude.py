"""STT_HOTWORDS_EXCLUDE removes named terms from the hotword list before the budget is spent.

The hotwords sit in the same previous-text slot of the decoder as the initial prompt, whose
"map grid" phrase the model in service echoed into pauses (punch list #63). Excluding one term
is how its effect is measured with tools/harness_chain.py; this pins the switch's behaviour.
No database, no API: the builder is called with no validator, so the list is the core terms
and the units passed in.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cfr_dispatch.stt.bias_prompt import build_stt_bias_words  # noqa: E402


def _hotwords(monkeypatch, exclude):
    monkeypatch.setenv("STT_INITIAL_PROMPT", "")
    monkeypatch.setenv("LOCAL_API_URL", "http://127.0.0.1:9")  # closed port: the HITL fetch fails fast
    if exclude is None:
        monkeypatch.delenv("STT_HOTWORDS_EXCLUDE", raising=False)
    else:
        monkeypatch.setenv("STT_HOTWORDS_EXCLUDE", exclude)
    _prompt, hotwords = build_stt_bias_words(None, ["E1", "L1"])
    return [t.strip().lower() for t in hotwords.split(",") if t.strip()]


def test_default_list_carries_map_grid(monkeypatch):
    assert "map grid" in _hotwords(monkeypatch, None)


def test_exclude_removes_only_the_named_terms(monkeypatch):
    terms = _hotwords(monkeypatch, "map grid, Structure Fire")
    assert "map grid" not in terms
    assert "structure fire" not in terms
    assert "coquitlam" in terms
    assert "use talk group" in terms
    assert "e1" in terms


def test_blank_exclude_changes_nothing(monkeypatch):
    assert _hotwords(monkeypatch, " , ") == _hotwords(monkeypatch, None)
