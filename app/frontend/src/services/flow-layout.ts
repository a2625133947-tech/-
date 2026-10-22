import { AppNode } from '@/nodes/types';
import { Edge } from '@xyflow/react';
import dagre from '@dagrejs/dagre';

export type LayoutDirection = 'LR' | 'TB';

export type AlignmentType = 'left' | 'center' | 'right' | 'top' | 'middle' | 'bottom';

export type DistributionAxis = 'horizontal' | 'vertical';

const DEFAULT_NODE_WIDTH = 280;
const DEFAULT_NODE_HEIGHT = 320;

// Semantic tier mapping for AI Hedge Fund nodes
function getNodeSemanticTier(type?: string): number {
  if (!type) return 1;
  if (type.includes('start') || type.includes('stock')) return 0; // Tier 0: Inputs
  if (type.includes('manager')) return 2;                          // Tier 2: Decision Manager
  if (type.includes('report') || type.includes('output')) return 3; // Tier 3: Output & Reports
  return 1;                                                       // Tier 1: Agents & Analysts
}

/**
 * Perform directed graph layout using Dagre with semantic pipeline awareness.
 */
export function calculateAutoLayout(
  nodes: AppNode[],
  edges: Edge[],
  direction: LayoutDirection = 'LR',
  targetNodeIds?: Set<string>
): AppNode[] {
  if (nodes.length === 0) return [];

  const isSubset = targetNodeIds && targetNodeIds.size > 0;
  const nodesToLayout = isSubset ? nodes.filter(n => targetNodeIds.has(n.id)) : nodes;
  const nodesToLayoutIds = new Set(nodesToLayout.map(n => n.id));

  if (nodesToLayout.length === 0) return nodes;

  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: direction,
    nodesep: 50,
    ranksep: 100,
    marginx: 40,
    marginy: 40,
  });
  g.setDefaultEdgeLabel(() => ({}));

  // Unique keys for dagre to safely handle any duplicate node IDs
  const dagreKeys = nodesToLayout.map((n, i) => `${n.id}___${i}`);

  // 1. Add nodes to Dagre with realistic dimensions
  nodesToLayout.forEach((node, i) => {
    const key = dagreKeys[i];
    const width = node.measured?.width || (node.type === 'portfolio-start-node' ? 320 : DEFAULT_NODE_WIDTH);
    const height = node.measured?.height || DEFAULT_NODE_HEIGHT;
    g.setNode(key, { width, height });
  });

  // 2. Add real edges
  let realEdgesCount = 0;
  edges.forEach(edge => {
    if (nodesToLayoutIds.has(edge.source) && nodesToLayoutIds.has(edge.target)) {
      const srcIndex = nodesToLayout.findIndex(n => n.id === edge.source);
      const tgtIndex = nodesToLayout.findIndex(n => n.id === edge.target);
      if (srcIndex !== -1 && tgtIndex !== -1) {
        g.setEdge(dagreKeys[srcIndex], dagreKeys[tgtIndex]);
        realEdgesCount++;
      }
    }
  });

  // 3. If there are no edges or disconnected nodes, apply semantic pipeline tier guidance
  const tiers: string[][] = [[], [], [], []];
  nodesToLayout.forEach((node, i) => {
    const tier = getNodeSemanticTier(node.type);
    tiers[tier].push(dagreKeys[i]);
  });

  // When few or no edges exist, order tiers logically: Inputs -> Analysts -> Manager -> Reports
  if (realEdgesCount === 0) {
    for (let t = 0; t < tiers.length - 1; t++) {
      const currentTier = tiers[t];
      const nextTier = tiers[t + 1];
      if (currentTier.length > 0 && nextTier.length > 0) {
        currentTier.forEach(src => {
          nextTier.forEach(tgt => {
            g.setEdge(src, tgt);
          });
        });
      }
    }
  }

  // 4. Execute Dagre layout
  dagre.layout(g);

  // 5. Map calculated coordinates back to nodes
  const layoutResultMap = new Map<string, { x: number; y: number }>();
  nodesToLayout.forEach((node, i) => {
    const key = dagreKeys[i];
    const pos = g.node(key);
    if (pos) {
      const width = node.measured?.width || (node.type === 'portfolio-start-node' ? 320 : DEFAULT_NODE_WIDTH);
      const height = node.measured?.height || DEFAULT_NODE_HEIGHT;
      layoutResultMap.set(key, {
        x: Math.round(pos.x - width / 2),
        y: Math.round(pos.y - height / 2),
      });
    }
  });

  return nodes.map((node, i) => {
    const key = `${node.id}___${i}`;
    const newPos = layoutResultMap.get(key);
    if (!newPos) return node;

    return {
      ...node,
      position: newPos,
    };
  });
}

/**
 * Align selected nodes (minimum 2 nodes required)
 */
export function alignSelectedNodes(
  nodes: AppNode[],
  alignment: AlignmentType
): AppNode[] {
  const selectedNodes = nodes.filter(n => n.selected);
  if (selectedNodes.length < 2) return nodes;

  const nodeBoxes = selectedNodes.map(node => {
    const w = node.measured?.width || (node as any).width || DEFAULT_NODE_WIDTH;
    const h = node.measured?.height || (node as any).height || DEFAULT_NODE_HEIGHT;
    return {
      id: node.id,
      x: node.position.x,
      y: node.position.y,
      width: w,
      height: h,
      right: node.position.x + w,
      bottom: node.position.y + h,
      centerX: node.position.x + w / 2,
      centerY: node.position.y + h / 2,
    };
  });

  const minX = Math.min(...nodeBoxes.map(b => b.x));
  const maxX = Math.max(...nodeBoxes.map(b => b.right));
  const avgCenterX = (minX + maxX) / 2;

  const minY = Math.min(...nodeBoxes.map(b => b.y));
  const maxY = Math.max(...nodeBoxes.map(b => b.bottom));
  const avgCenterY = (minY + maxY) / 2;

  return nodes.map(node => {
    if (!node.selected) return node;

    const w = node.measured?.width || (node as any).width || DEFAULT_NODE_WIDTH;
    const h = node.measured?.height || (node as any).height || DEFAULT_NODE_HEIGHT;

    let newX = node.position.x;
    let newY = node.position.y;

    switch (alignment) {
      case 'left':
        newX = minX;
        break;
      case 'center':
        newX = Math.round(avgCenterX - w / 2);
        break;
      case 'right':
        newX = Math.round(maxX - w);
        break;
      case 'top':
        newY = minY;
        break;
      case 'middle':
        newY = Math.round(avgCenterY - h / 2);
        break;
      case 'bottom':
        newY = Math.round(maxY - h);
        break;
    }

    return {
      ...node,
      position: { x: newX, y: newY },
    };
  });
}

/**
 * Distribute selected nodes evenly along horizontal or vertical axis (minimum 3 nodes required)
 */
export function distributeSelectedNodes(
  nodes: AppNode[],
  axis: DistributionAxis
): AppNode[] {
  const selectedNodes = nodes.filter(n => n.selected);
  if (selectedNodes.length < 3) return nodes;

  if (axis === 'horizontal') {
    const sorted = [...selectedNodes].sort((a, b) => a.position.x - b.position.x);
    const first = sorted[0];
    const last = sorted[sorted.length - 1];

    const firstX = first.position.x;
    const lastX = last.position.x;
    const totalDistance = lastX - firstX;
    const step = totalDistance / (sorted.length - 1);

    const targetPosMap = new Map<string, number>();
    sorted.forEach((node, index) => {
      targetPosMap.set(node.id, Math.round(firstX + index * step));
    });

    return nodes.map(node => {
      if (!node.selected || !targetPosMap.has(node.id)) return node;
      return {
        ...node,
        position: {
          ...node.position,
          x: targetPosMap.get(node.id)!,
        },
      };
    });
  } else {
    const sorted = [...selectedNodes].sort((a, b) => a.position.y - b.position.y);
    const first = sorted[0];
    const last = sorted[sorted.length - 1];

    const firstY = first.position.y;
    const lastY = last.position.y;
    const totalDistance = lastY - firstY;
    const step = totalDistance / (sorted.length - 1);

    const targetPosMap = new Map<string, number>();
    sorted.forEach((node, index) => {
      targetPosMap.set(node.id, Math.round(firstY + index * step));
    });

    return nodes.map(node => {
      if (!node.selected || !targetPosMap.has(node.id)) return node;
      return {
        ...node,
        position: {
          ...node.position,
          y: targetPosMap.get(node.id)!,
        },
      };
    });
  }
}
