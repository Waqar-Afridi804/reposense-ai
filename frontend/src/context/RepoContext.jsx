import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "./AuthContext";

const RepoContext = createContext(null);
const STORAGE_KEY = "reposense_selected_repo_id";

export function RepoProvider({ children }) {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [repositories, setRepositories] = useState([]);
  const [selectedRepoId, setSelectedRepoId] = useState(() => localStorage.getItem(STORAGE_KEY) || "");
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [repoError, setRepoError] = useState("");

  const selectRepository = useCallback((id) => {
    setSelectedRepoId(id || "");
    if (id) {
      localStorage.setItem(STORAGE_KEY, id);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const refreshRepositories = useCallback(async () => {
    if (!isAuthenticated) {
      setRepositories([]);
      setLoadingRepos(false);
      return;
    }
    setLoadingRepos(true);
    setRepoError("");
    try {
      const data = await api.listRepositories();
      const items = data?.items || [];
      setRepositories(items);

      setSelectedRepoId((currentId) => {
        if (currentId && items.some((r) => r.id === currentId)) {
          return currentId;
        }
        const fallback = items[0]?.id || "";
        if (fallback) {
          localStorage.setItem(STORAGE_KEY, fallback);
        } else {
          localStorage.removeItem(STORAGE_KEY);
        }
        return fallback;
      });
    } catch (err) {
      setRepoError(err.message || "Failed to load repositories.");
    } finally {
      setLoadingRepos(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (authLoading) return;
    if (isAuthenticated) {
      refreshRepositories();
    } else {
      setRepositories([]);
      setSelectedRepoId("");
      setRepoError("");
      setLoadingRepos(false);
    }
  }, [authLoading, isAuthenticated, refreshRepositories]);

  const selectedRepo = repositories.find((r) => r.id === selectedRepoId) || null;

  return (
    <RepoContext.Provider
      value={{
        repositories,
        selectedRepoId,
        selectedRepo,
        loadingRepos,
        repoError,
        selectRepository,
        refreshRepositories,
      }}
    >
      {children}
    </RepoContext.Provider>
  );
}

export function useRepo() {
  const ctx = useContext(RepoContext);
  if (!ctx) {
    throw new Error("useRepo must be used inside RepoProvider");
  }
  return ctx;
}
