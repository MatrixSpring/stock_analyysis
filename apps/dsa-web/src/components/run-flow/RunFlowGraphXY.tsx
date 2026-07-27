/**
 * RunFlowGraphXY — @xyflow/react v12 + @dagrejs/dagre
 * 双模式：view(查看SSE实时拓扑) / edit(拖拽连线自定义DAG)
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ReactFlow, Background, Controls, MiniMap,
  useNodesState, useEdgesState, MarkerType,
  BackgroundVariant, Panel, type Node, type Edge, type Connection,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { layoutDagreLR } from './xyflowLayout';
import type { RunFlowEdge, RunFlowNode, RunFlowStatus } from '../../types/runFlow';

const STATUS_BORDER: Record<RunFlowStatus, string> = {
  success: '#10B981', failed: '#EF4444', degraded: '#F59E0B', fallback: '#F59E0B',
  timeout: '#EF4444', running: '#3B82F6', pending: '#6B7280', skipped: '#6B7280',
  cancelled: '#6B7280', cancel_requested: '#6B7280', unknown: '#6B7280',
};

interface RunFlowGraphXYProps {
  nodes: RunFlowNode[];
  edges: RunFlowEdge[];
  onSelectNode?: (node: RunFlowNode) => void;
  editable?: boolean;
  onSaveDag?: (nodes: RunFlowNode[], edges: RunFlowEdge[]) => void;
}

const RunFlowGraphXY: React.FC<RunFlowGraphXYProps> = ({
  nodes: rawNodes, edges: rawEdges,
  onSelectNode, editable = false, onSaveDag,
}) => {
  const [mode, setMode] = useState<'view' | 'edit'>(editable ? 'edit' : 'view');

  const { xyNodes: initialNodes, xyEdges: initialEdges } = useMemo(() => {
    const xyNodeList: Node[] = rawNodes.map((n) => ({
      id: n.id, type: 'default', position: { x: 0, y: 0 },
      data: { label: n.label, kind: n.kind, status: n.status, provider: n.provider, durationMs: n.durationMs, message: n.message, lane: n.lane, id: n.id },
    }));
    const xyEdgeList: Edge[] = rawEdges.map((e) => ({
      id: e.id, source: e.from, target: e.to, label: e.label || e.kind,
      animated: e.status === 'running',
      style: { stroke: STATUS_BORDER[e.status] || '#6B7280', strokeWidth: e.status === 'running' ? 2 : 1.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color: STATUS_BORDER[e.status] || '#6B7280' },
    }));
    return layoutDagreLR(xyNodeList, xyEdgeList);
  }, [rawNodes, rawEdges]);

  const [xyNodes, setXyNodes, onNodesChange] = useNodesState(initialNodes);
  const [xyEdges, setXyEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => { setXyNodes(initialNodes); setXyEdges(initialEdges); }, [initialNodes, initialEdges, setXyNodes, setXyEdges]);

  const onConnect = useCallback((connection: Connection) => {
    if (mode !== 'edit') return;
    setXyEdges((eds) => [...eds, {
      id: `edge-${connection.source}-${connection.target}`,
      source: connection.source!, target: connection.target!,
      markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#6B7280' },
    }]);
  }, [mode, setXyEdges]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    const original = rawNodes.find((n) => n.id === node.id);
    if (original && onSelectNode) onSelectNode(original);
  }, [rawNodes, onSelectNode]);

  return (
    <div style={{ width: '100%', height: 600, background: '#0f172a', borderRadius: 12 }}>
      <ReactFlow
        nodes={xyNodes} edges={xyEdges}
        onNodesChange={mode === 'edit' ? onNodesChange : undefined}
        onEdgesChange={mode === 'edit' ? onEdgesChange : undefined}
        onConnect={onConnect} onNodeClick={onNodeClick}
        fitView fitViewOptions={{ padding: 0.3 }}
        nodesDraggable={mode === 'edit'} nodesConnectable={mode === 'edit'}
        elementsSelectable={mode === 'edit'} minZoom={0.3} maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#334155" />
        <Controls style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
        <MiniMap style={{ background: '#1e293b', border: '1px solid #334155' }}
          nodeColor={(n: Node) => STATUS_BORDER[(n.data as any)?.status as RunFlowStatus] || '#6B7280'}
          maskColor="rgba(0,0,0,0.7)" />
        <Panel position="top-right">
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setMode(mode === 'view' ? 'edit' : 'view')}
              style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #334155', background: mode === 'edit' ? '#3B82F6' : '#1e293b', color: '#e2e8f0', cursor: 'pointer', fontSize: 13 }}>
              {mode === 'view' ? '✏️ 编辑' : '👁 查看'}
            </button>
            {mode === 'edit' && onSaveDag && (
              <button onClick={() => {
                const saved: RunFlowNode[] = xyNodes.map((n: Node) => ({
                  id: n.id, lane: (n.data as any)?.lane || '', kind: (n.data as any)?.kind || 'analysis',
                  label: (n.data as any)?.label || '', status: 'pending' as RunFlowStatus,
                }));
                const savedEdges: RunFlowEdge[] = xyEdges.map((e: Edge) => ({
                  id: e.id, from: e.source, to: e.target, kind: 'control' as const, status: 'pending' as RunFlowStatus,
                }));
                onSaveDag(saved, savedEdges);
              }} style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #10B981', background: '#065f46', color: '#e2e8f0', cursor: 'pointer', fontSize: 13 }}>
                💾 保存
              </button>
            )}
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
};

export default RunFlowGraphXY;
