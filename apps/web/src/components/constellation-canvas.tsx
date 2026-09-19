"use client";

import { useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { EvidenceGraph, GraphNode } from "@/lib/graph";
import { StatusPill } from "@proofhire/design-system/ui";

type ProofNode = Node<
  { item: GraphNode; inspect: (id: string) => void },
  "proof"
>;
function ProofNodeCard({ data }: NodeProps<ProofNode>) {
  const { item } = data;
  return (
    <div className={`ph-node ph-node-${item.kind}`}>
      <Handle type="target" position={Position.Left} />
      <button
        className="nodrag"
        onClick={() => data.inspect(item.id)}
        title={
          item.sources.map((s) => s.locator).join("\n") || item.description
        }
      >
        <span className="ph-eyebrow">{item.kind}</span>
        <strong>{item.label}</strong>
        {item.status && <StatusPill status={item.status} />}
        {item.sources[0] && (
          <span className="ph-node-source">{item.sources[0].locator}</span>
        )}
      </button>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
const nodeTypes = { proof: ProofNodeCard };
const columns = {
  project: 0,
  evidence: 1,
  architecture: 1,
  skill: 2,
  requirement: 3,
};

export default function ConstellationCanvas({
  graph,
  selected,
  onSelect,
  reducedMotion,
}: {
  graph: EvidenceGraph;
  selected: string | null;
  onSelect: (id: string) => void;
  reducedMotion: boolean;
}) {
  const nodes = useMemo<ProofNode[]>(() => {
    const counts = [0, 0, 0, 0];
    return graph.nodes.map((item) => {
      const col = columns[item.kind];
      const row = counts[col] ?? 0;
      counts[col] = row + 1;
      return {
        id: item.id,
        type: "proof",
        data: { item, inspect: onSelect },
        position: { x: col * 330, y: row * 210 + (col % 2) * 35 },
        selected: item.id === selected,
        ariaLabel: `${item.kind}: ${item.label}, ${item.status ?? ""}`,
        className: item.kind === "requirement" ? "ph-requirement-enter" : "",
      };
    });
  }, [graph.nodes, onSelect, selected]);
  const edges = useMemo(() => {
    const matchedEvidence = new Set(
      graph.edges
        .filter(
          (e) =>
            e.kind === "matches" &&
            ["strong", "partial"].includes(e.status ?? ""),
        )
        .map((e) => e.source),
    );
    return graph.edges.map((edge) => {
      const lit =
        (edge.kind === "matches" &&
          ["strong", "partial"].includes(edge.status ?? "")) ||
        matchedEvidence.has(edge.target) ||
        matchedEvidence.has(edge.source);
      const status = edge.status ?? (lit ? "strong" : "unknown");
      return {
        ...edge,
        label: edge.kind === "matches" ? (edge.status ?? undefined) : undefined,
        animated: false,
        className: lit && !reducedMotion ? "ph-lit-edge" : "",
        style: {
          stroke: `var(--ph-${status})`,
          strokeWidth: 1 + edge.weight * 2,
          opacity: lit ? 1 : 0.45,
          strokeDasharray:
            status === "partial" || status === "unknown" ? "5 5" : undefined,
        },
        ariaLabel: `${edge.kind}: ${edge.status ?? ""} ${edge.explanation}`,
      };
    });
  }, [graph.edges, reducedMotion]);
  return (
    <div
      className="ph-canvas"
      aria-label="Evidence constellation. Use the table view for a complete text alternative."
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.15}
        maxZoom={1.5}
        nodesDraggable={false}
        nodesConnectable={false}
        edgesReconnectable={false}
        deleteKeyCode={null}
        onNodeClick={(_, node) => onSelect(node.id)}
        onlyRenderVisibleElements
      >
        <Background gap={24} size={1} color="var(--ph-line)" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
