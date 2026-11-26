import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, clearApiCache, configureApiAuth } from "../api/client";
import { isSupabaseConfigured, supabase } from "../lib/supabase";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const tokenRef = useRef(null);

  const syncProfile = useCallback(async (activeSession) => {
    if (!activeSession?.access_token) {
      tokenRef.current = null;
      setProfile(null);
      return;
    }
    tokenRef.current = activeSession.access_token;
    try {
      const me = await api.getMe();
      setProfile(me);
      setAuthError("");
    } catch (err) {
      if (err?.status === 401) {
        tokenRef.current = null;
        setSession(null);
        setProfile(null);
        if (supabase) {
          await supabase.auth.signOut().catch(() => null);
        }
        setAuthError("Your session expired. Please sign in again.");
      } else {
        // Fallback to Supabase user metadata if backend is temporarily unreachable
        const meta = activeSession.user?.user_metadata || {};
        setProfile({
          id: activeSession.user?.id,
          email: activeSession.user?.email,
          display_name: meta.full_name || meta.name || activeSession.user?.email?.split("@")[0],
          avatar_url: meta.avatar_url || meta.picture || null,
          created_at: activeSession.user?.created_at,
        });
      }
    }
  }, []);

  const signOut = useCallback(async () => {
    setAuthError("");
    try {
      if (tokenRef.current) {
        await api.logoutBackend();
      }
      if (supabase) {
        await supabase.auth.signOut();
      }
    } finally {
      tokenRef.current = null;
      clearApiCache();
      localStorage.removeItem("reposense_selected_repo_id");
      setSession(null);
      setProfile(null);
    }
  }, []);

  useEffect(() => {
    configureApiAuth({
      tokenGetter: () => tokenRef.current,
      onUnauthorized: () => {
        tokenRef.current = null;
        clearApiCache();
        setSession(null);
        setProfile(null);
        setAuthError("Session expired. Please sign in with Google again.");
      },
    });
  }, []);

  useEffect(() => {
    if (!isSupabaseConfigured || !supabase) {
      setLoading(false);
      setAuthError("Supabase authentication is not configured in frontend/.env.");
      return;
    }

    let mounted = true;
    supabase.auth
      .getSession()
      .then(async ({ data, error }) => {
        if (!mounted) return;
        if (error) {
          setAuthError(error.message);
          setLoading(false);
          return;
        }
        const currentSession = data?.session || null;
        setSession(currentSession);
        await syncProfile(currentSession);
        if (mounted) setLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setAuthError(err?.message || "Failed to restore authentication session.");
        setLoading(false);
      });

    const { data: listener } = supabase.auth.onAuthStateChange(async (_event, nextSession) => {
      if (!mounted) return;
      setSession(nextSession || null);
      if (nextSession?.access_token) {
        await syncProfile(nextSession);
      } else {
        tokenRef.current = null;
        clearApiCache();
        setProfile(null);
      }
      if (mounted) setLoading(false);
    });

    return () => {
      mounted = false;
      listener?.subscription?.unsubscribe();
    };
  }, [syncProfile]);

  const signInWithGoogle = useCallback(async () => {
    if (!supabase) {
      setAuthError("Supabase client is not configured.");
      return;
    }
    setAuthError("");
    const redirectTo = `${window.location.origin}/auth/callback`;
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo,
        queryParams: {
          prompt: "select_account",
        },
      },
    });
    if (error) {
      setAuthError(error.message || "Google sign-in failed.");
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        session,
        user: profile,
        isAuthenticated: Boolean(session?.access_token),
        isConfigured: isSupabaseConfigured,
        loading,
        authError,
        setAuthError,
        signInWithGoogle,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
