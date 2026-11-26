import base64
from datetime import datetime
from urllib.parse import quote
import httpx
from fastapi import status

from app.core.config import Settings
from app.core.errors import AppError

GITHUB_API_BASE = "https://api.github.com"

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".json": "JSON",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".sh": "Shell",
    ".env.example": "Env",
}

IGNORED_DIR_PARTS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".pytest_cache",
}


class GitHubService:
    """Client for retrieving public GitHub repository metadata, trees, and files via HTTPX."""

    def __init__(self, settings: Settings):
        self.settings = settings
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "RepoSense-AI/0.1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = settings.GITHUB_TOKEN.strip()
        self._raw_headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "RepoSense-AI/0.1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._headers = dict(self._raw_headers)
        if token and "YOUR_GITHUB" not in token:
            self._headers["Authorization"] = f"Bearer {token}"

    @staticmethod
    def _is_github_api_url(url: str) -> bool:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.scheme == "https" and parsed.netloc.lower() == "api.github.com"

    @staticmethod
    def _is_allowed_download_url(url: str) -> bool:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.scheme == "https" and parsed.netloc.lower() in {
            "raw.githubusercontent.com",
            "github.com",
            "api.github.com",
        }

    def _request(self, client: httpx.Client, url: str) -> httpx.Response:
        headers = self._headers if self._is_github_api_url(url) else self._raw_headers
        try:
            response = client.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise AppError(
                message="GitHub API request timed out.",
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                code="github_timeout",
            ) from exc
        except httpx.RequestError as exc:
            raise AppError(
                message="Network error while communicating with GitHub API.",
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="github_network_error",
            ) from exc

        if response.status_code == 404:
            raise AppError(
                message="GitHub repository or resource not found (or repository is private).",
                status_code=status.HTTP_404_NOT_FOUND,
                code="github_not_found",
            )

        if response.status_code in (403, 429):
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining == "0" or response.status_code == 429:
                raise AppError(
                    message="GitHub API rate limit exceeded. Configure or refresh GITHUB_TOKEN in backend/.env.",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    code="github_rate_limited",
                )
            raise AppError(
                message="Access denied by GitHub API.",
                status_code=status.HTTP_403_FORBIDDEN,
                code="github_forbidden",
            )

        if response.status_code >= 400:
            raise AppError(
                message=f"GitHub API returned unexpected status {response.status_code}.",
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="github_api_error",
            )
        return response

    def fetch_repo_metadata(self, owner: str, name: str) -> dict:
        """Fetch repository metadata and enforce maximum repository size limits."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{name}"
        with httpx.Client(timeout=self.settings.GITHUB_TIMEOUT_SECONDS, follow_redirects=True) as client:
            data = self._request(client, url).json()

        size_kb = data.get("size", 0) or 0
        if size_kb > self.settings.MAX_REPO_SIZE_KB:
            raise AppError(
                message=f"Repository size ({size_kb} KB) exceeds limit ({self.settings.MAX_REPO_SIZE_KB} KB).",
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                code="repository_too_large",
            )

        def parse_dt(value: str | None) -> datetime | None:
            if not value:
                return None
            return datetime.fromisoformat(value.replace("Z", "+00:00"))

        return {
            "owner": data.get("owner", {}).get("login", owner),
            "name": data.get("name", name),
            "github_url": data.get("html_url", f"https://github.com/{owner}/{name}"),
            "description": data.get("description"),
            "default_branch": data.get("default_branch") or "main",
            "primary_language": data.get("language"),
            "stars_count": data.get("stargazers_count", 0) or 0,
            "forks_count": data.get("forks_count", 0) or 0,
            "size_kb": size_kb,
            "github_created_at": parse_dt(data.get("created_at")),
            "github_updated_at": parse_dt(data.get("updated_at")),
        }

    def fetch_repo_tree(self, owner: str, name: str, branch: str) -> tuple[list[dict], bool]:
        """Fetch recursive file tree for the given branch."""
        encoded_branch = quote(branch, safe="")
        url = f"{GITHUB_API_BASE}/repos/{owner}/{name}/git/trees/{encoded_branch}?recursive=1"
        with httpx.Client(timeout=self.settings.GITHUB_TIMEOUT_SECONDS, follow_redirects=True) as client:
            data = self._request(client, url).json()

        tree_items = [item for item in data.get("tree", []) if item.get("type") == "blob"]
        truncated = bool(data.get("truncated", False))
        return tree_items, truncated

    def fetch_file_content(self, client: httpx.Client, owner: str, name: str, file_path: str, branch: str) -> str | None:
        """Fetch UTF-8 source text for a single file via GitHub Contents API."""
        encoded_path = quote(file_path, safe="/")
        encoded_branch = quote(branch, safe="")
        url = f"{GITHUB_API_BASE}/repos/{owner}/{name}/contents/{encoded_path}?ref={encoded_branch}"
        data = self._request(client, url).json()

        if not isinstance(data, dict):
            return None

        size = data.get("size", 0) or 0
        if size > self.settings.MAX_FILE_SIZE_BYTES:
            return None

        if data.get("encoding") == "base64" and data.get("content"):
            raw_bytes = base64.b64decode(data["content"])
            if b"\x00" in raw_bytes:
                return None
            return raw_bytes.decode("utf-8", errors="replace")

        download_url = data.get("download_url")
        if download_url and self._is_allowed_download_url(download_url):
            raw_resp = self._request(client, download_url)
            if len(raw_resp.content) > self.settings.MAX_FILE_SIZE_BYTES or b"\x00" in raw_resp.content:
                return None
            return raw_resp.content.decode("utf-8", errors="replace")

        return None

    async def _async_request(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        headers = self._headers if self._is_github_api_url(url) else self._raw_headers
        try:
            response = await client.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise AppError(
                message="GitHub API request timed out.",
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                code="github_timeout",
            ) from exc
        except httpx.RequestError as exc:
            raise AppError(
                message="Network error while communicating with GitHub API.",
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="github_network_error",
            ) from exc

        if response.status_code == 404:
            raise AppError(
                message="GitHub repository or resource not found (or repository is private).",
                status_code=status.HTTP_404_NOT_FOUND,
                code="github_not_found",
            )
        if response.status_code in (403, 429):
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining == "0" or response.status_code == 429:
                raise AppError(
                    message="GitHub API rate limit exceeded. Configure or refresh GITHUB_TOKEN in backend/.env.",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    code="github_rate_limited",
                )
            raise AppError(
                message="Access denied by GitHub API.",
                status_code=status.HTTP_403_FORBIDDEN,
                code="github_forbidden",
            )
        if response.status_code >= 400:
            raise AppError(
                message=f"GitHub API returned unexpected status {response.status_code}.",
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="github_api_error",
            )
        return response

    async def fetch_files_concurrent(
        self,
        owner: str,
        name: str,
        branch: str,
        paths: list[str],
        max_concurrency: int = 12,
    ) -> dict[str, str | None]:
        """Fetch multiple UTF-8 source files concurrently with bounded semaphore."""
        import asyncio

        semaphore = asyncio.Semaphore(max_concurrency)
        encoded_branch = quote(branch, safe="")
        limits = httpx.Limits(max_connections=max_concurrency + 4, max_keepalive_connections=max_concurrency)

        async with httpx.AsyncClient(
            timeout=self.settings.GITHUB_TIMEOUT_SECONDS,
            follow_redirects=True,
            limits=limits,
        ) as client:
            async def fetch_one(file_path: str) -> tuple[str, str | None]:
                async with semaphore:
                    encoded_path = quote(file_path, safe="/")
                    url = f"{GITHUB_API_BASE}/repos/{owner}/{name}/contents/{encoded_path}?ref={encoded_branch}"
                    data = (await self._async_request(client, url)).json()
                    if not isinstance(data, dict):
                        return file_path, None
                    size = data.get("size", 0) or 0
                    if size > self.settings.MAX_FILE_SIZE_BYTES:
                        return file_path, None
                    if data.get("encoding") == "base64" and data.get("content"):
                        raw_bytes = base64.b64decode(data["content"])
                        if b"\x00" in raw_bytes:
                            return file_path, None
                        return file_path, raw_bytes.decode("utf-8", errors="replace")
                    download_url = data.get("download_url")
                    if download_url and self._is_allowed_download_url(download_url):
                        raw_resp = await self._async_request(client, download_url)
                        if len(raw_resp.content) > self.settings.MAX_FILE_SIZE_BYTES or b"\x00" in raw_resp.content:
                            return file_path, None
                        return file_path, raw_resp.content.decode("utf-8", errors="replace")
                    return file_path, None

            pairs = await asyncio.gather(*(fetch_one(p) for p in paths))
            return dict(pairs)


def classify_file(file_path: str) -> tuple[str | None, str | None, bool]:
    """Return (extension, language, is_supported) for a repository file path."""
    parts = file_path.split("/")
    if any(part in IGNORED_DIR_PARTS for part in parts[:-1]):
        return None, None, False

    filename = parts[-1]
    lower_name = filename.lower()

    if lower_name == ".env.example":
        return ".env.example", "Env", True

    if "." not in filename:
        return None, None, False

    ext = "." + filename.rsplit(".", 1)[-1].lower()
    language = SUPPORTED_EXTENSIONS.get(ext)
    return ext, language, language is not None
