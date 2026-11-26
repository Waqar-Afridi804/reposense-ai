import hashlib
from datetime import datetime, timezone
import httpx
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import AnalysisResult, Repository, RepositoryFile
from app.services.ast_analyzer import analyze_python_source
from app.services.dependency_graph import build_dependency_graph
from app.services.github_service import GitHubService, classify_file


def run_repository_analysis(db: Session, repo: Repository, settings: Settings) -> AnalysisResult:
    """Fetch GitHub files, run Python AST & dependency analysis, and persist results."""
    github = GitHubService(settings)

    repo.status = "analyzing"
    db.commit()

    analysis = AnalysisResult(repository_id=repo.id, status="running")
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    try:
        meta = github.fetch_repo_metadata(repo.owner, repo.name)
        repo.github_url = meta["github_url"]
        repo.description = meta["description"]
        repo.default_branch = meta["default_branch"]
        repo.primary_language = meta["primary_language"]
        repo.stars_count = meta["stars_count"]
        repo.forks_count = meta["forks_count"]
        repo.github_created_at = meta["github_created_at"]
        repo.github_updated_at = meta["github_updated_at"]

        tree_items, tree_truncated = github.fetch_repo_tree(
            repo.owner, repo.name, repo.default_branch or "main"
        )

        # Classify all blobs in tree
        classified: list[dict] = []
        language_stats: dict[str, int] = {}
        for item in tree_items:
            path = item.get("path", "")
            size = item.get("size", 0) or 0
            ext, language, is_supported = classify_file(path)
            if language:
                language_stats[language] = language_stats.get(language, 0) + 1
            classified.append(
                {
                    "path": path,
                    "size": size,
                    "extension": ext,
                    "language": language,
                    "is_supported": is_supported,
                }
            )

        supported_items = [
            f for f in classified if f["is_supported"] and f["size"] <= settings.MAX_FILE_SIZE_BYTES
        ]
        # Prioritize Python files first, then other supported files up to MAX_FILES_PER_REPO
        supported_items.sort(key=lambda f: (0 if f["extension"] == ".py" else 1, f["path"]))
        selected_items = supported_items[: settings.MAX_FILES_PER_REPO]

        import asyncio

        selected_paths = [item["path"] for item in selected_items]
        fetched_contents = asyncio.run(
            github.fetch_files_concurrent(
                repo.owner,
                repo.name,
                repo.default_branch or "main",
                selected_paths,
                max_concurrency=12,
            )
        )

        # Clear previous files for this repository to keep re-analysis idempotent
        db.execute(delete(RepositoryFile).where(RepositoryFile.repository_id == repo.id))

        ast_results: list[dict] = []
        new_db_files: list[RepositoryFile] = []
        python_files_count = 0
        other_supported_files_count = 0
        total_lines = 0
        total_classes = 0
        total_functions = 0
        total_methods = 0

        for item in selected_items:
            path = item["path"]
            content = fetched_contents.get(path)
            if content is None:
                continue

            line_count = len(content.splitlines())
            total_lines += line_count
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            file_name = path.rsplit("/", 1)[-1]

            new_db_files.append(
                RepositoryFile(
                    repository_id=repo.id,
                    file_path=path,
                    file_name=file_name,
                    extension=item["extension"],
                    language=item["language"],
                    size_bytes=len(content.encode("utf-8")),
                    line_count=line_count,
                    content_hash=content_hash,
                    content=content,
                    is_supported=True,
                )
            )

            if item["extension"] == ".py":
                python_files_count += 1
                ast_info = analyze_python_source(path, content)
                ast_results.append(ast_info)
                total_classes += len(ast_info["classes"])
                total_functions += len(ast_info["functions"])
                total_methods += ast_info["methods_count"]
            else:
                other_supported_files_count += 1

        if new_db_files:
            db.add_all(new_db_files)

        dep_graph = build_dependency_graph(ast_results)
        analyzed_supported_count = python_files_count + other_supported_files_count

        summary_parts = [
            f"Analyzed {analyzed_supported_count} supported files out of {len(tree_items)} total blobs in {repo.owner}/{repo.name}.",
            f"Detected {python_files_count} Python files with {total_classes} classes, {total_functions} top-level functions, and {total_methods} methods.",
            f"Identified {dep_graph['internal_dependency_count']} internal module dependencies and {len(dep_graph['external_dependencies'])} external/unresolved packages.",
        ]
        if tree_truncated or len(supported_items) > settings.MAX_FILES_PER_REPO:
            summary_parts.append(
                f"Note: Repository file retrieval was capped at {settings.MAX_FILES_PER_REPO} supported files."
            )

        analysis.summary = " ".join(summary_parts)
        analysis.total_files = len(tree_items)
        analysis.supported_files = analyzed_supported_count
        analysis.python_files_count = python_files_count
        analysis.other_supported_files_count = other_supported_files_count
        analysis.total_lines = total_lines
        analysis.total_classes = total_classes
        analysis.total_functions = total_functions
        analysis.total_methods = total_methods
        analysis.language_stats = language_stats
        analysis.dependency_graph = {
            "nodes": dep_graph["nodes"],
            "edges": dep_graph["edges"],
            "internal_dependency_count": dep_graph["internal_dependency_count"],
            "external_dependencies": dep_graph["external_dependencies"],
        }
        analysis.ast_details = {"files": ast_results}
        analysis.mermaid_diagram = dep_graph["mermaid"]
        analysis.status = "completed"

        repo.status = "completed"
        repo.last_analyzed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(analysis)
        return analysis

    except AppError as exc:
        analysis.status = "failed"
        analysis.error_message = exc.message
        repo.status = "failed"
        db.commit()
        raise
    except Exception as exc:
        analysis.status = "failed"
        analysis.error_message = "Unexpected error during repository analysis."
        repo.status = "failed"
        db.commit()
        raise AppError(
            message="Unexpected error during repository analysis.",
            status_code=500,
            code="analysis_failed",
        ) from exc
