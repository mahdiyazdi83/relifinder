import ELK from "elkjs/lib/elk.bundled.js";

import type { ErdRelationshipEdge, ErdTableNode } from "./erd-types";

const elk = new ELK();

export async function layoutErdGraph(
  nodes: ErdTableNode[],
  edges: ErdRelationshipEdge[],
): Promise<ErdTableNode[]> {
  if (nodes.length === 0) return [];
  const result = await elk.layout({
    id: "relifinder-erd",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.spacing.nodeNode": "64",
      "elk.layered.spacing.nodeNodeBetweenLayers": "150",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      "elk.randomSeed": "1",
    },
    children: nodes.map((node) => ({
      id: node.id,
      width: node.data.width,
      height: node.data.height,
    })),
    edges: edges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    })),
  });
  const positions = new Map(
    result.children?.map((node) => [node.id, { x: node.x ?? 0, y: node.y ?? 0 }]),
  );
  return nodes.map((node) => ({
    ...node,
    position: positions.get(node.id) ?? node.position,
  }));
}

export function fallbackGridLayout(nodes: ErdTableNode[]): ErdTableNode[] {
  const columns = Math.max(1, Math.ceil(Math.sqrt(nodes.length)));
  return nodes.map((node, index) => ({
    ...node,
    position: {
      x: (index % columns) * 340,
      y: Math.floor(index / columns) * 300,
    },
  }));
}
