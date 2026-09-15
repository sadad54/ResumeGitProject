"""Repository Protocol interfaces + SQLAlchemy implementations.

This is the boundary the worker's AI code (apps/worker/proofhire_worker/intelligence)
depends on instead of importing SQLAlchemy directly (PRD §35). Established in Phase 2
with evidence.py; extended per-phase as new aggregates are added.
"""
