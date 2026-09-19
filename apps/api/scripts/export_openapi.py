"""Write the API's OpenAPI document to a file, for the typed client generator.

Run from apps/api: `python scripts/export_openapi.py ../../docs/api/openapi.json`

This imports the app rather than hitting a running server, so it works in CI
with no database (settings load with defaults; nothing connects at import).
"""

import json
import sys
from pathlib import Path

from proofhire_api.main import app

out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
print(f"wrote {out} ({len(app.openapi()['paths'])} paths)")
