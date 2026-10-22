import { extractBaseAgentKey } from '@/data/node-mappings';
import { getNodeInternalState, setNodeInternalState } from '@/hooks/use-node-state';
import { AppNode } from '@/nodes/types';
import { Edge } from '@xyflow/react';

export const generateUniqueIdSuffix = (): string => {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  for (let i = 0; i < 6; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
};

export const generateClonedNodeId = (oldId: string): string => {
  const baseKey = extractBaseAgentKey(oldId);
  return `${baseKey}_${generateUniqueIdSuffix()}`;
};

export const generateEdgeId = (_source?: string, _target?: string): string => {
  return `edge-${Date.now()}-${generateUniqueIdSuffix()}`;
};

interface ClipboardContent {
  nodes: AppNode[];
  internalEdges: Edge[];
  nodeInternalStates: Record<string, Record<string, any>>;
}

class FlowClipboardService {
  private clipboard: ClipboardContent | null = null;
  private pasteCount = 0;

  /**
   * Copy selected nodes and the edges that connect strictly between them.
   */
  copy(nodes: AppNode[], edges: Edge[]): boolean {
    const selectedNodes = nodes.filter(n => n.selected);
    if (selectedNodes.length === 0) return false;

    const selectedNodeIds = new Set(selectedNodes.map(n => n.id));

    // Only copy edges whose source AND target are both within the selected node set
    const internalEdges = edges.filter(
      e => selectedNodeIds.has(e.source) && selectedNodeIds.has(e.target)
    );

    // Snapshot internal business state for each selected node
    const nodeInternalStates: Record<string, Record<string, any>> = {};
    selectedNodes.forEach(node => {
      const state = getNodeInternalState(node.id);
      if (state) {
        nodeInternalStates[node.id] = JSON.parse(JSON.stringify(state));
      }
    });

    this.clipboard = {
      nodes: JSON.parse(JSON.stringify(selectedNodes)),
      internalEdges: JSON.parse(JSON.stringify(internalEdges)),
      nodeInternalStates,
    };
    this.pasteCount = 0;
    return true;
  }

  hasContent(): boolean {
    return this.clipboard !== null && this.clipboard.nodes.length > 0;
  }

  /**
   * Paste clipboard content with offset and remapped IDs.
   */
  paste(
    existingNodes: AppNode[],
    existingEdges: Edge[],
    offsetStep = 30
  ): { newNodes: AppNode[]; newEdges: Edge[] } | null {
    if (!this.clipboard || this.clipboard.nodes.length === 0) return null;

    this.pasteCount += 1;
    const currentOffset = this.pasteCount * offsetStep;

    const oldToNewIdMap = new Map<string, string>();
    const clonedNodes: AppNode[] = [];

    // 1. Clone nodes with new IDs and offset positions
    for (const oldNode of this.clipboard.nodes) {
      const newId = generateClonedNodeId(oldNode.id);
      oldToNewIdMap.set(oldNode.id, newId);

      // Deep clone node data
      let clonedData: any = {};
      try {
        clonedData = structuredClone(oldNode.data);
      } catch {
        clonedData = JSON.parse(JSON.stringify(oldNode.data));
      }

      // Restore internal business state under new ID
      const oldInternalState = this.clipboard.nodeInternalStates[oldNode.id];
      if (oldInternalState) {
        const clonedState = JSON.parse(JSON.stringify(oldInternalState));
        setNodeInternalState(newId, clonedState);
        clonedData.internal_state = clonedState;
      }

      const newNode: AppNode = {
        ...oldNode,
        id: newId,
        position: {
          x: oldNode.position.x + currentOffset,
          y: oldNode.position.y + currentOffset,
        },
        data: clonedData,
        selected: true, // Auto-select newly pasted nodes
      };

      clonedNodes.push(newNode);
    }

    // 2. Clone internal edges with remapped source and target IDs
    const clonedEdges: Edge[] = [];
    for (const oldEdge of this.clipboard.internalEdges) {
      const newSource = oldToNewIdMap.get(oldEdge.source);
      const newTarget = oldToNewIdMap.get(oldEdge.target);

      if (newSource && newTarget) {
        const newEdgeId = generateEdgeId(newSource, newTarget);
        clonedEdges.push({
          ...oldEdge,
          id: newEdgeId,
          source: newSource,
          target: newTarget,
          selected: false,
        });
      }
    }

    // Deselect previously existing nodes so the newly pasted ones stand out
    const updatedExistingNodes = existingNodes.map(n => ({
      ...n,
      selected: false,
    }));
    const updatedExistingEdges = existingEdges.map(e => ({
      ...e,
      selected: false,
    }));

    return {
      newNodes: [...updatedExistingNodes, ...clonedNodes],
      newEdges: [...updatedExistingEdges, ...clonedEdges],
    };
  }

  /**
   * Directly duplicate selected nodes (and their internal edges) without overwriting clipboard.
   */
  duplicate(
    nodes: AppNode[],
    edges: Edge[],
    offsetStep = 30
  ): { newNodes: AppNode[]; newEdges: Edge[] } | null {
    const selectedNodes = nodes.filter(n => n.selected);
    if (selectedNodes.length === 0) return null;

    const selectedNodeIds = new Set(selectedNodes.map(n => n.id));
    const internalEdges = edges.filter(
      e => selectedNodeIds.has(e.source) && selectedNodeIds.has(e.target)
    );

    const oldToNewIdMap = new Map<string, string>();
    const clonedNodes: AppNode[] = [];

    for (const oldNode of selectedNodes) {
      const newId = generateClonedNodeId(oldNode.id);
      oldToNewIdMap.set(oldNode.id, newId);

      let clonedData: any = {};
      try {
        clonedData = structuredClone(oldNode.data);
      } catch {
        clonedData = JSON.parse(JSON.stringify(oldNode.data));
      }

      const internalState = getNodeInternalState(oldNode.id);
      if (internalState) {
        const clonedState = JSON.parse(JSON.stringify(internalState));
        setNodeInternalState(newId, clonedState);
        clonedData.internal_state = clonedState;
      }

      clonedNodes.push({
        ...oldNode,
        id: newId,
        position: {
          x: oldNode.position.x + offsetStep,
          y: oldNode.position.y + offsetStep,
        },
        data: clonedData,
        selected: true,
      });
    }

    const clonedEdges: Edge[] = [];
    for (const oldEdge of internalEdges) {
      const newSource = oldToNewIdMap.get(oldEdge.source);
      const newTarget = oldToNewIdMap.get(oldEdge.target);

      if (newSource && newTarget) {
        clonedEdges.push({
          ...oldEdge,
          id: generateEdgeId(newSource, newTarget),
          source: newSource,
          target: newTarget,
          selected: false,
        });
      }
    }

    const updatedExistingNodes = nodes.map(n => ({ ...n, selected: false }));
    const updatedExistingEdges = edges.map(e => ({ ...e, selected: false }));

    return {
      newNodes: [...updatedExistingNodes, ...clonedNodes],
      newEdges: [...updatedExistingEdges, ...clonedEdges],
    };
  }
}

export const flowClipboard = new FlowClipboardService();
