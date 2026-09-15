"""Thin async GitHub REST API client used by both the API (repo listing) and the
worker (sync/ingestion). Handles auth headers and basic rate-limit backoff.
"""

import asyncio
import base64

import httpx

GITHUB_API_BASE = "https://api.github.com"


class GitHubRateLimitError(Exception):
    pass


class GitHubClient:
    def __init__(self, access_token: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(self, client: httpx.AsyncClient, method: str, path: str, **kwargs) -> httpx.Response:
        url = path if path.startswith("http") else f"{GITHUB_API_BASE}{path}"
        for attempt in range(3):
            response = await client.request(method, url, headers=self._headers, **kwargs)
            if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
                reset_at = int(response.headers.get("x-ratelimit-reset", "0"))
                wait_seconds = max(0, reset_at - int(asyncio.get_event_loop().time()))
                if attempt < 2 and wait_seconds < 60:
                    await asyncio.sleep(wait_seconds + 1)
                    continue
                raise GitHubRateLimitError("GitHub API rate limit exceeded")
            response.raise_for_status()
            return response
        raise GitHubRateLimitError("GitHub API rate limit exceeded after retries")

    async def list_user_repositories(self, per_page: int = 100) -> list[dict]:
        repos: list[dict] = []
        page = 1
        async with httpx.AsyncClient(timeout=15.0) as client:
            while True:
                response = await self._request(
                    client,
                    "GET",
                    "/user/repos",
                    params={"per_page": per_page, "page": page, "affiliation": "owner"},
                )
                batch = response.json()
                repos.extend(batch)
                if len(batch) < per_page:
                    break
                page += 1
        return repos

    async def get_repository_tree(self, owner: str, repo: str, sha: str) -> list[dict]:
        """Full recursive tree for a given commit SHA (PRD §15 Stage 1)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._request(
                client,
                "GET",
                f"/repos/{owner}/{repo}/git/trees/{sha}",
                params={"recursive": "1"},
            )
        payload = response.json()
        return [item for item in payload.get("tree", []) if item.get("type") == "blob"]

    async def get_default_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await self._request(
                client, "GET", f"/repos/{owner}/{repo}/branches/{branch}"
            )
        return response.json()["commit"]["sha"]

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str | None:
        """Returns decoded UTF-8 text content, or None for binary/undecodable files."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await self._request(
                client, "GET", f"/repos/{owner}/{repo}/contents/{path}", params={"ref": ref}
            )
        payload = response.json()
        if payload.get("encoding") != "base64":
            return None
        raw = base64.b64decode(payload["content"])
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
