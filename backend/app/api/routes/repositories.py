from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, defer

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.cache import repo_response_cache
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.rate_limit import rate_limiter
from app.db.models import AnalysisResult, Repository, RepositoryFile
from app.db.session import get_db
from app.schemas.repository import (
    AnalysisResultResponse,
    AnalysisStatusResponse,
    DependencyGraphResponse,
    EmbeddingGenerationResponse,
    EmbeddingStatusResponse,
    RagAskRequest,
    RagAskResponse,
    RepositoryCreate,
    RepositoryFileDetail,
    RepositoryFileListResponse,
    RepositoryFileSummary,
    RepositoryListResponse,
    RepositoryResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.services.analysis_service import run_repository_analysis
from app.services.embedding_service import generate_repository_embeddings, get_embedding_status
from app.services.github_service import GitHubService
from app.services.rag_service import answer_repository_question, stream_repository_question
from app.services.search_service import semantic_search_repository

router = APIRouter(prefix="/repositories", tags=["Repositories"])


def _user_cache_prefix(user_id: UUID) -> str:
    return f"u:{user_id}:"


def _invalidate_user_cache(user_id: UUID) -> None:
    repo_response_cache.invalidate_prefix(_user_cache_prefix(user_id))


def _get_repo_or_404(db: Session, repository_id: UUID, user_id: UUID) -> Repository:
    repo = db.execute(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not repo:
        raise AppError(
            message="Repository not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="repository_not_found",
        )
    return repo


def _get_latest_analysis(db: Session, repository_id: UUID) -> AnalysisResult | None:
    return db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.repository_id == repository_id)
        .order_by(AnalysisResult.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


@router.get("", response_model=RepositoryListResponse)
def list_repositories(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RepositoryListResponse:
    """List repositories owned by the authenticated user."""
    cache_key = f"{_user_cache_prefix(current_user.id)}list:{limit}:{offset}"
    cached = repo_response_cache.get(cache_key)
    if cached is not None:
        return cached

    rows = db.execute(
        select(Repository, func.count().over().label("total_count"))
        .where(Repository.user_id == current_user.id)
        .order_by(Repository.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    items = [RepositoryResponse.model_validate(row[0]) for row in rows]
    total = int(rows[0][1]) if rows else 0
    result = RepositoryListResponse(items=items, total=total)
    repo_response_cache.set(cache_key, result, ttl=60.0)
    return result


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def create_repository(
    payload: RepositoryCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RepositoryResponse:
    """Validate and register a public GitHub repository for the current user."""
    owner, name = payload.extract_owner_and_name()

    existing = db.execute(
        select(Repository).where(
            Repository.user_id == current_user.id,
            (Repository.github_url == payload.github_url)
            | ((func.lower(Repository.owner) == owner.lower()) & (func.lower(Repository.name) == name.lower())),
        )
    ).scalar_one_or_none()

    if existing:
        raise AppError(
            message=f"Repository '{existing.owner}/{existing.name}' is already registered.",
            status_code=status.HTTP_409_CONFLICT,
            code="repository_exists",
        )

    github = GitHubService(settings)
    meta = github.fetch_repo_metadata(owner, name)

    repo = Repository(
        user_id=current_user.id,
        github_url=meta["github_url"],
        owner=meta["owner"],
        name=meta["name"],
        default_branch=payload.default_branch or meta["default_branch"],
        description=payload.description if payload.description is not None else meta["description"],
        primary_language=meta["primary_language"],
        stars_count=meta["stars_count"],
        forks_count=meta["forks_count"],
        github_created_at=meta["github_created_at"],
        github_updated_at=meta["github_updated_at"],
        status="pending",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    _invalidate_user_cache(current_user.id)
    return repo


@router.get("/{repository_id}", response_model=RepositoryResponse)
def get_repository(
    repository_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RepositoryResponse:
    """Fetch a single registered repository owned by the current user."""
    return _get_repo_or_404(db, repository_id, current_user.id)


@router.delete("/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(
    repository_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a user-owned repository and cascade child records on PostgreSQL."""
    result = db.execute(
        delete(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == current_user.id,
        )
    )
    if result.rowcount == 0:
        raise AppError(
            message="Repository not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="repository_not_found",
        )
    db.commit()
    _invalidate_user_cache(current_user.id)


@router.post("/{repository_id}/analyze", response_model=AnalysisResultResponse)
def analyze_repository(
    repository_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AnalysisResultResponse:
    """Fetch repository files from GitHub, run Python AST analysis, and store results."""
    rate_limiter.check(current_user.id, "analyze", max_requests=10, window_seconds=60.0)
    repo = _get_repo_or_404(db, repository_id, current_user.id)
    result = run_repository_analysis(db, repo, settings)
    _invalidate_user_cache(current_user.id)
    return result


@router.get("/{repository_id}/status", response_model=AnalysisStatusResponse)
def get_analysis_status(
    repository_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisStatusResponse:
    """Return repository analysis status and latest analysis run metadata."""
    repo = _get_repo_or_404(db, repository_id, current_user.id)
    latest = _get_latest_analysis(db, repository_id)
    return AnalysisStatusResponse(
        repository_id=repo.id,
        repository_status=repo.status,
        latest_analysis_id=latest.id if latest else None,
        latest_analysis_status=latest.status if latest else None,
        error_message=latest.error_message if latest else None,
        last_analyzed_at=repo.last_analyzed_at,
    )


@router.get("/{repository_id}/files", response_model=RepositoryFileListResponse)
def list_repository_files(
    repository_id: UUID,
    language: str | None = Query(default=None),
    extension: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RepositoryFileListResponse:
    """List analyzed files stored for a repository without transferring file content."""
    cache_key = f"{_user_cache_prefix(current_user.id)}files:{repository_id}:{language}:{extension}:{limit}:{offset}"
    cached = repo_response_cache.get(cache_key)
    if cached is not None:
        return cached

    _get_repo_or_404(db, repository_id, current_user.id)

    filters = [RepositoryFile.repository_id == repository_id]
    if language:
        filters.append(func.lower(RepositoryFile.language) == language.lower())
    if extension:
        ext_norm = extension if extension.startswith(".") else f".{extension}"
        filters.append(func.lower(RepositoryFile.extension) == ext_norm.lower())

    rows = db.execute(
        select(RepositoryFile, func.count().over().label("total_count"))
        .options(defer(RepositoryFile.content))
        .where(*filters)
        .order_by(RepositoryFile.file_path.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    items = [RepositoryFileSummary.model_validate(row[0]) for row in rows]
    total = int(rows[0][1]) if rows else 0
    result = RepositoryFileListResponse(items=items, total=total)
    repo_response_cache.set(cache_key, result, ttl=90.0)
    return result


@router.get("/{repository_id}/files/{file_id}", response_model=RepositoryFileDetail)
def get_repository_file(
    repository_id: UUID,
    file_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RepositoryFileDetail:
    """Retrieve metadata and source content for a single repository file."""
    cache_key = f"{_user_cache_prefix(current_user.id)}file:{repository_id}:{file_id}"
    cached = repo_response_cache.get(cache_key)
    if cached is not None:
        return cached

    file_obj = db.execute(
        select(RepositoryFile)
        .join(Repository, Repository.id == RepositoryFile.repository_id)
        .where(
            RepositoryFile.id == file_id,
            RepositoryFile.repository_id == repository_id,
            Repository.user_id == current_user.id,
        )
    ).scalar_one_or_none()

    if not file_obj:
        raise AppError(
            message="Repository file not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="file_not_found",
        )
    result = RepositoryFileDetail.model_validate(file_obj)
    repo_response_cache.set(cache_key, result, ttl=120.0)
    return result


@router.get("/{repository_id}/analysis", response_model=AnalysisResultResponse)
def get_repository_analysis(
    repository_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisResultResponse:
    """Retrieve the latest analysis result for a user-owned repository."""
    cache_key = f"{_user_cache_prefix(current_user.id)}analysis:{repository_id}"
    cached = repo_response_cache.get(cache_key)
    if cached is not None:
        return cached

    _get_repo_or_404(db, repository_id, current_user.id)
    latest = _get_latest_analysis(db, repository_id)
    if not latest:
        raise AppError(
            message="No analysis results found for this repository. Run POST /analyze first.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="analysis_not_found",
        )
    result = AnalysisResultResponse.model_validate(latest)
    repo_response_cache.set(cache_key, result, ttl=90.0)
    return result


@router.get("/{repository_id}/dependencies", response_model=DependencyGraphResponse)
def get_repository_dependencies(
    repository_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DependencyGraphResponse:
    """Retrieve dependency graph data and Mermaid.js flowchart for a repository."""
    cache_key = f"{_user_cache_prefix(current_user.id)}deps:{repository_id}"
    cached = repo_response_cache.get(cache_key)
    if cached is not None:
        return cached

    _get_repo_or_404(db, repository_id, current_user.id)
    latest = _get_latest_analysis(db, repository_id)
    if not latest or not latest.dependency_graph:
        raise AppError(
            message="No dependency graph found for this repository. Run POST /analyze first.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="dependency_graph_not_found",
        )

    graph = latest.dependency_graph
    result = DependencyGraphResponse(
        repository_id=repository_id,
        analysis_id=latest.id,
        nodes=graph.get("nodes", []),
        edges=graph.get("edges", []),
        internal_dependency_count=graph.get("internal_dependency_count", 0),
        external_dependencies=graph.get("external_dependencies", []),
        mermaid=latest.mermaid_diagram or "",
    )
    repo_response_cache.set(cache_key, result, ttl=90.0)
    return result


@router.post("/{repository_id}/embeddings", response_model=EmbeddingGenerationResponse)
def create_repository_embeddings(
    repository_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EmbeddingGenerationResponse:
    """Chunk analyzed repository files and generate pgvector embeddings."""
    rate_limiter.check(current_user.id, "embeddings", max_requests=10, window_seconds=60.0)
    _get_repo_or_404(db, repository_id, current_user.id)
    result = generate_repository_embeddings(db=db, repository_id=repository_id, settings=settings)
    _invalidate_user_cache(current_user.id)
    return result


@router.get("/{repository_id}/embeddings/status", response_model=EmbeddingStatusResponse)
def read_embedding_status(
    repository_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EmbeddingStatusResponse:
    """Return chunk and embedding generation status for a repository."""
    cache_key = f"{_user_cache_prefix(current_user.id)}emb_status:{repository_id}"
    cached = repo_response_cache.get(cache_key)
    if cached is not None:
        return cached

    _get_repo_or_404(db, repository_id, current_user.id)
    result = EmbeddingStatusResponse(**get_embedding_status(db=db, repository_id=repository_id, settings=settings))
    repo_response_cache.set(cache_key, result, ttl=60.0)
    return result


@router.post("/{repository_id}/search", response_model=SemanticSearchResponse)
def search_repository_code(
    repository_id: UUID,
    payload: SemanticSearchRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SemanticSearchResponse:
    """Perform semantic code search isolated to a single user-owned repository."""
    rate_limiter.check(current_user.id, "search", max_requests=30, window_seconds=60.0)
    _get_repo_or_404(db, repository_id, current_user.id)
    results = semantic_search_repository(
        db=db,
        repository_id=repository_id,
        query=payload.query,
        settings=settings,
        top_k=payload.top_k,
    )
    return SemanticSearchResponse(
        repository_id=repository_id,
        query=payload.query,
        total_results=len(results),
        results=results,
    )


@router.post("/{repository_id}/ask", response_model=RagAskResponse)
def ask_repository_assistant(
    repository_id: UUID,
    payload: RagAskRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RagAskResponse:
    """Ask the Gemini RAG assistant a question grounded in retrieved repository code."""
    from app.services.quota_service import enforce_ai_quota

    rate_limiter.check(current_user.id, "assistant", max_requests=20, window_seconds=60.0)
    enforce_ai_quota(db, current_user.id)
    repo = _get_repo_or_404(db, repository_id, current_user.id)
    return answer_repository_question(
        db=db,
        repo=repo,
        question=payload.question,
        settings=settings,
        top_k=payload.top_k,
        user_id=current_user.id,
    )


@router.post("/{repository_id}/ask/stream")
def stream_repository_assistant(
    repository_id: UUID,
    payload: RagAskRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Stream Gemini RAG assistant response tokens via Server-Sent Events."""
    from app.services.quota_service import enforce_ai_quota

    rate_limiter.check(current_user.id, "assistant", max_requests=20, window_seconds=60.0)
    enforce_ai_quota(db, current_user.id)
    repo = _get_repo_or_404(db, repository_id, current_user.id)
    return StreamingResponse(
        stream_repository_question(
            db=db,
            repo=repo,
            question=payload.question,
            settings=settings,
            top_k=payload.top_k,
            user_id=current_user.id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
