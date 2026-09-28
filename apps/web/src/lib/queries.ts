"use client";

/**
 * Server state for the whole app: one query-key factory and a typed hook per
 * resource, all on the generated client (api-client.ts). Types come from the
 * OpenAPI document, so a backend response change is a compile error here.
 *
 * Keys are hierarchical so one invalidation covers related views: e.g.
 * invalidating `qk.documents.all` refreshes the list, every open document and
 * its claims.
 */

import { useQuery } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "./api-client";
import { toGraphView } from "./graph";
import { useSession } from "./session";

export type Job = Schemas["JobPublic"];
export type GeneratedDocument = Schemas["GeneratedDocumentPublic"];
export type GeneratedClaim = Schemas["GeneratedClaimPublic"];
export type Repository = Schemas["RepositoryPublic"];
export type Evidence = Schemas["EvidencePublic"];
export type Application = Schemas["ApplicationPublic"];
export type ProfileFact = Schemas["ProfileFactPublic"];
export type Overview = Schemas["OverviewResponse"];
export type { EvidenceGraph } from "./graph";

export const qk = {
  overview: ["overview"] as const,
  jobs: {
    all: ["jobs"] as const,
    detail: (id: string) => ["jobs", id] as const,
  },
  documents: {
    all: ["documents"] as const,
    detail: (id: string) => ["documents", id] as const,
    claims: (id: string) => ["documents", id, "claims"] as const,
  },
  repositories: ["repositories"] as const,
  evidence: {
    all: ["evidence"] as const,
    graph: (jobId: string | null) => ["evidence", "graph", jobId] as const,
  },
  applications: ["applications"] as const,
  facts: ["profile", "facts"] as const,
};

/** Every data hook waits for a session: without one there is nothing to fetch. */
function useAuthed() {
  return useSession().status === "authenticated";
}

/** Repository statuses that will still change without the user doing anything. */
export const REPOSITORY_BUSY = ["queued", "syncing", "extracting"];

export function useOverview() {
  return useQuery({
    queryKey: qk.overview,
    queryFn: async () => unwrap(await api.GET("/api/v1/me/overview")),
    enabled: useAuthed(),
    // Evidence arrives in the background after a sync; keep the counts live
    // until every repository has settled.
    refetchInterval: (query) =>
      (query.state.data?.repositories.in_progress ?? 0) > 0 ? 5000 : false,
  });
}

export function useJobs() {
  return useQuery({
    queryKey: qk.jobs.all,
    queryFn: async () => unwrap(await api.GET("/api/v1/jobs")),
    enabled: useAuthed(),
  });
}

/** Polls while the job is being analysed or matched, then stops. */
export function useJob(id: string) {
  return useQuery({
    queryKey: qk.jobs.detail(id),
    queryFn: async ({ signal }) =>
      unwrap(await api.GET("/api/v1/jobs/{job_id}", { params: { path: { job_id: id } }, signal })),
    enabled: useAuthed() && !!id,
    refetchInterval: (query) =>
      ["analyzing", "matching", "analyzed"].includes(query.state.data?.status ?? "") ? 2000 : false,
  });
}

export function useDocuments() {
  return useQuery({
    queryKey: qk.documents.all,
    queryFn: async () => unwrap(await api.GET("/api/v1/documents")),
    enabled: useAuthed(),
  });
}

export function useDocument(id: string | null) {
  return useQuery({
    queryKey: qk.documents.detail(id ?? ""),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/documents/{document_id}", {
          params: { path: { document_id: id! } },
        }),
      ),
    enabled: useAuthed() && !!id,
  });
}

export function useClaims(documentId: string | null) {
  return useQuery({
    queryKey: qk.documents.claims(documentId ?? ""),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/documents/{document_id}/claims", {
          params: { path: { document_id: documentId! } },
        }),
      ),
    enabled: useAuthed() && !!documentId,
  });
}

export function useRepositories() {
  return useQuery({
    queryKey: qk.repositories,
    queryFn: async () => unwrap(await api.GET("/api/v1/github/repositories")),
    enabled: useAuthed(),
    refetchInterval: (query) =>
      query.state.data?.some((r) => REPOSITORY_BUSY.includes(r.sync_status)) ? 5000 : false,
  });
}

export function useEvidence() {
  return useQuery({
    queryKey: qk.evidence.all,
    queryFn: async () => unwrap(await api.GET("/api/v1/evidence")),
    enabled: useAuthed(),
  });
}

export function useEvidenceGraph(jobId: string | null) {
  return useQuery({
    queryKey: qk.evidence.graph(jobId),
    queryFn: async ({ signal }) =>
      toGraphView(
        unwrap(
          await api.GET("/api/v1/evidence/graph", {
            params: { query: jobId ? { job_id: jobId } : {} },
            signal,
          }),
        ),
      ),
    enabled: useAuthed(),
  });
}

export function useApplications() {
  return useQuery({
    queryKey: qk.applications,
    queryFn: async () => unwrap(await api.GET("/api/v1/applications")),
    enabled: useAuthed(),
  });
}

export function useProfileFacts() {
  return useQuery({
    queryKey: qk.facts,
    queryFn: async () => unwrap(await api.GET("/api/v1/profile/facts")),
    enabled: useAuthed(),
  });
}
