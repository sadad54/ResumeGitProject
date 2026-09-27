/**
 * Typed API client, generated from the FastAPI OpenAPI document (checklist
 * §9 / §11 "generated typed API client").
 *
 * `src/lib/api-types.generated.ts` is produced by `npm run generate:api` from
 * `docs/api/openapi.json`, which is itself exported from the app by
 * `apps/api/scripts/export_openapi.py`. CI runs `check:api-types`, and every
 * call goes through this client, so a backend change to a path, parameter or
 * response shape fails `npm run typecheck` here instead of surfacing as
 * `undefined` at runtime.
 *
 * Requests go through `authFetch`, which attaches the bearer token and
 * renews an expired session once, transparently. Non-2xx responses throw
 * `ApiError` with the server's `detail` message, so callers (TanStack Query
 * hooks in queries.ts) only ever see data or an error.
 */

import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./api-types.generated";
import { apiBaseUrl, authFetch, errorFromResponse } from "./api";

const throwOnError: Middleware = {
  async onResponse({ response }) {
    if (!response.ok) throw await errorFromResponse(response.clone());
    return response;
  },
};

export const api = createClient<paths>({ baseUrl: apiBaseUrl(), fetch: authFetch });
api.use(throwOnError);

/** openapi-fetch returns `{ data?, error? }`; the middleware already threw on
 * error, so this narrows `data` for callers. */
export function unwrap<T>(result: { data?: T }): T {
  return result.data as T;
}

export type Schemas = components["schemas"];
export type { components, operations, paths } from "./api-types.generated";
