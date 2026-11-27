const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const ACCESS_TOKEN_KEY = "proofhire.access_token";
const REFRESH_TOKEN_KEY = "proofhire.refresh_token";

/** Dispatched on window when the session can no longer be renewed. */
export const SESSION_EXPIRED_EVENT = "proofhire:session-expired";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(ACCESS_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(REFRESH_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setTokens(accessToken: string, refreshToken: string): void {
  try {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  } catch {
    // localStorage unavailable (private browsing, etc.) — session won't persist.
  }
}

export function clearTokens(): void {
  try {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    // ignore
  }
}

export const TOKEN_STORAGE_KEYS = [ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY];

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/**
 * The user-facing message for a failed response. FastAPI errors are
 * `{"detail": "..."}` (or a list of validation errors); showing the raw body
 * put literal JSON in front of users.
 */
export async function errorFromResponse(response: Response): Promise<ApiError> {
  const body = await response.text();
  let message = body || response.statusText || `Request failed (${response.status})`;
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") message = parsed.detail;
    else if (Array.isArray(parsed.detail)) message = "Some of the values sent were invalid.";
  } catch {
    // not JSON — keep the text
  }
  return new ApiError(response.status, message);
}

let refreshing: Promise<boolean> | null = null;

/**
 * Trade the refresh token for a new pair. Single-flight: when several
 * requests hit 401 together (a page mounting five queries after the access
 * token expired), they share one refresh. That matters beyond efficiency —
 * the server rotates refresh tokens, so a second concurrent refresh would
 * present an already-spent token and end the session.
 */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) return false;
      const tokens = (await response.json()) as {
        access_token: string;
        refresh_token: string;
      };
      setTokens(tokens.access_token, tokens.refresh_token);
      return true;
    } catch {
      return false;
    }
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

function expireSession(): void {
  clearTokens();
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
}

/**
 * fetch with the bearer token, renewing the session once on a 401. Used by
 * the typed client, `apiFetch` and the SSE stream alike, so no call path can
 * forget to handle an expired access token (they last 30 minutes).
 */
export async function authFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const request = new Request(input, init);
  // Cloned before the first send: a request body can only be read once.
  const retry = request.clone();
  const token = getAccessToken();
  if (token) request.headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(request);
  if (response.status !== 401 || !token) return response;

  // Another request may have renewed the session while this one was in
  // flight; then the stored token is already new and no refresh is needed.
  const renewed = getAccessToken() !== token || (await refreshSession());
  if (renewed) {
    retry.headers.set("Authorization", `Bearer ${getAccessToken()}`);
    return fetch(retry);
  }
  expireSession();
  return response;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  // Let the browser set Content-Type (with the multipart boundary) for
  // FormData bodies — forcing application/json here would break file uploads.
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await authFetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  if (!response.ok) throw await errorFromResponse(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function apiBaseUrl(): string {
  return API_BASE_URL;
}
