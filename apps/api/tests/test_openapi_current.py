"""The committed OpenAPI document is the contract the web app's generated
client is built from (ADR-0010). CI already fails on drift, but only after a
push — this makes the ordinary local test run catch it first. It exists
because exactly that happened: /api/v1/demo/session shipped without the
document being regenerated and master's CI went red.
"""

import json
from pathlib import Path

from proofhire_api.main import app

DOCUMENT = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.json"


def test_committed_openapi_document_matches_the_app():
    committed = json.loads(DOCUMENT.read_text(encoding="utf-8"))
    current = json.loads(json.dumps(app.openapi(), sort_keys=True))
    stale = sorted(set(current["paths"]) ^ set(committed["paths"]))
    assert committed == current, (
        "docs/api/openapi.json is stale"
        + (f" (paths differ: {stale})" if stale else "")
        + ". From apps/api run `python scripts/export_openapi.py ../../docs/api/openapi.json`, "
        "then `npm run generate:api --workspace apps/web`."
    )
