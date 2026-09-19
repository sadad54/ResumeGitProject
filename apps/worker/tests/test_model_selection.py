from proofhire_worker.intelligence.model_selection import DEFAULT_MODEL, config_for, embedding_model, model_for


def test_falls_back_to_builtin_default(monkeypatch):
    monkeypatch.delenv("LLM_MODEL_DEFAULT", raising=False)
    monkeypatch.delenv("LLM_MODEL_RERANK", raising=False)
    assert model_for("rerank") == DEFAULT_MODEL


def test_global_override_applies_to_every_task(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")
    monkeypatch.delenv("LLM_MODEL_RERANK", raising=False)
    assert model_for("rerank") == "gpt-4o-mini"
    assert model_for("resume_write") == "gpt-4o-mini"


def test_per_task_override_beats_global(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_DEFAULT", "gpt-4o-mini")
    monkeypatch.setenv("LLM_MODEL_RESUME_WRITE", "claude-sonnet-5")
    assert model_for("rerank") == "gpt-4o-mini"
    assert config_for("resume_write").model == "claude-sonnet-5"


def test_embedding_model_is_separately_configurable(monkeypatch):
    monkeypatch.setenv("LLM_EMBEDDING_MODEL", "text-embedding-3-large")
    assert embedding_model() == "text-embedding-3-large"
