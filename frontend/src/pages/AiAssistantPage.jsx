import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EmptyRepoState, ErrorBanner } from "../components/StatusAlert";
import { useRepo } from "../context/RepoContext";

export default function AiAssistantPage() {
  const { selectedRepo } = useRepo();
  const [embStatus, setEmbStatus] = useState(null);
  const [quota, setQuota] = useState(null);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  const loadQuota = useCallback(async () => {
    try {
      const q = await api.getAiQuota();
      setQuota(q);
    } catch {
      setQuota(null);
    }
  }, []);

  const loadStatus = useCallback(async (repoId) => {
    try {
      const st = await api.getEmbeddingStatus(repoId);
      setEmbStatus(st);
    } catch {
      setEmbStatus(null);
    }
  }, []);

  useEffect(() => {
    loadQuota();
  }, [loadQuota]);

  useEffect(() => {
    setMessages([]);
    setError("");
    if (selectedRepo?.id) {
      loadStatus(selectedRepo.id);
    } else {
      setEmbStatus(null);
    }
  }, [selectedRepo?.id, loadStatus]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

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

  async function handleAsk(e) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!selectedRepo || trimmed.length < 3) {
      setError("Enter a question (at least 3 characters).");
      return;
    }
    if (quota?.is_limited) {
      setError("You have reached your 7-day AI assistant limit (6 chats or 400 words).");
      return;
    }

    setError("");
    setAsking(true);
    setQuestion("");

    const assistantId = `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    setMessages((prev) => [
      ...prev,
      { id: `${assistantId}_u`, role: "user", text: trimmed },
      {
        id: assistantId,
        role: "assistant",
        text: "",
        model: "",
        sufficientContext: true,
        references: [],
        streaming: true,
      },
    ]);

    try {
      await api.askAssistantStream(selectedRepo.id, trimmed, 5, {
        onMetadata: (meta) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    model: meta.model,
                    sufficientContext: meta.sufficient_context,
                    references: meta.references || [],
                  }
                : m
            )
          );
        },
        onDelta: (chunkText) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + chunkText } : m))
          );
        },
        onError: (msg) => {
          setError(msg || "Streaming response failed.");
        },
        onDone: () => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m))
          );
        },
      });
    } catch (err) {
      setError(err.message || "Failed to get answer from AI assistant.");
      setMessages((prev) => prev.filter((m) => m.id !== assistantId || m.text.length > 0));
    } finally {
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m))
      );
      setAsking(false);
      loadQuota();
    }
  }

  if (!selectedRepo) {
    return <EmptyRepoState title="No repository selected" />;
  }

  const ready = embStatus?.status === "completed";
  const quotaBlocked = Boolean(quota?.is_limited);

  return (
    <div className="space-y-4">
      <ErrorBanner message={error} />

      <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-zinc-800/80 bg-[#0b0b0e] px-4 py-3">
        <div className="font-mono text-xs text-zinc-400">
          <span className="font-medium text-zinc-200">RAG Context:</span>{" "}
          {embStatus
            ? `${embStatus.total_embeddings}/${embStatus.total_chunks} chunks indexed for ${selectedRepo.owner}/${selectedRepo.name}`
            : "Checking embedding status..."}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {quota && (
            <span
              className={`rounded border px-2 py-0.5 font-mono text-[11px] tabular-nums ${
                quotaBlocked
                  ? "border-amber-500/30 bg-amber-950/20 text-amber-300"
                  : "border-zinc-800 bg-[#09090b] text-zinc-400"
              }`}
              title={`Rolling ${quota.window_days}-day limit`}
            >
              Quota ({quota.window_days}d): {quota.chats_used}/{quota.chats_limit} chats · {quota.words_used}/{quota.words_limit} words
            </span>
          )}
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
        </div>
      </section>

      {quotaBlocked && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 px-4 py-3 text-xs text-amber-200">
          7-day AI assistant limit reached ({quota.chats_used}/{quota.chats_limit} chats, {quota.words_used}/{quota.words_limit} words).{" "}
          {quota.reset_at
            ? `Next slot unlocks on ${new Date(quota.reset_at).toLocaleString()}.`
            : "Please wait 7 days for your quota to reset."}
        </div>
      )}

      <section className="flex min-h-[500px] flex-col justify-between rounded-lg border border-zinc-800/80 bg-[#0b0b0e]">
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {messages.length === 0 ? (
            <div className="flex h-80 flex-col items-center justify-center text-center">
              <p className="text-sm font-medium text-zinc-200">
                Ask about {selectedRepo.owner}/{selectedRepo.name}
              </p>
              <p className="mt-1.5 max-w-md text-xs leading-relaxed text-zinc-500">
                Answers are grounded in retrieved code chunks from pgvector and streamed live from Gemini with exact file and line citations.
              </p>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`rounded-md border p-4 text-xs ${
                  msg.role === "user"
                    ? "ml-auto max-w-2xl border-zinc-700 bg-zinc-900 text-zinc-100"
                    : "max-w-4xl border-zinc-800/80 bg-[#09090b] text-zinc-200"
                }`}
              >
                <div className="mb-2 flex items-center justify-between gap-2 font-mono text-[11px] text-zinc-500">
                  <span className="font-medium uppercase tracking-wider">
                    {msg.role === "user" ? "You" : `RepoSense AI · ${msg.model || "Gemini"}`}
                  </span>
                  {msg.role === "assistant" && msg.sufficientContext === false && (
                    <span className="rounded border border-amber-500/30 bg-amber-950/20 px-1.5 py-0.5 text-[10px] text-amber-300">
                      Insufficient Context
                    </span>
                  )}
                </div>

                <div className="whitespace-pre-wrap leading-relaxed text-zinc-200">
                  {msg.text || (msg.streaming ? "Retrieving code context..." : "")}
                </div>

                {msg.references && msg.references.length > 0 && (
                  <div className="mt-3 border-t border-zinc-800/80 pt-2.5">
                    <p className="mb-1.5 text-[11px] font-medium text-zinc-500">Source References</p>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.references.map((ref) => (
                        <Link
                          key={ref.chunk_id}
                          to={`/explorer?file=${encodeURIComponent(ref.file_path)}&line=${ref.start_line}`}
                          className="rounded border border-zinc-800 bg-[#0b0b0e] px-2 py-0.5 font-mono text-[11px] text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white"
                        >
                          {ref.file_path}:L{ref.start_line}-{ref.end_line} ({(ref.similarity * 100).toFixed(0)}%)
                        </Link>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={handleAsk} className="flex flex-col gap-2.5 border-t border-zinc-800/80 p-4 sm:flex-row">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={
              quotaBlocked
                ? "7-day AI assistant limit reached..."
                : "Ask about architecture, functions, classes, or dependencies..."
            }
            disabled={asking || quotaBlocked}
            className="flex-1 rounded-md border border-zinc-800 bg-[#09090b] px-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:border-zinc-600 focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={asking || !ready || quotaBlocked}
            className="rounded-md bg-zinc-100 px-4 py-2 text-xs font-semibold text-zinc-950 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {asking ? "Streaming..." : "Ask"}
          </button>
        </form>
      </section>
    </div>
  );
}
