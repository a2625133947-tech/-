import { Edge, Node, useReactFlow } from '@xyflow/react';
import { useCallback, useRef, useState } from 'react';

export interface FlowSnapshot {
  nodes: Node[];
  edges: Edge[];
}

interface UseFlowHistoryOptions {
  maxHistorySize?: number;
  flowId?: number | null;
  setNodesState?: (nodes: Node[] | ((nds: Node[]) => Node[])) => void;
  setEdgesState?: (edges: Edge[] | ((eds: Edge[]) => Edge[])) => void;
  onStateRestored?: (snapshot: FlowSnapshot) => void;
}

// Clean snapshot data by removing temporary UI states like selection
export function cleanSnapshotData(nodes: Node[], edges: Edge[]): FlowSnapshot {
  const cleanNodes = nodes.map(node => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { selected, dragging, ...rest } = node as any;
    return rest;
  });

  const cleanEdges = edges.map(edge => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { selected, ...rest } = edge as any;
    return rest;
  });

  return {
    nodes: JSON.parse(JSON.stringify(cleanNodes)),
    edges: JSON.parse(JSON.stringify(cleanEdges)),
  };
}

export function areSnapshotsEqual(s1: FlowSnapshot | null, s2: FlowSnapshot | null): boolean {
  if (!s1 || !s2) return false;
  return (
    JSON.stringify(s1.nodes) === JSON.stringify(s2.nodes) &&
    JSON.stringify(s1.edges) === JSON.stringify(s2.edges)
  );
}

export function useFlowHistory({
  maxHistorySize = 50,
  flowId,
  setNodesState,
  setEdgesState,
  onStateRestored,
}: UseFlowHistoryOptions = {}) {
  const reactFlow = useReactFlow();
  
  // Isolated history storage per flow key
  const historiesRef = useRef<Record<string, FlowSnapshot[]>>({});
  const indexesRef = useRef<Record<string, number>>({});
  const isPerformingActionRef = useRef(false);

  // Reactive state for UI toolbar
  const [, setRevision] = useState(0);

  const getFlowKey = useCallback((id: number | null | undefined) => {
    return id ? `flow-${id}` : 'flow-default';
  }, []);

  const flowKey = getFlowKey(flowId);

  const getCurrentHistory = useCallback((): FlowSnapshot[] => {
    if (!historiesRef.current[flowKey]) {
      historiesRef.current[flowKey] = [];
    }
    return historiesRef.current[flowKey];
  }, [flowKey]);

  const getCurrentIndex = useCallback((): number => {
    return indexesRef.current[flowKey] ?? -1;
  }, [flowKey]);

  const setCurrentIndex = useCallback((idx: number) => {
    indexesRef.current[flowKey] = idx;
    setRevision(r => r + 1);
  }, [flowKey]);

  // Set initial baseline for a loaded flow (does not count as an undoable step)
  const initBaseline = useCallback((nodes: Node[], edges: Edge[]) => {
    const snapshot = cleanSnapshotData(nodes, edges);
    historiesRef.current[flowKey] = [snapshot];
    indexesRef.current[flowKey] = 0;
    setRevision(r => r + 1);
  }, [flowKey]);

  // Commit a new state snapshot to history
  const commitSnapshot = useCallback((nodes?: Node[], edges?: Edge[]) => {
    if (isPerformingActionRef.current) return;

    const currentNodes = nodes ?? reactFlow.getNodes();
    const currentEdges = edges ?? reactFlow.getEdges();
    const snapshot = cleanSnapshotData(currentNodes, currentEdges);

    const history = getCurrentHistory();
    const currentIndex = getCurrentIndex();

    // If identical to last snapshot, skip
    if (history.length > 0 && currentIndex >= 0) {
      const lastSnapshot = history[currentIndex];
      if (areSnapshotsEqual(snapshot, lastSnapshot)) {
        return;
      }
    }

    // Discard any future history beyond currentIndex (branching behavior)
    const newHistory = history.slice(0, currentIndex + 1);
    newHistory.push(snapshot);

    // Bounded history length
    if (newHistory.length > maxHistorySize) {
      newHistory.shift();
      historiesRef.current[flowKey] = newHistory;
      setCurrentIndex(maxHistorySize - 1);
    } else {
      historiesRef.current[flowKey] = newHistory;
      setCurrentIndex(newHistory.length - 1);
    }
  }, [getCurrentHistory, getCurrentIndex, maxHistorySize, reactFlow, flowKey, setCurrentIndex]);

  // Restore snapshot helper
  const restoreSnapshot = useCallback((snapshot: FlowSnapshot) => {
    isPerformingActionRef.current = true;

    const clonedSnapshot = cleanSnapshotData(snapshot.nodes, snapshot.edges);

    // 1. Update React Flow instance store
    reactFlow.setNodes(clonedSnapshot.nodes);
    reactFlow.setEdges(clonedSnapshot.edges);

    // 2. Update parent component controlled state
    if (setNodesState) {
      setNodesState(clonedSnapshot.nodes as any);
    }
    if (setEdgesState) {
      setEdgesState(clonedSnapshot.edges);
    }

    // 3. Callback for autosave / context notification
    onStateRestored?.(clonedSnapshot);

    setTimeout(() => {
      isPerformingActionRef.current = false;
    }, 50);
  }, [reactFlow, setNodesState, setEdgesState, onStateRestored]);

  // Undo
  const undo = useCallback(() => {
    const currentIndex = getCurrentIndex();
    const history = getCurrentHistory();

    if (currentIndex > 0) {
      const targetIndex = currentIndex - 1;
      const targetSnapshot = history[targetIndex];
      if (targetSnapshot) {
        restoreSnapshot(targetSnapshot);
        setCurrentIndex(targetIndex);
      }
    }
  }, [getCurrentIndex, getCurrentHistory, restoreSnapshot, setCurrentIndex]);

  // Redo
  const redo = useCallback(() => {
    const currentIndex = getCurrentIndex();
    const history = getCurrentHistory();

    if (currentIndex < history.length - 1) {
      const targetIndex = currentIndex + 1;
      const targetSnapshot = history[targetIndex];
      if (targetSnapshot) {
        restoreSnapshot(targetSnapshot);
        setCurrentIndex(targetIndex);
      }
    }
  }, [getCurrentIndex, getCurrentHistory, restoreSnapshot, setCurrentIndex]);

  const canUndo = getCurrentIndex() > 0;
  const canRedo = getCurrentIndex() < getCurrentHistory().length - 1 && getCurrentIndex() >= 0;

  const clearHistory = useCallback(() => {
    historiesRef.current[flowKey] = [];
    indexesRef.current[flowKey] = -1;
    setRevision(r => r + 1);
  }, [flowKey]);

  return {
    initBaseline,
    commitSnapshot,
    undo,
    redo,
    canUndo,
    canRedo,
    clearHistory,
    isPerformingAction: () => isPerformingActionRef.current,
  };
}
