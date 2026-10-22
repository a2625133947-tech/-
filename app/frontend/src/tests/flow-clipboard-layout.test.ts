import { describe, it, expect } from 'vitest';
import { flowClipboard } from '../services/flow-clipboard';
import {
  calculateAutoLayout,
  alignSelectedNodes,
  distributeSelectedNodes,
} from '../services/flow-layout';
import { AppNode } from '../nodes/types';
import { Edge } from '@xyflow/react';

describe('Flow Clipboard Service', () => {
  it('correctly copies selected nodes and only internal edges', () => {
    const nodes: AppNode[] = [
      {
        id: 'node-a',
        type: 'agent-node',
        position: { x: 100, y: 100 },
        data: { name: 'Node A' },
        selected: true,
      } as any,
      {
        id: 'node-b',
        type: 'agent-node',
        position: { x: 400, y: 100 },
        data: { name: 'Node B' },
        selected: true,
      } as any,
      {
        id: 'node-c',
        type: 'agent-node',
        position: { x: 700, y: 100 },
        data: { name: 'Node C' },
        selected: false, // NOT selected
      } as any,
    ];

    const edges: Edge[] = [
      { id: 'e-ab', source: 'node-a', target: 'node-b' }, // Internal
      { id: 'e-bc', source: 'node-b', target: 'node-c' }, // External
    ];

    const copied = flowClipboard.copy(nodes, edges);
    expect(copied).toBe(true);
    expect(flowClipboard.hasContent()).toBe(true);

    const pasted = flowClipboard.paste(nodes, edges, 25);
    expect(pasted).not.toBeNull();
    if (!pasted) return;

    // Original 3 nodes + 2 new cloned nodes
    expect(pasted.newNodes.length).toBe(5);

    const newA = pasted.newNodes.find(n => (n.data as any).name === 'Node A' && n.id !== 'node-a');
    const newB = pasted.newNodes.find(n => (n.data as any).name === 'Node B' && n.id !== 'node-b');

    expect(newA).toBeDefined();
    expect(newB).toBeDefined();
    expect(newA!.id).not.toBe('node-a');
    expect(newB!.id).not.toBe('node-b');
    expect(newA!.position.x).toBe(125);
    expect(newB!.position.x).toBe(425);

    // Edges: original 2 + exactly 1 internal cloned edge
    expect(pasted.newEdges.length).toBe(3);
    const newEdge = pasted.newEdges.find(e => e.id !== 'e-ab' && e.id !== 'e-bc');
    expect(newEdge).toBeDefined();
    expect(newEdge!.source).toBe(newA!.id);
    expect(newEdge!.target).toBe(newB!.id);
  });

  it('correctly duplicates selected nodes with offset without polluting clipboard', () => {
    const nodes: AppNode[] = [
      {
        id: 'stock-analyzer-1',
        type: 'stock-analyzer-node',
        position: { x: 50, y: 50 },
        data: { name: 'Stock Analyzer' },
        selected: true,
      } as any,
    ];

    const result = flowClipboard.duplicate(nodes, [], 30);
    expect(result).not.toBeNull();
    if (!result) return;

    expect(result.newNodes.length).toBe(2);
    const duplicatedNode = result.newNodes.find(n => n.id !== 'stock-analyzer-1');
    expect(duplicatedNode).toBeDefined();
    expect(duplicatedNode!.position).toEqual({ x: 80, y: 80 });
  });
});

describe('Flow Auto Layout and Alignment', () => {
  it('correctly calculates Dagre left-to-right auto layout', () => {
    const nodes: AppNode[] = [
      {
        id: 'n1',
        type: 'portfolio-start-node',
        position: { x: 500, y: 500 }, // disorganized
        data: {},
      } as any,
      {
        id: 'n2',
        type: 'agent-node',
        position: { x: 0, y: 0 },
        data: {},
      } as any,
    ];

    const edges: Edge[] = [
      { id: 'e1', source: 'n1', target: 'n2' },
    ];

    const laidOut = calculateAutoLayout(nodes, edges, 'LR');
    expect(laidOut.length).toBe(2);

    const laidOutN1 = laidOut.find(n => n.id === 'n1')!;
    const laidOutN2 = laidOut.find(n => n.id === 'n2')!;

    // In Left-to-Right layout with n1 -> n2, n2 must be placed to the right of n1
    expect(laidOutN2.position.x).toBeGreaterThan(laidOutN1.position.x);
  });

  it('correctly aligns selected nodes to the left', () => {
    const nodes: AppNode[] = [
      { id: 'a', position: { x: 100, y: 10 }, data: {}, selected: true } as any,
      { id: 'b', position: { x: 250, y: 50 }, data: {}, selected: true } as any,
      { id: 'c', position: { x: 400, y: 90 }, data: {}, selected: false } as any,
    ];

    const aligned = alignSelectedNodes(nodes, 'left');
    const a = aligned.find(n => n.id === 'a')!;
    const b = aligned.find(n => n.id === 'b')!;
    const c = aligned.find(n => n.id === 'c')!;

    expect(a.position.x).toBe(100);
    expect(b.position.x).toBe(100); // Aligned to minX (100)
    expect(c.position.x).toBe(400); // Unselected untouched
  });

  it('correctly distributes nodes evenly horizontally', () => {
    const nodes: AppNode[] = [
      { id: 'a', position: { x: 0, y: 0 }, data: {}, selected: true } as any,
      { id: 'b', position: { x: 50, y: 0 }, data: {}, selected: true } as any, // Clustered close to a
      { id: 'c', position: { x: 200, y: 0 }, data: {}, selected: true } as any,
    ];

    const distributed = distributeSelectedNodes(nodes, 'horizontal');
    const b = distributed.find(n => n.id === 'b')!;

    // Midpoint between 0 and 200 should be exactly 100
    expect(b.position.x).toBe(100);
  });
});
