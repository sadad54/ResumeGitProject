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


def test_groq_verification_runs_on_the_larger_model(monkeypatch):
    """qwen3.8-27b (the previous, different-family verifier) now rejects any
    request over 1,000 output tokens on this account; see PROVIDER_DEFAULTS."""
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "groq")
    assert model_for("claim_verify") == "openai/gpt-oss-120b"
    assert all(not m.startswith("qwen/") for m in resolved_models().values())


def test_reasoning_effort_is_low_for_extraction_and_overridable(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "groq")
    monkeypatch.delenv("LLM_REASONING_EFFORT_EVIDENCE_EXTRACT", raising=False)
    assert config_for("evidence_extract").reasoning_effort == "low"
    assert config_for("resume_write").reasoning_effort is None
    monkeypatch.setenv("LLM_REASONING_EFFORT_RESUME_WRITE", "high")
    assert config_for("resume_write").reasoning_effort == "high"
    # Other providers get no reasoning parameter at all.
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "anthropic")
    assert config_for("evidence_extract").reasoning_effort is None


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


async def test_probe_reports_a_model_that_refuses_the_real_request_size(monkeypatch):
    """The failure the model list can't see: listed, but every real call refused."""
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL_CLAIM_VERIFY", "qwen/qwen3.8-27b")
    sent: list[dict] = []

    async def create(**request):
        sent.append(request)
        if request["model"].startswith("qwen/"):
            raise RuntimeError("Request too large ... (OTPM): Limit 1000, Requested 4096")
        return object()

    refused = await check_models.probe_limits(create)
    assert list(refused) == ["claim_verify"]
    assert "Request too large" in refused["claim_verify"]
    # One request per distinct shape, not one per task.
    assert len(sent) == len({(r["model"], r["max_tokens"], str(r["extra_body"])) for r in sent})
    assert all(r["response_format"]["json_schema"]["strict"] for r in sent)


async def test_probe_is_a_no_op_for_other_providers(monkeypatch):
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "anthropic")

    async def create(**_request):
        raise AssertionError("must not be called")

    assert await check_models.probe_limits(create) == {}
