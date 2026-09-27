"""Single source of truth for the embedding vector dimension, shared by the
pgvector column definition (apps/api/proofhire_api/models/evidence.py) and the
worker's embedding providers (apps/worker/proofhire_worker/intelligence/
embeddings.py) — all must agree or inserts fail pgvector's dimension check.
Lives in packages/contracts (a leaf dependency of both apps/api and
apps/worker) specifically to avoid a circular import between the two.

384 dims (ADR-0018): the native size of the default local model, and a size
OpenAI's text-embedding-3 models can be asked for, so either provider fills
the same column. It was 1536 (text-embedding-3-small's native size) while the
only real provider was OpenAI.
"""

EMBEDDING_DIMENSION = 384
DEFAULT_LOCAL_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
