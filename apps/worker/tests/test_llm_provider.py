import pytest
from pydantic import BaseModel

from proofhire_worker.intelligence.llm_provider import Message, ModelConfig
from proofhire_worker.intelligence.provider_factory import get_provider
from proofhire_worker.intelligence.providers.mock_provider import MockLLMProvider


class _Greeting(BaseModel):
    text: str


@pytest.mark.asyncio
async def test_mock_provider_uses_registered_fixture():
    def fixture(task, messages, schema):
        return schema(text=f"hello from {task}")

    provider = MockLLMProvider(fixtures={"greet": fixture})
    result = await provider.structured_generate(
        task="greet",
        messages=[Message(role="user", content="hi")],
        schema=_Greeting,
        model_config=ModelConfig(model="mock-model"),
    )
    assert result.value.text == "hello from greet"
    assert result.usage.provider == "mock"
    assert result.usage.estimated_cost_usd == 0.0


@pytest.mark.asyncio
async def test_mock_provider_embed_is_deterministic():
    provider = MockLLMProvider()
    v1 = await provider.embed(["same text"], model="mock")
    v2 = await provider.embed(["same text"], model="mock")
    assert v1 == v2
    assert len(v1[0]) > 0


@pytest.mark.asyncio
async def test_mock_provider_embed_differs_for_different_text():
    provider = MockLLMProvider()
    vectors = await provider.embed(["text a", "text b"], model="mock")
    assert vectors[0] != vectors[1]


def test_provider_factory_returns_mock():
    provider = get_provider("mock")
    assert provider.name == "mock"


def test_provider_factory_rejects_unknown_provider():
    with pytest.raises(ValueError):
        get_provider("not-a-real-provider")
