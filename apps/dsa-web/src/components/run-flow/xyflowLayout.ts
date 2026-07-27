import dagre from '@dagrejs/dagre';
import type { Node, Edge } from '@xyflow/react';

const NODE_WIDTH = 200; const NODE_HEIGHT = 90;
const H_SPACING = 80; const V_SPACING = 40;

interface LayoutResult { xyNodes: Node[]; xyEdges: Edge[] }

export function layoutDagreLR(nodes: Node[], edges: Edge[]): LayoutResult {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'LR', nodesep: V_SPACING, ranksep: H_SPACING, marginx: 30, marginy: 30 });
  for (const node of nodes) g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  for (const edge of edges) g.setEdge(edge.source, edge.target);
  dagre.layout(g);
  const positionedNodes = nodes.map((node) => {
    const dn = g.node(node.id);
    return dn ? { ...node, position: { x: dn.x - NODE_WIDTH / 2, y: dn.y - NODE_HEIGHT / 2 } } : node;
  });
  return { xyNodes: positionedNodes, xyEdges: edges };
}

export function layoutDagreTB(nodes: Node[], edges: Edge[]): LayoutResult {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 50, ranksep: 80, marginx: 30, marginy: 30 });
  for (const node of nodes) g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  for (const edge of edges) g.setEdge(edge.source, edge.target);
  dagre.layout(g);
  const positionedNodes = nodes.map((node) => {
    const dn = g.node(node.id);
    return dn ? { ...node, position: { x: dn.x - NODE_WIDTH / 2, y: dn.y - NODE_HEIGHT / 2 } } : node;
  });
  return { xyNodes: positionedNodes, xyEdges: edges };
}
