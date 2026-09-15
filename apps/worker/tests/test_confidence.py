from proofhire_worker.intelligence.confidence import combine_confidence


def test_no_boosts_returns_semantic_confidence_unchanged():
    result = combine_confidence(0.7, source_count=1, skill_names=[], deterministic_tech=set())
    assert result == 0.7


def test_deterministic_match_boosts_confidence():
    result = combine_confidence(
        0.7, source_count=1, skill_names=["FastAPI"], deterministic_tech={"fastapi"}
    )
    assert result > 0.7


def test_deterministic_boost_is_case_insensitive():
    a = combine_confidence(0.5, 1, ["fastapi"], {"fastapi"})
    b = combine_confidence(0.5, 1, ["FastAPI"], {"fastapi"})
    assert a == b


def test_extra_sources_boost_confidence():
    one_source = combine_confidence(0.6, source_count=1, skill_names=[], deterministic_tech=set())
    three_sources = combine_confidence(0.6, source_count=3, skill_names=[], deterministic_tech=set())
    assert three_sources > one_source


def test_confidence_never_exceeds_one():
    result = combine_confidence(
        0.99, source_count=10, skill_names=["a", "b", "c"], deterministic_tech={"a", "b", "c"}
    )
    assert result <= 1.0


def test_unrelated_skill_gives_no_deterministic_boost():
    with_match = combine_confidence(0.5, 1, ["docker"], {"docker"})
    without_match = combine_confidence(0.5, 1, ["docker"], {"kubernetes"})
    assert with_match > without_match
    assert without_match == 0.5
