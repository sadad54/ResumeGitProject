import pytest
from proofhire_contracts import MatchLabel

from proofhire_worker.intelligence.match_label import resolve_match_label


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("strong", MatchLabel.STRONG),
        ("Strong", MatchLabel.STRONG),
        ("  STRONG  ", MatchLabel.STRONG),
        ("partial", MatchLabel.PARTIAL),
        ("gap", MatchLabel.GAP),
        ("unknown", MatchLabel.UNKNOWN),
    ],
)
def test_valid_labels_resolve_correctly(raw, expected):
    assert resolve_match_label(raw) == expected


@pytest.mark.parametrize("garbage", ["", "very strong", "yes", "strong!!", "123", "None"])
def test_invalid_labels_fall_back_to_unknown_never_strong(garbage):
    """PRD §17: 'Never collapse Partial into Strong merely to improve perceived
    fit.' An unparseable/invalid LLM output must never resolve to STRONG — the
    only safe fallback is UNKNOWN, since we have no basis to claim any match."""
    result = resolve_match_label(garbage)
    assert result != MatchLabel.STRONG
    assert result == MatchLabel.UNKNOWN


def test_partial_never_becomes_strong_regardless_of_casing_or_whitespace():
    for variant in ["partial", "Partial", " PARTIAL ", "PaRtIaL"]:
        assert resolve_match_label(variant) == MatchLabel.PARTIAL
        assert resolve_match_label(variant) != MatchLabel.STRONG
