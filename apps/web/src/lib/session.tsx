"use client";

/**
 * Who is signed in, for the whole app. Every data hook in queries.ts waits on
 * `status === "authenticated"`, so pages no longer each read localStorage and
 * guess (they used to, independently, and all said "Log in on Home").
 *
 * - Tokens stay in localStorage (bearer auth; ADR-0017 on why that makes
 *   CSRF inapplicable). They are read after mount so the first client render
 *   matches the server's (the hydration bug fixed in 3bae63d).
 * - `/auth/me` is the source of truth for the user and for `isDemo`.
 * - A session that can't be renewed ends visibly (`expired`), not silently.
 * - Sign-out revokes both tokens server-side before forgetting them.
 * - Other tabs follow along through the `storage` event.
 * - An unreachable API (a free-tier backend waking from sleep) is its own
 *   state, retried with backoff, rather than being mistaken for signed-out.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "./api-client";
import {
  ApiError,
  SESSION_EXPIRED_EVENT,
  TOKEN_STORAGE_KEYS,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "./api";

export type User = Schemas["UserPublic"];
type Tokens = { access_token: string; refresh_token: string };
export type SessionStatus = "loading" | "anonymous" | "authenticated" | "unreachable";

type SessionValue = {
  status: SessionStatus;
  user: User | null;
  isDemo: boolean;
  /** False for the read-only demo account: disable writes up front. */
  canWrite: boolean;
  expired: boolean;
  signIn: (tokens: Tokens) => void;
  signOut: () => Promise<void>;
  startDemo: () => Promise<void>;
  dismissExpired: () => void;
  retry: () => void;
};

const SessionContext = createContext<SessionValue | null>(null);

export const ME_KEY = ["me"] as const;

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  // null until mounted: the server can't know, and must render like the client's first pass.
  const [hasToken, setHasToken] = useState<boolean | null>(null);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    setHasToken(!!getAccessToken());
    const onExpired = () => {
      setExpired(true);
      setHasToken(false);
      queryClient.clear();
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key !== null && !TOKEN_STORAGE_KEYS.includes(event.key)) return;
      const signedIn = !!getAccessToken();
      setHasToken(signedIn);
      queryClient.clear();
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
      window.removeEventListener("storage", onStorage);
    };
  }, [queryClient]);

  const me = useQuery({
    queryKey: ME_KEY,
    queryFn: async () => unwrap(await api.GET("/api/v1/auth/me")),
    enabled: hasToken === true,
    staleTime: 5 * 60_000,
    // 401s are handled by authFetch (refresh, else expire). Anything else is
    // the API being unreachable — retry with backoff while it wakes up.
    retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 8,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 15_000),
  });

  const signIn = useCallback(
    (tokens: Tokens) => {
      setTokens(tokens.access_token, tokens.refresh_token);
      queryClient.clear(); // nothing from a previous account may survive
      setExpired(false);
      setHasToken(true);
    },
    [queryClient],
  );

  const signOut = useCallback(async () => {
    const refreshToken = getRefreshToken();
    try {
      await api.POST("/api/v1/auth/logout", { body: { refresh_token: refreshToken } });
    } catch {
      // Already expired or unreachable: forgetting the tokens is still right.
    }
    clearTokens();
    setHasToken(false);
    queryClient.clear();
  }, [queryClient]);

  const startDemo = useCallback(async () => {
    signIn(unwrap(await api.POST("/api/v1/demo/session")));
  }, [signIn]);

  const value = useMemo<SessionValue>(() => {
    let status: SessionStatus;
    if (hasToken === null) status = "loading";
    else if (!hasToken) status = "anonymous";
    else if (me.data) status = "authenticated";
    // failureCount, not just isError: the query stays "pending" through its
    // retries, which would leave a cold-starting API looking like a hung page.
    else if (me.isError || me.failureCount > 0) status = "unreachable";
    else status = "loading";
    const user = status === "authenticated" ? (me.data ?? null) : null;
    return {
      status,
      user,
      isDemo: !!user?.is_demo,
      canWrite: !!user && !user.is_demo,
      expired,
      signIn,
      signOut,
      startDemo,
      dismissExpired: () => setExpired(false),
      retry: () => void me.refetch(),
    };
  }, [hasToken, me, expired, signIn, signOut, startDemo]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside <SessionProvider>");
  return value;
}
