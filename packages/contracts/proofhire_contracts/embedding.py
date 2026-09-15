"""Single source of truth for the embedding vector dimension, shared by the
pgvector column definition (apps/api/proofhire_api/models/evidence.py) and the
worker's embedding calls (real OpenAI + mock fallback) — all must agree or
inserts fail pgvector's dimension check. Lives in packages/contracts (a leaf
dependency of both apps/api and apps/worker) specifically to avoid a circular
import between the two.
"""

EMBEDDING_DIMENSION = 1536  # text-embedding-3-small
EMBEDDING_MODEL = "text-embedding-3-small"
