const API_ROOT = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");
const API_BASE = `${API_ROOT}/api`;

export class ApiError extends Error {
  constructor(message, status, code = "api_error") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

let getAccessToken = () => null;
let onUnauthorizedHandler = null;

const inflightRequests = new Map();
const getCache = new Map();
const CACHE_TTL_MS = 30_000;

export function configureApiAuth({ tokenGetter, onUnauthorized }) {
  getAccessToken = tokenGetter || (() => null);
  onUnauthorizedHandler = onUnauthorized || null;
}

export function clearApiCache() {
  getCache.clear();
  inflightRequests.clear();
}

function buildHeaders(customHeaders = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...customHeaders,
  };
  const token = getAccessToken?.();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function apiRequest(path, options = {}, { cacheable = false } = {}) {
  const method = (options.method || "GET").toUpperCase();
  const cacheKey = `${method}:${path}`;

  if (method === "GET" && cacheable) {
    const cached = getCache.get(cacheKey);
    if (cached && Date.now() < cached.expiresAt) {
      return cached.data;
    }
    if (inflightRequests.has(cacheKey)) {
      return inflightRequests.get(cacheKey);
    }
  }

  const runFetch = async () => {
    const config = {
      ...options,
      headers: buildHeaders(options.headers),
    };

    let response;
    try {
      response = await fetch(`${API_BASE}${path}`, config);
    } catch {
      throw new ApiError(
        "Unable to reach the backend server. Ensure FastAPI is running on port 8000.",
        0,
        "network_error"
      );
    }

    if (response.status === 204) {
      return null;
    }

    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (!response.ok) {
      if (response.status === 401 && onUnauthorizedHandler) {
        onUnauthorizedHandler();
      }
      const message = data?.error?.message || data?.detail || `Request failed with status ${response.status}.`;
      const code = data?.error?.code || "http_error";
      throw new ApiError(message, response.status, code);
    }

    if (method === "GET" && cacheable) {
      getCache.set(cacheKey, { data, expiresAt: Date.now() + CACHE_TTL_MS });
    } else if (method !== "GET") {
      getCache.clear();
    }

    return data;
  };

  if (method === "GET" && cacheable) {
    const promise = runFetch().finally(() => {
      inflightRequests.delete(cacheKey);
    });
    inflightRequests.set(cacheKey, promise);
    return promise;
  }

  return runFetch();
}

export const api = {
  checkHealth: () => apiRequest("/health", {}, { cacheable: true }),
  checkDbHealth: () => apiRequest("/health/db", {}, { cacheable: true }),

  getMe: () => apiRequest("/auth/me"),
  logoutBackend: () =>
    apiRequest("/auth/logout", {
      method: "POST",
    }).catch(() => null),

  listRepositories: () => apiRequest("/repositories?limit=50", {}, { cacheable: true }),
  createRepository: (githubUrl) =>
    apiRequest("/repositories", {
      method: "POST",
      body: JSON.stringify({ github_url: githubUrl }),
    }),
  getRepository: (id) => apiRequest(`/repositories/${id}`, {}, { cacheable: true }),
  deleteRepository: (id) =>
    apiRequest(`/repositories/${id}`, {
      method: "DELETE",
    }),

  analyzeRepository: (id) =>
    apiRequest(`/repositories/${id}/analyze`, {
      method: "POST",
    }),
  getAnalysisStatus: (id) => apiRequest(`/repositories/${id}/status`),
  getRepositoryFiles: (id, { language, limit = 500 } = {}) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (language) params.set("language", language);
    return apiRequest(`/repositories/${id}/files?${params.toString()}`, {}, { cacheable: true });
  },
  getRepositoryFile: (id, fileId) => apiRequest(`/repositories/${id}/files/${fileId}`, {}, { cacheable: true }),
  getRepositoryAnalysis: (id) => apiRequest(`/repositories/${id}/analysis`, {}, { cacheable: true }),
  getRepositoryDependencies: (id) => apiRequest(`/repositories/${id}/dependencies`, {}, { cacheable: true }),

  generateEmbeddings: (id) =>
    apiRequest(`/repositories/${id}/embeddings`, {
      method: "POST",
    }),
  getEmbeddingStatus: (id) => apiRequest(`/repositories/${id}/embeddings/status`, {}, { cacheable: true }),
  searchRepository: (id, query, topK = 5) =>
    apiRequest(`/repositories/${id}/search`, {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK }),
    }),
  askAssistant: (id, question, topK = 5) =>
    apiRequest(`/repositories/${id}/ask`, {
      method: "POST",
      body: JSON.stringify({ question, top_k: topK }),
    }),

  async askAssistantStream(id, question, topK = 5, { onMetadata, onDelta, onDone, onError } = {}) {
    let response;
    try {
      response = await fetch(`${API_BASE}/repositories/${id}/ask/stream`, {
        method: "POST",
        headers: buildHeaders(),
        body: JSON.stringify({ question, top_k: topK }),
      });
    } catch {
      throw new ApiError(
        "Unable to reach the backend server. Ensure FastAPI is running on port 8000.",
        0,
        "network_error"
      );
    }

    if (!response.ok) {
      if (response.status === 401 && onUnauthorizedHandler) {
        onUnauthorizedHandler();
      }
      let errData = null;
      try {
        errData = await response.json();
      } catch {
        errData = null;
      }
      throw new ApiError(
        errData?.error?.message || errData?.detail || `Stream request failed (${response.status}).`,
        response.status,
        errData?.error?.code || "http_error"
      );
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const evt of events) {
        const line = evt
          .split("\n")
          .find((l) => l.startsWith("data:"));
        if (!line) continue;
        const jsonText = line.slice(5).trim();
        if (!jsonText) continue;

        let parsed;
        try {
          parsed = JSON.parse(jsonText);
        } catch {
          continue;
        }

        if (parsed.type === "metadata") {
          onMetadata?.(parsed);
        } else if (parsed.type === "delta") {
          onDelta?.(parsed.text || "");
        } else if (parsed.type === "error") {
          onError?.(parsed.message || "Streaming error.");
        } else if (parsed.type === "done") {
          onDone?.();
        }
      }
    }
  },
};
