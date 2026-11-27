"""Session-wide test defaults (repo root, so every suite picks them up).

Tests must not spend real provider quota or download models by accident. A
developer's .env exported into the shell sets e.g. LLM_DEFAULT_PROVIDER=groq,
and without this the pipeline tests would call Groq with a real key. Tests
that need the real local embedding model construct it explicitly
(apps/worker/tests/test_embeddings.py). Opt out with
PROOFHIRE_TEST_REAL_PROVIDERS=1.
"""

import os

from cryptography.fernet import Fernet

# Tests that store a GitHub connection encrypt its token. CI has no .env, so
# without this they would hit the config's placeholder key, which is not a
# valid Fernet key.
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

if os.environ.get("PROOFHIRE_TEST_REAL_PROVIDERS") != "1":
    os.environ["LLM_DEFAULT_PROVIDER"] = "mock"
    os.environ["EMBEDDING_PROVIDER"] = "mock"
