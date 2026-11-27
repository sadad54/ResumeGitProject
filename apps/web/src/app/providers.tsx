"use client";

import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";
import { SessionProvider } from "@/lib/session";

let browserQueryClient: QueryClient | undefined;

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // A 4xx won't change on retry (and 401 is already handled by
        // authFetch); network errors and 5xx get two more attempts.
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      },
    },
  });
}

// One client per server render, one reused in the browser (Next.js
// TanStack Query guide, node_modules/next/dist/docs).
function getQueryClient() {
  if (typeof window === "undefined") return makeQueryClient();
  browserQueryClient ??= makeQueryClient();
  return browserQueryClient;
}

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={getQueryClient()}>
      <SessionProvider>{children}</SessionProvider>
    </QueryClientProvider>
  );
}
