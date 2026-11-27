"""Pydantic JSON Schema -> the subset strict structured outputs accept.

Strict mode (Groq, OpenAI) decodes under the schema's constraints, so the
response is valid JSON of the right shape by construction; JSON-object mode
only asks for JSON and can fail. The first live run lost extraction groups to
Groq's `json_validate_failed` in JSON-object mode.

Strict mode's rules: every property listed in `required`, every object closed
with `additionalProperties: false`, and no keywords outside the supported
subset. Optional-with-default fields become required, so the model always
writes them (an empty list, a null); Pydantic still validates the result,
including the numeric bounds removed here (`ge`/`le` become minimum/maximum,
which constrained decoding doesn't take), and a violation goes through the
provider's existing repair loop.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# Annotations and validation keywords outside the strict subset. Removed from
# schema nodes only, never from `properties` (whose keys are field names:
# several output models have a field called `title`).
_UNSUPPORTED = {
    "title", "default", "examples",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minLength", "maxLength", "pattern", "format",
    "minItems", "maxItems", "uniqueItems",
}


def _close(node: Any) -> None:
    if not isinstance(node, dict):
        return
    for key in _UNSUPPORTED:
        node.pop(key, None)
    properties = node.get("properties")
    if isinstance(properties, dict):
        node["required"] = list(properties)
        node["additionalProperties"] = False
        for sub in properties.values():
            _close(sub)
    if isinstance(node.get("items"), dict):
        _close(node["items"])
    for key in ("anyOf", "allOf", "oneOf"):
        for sub in node.get(key, []):
            _close(sub)
    for sub in node.get("$defs", {}).values():
        _close(sub)


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    _close(schema)
    return schema
