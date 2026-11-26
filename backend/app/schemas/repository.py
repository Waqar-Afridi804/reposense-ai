import re
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

GITHUB_REPO_PATTERN = re.compile(r"^https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


class RepositoryCreate(BaseModel):
    """Request schema for registering a GitHub repository."""

    github_url: str = Field(..., min_length=19, max_length=500, description="Public GitHub repository URL")
    default_branch: str | None = Field(default=None, max_length=100)
    description: str | None = None

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        if cleaned.endswith(".git"):
            cleaned = cleaned[:-4]
        match = GITHUB_REPO_PATTERN.match(cleaned)
        if not match:
            raise ValueError("github_url must be a valid GitHub repository URL (e.g., https://github.com/owner/repo)")
        owner, name = match.group(1), match.group(2)
        if owner in {".", ".."} or name in {".", ".."} or ".." in owner or ".." in name:
            raise ValueError("Invalid repository owner or name in github_url")
        return cleaned

    def extract_owner_and_name(self) -> tuple[str, str]:
        match = GITHUB_REPO_PATTERN.match(self.github_url)
        if not match:
            raise ValueError("Invalid GitHub repository URL")
        owner, name = match.group(1), match.group(2)
        if owner in {".", ".."} or name in {".", ".."} or ".." in owner or ".." in name:
            raise ValueError("Invalid repository owner or name")
        return owner, name


class RepositoryResponse(BaseModel):
    """Response schema for a tracked repository."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    github_url: str
    owner: str
    name: str
    default_branch: str | None = None
    description: str | None = None
    primary_language: str | None = None
    stars_count: int
    forks_count: int
    status: str
    github_created_at: datetime | None = None
    github_updated_at: datetime | None = None
    last_analyzed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RepositoryListResponse(BaseModel):
    """Paginated list of repositories."""

    items: list[RepositoryResponse]
    total: int


class RepositoryFileSummary(BaseModel):
    """File metadata without full source content."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    file_path: str
    file_name: str
    extension: str | None = None
    language: str | None = None
    size_bytes: int
    line_count: int
    content_hash: str | None = None
    is_supported: bool
    created_at: datetime


class RepositoryFileDetail(RepositoryFileSummary):
    """File metadata including source content."""

    content: str | None = None


class RepositoryFileListResponse(BaseModel):
    """List of repository files."""

    items: list[RepositoryFileSummary]
    total: int


class AnalysisStatusResponse(BaseModel):
    """Current status of a repository and its latest analysis."""

    repository_id: UUID
    repository_status: str
    latest_analysis_id: UUID | None = None
    latest_analysis_status: str | None = None
    error_message: str | None = None
    last_analyzed_at: datetime | None = None


class AnalysisResultResponse(BaseModel):
    """Full analysis results including AST details and statistics."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    status: str
    summary: str | None = None
    total_files: int
    supported_files: int
    python_files_count: int
    other_supported_files_count: int
    total_lines: int
    total_classes: int
    total_functions: int
    total_methods: int
    language_stats: dict
    ast_details: dict | None = None
    error_message: str | None = None
    created_at: datetime


class DependencyGraphResponse(BaseModel):
    """Dependency graph nodes, edges, external packages, and Mermaid diagram."""

    repository_id: UUID
    analysis_id: UUID
    nodes: list[dict]
    edges: list[dict]
    internal_dependency_count: int
    external_dependencies: list[str]
    mermaid: str


class DatabaseHealthResponse(BaseModel):
    """Database and pgvector health check response."""

    status: str
    configured: bool
    connected: bool
    pgvector_enabled: bool
    pgvector_version: str | None = None
    detail: str


class EmbeddingGenerationResponse(BaseModel):
    """Result of code chunking and embedding generation for a repository."""

    repository_id: UUID
    embedding_model: str
    vector_dimension: int
    files_processed: int
    total_chunks: int
    total_embeddings: int
    newly_embedded: int
    skipped_existing: int
    status: str


class EmbeddingStatusResponse(BaseModel):
    """Current chunk and embedding status for a repository."""

    repository_id: UUID
    embedding_model: str
    vector_dimension: int
    total_chunks: int
    total_embeddings: int
    status: str


class SemanticSearchRequest(BaseModel):
    """Natural-language semantic code search request."""

    query: str = Field(..., min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class SemanticSearchResultItem(BaseModel):
    """Single semantic search match with file path, lines, and similarity."""

    chunk_id: UUID
    file_path: str
    start_line: int
    end_line: int
    symbol_name: str | None = None
    chunk_type: str | None = None
    similarity: float
    content: str


class SemanticSearchResponse(BaseModel):
    """Semantic search response."""

    repository_id: UUID
    query: str
    total_results: int
    results: list[SemanticSearchResultItem]


class RagAskRequest(BaseModel):
    """Question for the Gemini RAG code assistant."""

    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=15)


class CodeReference(BaseModel):
    """Code location reference used to ground an AI answer."""

    chunk_id: UUID
    file_path: str
    start_line: int
    end_line: int
    symbol_name: str | None = None
    similarity: float


class RagAskResponse(BaseModel):
    """Grounded RAG assistant response with file and line references."""

    repository_id: UUID
    question: str
    model: str
    sufficient_context: bool
    answer: str
    references: list[CodeReference]
