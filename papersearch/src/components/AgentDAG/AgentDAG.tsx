import { useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import AgentNode from './AgentNode';
import AgentLegend from './AgentLegend';
import { AGENTS_INFO } from '../../types';

const nodeTypes = { agentNode: AgentNode };

function AgentDAG() {
  const nodes: Node[] = useMemo(() => [
    {
      id: 'agent1',
      type: 'agentNode',
      position: { x: 60, y: 20 },
      data: {
        agentId: 'agent1',
        name: AGENTS_INFO[0].name,
        role: AGENTS_INFO[0].role,
        emoji: AGENTS_INFO[0].emoji,
        color: AGENTS_INFO[0].color,
      },
    },
    {
      id: 'agent2',
      type: 'agentNode',
      position: { x: 0, y: 160 },
      data: {
        agentId: 'agent2',
        name: AGENTS_INFO[1].name,
        role: AGENTS_INFO[1].role,
        emoji: AGENTS_INFO[1].emoji,
        color: AGENTS_INFO[1].color,
      },
    },
    {
      id: 'agent3',
      type: 'agentNode',
      position: { x: 60, y: 300 },
      data: {
        agentId: 'agent3',
        name: AGENTS_INFO[2].name,
        role: AGENTS_INFO[2].role,
        emoji: AGENTS_INFO[2].emoji,
        color: AGENTS_INFO[2].color,
      },
    },
    {
      id: 'agent6',
      type: 'agentNode',
      position: { x: 120, y: 160 },
      data: {
        agentId: 'agent6',
        name: AGENTS_INFO[5].name,
        role: AGENTS_INFO[5].role,
        emoji: AGENTS_INFO[5].emoji,
        color: AGENTS_INFO[5].color,
      },
    },
    {
      id: 'agent4',
      type: 'agentNode',
      position: { x: 0, y: 440 },
      data: {
        agentId: 'agent4',
        name: AGENTS_INFO[3].name,
        role: AGENTS_INFO[3].role,
        emoji: AGENTS_INFO[3].emoji,
        color: AGENTS_INFO[3].color,
      },
    },
    {
      id: 'agent5',
      type: 'agentNode',
      position: { x: 60, y: 580 },
      data: {
        agentId: 'agent5',
        name: AGENTS_INFO[4].name,
        role: AGENTS_INFO[4].role,
        emoji: AGENTS_INFO[4].emoji,
        color: AGENTS_INFO[4].color,
      },
    },
  ], []);

  const edges: Edge[] = useMemo(() => [
    // agent1 -> agent2
    { id: 'e1-2', source: 'agent1', target: 'agent2', animated: false, style: { stroke: 'rgba(255,255,255,0.2)' } },
    // agent1 -> agent3
    { id: 'e1-3', source: 'agent1', target: 'agent3', animated: false, style: { stroke: 'rgba(255,255,255,0.2)' } },
    // agent1 -> agent6
    { id: 'e1-6', source: 'agent1', target: 'agent6', animated: false, style: { stroke: 'rgba(255,255,255,0.2)' } },
    // agent2 -> agent3
    { id: 'e2-3', source: 'agent2', target: 'agent3', animated: false, style: { stroke: 'rgba(255,255,255,0.2)' } },
    // agent3 -> agent4
    { id: 'e3-4', source: 'agent3', target: 'agent4', animated: false, style: { stroke: 'rgba(255,255,255,0.2)' } },
    // agent3 -> agent6
    { id: 'e3-6', source: 'agent3', target: 'agent6', animated: false, style: { stroke: 'rgba(255,255,255,0.2)' } },
    // agent4 -> agent5
    { id: 'e4-5', source: 'agent4', target: 'agent5', animated: false, style: { stroke: 'rgba(255,255,255,0.2)' } },
    // agent5 -> agent6
    { id: 'e5-6', source: 'agent5', target: 'agent6', animated: false, style: { stroke: 'rgba(255,255,255,0.2)' } },
  ], []);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 min-h-0">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="rgba(255,255,255,0.04)" gap={20} />
          <Controls className="!bg-[var(--card)] !border-[var(--border)] !fill-[var(--text)]" />
        </ReactFlow>
      </div>
      <AgentLegend />
    </div>
  );
}

export default AgentDAG;
