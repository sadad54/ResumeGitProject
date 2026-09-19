/**
 * Typed API client, generated from the FastAPI OpenAPI document (checklist
 * §9 / §11 "generated typed API client").
 *
 * `src/lib/api-types.generated.ts` is produced by `npm run generate:api` from
 * `docs/api/openapi.json`, which is itself exported from the running app by
 * `apps/api/scripts/export_openapi.py`. CI runs `check:api-types`, so a backend
 * change to a response shape fails the build here instead of at runtime.
 *
 * This wraps openapi-fetch with the same auth behavior as the hand-written
 * `apiFetch` (bearer token from localStorage, JSON by default, FormData left
 * alone) so the two can coexist while call sites migrate. New code should use
 * `api.GET("/api/v1/jobs")` and get path, query, body and response types for
 * free; `apiFetch` remains for the SSE stream and file uploads.
 */

import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./api-types.generated";
import { ApiError, apiBaseUrl, getAccessToken } from "./api";

const auth: Middleware = {
  async onRequest({ request }) {
    const token = getAccessToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
  async onResponse({ response }) {
    if (!response.ok) {
      const body = await response.clone().text();
      throw new ApiError(response.status, body || response.statusText);
    }
    return response;
  },
};

export const api = createClient<paths>({ baseUrl: apiBaseUrl() });
api.use(auth);

export type { components, operations, paths } from "./api-types.generated";
