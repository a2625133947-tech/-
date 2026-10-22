import { describe, it, expect } from 'vitest';
import { cleanSnapshotData, areSnapshotsEqual } from '../hooks/use-flow-history';
import { Node, Edge } from '@xyflow/react';

describe('Flow History and Snapshot System', () => {
  it('correctly cleans ephemeral UI properties (selected, dragging) from snapshots', () => {
    const rawNodes: Node[] = [
      {
        id: 'node-1',
        type: 'stock-analyzer-node',
        position: { x: 100, y: 150 },
        data: { label: 'Stock Analyzer' },
        selected: true,
        dragging: true,
      } as any,
    ];

    const rawEdges: Edge[] = [
      {
        id: 'edge-1',
        source: 'node-1',
        target: 'node-2',
        selected: true,
      } as any,
    ];

    const snapshot = cleanSnapshotData(rawNodes, rawEdges);

    expect(snapshot.nodes[0].id).toBe('node-1');
    expect(snapshot.nodes[0].position).toEqual({ x: 100, y: 150 });
    expect((snapshot.nodes[0] as any).selected).toBeUndefined();
    expect((snapshot.nodes[0] as any).dragging).toBeUndefined();
    expect((snapshot.edges[0] as any).selected).toBeUndefined();
  });

  it('correctly compares two snapshots for equality', () => {
    const s1 = cleanSnapshotData(
      [{ id: 'n1', type: 'a', position: { x: 0, y: 0 }, data: {} }],
      [{ id: 'e1', source: 'n1', target: 'n2' }]
    );

    const s2 = cleanSnapshotData(
      [{ id: 'n1', type: 'a', position: { x: 0, y: 0 }, data: {} }],
      [{ id: 'e1', source: 'n1', target: 'n2' }]
    );

    const s3 = cleanSnapshotData(
      [{ id: 'n1', type: 'a', position: { x: 50, y: 50 }, data: {} }], // moved
      [{ id: 'e1', source: 'n1', target: 'n2' }]
    );

    expect(areSnapshotsEqual(s1, s2)).toBe(true);
    expect(areSnapshotsEqual(s1, s3)).toBe(false);
  });
});
