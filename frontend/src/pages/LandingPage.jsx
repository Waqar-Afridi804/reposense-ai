import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { ErrorBanner, LoadingSpinner } from "../components/StatusAlert";
import { useRepo } from "../context/RepoContext";

const GITHUB_URL_REGEX = /^https?:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?\/?$/i;

const CAPABILITIES = [
  {
    title: "Static AST Inspection",
    description: "Extract classes, functions, methods, and exact line ranges without executing untrusted code.",
  },
  {
    title: "Dependency Mapping",
    description: "Resolve internal module imports and separate external or unresolved packages.",
  },
  {
    title: "Semantic Code Search",
    description: "Query indexed code chunks in natural language via all-MiniLM-L6-v2 and pgvector.",
  },
  {
    title: "Grounded AI Assistant",
    description: "Stream answers from Gemini with verifiable file-path and line-number citations.",
  },
];

export default function LandingPage() {
  const navigate = useNavigate();
  const { repositories, loadingRepos, repoError, selectRepository, refreshRepositories } = useRepo();

  const [githubUrl, setGithubUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [stepLabel, setStepLabel] = useState("");
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState("");

  async function handleAnalyzeSubmit(e) {
    e.preventDefault();
    const trimmed = githubUrl.trim();
    if (!GITHUB_URL_REGEX.test(trimmed)) {
      setError("Enter a valid public GitHub repository URL (e.g., https://github.com/pallets/markupsafe).");
      return;
    }

    setError("");
    setSubmitting(true);
    try {
      setStepLabel("Fetching repository metadata from GitHub...");
      const created = await api.createRepository(trimmed);
      setStepLabel("Downloading source tree and running static AST analysis...");
      await api.analyzeRepository(created.id);
      await refreshRepositories();
      selectRepository(created.id);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message || "Failed to analyze repository.");
    } finally {
      setSubmitting(false);
      setStepLabel("");
    }
  }

  function handleOpenRepo(id) {
    selectRepository(id);
    navigate("/dashboard");
  }

  async function handleDeleteRepo(id) {
    setDeletingId(id);
    setError("");
    try {
      await api.deleteRepository(id);
      await refreshRepositories();
    } catch (err) {
      setError(err.message || "Failed to delete repository.");
    } finally {
      setDeletingId("");
    }
  }

  return (
    <div className="space-y-6">
      {/* Repository Ingestion Bar */}
      <section className="rounded-lg border border-zinc-800/80 bg-[#0b0b0e] p-5 sm:p-6">
        <div className="max-w-2xl">
          <h2 className="text-lg font-semibold tracking-tight text-zinc-100">
            Analyze a GitHub repository
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-zinc-400">
            Paste a public GitHub URL to index source files, map module dependencies, generate vector embeddings, and query the codebase.
          </p>
        </div>

        <form onSubmit={handleAnalyzeSubmit} className="mt-4 flex flex-col gap-2.5 sm:flex-row">
          <input
            type="url"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
            placeholder="https://github.com/owner/repository"
            disabled={submitting}
            className="flex-1 rounded-md border border-zinc-800 bg-[#09090b] px-3 py-2 font-mono text-xs text-zinc-100 placeholder-zinc-500 focus:border-zinc-500 focus:outline-none disabled:opacity-60"
            required
          />
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex shrink-0 items-center justify-center rounded-md bg-zinc-100 px-4 py-2 text-xs font-semibold text-zinc-950 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Analyzing..." : "Analyze Repository"}
          </button>
        </form>

        {submitting && stepLabel && (
          <p className="mt-2.5 font-mono text-[11px] text-zinc-400">{stepLabel}</p>
        )}

        <div className="mt-3">
          <ErrorBanner message={error || repoError} />
        </div>
      </section>

      {/* Capabilities Strip */}
      <section className="grid grid-cols-1 divide-y divide-zinc-800/80 rounded-lg border border-zinc-800/80 bg-[#0b0b0e] sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-4">
        {CAPABILITIES.map((cap) => (
          <div key={cap.title} className="p-4">
            <h3 className="text-xs font-medium text-zinc-200">{cap.title}</h3>
            <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">{cap.description}</p>
          </div>
        ))}
      </section>

      {/* Tracked Repositories */}
      <section className="rounded-lg border border-zinc-800/80 bg-[#0b0b0e]">
        <div className="flex items-center justify-between border-b border-zinc-800/80 px-5 py-3.5">
          <div className="flex items-center gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              Your Repositories
            </h3>
            <span className="rounded bg-zinc-900 px-1.5 py-0.5 font-mono text-[11px] text-zinc-400 tabular-nums">
              {repositories.length}
            </span>
          </div>
          <button
            type="button"
            onClick={refreshRepositories}
            className="rounded-md border border-zinc-800 bg-[#09090b] px-2.5 py-1 text-xs font-medium text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white"
          >
            Refresh
          </button>
        </div>

        {loadingRepos ? (
          <LoadingSpinner label="Loading repositories..." />
        ) : repositories.length === 0 ? (
          <div className="px-5 py-10 text-center text-xs text-zinc-500">
            No repositories registered yet. Paste a public GitHub URL above to begin.
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/70">
            {repositories.map((repo) => (
              <div
                key={repo.id}
                className="flex flex-col justify-between gap-3 px-5 py-3.5 transition-colors hover:bg-zinc-900/40 sm:flex-row sm:items-center"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        repo.status === "completed"
                          ? "bg-emerald-400"
                          : repo.status === "failed"
                          ? "bg-red-400"
                          : "bg-amber-400"
                      }`}
                    />
                    <span className="font-mono text-xs font-medium text-zinc-100">
                      {repo.owner}/{repo.name}
                    </span>
                    <span className="rounded border border-zinc-800 bg-[#09090b] px-1.5 py-0.5 text-[11px] text-zinc-400">
                      {repo.status}
                    </span>
                    {repo.primary_language && (
                      <span className="rounded border border-zinc-800 bg-[#09090b] px-1.5 py-0.5 text-[11px] text-zinc-300">
                        {repo.primary_language}
                      </span>
                    )}
                    <span className="font-mono text-[11px] text-zinc-500 tabular-nums">
                      ★ {repo.stars_count}
                    </span>
                  </div>
                  <p className="mt-1 truncate text-xs text-zinc-500">
                    {repo.description || repo.github_url}
                  </p>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleOpenRepo(repo.id)}
                    className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1 text-xs font-medium text-zinc-100 transition-colors hover:bg-zinc-800"
                  >
                    Open
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteRepo(repo.id)}
                    disabled={deletingId === repo.id}
                    className="rounded-md border border-zinc-800 bg-transparent px-3 py-1 text-xs font-medium text-zinc-400 transition-colors hover:border-red-500/40 hover:bg-red-950/30 hover:text-red-300 disabled:opacity-50"
                  >
                    {deletingId === repo.id ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
