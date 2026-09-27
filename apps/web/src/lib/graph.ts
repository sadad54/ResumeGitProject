export type GraphSource = {
  locator: string;
  url: string;
  commit_sha: string;
  line_start: number | null;
  line_end: number | null;
};
export type GraphNode = {
  id: string;
  kind: "project" | "skill" | "architecture" | "evidence" | "requirement";
  label: string;
  description: string;
  status: string | null;
  confidence: number | null;
  repository_id: string | null;
  evidence_id: string | null;
  required: boolean | null;
  sources: GraphSource[];
};
export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  kind: "contains" | "demonstrates" | "matches";
  weight: number;
  status: string | null;
  explanation: string;
};
export type EvidenceGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  job_id: string | null;
  job_status: string | null;
  truncated: boolean;
  evidence_limit: number;
};

const NODE_KINDS: readonly GraphNode["kind"][] = [
  "project",
  "skill",
  "architecture",
  "evidence",
  "requirement",
];
const EDGE_KINDS: readonly GraphEdge["kind"][] = ["contains", "demonstrates", "matches"];

/** The API's response type, generated from OpenAPI (looser: optional fields,
 * `kind` as plain string). Declared structurally here so this module stays
 * free of the client import. */
type ApiGraph = {
  nodes: {
    id: string;
    kind: string;
    label: string;
    description?: string;
    status?: string | null;
    confidence?: number | null;
    repository_id?: string | null;
    evidence_id?: string | null;
    required?: boolean | null;
    sources?: {
      locator: string;
      url: string;
      commit_sha: string;
      line_start?: number | null;
      line_end?: number | null;
    }[];
  }[];
  edges: {
    id: string;
    source: string;
    target: string;
    kind: string;
    weight: number;
    status?: string | null;
    explanation?: string;
  }[];
  job_id?: string | null;
  job_status?: string | null;
  truncated?: boolean;
  evidence_limit: number;
};

/**
 * Normalize the API response into the view model the canvas renders. The
 * boundary is typed by the generated schema; everything past it can rely on
 * defaults being filled. An unknown node kind (a newer API) renders as plain
 * evidence rather than breaking the canvas.
 */
export function toGraphView(api: ApiGraph): EvidenceGraph {
  return {
    nodes: api.nodes.map((n) => ({
      id: n.id,
      kind: NODE_KINDS.includes(n.kind as GraphNode["kind"])
        ? (n.kind as GraphNode["kind"])
        : "evidence",
      label: n.label,
      description: n.description ?? "",
      status: n.status ?? null,
      confidence: n.confidence ?? null,
      repository_id: n.repository_id ?? null,
      evidence_id: n.evidence_id ?? null,
      required: n.required ?? null,
      sources: (n.sources ?? []).map((s) => ({
        locator: s.locator,
        url: s.url,
        commit_sha: s.commit_sha,
        line_start: s.line_start ?? null,
        line_end: s.line_end ?? null,
      })),
    })),
    edges: api.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      kind: EDGE_KINDS.includes(e.kind as GraphEdge["kind"])
        ? (e.kind as GraphEdge["kind"])
        : "contains",
      weight: e.weight,
      status: e.status ?? null,
      explanation: e.explanation ?? "",
    })),
    job_id: api.job_id ?? null,
    job_status: api.job_status ?? null,
    truncated: api.truncated ?? false,
    evidence_limit: api.evidence_limit,
  };
}
