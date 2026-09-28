"""GroqProvider request shape and failure handling, against a stub client.

Each behaviour here was found by the first live run on Groq's free tier
(docs/product/metrics/e2e-live.json has the run that followed the fixes).
"""

import json

import httpx
import openai
import pytest
from pydantic import BaseModel, Field

from proofhire_worker.intelligence.json_schema import strict_json_schema
from proofhire_worker.intelligence.llm_provider import Message, ModelConfig
from proofhire_worker.intelligence.providers.groq_provider import (
    GroqProvider,
    OutputTruncatedError,
    _is_retryable,
)
from proofhire_worker.intelligence.schemas import EvidenceExtractionOutput


class _Item(BaseModel):
    title: str
    confidence: float = Field(ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class _Out(BaseModel):
    items: list[_Item] = Field(default_factory=list)
    note: str | None = None


def _response(content: str | None, finish_reason: str = "stop"):
    class _Message:
        pass

    class _Choice:
        pass

    class _Usage:
        prompt_tokens = 10
        completion_tokens = 5

    class _Response:
        pass

    message = _Message()
    message.content = content
    choice = _Choice()
    choice.message, choice.finish_reason = message, finish_reason
    response = _Response()
    response.choices, response.usage = [choice], _Usage()
    return response


def _status_error(cls, status: int, message: str):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return cls(message, response=httpx.Response(status, request=request), body=None)


class _Completions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests: list[dict] = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _provider(outcomes) -> tuple[GroqProvider, _Completions]:
    provider = GroqProvider(api_key="test")
    completions = _Completions(outcomes)

    class _Chat:
        pass

    class _Client:
        pass

    chat = _Chat()
    chat.completions = completions
    client = _Client()
    client.chat = chat
    provider._client = client
    return provider, completions


async def _call(provider, effort=None):
    return await provider.structured_generate(
        task="evidence_extract",
        messages=[Message(role="system", content="sys"), Message(role="user", content="u")],
        schema=_Out,
        model_config=ModelConfig(model="openai/gpt-oss-20b", reasoning_effort=effort),
    )


# --- strict schema -------------------------------------------------------------


def test_strict_schema_requires_every_field_and_closes_every_object():
    schema = strict_json_schema(_Out)
    assert schema["required"] == ["items", "note"]
    assert schema["additionalProperties"] is False
    item = schema["$defs"]["_Item"]
    assert item["required"] == ["title", "confidence", "tags"]
    assert item["additionalProperties"] is False
    # A field called `title` survives; the `title` keyword and bounds don't.
    assert "title" in item["properties"]
    assert "title" not in item and "maximum" not in item["properties"]["confidence"]


def test_every_pipeline_schema_converts():
    schema = strict_json_schema(EvidenceExtractionOutput)
    json.dumps(schema)
    assert schema["$defs"]["EvidenceItemOutput"]["additionalProperties"] is False


# --- request and responses ---------------------------------------------------


async def test_requests_strict_structured_output_and_the_configured_effort():
    provider, completions = _provider([_response('{"items": [], "note": null}')])
    await _call(provider, effort="low")
    request = completions.requests[0]
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True
    assert request["extra_body"] == {"reasoning_effort": "low"}


async def test_a_reply_cut_off_at_max_tokens_is_an_error_not_an_empty_result():
    """`{}` validates for a schema whose fields all have defaults: reading a
    truncated reply that way would report 'no evidence' for a group that was
    never actually answered."""
    provider, _ = _provider([_response(None, finish_reason="length")])
    with pytest.raises(OutputTruncatedError):
        await _call(provider)


async def test_json_validate_failed_retries_once_at_low_effort():
    failure = _status_error(
        openai.BadRequestError, 400, "Error code: 400 - {'code': 'json_validate_failed'}"
    )
    provider, completions = _provider([failure, _response('{"items": [], "note": null}')])
    result = await _call(provider)
    assert result.value == _Out()
    assert completions.requests[0]["extra_body"] is None
    assert completions.requests[1]["extra_body"] == {"reasoning_effort": "low"}


async def test_json_validate_failed_at_low_effort_is_final():
    failure = _status_error(openai.BadRequestError, 400, "json_validate_failed")
    provider, completions = _provider([failure])
    with pytest.raises(openai.BadRequestError):
        await _call(provider, effort="low")
    assert len(completions.requests) == 1


def test_request_too_large_is_not_retried_but_ordinary_rate_limits_are():
    too_large = _status_error(
        openai.RateLimitError,
        429,
        "Request too large for model `qwen/qwen3.8-27b` ... (OTPM): Limit 1000",
    )
    busy = _status_error(openai.RateLimitError, 429, "Rate limit reached for tokens per minute")
    assert _is_retryable(too_large) is False
    assert _is_retryable(busy) is True
