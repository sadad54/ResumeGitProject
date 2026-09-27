from proofhire_worker.intelligence import check_models
from proofhire_worker.intelligence.model_selection import (
    PROVIDER_DEFAULTS,
    config_for,
    model_for,
    resolved_models,
)


def _clear(monkeypatch):
    monkeypatch.delenv("LLM_MODEL_DEFAULT", raising=False)
    for task in resolved_models():
        monkeypatch.delenv(f"LLM_MODEL_{task.upper()}", raising=False)


def test_defaults_follow_the_configured_provider(monkeypatch):
    """The old single default ("claude-sonnet-5") was sent to Groq whenever
    no override was set, failing every call."""
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "groq")
    assert model_for("resume_write") == PROVIDER_DEFAULTS["groq"]["*"]
    assert model_for("rerank") == PROVIDER_DEFAULTS["groq"]["rerank"]

    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "anthropic")
    assert model_for("rerank") == "claude-sonnet-5"


def test_groq_verifier_is_a_different_model_family_than_the_writer(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "groq")
    writer, verifier = model_for("resume_write"), model_for("claim_verify")
    assert writer.split("/")[0] != verifier.split("/")[0]


def test_global_override_applies_to_every_task(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")
    assert model_for("rerank") == "gpt-4o-mini"
    assert model_for("resume_write") == "gpt-4o-mini"


def test_per_task_override_beats_global(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")
    monkeypatch.setenv("LLM_MODEL_RESUME_WRITE", "claude-sonnet-5")
    assert model_for("rerank") == "gpt-4o-mini"
    assert config_for("resume_write").model == "claude-sonnet-5"


async def test_check_reports_models_the_provider_does_not_serve(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL_RESUME_WRITE", "llama-3.3-70b-versatile")  # retired by Groq

    async def served(_provider):
        return set(PROVIDER_DEFAULTS["groq"].values())

    monkeypatch.setattr(check_models, "available_models", served)
    assert await check_models.missing_models() == {"resume_write": "llama-3.3-70b-versatile"}


async def test_check_is_a_no_op_for_the_mock_provider(monkeypatch):
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "mock")
    assert await check_models.missing_models() == {}
