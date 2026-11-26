import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EmptyRepoState, ErrorBanner } from "../components/StatusAlert";
import { useRepo } from "../context/RepoContext";

export default function SemanticSearchPage() {
  const { selectedRepo } = useRepo();
  const [embStatus, setEmbStatus] = useState(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);
  const [searching, setSearching] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const loadStatus = useCallback(async (repoId) => {
    try {
      const st = await api.getEmbeddingStatus(repoId);
      setEmbStatus(st);
    } catch {
      setEmbStatus(null);
    }
  }, []);

  useEffect(() => {
    setResults([]);
    setSearched(false);
    setError("");
    if (selectedRepo?.id) {
      loadStatus(selectedRepo.id);
    } else {
      setEmbStatus(null);
    }
  }, [selectedRepo?.id, loadStatus]);

  async function handleGenerateEmbeddings() {
    if (!selectedRepo) return;
    setGenerating(true);
    setError("");
    try {
      await api.generateEmbeddings(selectedRepo.id);
      await loadStatus(selectedRepo.id);
    } catch (err) {
      setError(err.message || "Failed to generate embeddings.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (!selectedRepo || query.trim().length < 2) {
      setError("Enter a search query (at least 2 characters).");
      return;
    }
    setSearching(true);
    setError("");
    try {
      const data = await api.searchRepository(selectedRepo.id, query.trim(), 8);
      setResults(data?.results || []);
      setSearched(true);
    } catch (err) {
      setError(err.message || "Semantic search failed.");
    } finally {
      setSearching(false);
    }
  }

  if (!selectedRepo) {
    return <EmptyRepoState title="No repository selected" />;
  }

  const ready = embStatus?.status === "completed";

  return (
    <div className="space-y-5">
      <ErrorBanner message={error} />

      {/* Vector Index Status */}
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-zinc-800/80 bg-[#0b0b0e] px-4 py-3">
        <div className="font-mono text-xs text-zinc-400">
          <span className="font-medium text-zinc-200">Vector Index:</span>{" "}
          {embStatus
            ? `${embStatus.total_embeddings}/${embStatus.total_chunks} chunks · ${embStatus.embedding_model}`
            : "Checking index status..."}
        </div>
        {!ready && (
          <button
            type="button"
            onClick={handleGenerateEmbeddings}
            disabled={generating}
            className="rounded-md bg-zinc-100 px-3 py-1.5 text-xs font-semibold text-zinc-950 transition-colors hover:bg-white disabled:opacity-50"
          >
            {generating ? "Indexing..." : "Generate Embeddings"}
          </button>
        )}
      </section>

      {/* Search Form */}
      <section className="rounded-lg border border-zinc-800/80 bg-[#0b0b0e] p-4">
        <form onSubmit={handleSearch} className="flex flex-col gap-2.5 sm:flex-row">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search codebase by intent (e.g., 'How is HTML escaping implemented?')"
            disabled={searching}
            className="flex-1 rounded-md border border-zinc-800 bg-[#09090b] px-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:border-zinc-600 focus:outline-none"
          />
          <button
            type="submit"
            disabled={searching || !ready}
            className="rounded-md bg-zinc-100 px-4 py-2 text-xs font-semibold text-zinc-950 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {searching ? "Searching..." : "Search"}
          </button>
        </form>
        {!ready && (
          <p className="mt-2 text-[11px] text-amber-300">
            Generate embeddings first so pgvector can search this repository.
          </p>
        )}
      </section>

      {/* Results */}
      {searched && results.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-800 bg-[#0b0b0e] p-8 text-center text-xs text-zinc-500">
          No matching code chunks found for &ldquo;{query}&rdquo;.
        </div>
      ) : (
        <div className="space-y-3">
          {results.map((item) => (
            <article key={item.chunk_id} className="overflow-hidden rounded-lg border border-zinc-800/80 bg-[#0b0b0e]">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/80 px-4 py-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs font-medium text-zinc-100">
                    {item.file_path}
                  </span>
                  <span className="rounded border border-zinc-800 bg-[#09090b] px-1.5 py-0.5 font-mono text-[11px] text-zinc-400 tabular-nums">
                    L{item.start_line}–{item.end_line}
                  </span>
                  {item.symbol_name && (
                    <span className="rounded border border-emerald-500/25 bg-emerald-950/20 px-1.5 py-0.5 font-mono text-[11px] text-emerald-300">
                      {item.symbol_name}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <span className="font-mono text-[11px] text-zinc-400 tabular-nums">
                    {(item.similarity * 100).toFixed(1)}% match
                  </span>
                  <Link
                    to={`/explorer?file=${encodeURIComponent(item.file_path)}&line=${item.start_line}`}
                    className="rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-[11px] font-medium text-zinc-200 transition-colors hover:bg-zinc-800"
                  >
                    Open in Explorer
                  </Link>
                </div>
              </div>

              <pre className="max-h-64 overflow-auto bg-[#09090b] p-3.5 font-mono text-xs leading-relaxed text-zinc-300">
                <code>{item.content}</code>
              </pre>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
