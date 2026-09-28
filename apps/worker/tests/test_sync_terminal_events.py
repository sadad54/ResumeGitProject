"""Every sync run ends with exactly one terminal event (github.sync.completed
or github.sync.failed). Before these existed, a run that raised was marked
FAILED in the database but published nothing, and the progress stream's
30-second pings kept the browser's "Syncing…" state open indefinitely."""

import uuid

import pytest
from proofhire_api.db import async_session_factory
from proofhire_api.models.github_connection import GitHubConnection
from proofhire_api.models.repository import Repository
from proofhire_api.models.sync_run import SyncRun
from proofhire_api.models.user import User
from proofhire_api.security.password import hash_password
from proofhire_api.security.token_crypto import encrypt_token
from proofhire_contracts import RunEventName, SyncStatus

from proofhire_worker.ingestion import sync as sync_module


@pytest.fixture
async def run_env():
    async with async_session_factory() as session:
        user = User(email=f"sync-events-{uuid.uuid4().hex[:8]}@example.com",
                    hashed_password=hash_password("x"))
        session.add(user)
        await session.flush()
        session.add(GitHubConnection(user_id=user.id, github_user_id=1, login="octo",
                                     token_ref=encrypt_token("gho_test"), scopes=[]))
        repo_number = int.from_bytes(uuid.uuid4().bytes[:4], "big") % 2_000_000_000
        repo = Repository(user_id=user.id, provider_repo_id=repo_number,
                          owner="octo", name="svc", url="https://github.com/octo/svc")
        session.add(repo)
        await session.flush()
        run = SyncRun(user_id=user.id, repository_ids=[str(repo.id)], status=SyncStatus.QUEUED)
        session.add(run)
        await session.commit()
        yield str(run.id), str(repo.id)
        await session.delete(await session.get(User, user.id))
        await session.commit()


@pytest.fixture
def published(monkeypatch):
    events: list[tuple[str, RunEventName, dict]] = []

    async def capture(run_id, event, data):
        events.append((run_id, event, data))

    monkeypatch.setattr(sync_module, "publish_event", capture)
    return events


async def _status(run_id: str) -> SyncStatus:
    async with async_session_factory() as session:
        return (await session.get(SyncRun, uuid.UUID(run_id))).status


async def test_a_failed_run_publishes_sync_failed(run_env, published, monkeypatch):
    run_id, repo_id = run_env

    async def boom(*_args, **_kwargs):
        raise RuntimeError("GitHub returned 502")

    monkeypatch.setattr(sync_module, "_sync_one_repository", boom)
    await sync_module._run(run_id, [repo_id])

    assert await _status(run_id) == SyncStatus.FAILED
    terminal = [e for _r, e, _d in published if e in {
        RunEventName.GITHUB_SYNC_COMPLETED, RunEventName.GITHUB_SYNC_FAILED}]
    assert terminal == [RunEventName.GITHUB_SYNC_FAILED]
    assert published[-1][1] == RunEventName.GITHUB_SYNC_FAILED
    # The detail stays on the row; the event carries a fixed, safe message.
    assert "502" not in published[-1][2]["message"]


async def test_a_successful_run_publishes_sync_completed_last(run_env, published, monkeypatch):
    run_id, repo_id = run_env

    async def nothing_changed(*_args, **_kwargs):
        return []

    monkeypatch.setattr(sync_module, "_sync_one_repository", nothing_changed)
    await sync_module._run(run_id, [repo_id])

    assert await _status(run_id) == SyncStatus.COMPLETED
    assert [e for _r, e, _d in published] == [
        RunEventName.GITHUB_SYNC_STARTED,
        RunEventName.GITHUB_SYNC_COMPLETED,
    ]
    assert published[-1][2]["repository_ids"] == [repo_id]


async def _repo_status(repo_id: str) -> SyncStatus:
    async with async_session_factory() as session:
        return (await session.get(Repository, uuid.UUID(repo_id))).sync_status


async def test_changed_files_leave_the_repository_extracting_until_extraction_settles(
    run_env, published, monkeypatch
):
    """The run is complete once files are fetched, but the repository isn't:
    its evidence is still being extracted (test_extraction_status covers the
    settling side)."""
    run_id, repo_id = run_env
    from proofhire_worker.intelligence import evidence_extraction

    queued: list[tuple] = []

    async def some_files_changed(session, _client, repository, _run_id):
        repository.sync_status = (
            SyncStatus.EXTRACTING  # what _sync_one_repository now sets for changed files
        )
        await session.commit()
        return [uuid.uuid4()]

    monkeypatch.setattr(sync_module, "_sync_one_repository", some_files_changed)
    monkeypatch.setattr(evidence_extraction.extract_evidence, "send",
                        lambda *args: queued.append(args))
    await sync_module._run(run_id, [repo_id])

    assert await _status(run_id) == SyncStatus.COMPLETED
    assert await _repo_status(repo_id) == SyncStatus.EXTRACTING
    assert len(queued) == 1 and queued[0][0] == repo_id


async def test_failing_to_queue_extraction_does_not_leave_it_extracting(
    run_env, published, monkeypatch
):
    run_id, repo_id = run_env
    from proofhire_worker.intelligence import evidence_extraction

    async def some_files_changed(session, _client, repository, _run_id):
        repository.sync_status = SyncStatus.EXTRACTING
        await session.commit()
        return [uuid.uuid4()]

    def broker_down(*_args):
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(sync_module, "_sync_one_repository", some_files_changed)
    monkeypatch.setattr(evidence_extraction.extract_evidence, "send", broker_down)
    await sync_module._run(run_id, [repo_id])

    assert await _status(run_id) == SyncStatus.FAILED
    assert await _repo_status(repo_id) == SyncStatus.FAILED


class _Tree:
    """Just enough of GitHubClient for the real _sync_one_repository."""

    def __init__(self, files: dict[str, str]):
        self.files = files

    async def get_default_branch_sha(self, _owner, _name, _branch):
        return "b" * 40

    async def get_repository_tree(self, _owner, _name, _sha):
        return [{"path": path, "type": "blob"} for path in self.files]

    async def get_file_content(self, _owner, _name, path, _sha):
        return self.files.get(path)


async def test_real_sync_marks_changed_repositories_extracting_and_unchanged_completed(
    run_env, published
):
    run_id, repo_id = run_env
    files = {
        "README.md": "# svc\nA FastAPI service with an LLM planner.\n",
        "app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
    }
    async with async_session_factory() as session:
        repo = await session.get(Repository, uuid.UUID(repo_id))
        changed = await sync_module._sync_one_repository(
            session, _Tree(files), repo, uuid.UUID(run_id))
        assert changed, "new files must be queued for extraction"
        assert repo.sync_status == SyncStatus.EXTRACTING

        # Same content again: nothing to extract, so nothing to wait for.
        unchanged = await sync_module._sync_one_repository(
            session, _Tree(files), repo, uuid.UUID(run_id))
        assert unchanged == []
        assert repo.sync_status == SyncStatus.COMPLETED
