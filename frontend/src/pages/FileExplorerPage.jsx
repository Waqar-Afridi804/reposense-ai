import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import Editor from "@monaco-editor/react";
import { api } from "../api/client";
import { EmptyRepoState, ErrorBanner, LoadingSpinner } from "../components/StatusAlert";
import { useRepo } from "../context/RepoContext";

function mapMonacoLanguage(ext, language) {
  const byExt = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".md": "markdown",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".sh": "shell",
    ".toml": "ini",
  };
  if (ext && byExt[ext]) return byExt[ext];
  if (language) return language.toLowerCase();
  return "plaintext";
}

export default function FileExplorerPage() {
  const { selectedRepo } = useRepo();
  const [searchParams] = useSearchParams();
  const requestedFilePath = searchParams.get("file") || "";
  const requestedLine = Number(searchParams.get("line")) || 1;

  const [files, setFiles] = useState([]);
  const [selectedFileId, setSelectedFileId] = useState("");
  const [fileDetail, setFileDetail] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loadingList, setLoadingList] = useState(false);
  const [loadingFile, setLoadingFile] = useState(false);
  const [error, setError] = useState("");
  const editorRef = useRef(null);

  useEffect(() => {
    if (!selectedRepo?.id) return;
    let active = true;
    setLoadingList(true);
    setError("");
    setFileDetail(null);
    setSelectedFileId("");

    api
      .getRepositoryFiles(selectedRepo.id, { limit: 500 })
      .then((res) => {
        if (!active) return;
        const items = res?.items || [];
        setFiles(items);
        if (items.length > 0) {
          const match = requestedFilePath
            ? items.find((f) => f.file_path === requestedFilePath)
            : null;
          setSelectedFileId((match || items[0]).id);
        }
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || "Failed to load repository files.");
      })
      .finally(() => {
        if (active) setLoadingList(false);
      });

    return () => {
      active = false;
    };
  }, [selectedRepo?.id, requestedFilePath]);

  useEffect(() => {
    if (!selectedRepo?.id || !selectedFileId) return;
    let active = true;
    setLoadingFile(true);
    setError("");

    api
      .getRepositoryFile(selectedRepo.id, selectedFileId)
      .then((detail) => {
        if (active) setFileDetail(detail);
      })
      .catch((err) => {
        if (active) setError(err.message || "Failed to load file contents.");
      })
      .finally(() => {
        if (active) setLoadingFile(false);
      });

    return () => {
      active = false;
    };
  }, [selectedRepo?.id, selectedFileId]);

  useEffect(() => {
    if (editorRef.current && fileDetail && requestedLine > 1 && fileDetail.file_path === requestedFilePath) {
      editorRef.current.revealLineInCenter(requestedLine);
      editorRef.current.setPosition({ lineNumber: requestedLine, column: 1 });
    }
  }, [fileDetail, requestedLine, requestedFilePath]);

  const filteredFiles = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return files;
    return files.filter((f) => f.file_path.toLowerCase().includes(q));
  }, [files, searchQuery]);

  if (!selectedRepo) {
    return <EmptyRepoState title="No repository selected" />;
  }

  return (
    <div className="space-y-4">
      <ErrorBanner message={error} />

      {loadingList ? (
        <LoadingSpinner label="Loading repository files..." />
      ) : files.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-800 bg-[#0b0b0e] p-8 text-center text-xs text-zinc-500">
          No analyzed files found for this repository. Run analysis on the Overview page first.
        </div>
      ) : (
        <div className="grid grid-cols-1 overflow-hidden rounded-lg border border-zinc-800/80 bg-[#0b0b0e] lg:grid-cols-12">
          {/* File Tree */}
          <section className="flex flex-col border-b border-zinc-800/80 p-3 lg:col-span-4 lg:border-b-0 lg:border-r">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter files..."
              className="mb-2.5 rounded-md border border-zinc-800 bg-[#09090b] px-2.5 py-1.5 font-mono text-xs text-zinc-100 placeholder-zinc-500 focus:border-zinc-600 focus:outline-none"
            />
            <p className="mb-2 px-1 font-mono text-[11px] text-zinc-500 tabular-nums">
              {filteredFiles.length} / {files.length} files
            </p>
            <div className="max-h-[560px] flex-1 space-y-0.5 overflow-y-auto pr-1">
              {filteredFiles.map((f) => {
                const active = f.id === selectedFileId;
                return (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setSelectedFileId(f.id)}
                    className={`flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-left text-xs transition-colors ${
                      active
                        ? "bg-zinc-800 text-white"
                        : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                    }`}
                  >
                    <span className="truncate font-mono text-[11px]" title={f.file_path}>
                      {f.file_path}
                    </span>
                    <span className="shrink-0 font-mono text-[10px] text-zinc-500 tabular-nums">
                      {f.line_count}L
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Monaco Code Viewer */}
          <section className="flex flex-col lg:col-span-8">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/80 px-4 py-2.5">
              <span className="truncate font-mono text-xs font-medium text-zinc-200">
                {fileDetail?.file_path || "Select a file"}
              </span>
              {fileDetail && (
                <span className="font-mono text-[11px] text-zinc-500 tabular-nums">
                  {fileDetail.language || "Text"} · {fileDetail.line_count} lines · {fileDetail.size_bytes} B
                </span>
              )}
            </div>

            <div className="h-[580px] w-full bg-[#09090b]">
              {loadingFile ? (
                <LoadingSpinner label="Loading file content..." />
              ) : fileDetail ? (
                <Editor
                  height="100%"
                  theme="vs-dark"
                  language={mapMonacoLanguage(fileDetail.extension, fileDetail.language)}
                  value={fileDetail.content || ""}
                  onMount={(editor) => {
                    editorRef.current = editor;
                    if (requestedLine > 1 && fileDetail.file_path === requestedFilePath) {
                      editor.revealLineInCenter(requestedLine);
                      editor.setPosition({ lineNumber: requestedLine, column: 1 });
                    }
                  }}
                  options={{
                    readOnly: true,
                    minimap: { enabled: false },
                    fontSize: 12.5,
                    fontFamily: "'JetBrains Mono', monospace",
                    lineNumbers: "on",
                    scrollBeyondLastLine: false,
                    wordWrap: "on",
                  }}
                />
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-zinc-500">
                  Select a file to inspect its source code.
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
