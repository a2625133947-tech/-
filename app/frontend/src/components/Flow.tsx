import {
  Background,
  BackgroundVariant,
  ColorMode,
  Connection,
  Edge,
  EdgeChange,
  MarkerType,
  MiniMap,
  Node,
  NodeChange,
  ReactFlow,
  SelectionMode,
  addEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from '@xyflow/react';
import { useTheme } from 'next-themes';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import '@xyflow/react/dist/style.css';

import { useFlowContext } from '@/contexts/flow-context';
import { useEnhancedFlowActions } from '@/hooks/use-enhanced-flow-actions';
import { useFlowHistory } from '@/hooks/use-flow-history';
import { useFlowKeyboardShortcuts, useKeyboardShortcuts } from '@/hooks/use-keyboard-shortcuts';
import { useToastManager } from '@/hooks/use-toast-manager';
import { AppNode } from '@/nodes/types';
import { edgeTypes } from '../edges';
import { nodeTypes } from '../nodes';
import { FlowCanvasContextMenu, ContextMenuTarget } from './flow/flow-canvas-context-menu';
import { FlowHistoryToolbar } from './flow/flow-history-toolbar';
import { FlowSelectionToolbar } from './flow/flow-selection-toolbar';
import { FlowViewportControls } from './flow/flow-viewport-controls';
import { TooltipProvider } from './ui/tooltip';
import { flowClipboard } from '@/services/flow-clipboard';
import {
  calculateAutoLayout,
  alignSelectedNodes,
  distributeSelectedNodes,
  LayoutDirection,
  AlignmentType,
  DistributionAxis,
} from '@/services/flow-layout';

type FlowProps = {
  className?: string;
};

export function Flow({ className = '' }: FlowProps) {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const reactFlow = useReactFlow();
  
  const colorMode: ColorMode = resolvedTheme === 'light' ? 'light' : 'dark';
  
  const [nodes, setNodes, onNodesChange] = useNodesState<AppNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [isInitialized, setIsInitialized] = useState(false);
  const baselineSetRef = useRef<number | null>(null);
  const proOptions = { hideAttribution: true };

  // Viewport & Toolbar States
  const [snapToGrid, setSnapToGrid] = useState(false);
  const [showMiniMap, setShowMiniMap] = useState(false);
  const [contextMenuTarget, setContextMenuTarget] = useState<ContextMenuTarget | null>(null);

  // Selection calculations
  const selectedNodes = nodes.filter(n => n.selected);
  const selectedEdges = edges.filter(e => e.selected);
  const selectedCount = selectedNodes.length;
  
  // Flow Context
  const { currentFlowId } = useFlowContext();
  const { saveCurrentFlowWithCompleteState } = useEnhancedFlowActions();
  const { success, error } = useToastManager();

  // Auto-save debounce timer
  const autoSaveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastSavedFlowIdRef = useRef<number | null>(null);
  
  const autoSave = useCallback(async (flowIdToSave?: number | null) => {
    const targetFlowId = flowIdToSave !== undefined ? flowIdToSave : currentFlowId;
    
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current);
    }
    
    autoSaveTimeoutRef.current = setTimeout(async () => {
      if (!targetFlowId) return;
      if (targetFlowId !== currentFlowId) return;
      
      try {
        await saveCurrentFlowWithCompleteState();
        lastSavedFlowIdRef.current = targetFlowId;
      } catch (err) {
        console.error(`[Auto-save] Failed to save flow ${targetFlowId}:`, err);
      }
    }, 1000);
  }, [currentFlowId, saveCurrentFlowWithCompleteState]);

  // History hook
  const {
    initBaseline,
    commitSnapshot,
    undo,
    redo,
    canUndo,
    canRedo,
    isPerformingAction,
  } = useFlowHistory({
    flowId: currentFlowId,
    setNodesState: setNodes as any,
    setEdgesState: setEdges,
    onStateRestored: () => {
      if (currentFlowId) {
        autoSave(currentFlowId);
      }
    },
  });

  // Set baseline when nodes or edges first load for this flow ID
  useEffect(() => {
    if (isInitialized && currentFlowId !== baselineSetRef.current) {
      initBaseline(nodes, edges);
      baselineSetRef.current = currentFlowId;
    }
  }, [isInitialized, currentFlowId, nodes, edges, initBaseline]);

  // Enhanced onNodesChange handler
  const handleNodesChange = useCallback((changes: NodeChange<AppNode>[]) => {
    onNodesChange(changes);
    
    const hasStructuralRemoval = changes.some(change => change.type === 'remove');
    const hasStructuralAdd = changes.some(change => change.type === 'add');

    if ((hasStructuralRemoval || hasStructuralAdd) && !isPerformingAction()) {
      setTimeout(() => {
        commitSnapshot();
      }, 20);
    }

    const shouldAutoSave = changes.some(change => {
      switch (change.type) {
        case 'add':
        case 'remove':
          return true;
        case 'position':
          return !change.dragging;
        default:
          return false;
      }
    });

    if (shouldAutoSave && isInitialized && currentFlowId) {
      autoSave(currentFlowId);
    }
  }, [onNodesChange, autoSave, isInitialized, currentFlowId, commitSnapshot, isPerformingAction]);

  // Handle node drag stop -> commit exactly 1 snapshot for the full drag
  const handleNodeDragStop = useCallback((_event: React.MouseEvent, _node: Node, allNodes: Node[]) => {
    if (!isPerformingAction()) {
      commitSnapshot(allNodes, edges);
    }
  }, [commitSnapshot, edges, isPerformingAction]);

  // Enhanced onEdgesChange handler
  const handleEdgesChange = useCallback((changes: EdgeChange[]) => {
    onEdgesChange(changes);
    
    const hasRemoval = changes.some(change => change.type === 'remove');
    if (hasRemoval && !isPerformingAction()) {
      setTimeout(() => {
        commitSnapshot();
      }, 20);
    }

    const shouldAutoSave = changes.some(change => change.type === 'remove');
    if (shouldAutoSave && isInitialized && currentFlowId) {
      autoSave(currentFlowId);
    }
  }, [onEdgesChange, autoSave, isInitialized, currentFlowId, commitSnapshot, isPerformingAction]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current);
      }
    };
  }, []);

  // Cancel pending auto-saves when flow changes
  useEffect(() => {
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current);
      autoSaveTimeoutRef.current = null;
    }
  }, [currentFlowId]);

  // =========================================================================
  // CLIPBOARD OPERATIONS (Copy, Paste, Duplicate)
  // =========================================================================

  const handleCopy = useCallback(() => {
    if (selectedNodes.length === 0) return;
    const ok = flowClipboard.copy(nodes, edges);
    if (ok) {
      success(t('flow.copied_success', { defaultValue: '已复制选中项' }), 'flow-clipboard');
    }
  }, [nodes, edges, selectedNodes.length, success, t]);

  const handlePaste = useCallback(() => {
    if (!flowClipboard.hasContent()) return;
    const result = flowClipboard.paste(nodes, edges);
    if (result) {
      setNodes(result.newNodes);
      setEdges(result.newEdges);
      commitSnapshot(result.newNodes, result.newEdges);
      if (currentFlowId) autoSave(currentFlowId);
      success(t('flow.pasted_success', { defaultValue: '已粘贴到画布' }), 'flow-clipboard');
    }
  }, [nodes, edges, setNodes, setEdges, commitSnapshot, currentFlowId, autoSave, success, t]);

  const handleDuplicate = useCallback(() => {
    if (selectedNodes.length === 0) return;
    const result = flowClipboard.duplicate(nodes, edges);
    if (result) {
      setNodes(result.newNodes);
      setEdges(result.newEdges);
      commitSnapshot(result.newNodes, result.newEdges);
      if (currentFlowId) autoSave(currentFlowId);
      success(t('flow.duplicated_success', { defaultValue: '已创建副本' }), 'flow-clipboard');
    }
  }, [nodes, edges, selectedNodes.length, setNodes, setEdges, commitSnapshot, currentFlowId, autoSave, success, t]);

  // =========================================================================
  // SELECTION & DELETION OPERATIONS
  // =========================================================================

  const handleBatchDelete = useCallback(() => {
    if (selectedNodes.length === 0 && selectedEdges.length === 0) return;
    reactFlow.deleteElements({
      nodes: selectedNodes,
      edges: selectedEdges,
    });
  }, [selectedNodes, selectedEdges, reactFlow]);

  const handleSelectAll = useCallback(() => {
    setNodes(nds => nds.map(n => ({ ...n, selected: true })));
  }, [setNodes]);

  const handleClearSelection = useCallback(() => {
    setNodes(nds => nds.map(n => ({ ...n, selected: false })));
    setEdges(eds => eds.map(e => ({ ...e, selected: false })));
  }, [setNodes, setEdges]);

  // =========================================================================
  // LAYOUT & ALIGNMENT
  // =========================================================================

  const handleAutoLayout = useCallback((direction: LayoutDirection) => {
    const updatedNodes = calculateAutoLayout(nodes, edges, direction);
    reactFlow.setNodes(updatedNodes);
    setNodes(updatedNodes);
    commitSnapshot(updatedNodes, edges);
    if (currentFlowId) autoSave(currentFlowId);
    setTimeout(() => {
      reactFlow.fitView({ padding: 0.15, duration: 400 });
    }, 50);
    success(t('flow.layout_applied', { defaultValue: '已完成自动布局整理' }), 'flow-layout');
  }, [nodes, edges, setNodes, commitSnapshot, currentFlowId, autoSave, reactFlow, success, t]);

  const handleLayoutSelection = useCallback(() => {
    if (selectedNodes.length < 2) return;
    const targetIds = new Set(selectedNodes.map(n => n.id));
    const updatedNodes = calculateAutoLayout(nodes, edges, 'LR', targetIds);
    reactFlow.setNodes(updatedNodes);
    setNodes(updatedNodes);
    commitSnapshot(updatedNodes, edges);
    if (currentFlowId) autoSave(currentFlowId);
    setTimeout(() => {
      reactFlow.fitView({ nodes: selectedNodes, padding: 0.2, duration: 400 });
    }, 50);
    success(t('flow.layout_applied', { defaultValue: '已完成选中节点整理' }), 'flow-layout');
  }, [nodes, edges, selectedNodes, setNodes, commitSnapshot, currentFlowId, autoSave, reactFlow, success, t]);

  const handleAlign = useCallback((alignment: AlignmentType) => {
    if (selectedNodes.length < 2) return;
    const updatedNodes = alignSelectedNodes(nodes, alignment);
    reactFlow.setNodes(updatedNodes);
    setNodes(updatedNodes);
    commitSnapshot(updatedNodes, edges);
    if (currentFlowId) autoSave(currentFlowId);
  }, [nodes, edges, selectedNodes.length, setNodes, commitSnapshot, currentFlowId, autoSave, reactFlow]);

  const handleDistribute = useCallback((axis: DistributionAxis) => {
    if (selectedNodes.length < 3) return;
    const updatedNodes = distributeSelectedNodes(nodes, axis);
    reactFlow.setNodes(updatedNodes);
    setNodes(updatedNodes);
    commitSnapshot(updatedNodes, edges);
    if (currentFlowId) autoSave(currentFlowId);
  }, [nodes, edges, selectedNodes.length, setNodes, commitSnapshot, currentFlowId, autoSave, reactFlow]);

  // =========================================================================
  // VIEWPORT CONTROLS
  // =========================================================================

  const handleFitView = useCallback(() => {
    reactFlow.fitView({ padding: 0.15, duration: 400 });
  }, [reactFlow]);

  const handleResetView = useCallback(() => {
    reactFlow.setViewport({ x: 0, y: 0, zoom: 1 }, { duration: 400 });
  }, [reactFlow]);

  const handleCenterSelection = useCallback(() => {
    if (selectedNodes.length > 0) {
      reactFlow.fitView({ nodes: selectedNodes, padding: 0.3, duration: 400 });
    }
  }, [reactFlow, selectedNodes]);

  // =========================================================================
  // CONTEXT MENUS
  // =========================================================================

  const handleNodeContextMenu = useCallback((event: React.MouseEvent, node: Node) => {
    event.preventDefault();
    event.stopPropagation();

    // If right clicked node isn't selected, select it exclusively
    if (!node.selected) {
      setNodes(nds => nds.map(n => ({ ...n, selected: n.id === node.id })));
    }

    setContextMenuTarget({
      type: 'node',
      id: node.id,
      x: event.clientX,
      y: event.clientY,
    });
  }, [setNodes]);

  const handleEdgeContextMenu = useCallback((event: React.MouseEvent, edge: Edge) => {
    event.preventDefault();
    event.stopPropagation();

    setEdges(eds => eds.map(e => ({ ...e, selected: e.id === edge.id })));

    setContextMenuTarget({
      type: 'edge',
      id: edge.id,
      x: event.clientX,
      y: event.clientY,
    });
  }, [setEdges]);

  const handlePaneContextMenu = useCallback((event: MouseEvent | React.MouseEvent) => {
    event.preventDefault();
    setContextMenuTarget({
      type: 'pane',
      x: event.clientX,
      y: event.clientY,
    });
  }, []);

  // =========================================================================
  // KEYBOARD SHORTCUTS
  // =========================================================================

  useFlowKeyboardShortcuts(async () => {
    try {
      const savedFlow = await saveCurrentFlowWithCompleteState();
      if (savedFlow) {
        success(`"${savedFlow.name}" saved!`, 'flow-save');
      } else {
        error('Failed to save flow', 'flow-save-error');
      }
    } catch {
      error('Failed to save flow', 'flow-save-error');
    }
  });

  useKeyboardShortcuts({
    shortcuts: [
      { key: 'z', ctrlKey: true, metaKey: true, callback: undo, preventDefault: true },
      { key: 'z', ctrlKey: true, metaKey: true, shiftKey: true, callback: redo, preventDefault: true },
      { key: 'y', ctrlKey: true, metaKey: true, callback: redo, preventDefault: true },
      { key: 'c', ctrlKey: true, metaKey: true, callback: handleCopy, preventDefault: true },
      { key: 'v', ctrlKey: true, metaKey: true, callback: handlePaste, preventDefault: true },
      { key: 'd', ctrlKey: true, metaKey: true, callback: handleDuplicate, preventDefault: true },
      { key: 'a', ctrlKey: true, metaKey: true, callback: handleSelectAll, preventDefault: true },
      { key: '0', ctrlKey: true, metaKey: true, callback: handleFitView, preventDefault: true },
      { key: 'Escape', callback: handleClearSelection, preventDefault: true },
    ],
  });
  
  const onInit = useCallback(() => {
    if (!isInitialized) {
      setIsInitialized(true);
    }
  }, [isInitialized]);

  // Connect two nodes
  const onConnect = useCallback(
    (connection: Connection) => {
      const newEdge: Edge = {
        ...connection,
        id: `edge-${Date.now()}`,
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      };

      setEdges((eds) => {
        const next = addEdge(newEdge, eds);
        if (!isPerformingAction()) {
          setTimeout(() => {
            commitSnapshot(nodes, next);
          }, 20);
        }
        return next;
      });
      
      if (currentFlowId) {
        const flowIdAtTimeOfChange = currentFlowId;
        if (autoSaveTimeoutRef.current) {
          clearTimeout(autoSaveTimeoutRef.current);
        }
        
        setTimeout(async () => {
          if (flowIdAtTimeOfChange !== currentFlowId) return;
          try {
            await saveCurrentFlowWithCompleteState();
          } catch (err) {
            console.error(`[Auto-save] Failed to save new connection:`, err);
          }
        }, 100);
      }
    },
    [setEdges, currentFlowId, saveCurrentFlowWithCompleteState, commitSnapshot, nodes, isPerformingAction]
  );

  const backgroundStyle = {
    backgroundColor: 'hsl(var(--background))'
  };
  
  const gridColor = resolvedTheme === 'light' ? 'hsl(var(--foreground))' : 'hsl(var(--muted-foreground))';

  return (
    <div className={`w-full h-full relative overflow-hidden ${className}`}>
      <TooltipProvider>
        {/* Floating Undo / Redo Toolbar */}
        <FlowHistoryToolbar
          id="tour-history-toolbar"
          canUndo={canUndo}
          canRedo={canRedo}
          onUndo={undo}
          onRedo={redo}
          className="absolute top-3 left-3 z-30"
        />

        {/* Floating Selection Toolbar (when >= 2 nodes selected) */}
        <FlowSelectionToolbar
          selectedCount={selectedCount}
          onCopy={handleCopy}
          onDuplicate={handleDuplicate}
          onDelete={handleBatchDelete}
          onAlign={handleAlign}
          onDistribute={handleDistribute}
          onLayoutSelection={handleLayoutSelection}
          className="absolute top-3 left-1/2 -translate-x-1/2"
        />

        {/* Floating Viewport & Layout Controls */}
        <FlowViewportControls
          id="tour-viewport-controls"
          onFitView={handleFitView}
          onResetView={handleResetView}
          onCenterSelection={handleCenterSelection}
          onAutoLayout={handleAutoLayout}
          snapToGrid={snapToGrid}
          onToggleSnapToGrid={() => setSnapToGrid(s => !s)}
          showMiniMap={showMiniMap}
          onToggleMiniMap={() => setShowMiniMap(m => !m)}
          hasSelection={selectedCount > 0}
          className="absolute bottom-4 left-4"
        />

        {/* Right-click Context Menu */}
        <FlowCanvasContextMenu
          target={contextMenuTarget}
          onClose={() => setContextMenuTarget(null)}
          selectedCount={selectedCount}
          hasClipboard={flowClipboard.hasContent()}
          onCopy={handleCopy}
          onPaste={handlePaste}
          onDuplicate={handleDuplicate}
          onDelete={handleBatchDelete}
          onSelectAll={handleSelectAll}
          onFitView={handleFitView}
          onResetView={handleResetView}
          onAutoLayout={handleAutoLayout}
        />

        <ReactFlow
          nodes={nodes}
          nodeTypes={nodeTypes}
          onNodesChange={handleNodesChange}
          onNodeDragStop={handleNodeDragStop}
          edges={edges}
          edgeTypes={edgeTypes}
          onEdgesChange={handleEdgesChange}
          onConnect={onConnect}
          onInit={onInit}
          colorMode={colorMode}
          proOptions={proOptions}
          snapToGrid={snapToGrid}
          snapGrid={[20, 20]}
          onNodeContextMenu={handleNodeContextMenu}
          onEdgeContextMenu={handleEdgeContextMenu}
          onPaneContextMenu={handlePaneContextMenu}
          selectionMode={SelectionMode.Partial}
          multiSelectionKeyCode={['Meta', 'Ctrl', 'Shift']}
          elementsSelectable={true}
        >
          <Background 
            variant={BackgroundVariant.Dots}
            gap={snapToGrid ? 20 : 13}
            color={gridColor}
            style={backgroundStyle}
          />

          {showMiniMap && (
            <MiniMap
              zoomable
              pannable
              position="bottom-right"
              nodeColor={n => {
                if (n.type === 'stock-analyzer-node') return '#10b981';
                if (n.type === 'portfolio-manager-node') return '#3b82f6';
                if (n.type === 'agent-node') return '#ef4444';
                return '#a855f7';
              }}
              maskColor="rgba(0, 0, 0, 0.75)"
              className="!bg-zinc-950/90 !border !border-zinc-800 !rounded-lg !shadow-2xl overflow-hidden m-4"
            />
          )}
        </ReactFlow>
      </TooltipProvider>
    </div>
  );
}
