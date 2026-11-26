import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { EmptyRepoState, ErrorBanner, LoadingSpinner } from "../components/StatusAlert";
import { useRepo } from "../context/RepoContext";

export default function DashboardPage() {
  const { selectedRepo, refreshRepositories } = useRepo();
  const [analysis, setAnalysis] = useState(null);
  const [embeddingStatus, setEmbeddingStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState("");
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async (repoId) => {
    setLoading(true);
    setError("");
    try {
      const [analysisRes, embRes] = await Promise.allSettled([
        api.getRepositoryAnalysis(repoId),
        api.getEmbeddingStatus(repoId),
      ]);

      setAnalysis(analysisRes.status === "fulfilled" ? analysisRes.value : null);
      setEmbeddingStatus(embRes.status === "fulfilled" ? embRes.value : null);

      if (analysisRes.status === "rejected" && analysisRes.reason?.status !== 404) {
        setError(analysisRes.reason?.message || "Failed to load analysis.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedRepo?.id) {
      loadDashboard(selectedRepo.id);
    } else {
      setAnalysis(null);
      setEmbeddingStatus(null);
    }
  }, [selectedRepo?.id, loadDashboard]);

  async function handleRunAnalysis() {
    if (!selectedRepo) return;
    setActionLoading("analyze");
    setError("");
    try {
      await api.analyzeRepository(selectedRepo.id);
      await refreshRepositories();
      await loadDashboard(selectedRepo.id);
    } catch (err) {
      setError(err.message || "Analysis failed.");
    } finally {
      setActionLoading("");
    }
  }

  async function handleGenerateEmbeddings() {
    if (!selectedRepo) return;
    setActionLoading("embed");
    setError("");
    try {
      await api.generateEmbeddings(selectedRepo.id);
      await loadDashboard(selectedRepo.id);
    } catch (err) {
      setError(err.message || "Embedding generation failed.");
    } finally {
      setActionLoading("");
    }
  }

  if (!selectedRepo) {
    return <EmptyRepoState title="No repository selected" />;
  }

  const languageData = Object.entries(analysis?.language_stats || {})
    .map(([name, files]) => ({ name, files }))
    .sort((a, b) => b.files - a.files);

  const stats = [
    { label: "Total Files", value: analysis ? analysis.total_files.toLocaleString() : "—" },
    { label: "Supported", value: analysis ? analysis.supported_files.toLocaleString() : "—" },
    { label: "Python Files", value: analysis ? analysis.python_files_count.toLocaleString() : "—" },
    { label: "Classes", value: analysis ? analysis.total_classes.toLocaleString() : "—" },
    {
      label: "Functions / Methods",
      value: analysis ? (analysis.total_functions + analysis.total_methods).toLocaleString() : "—",
    },
    { label: "Total Lines", value: analysis ? analysis.total_lines.toLocaleString() : "—" },
  ];

  return (
    <div className="space-y-5">
      <ErrorBanner message={error} onRetry={() => loadDashboard(selectedRepo.id)} />

      {/* Repo Summary Header */}
      <section className="flex flex-col justify-between gap-4 rounded-lg border border-zinc-800/80 bg-[#0b0b0e] p-5 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-mono text-sm font-semibold text-zinc-100">
              {selectedRepo.owner}/{selectedRepo.name}
            </h2>
            <span className="rounded border border-zinc-800 bg-[#09090b] px-2 py-0.5 text-[11px] font-medium text-zinc-300">
              {selectedRepo.status}
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            {selectedRepo.description || "No repository description."}
          </p>
          <div className="mt-2.5 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-zinc-500 tabular-nums">
            <span>branch:{selectedRepo.default_branch || "—"}</span>
            <span>stars:{selectedRepo.stars_count}</span>
            <span>forks:{selectedRepo.forks_count}</span>
            <span>
              vectors:{" "}
              {embeddingStatus
                ? `${embeddingStatus.total_embeddings}/${embeddingStatus.total_chunks} (${embeddingStatus.status})`
                : "—"}
            </span>
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={handleRunAnalysis}
            disabled={Boolean(actionLoading)}
            className="rounded-md bg-zinc-100 px-3.5 py-1.5 text-xs font-semibold text-zinc-950 transition-colors hover:bg-white disabled:opacity-50"
          >
            {actionLoading === "analyze" ? "Analyzing..." : analysis ? "Re-run Analysis" : "Run Analysis"}
          </button>
          {analysis && (
            <button
              type="button"
              onClick={handleGenerateEmbeddings}
              disabled={Boolean(actionLoading)}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3.5 py-1.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-zinc-800 disabled:opacity-50"
            >
              {actionLoading === "embed" ? "Indexing..." : "Generate Embeddings"}
            </button>
          )}
          <Link
            to="/report"
            className="rounded-md border border-zinc-800 bg-[#09090b] px-3.5 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white"
          >
            Full Report
          </Link>
        </div>
      </section>

      {loading ? (
        <LoadingSpinner label="Loading repository overview..." />
      ) : !analysis ? (
        <div className="rounded-lg border border-dashed border-zinc-800 bg-[#0b0b0e] p-8 text-center">
          <p className="text-xs text-zinc-400">
            This repository has not been analyzed yet. Click <strong className="text-zinc-200">Run Analysis</strong> above to fetch files and run AST analysis.
          </p>
        </div>
      ) : (
        <>
          {/* Unified Metric Strip */}
          <section className="grid grid-cols-2 divide-x divide-y divide-zinc-800/80 rounded-lg border border-zinc-800/80 bg-[#0b0b0e] sm:grid-cols-3 lg:grid-cols-6 lg:divide-y-0">
            {stats.map((s) => (
              <div key={s.label} className="px-4 py-3.5">
                <p className="text-[11px] font-medium text-zinc-500">{s.label}</p>
                <p className="mt-1 font-mono text-xl font-semibold text-zinc-100 tabular-nums">
                  {s.value}
                </p>
              </div>
            ))}
          </section>

          {/* Language Distribution Chart */}
          <section className="rounded-lg border border-zinc-800/80 bg-[#0b0b0e] p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Language Distribution
              </h3>
              <span className="font-mono text-[11px] text-zinc-500">Files in repository tree</span>
            </div>
            {languageData.length === 0 ? (
              <p className="mt-4 text-xs text-zinc-500">No supported language statistics detected.</p>
            ) : (
              <div className="mt-4 h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={languageData} margin={{ top: 8, right: 12, left: -12, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#18181b" vertical={false} />
                    <XAxis dataKey="name" stroke="#71717a" fontSize={11} tickLine={false} axisLine={{ stroke: "#27272a" }} />
                    <YAxis stroke="#71717a" fontSize={11} allowDecimals={false} tickLine={false} axisLine={false} />
                    <Tooltip
                      cursor={{ fill: "#18181b" }}
                      contentStyle={{
                        backgroundColor: "#111114",
                        borderColor: "#27272a",
                        color: "#f4f4f5",
                        borderRadius: "6px",
                        fontSize: "12px",
                      }}
                    />
                    <Bar dataKey="files" fill="#e4e4e7" radius={[3, 3, 0, 0]} maxBarSize={42} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
