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
