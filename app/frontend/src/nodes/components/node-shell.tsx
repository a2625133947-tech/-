import { Card, CardHeader } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Handle, NodeToolbar, Position, useReactFlow } from '@xyflow/react';
import { Trash2 } from 'lucide-react';
import { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

export interface NodeShellProps {
  id: string;
  selected?: boolean;
  isConnectable?: boolean;
  icon: ReactNode;
  iconColor?: string;
  name: string;
  description?: string;
  children: ReactNode;
  hasLeftHandle?: boolean;
  hasRightHandle?: boolean;
  status?: string;
  width?: string;
}

export function NodeShell({
  id,
  selected,
  isConnectable,
  icon,
  iconColor,
  name,
  description,
  children,
  hasLeftHandle = true,
  hasRightHandle = true,
  status = 'IDLE',
  width = 'w-64',
}: NodeShellProps) {
  const { t } = useTranslation();
  const { deleteElements } = useReactFlow();
  const isInProgress = status === 'IN_PROGRESS';

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    deleteElements({ nodes: [{ id }] });
  };

  return (
    <div
      className={cn(
        "react-flow__node-default relative select-none cursor-pointer p-0 rounded-lg border border-node transition-all duration-200",
        width,
        !selected && "hover:border-node-hover hover:shadow-lg",
        selected && "border-node-selected shadow-xl",
        isInProgress && "node-in-progress"
      )}
      data-id={id}
      data-nodeid={id}
    >
      {/* Selection Floating Toolbar with Delete button */}
      <NodeToolbar
        isVisible={selected}
        position={Position.Top}
        offset={8}
        className="nodrag nopan"
      >
        <div className="flex items-center gap-1 p-1 rounded-md bg-zinc-900/95 border border-zinc-700 shadow-xl backdrop-blur-sm animate-in fade-in zoom-in-95 duration-150">
          <button
            onClick={handleDelete}
            className="h-7 px-2.5 rounded bg-zinc-800 hover:bg-rose-950/70 border border-zinc-700 hover:border-rose-500/60 text-zinc-300 hover:text-rose-400 flex items-center gap-1.5 text-xs font-medium transition-all active:scale-95 cursor-pointer"
            title={t('flow.delete_node', { defaultValue: '删除节点' })}
            aria-label="Delete node"
          >
            <Trash2 size={13} className="text-rose-400" />
            <span>{t('flow.delete_node', { defaultValue: '删除' })}</span>
          </button>
        </div>
      </NodeToolbar>

      {isInProgress && (
        <div className="animated-border-container"></div>
      )}
      {hasLeftHandle && (
        <Handle
          type="target"
          position={Position.Left}
          className="w-3 h-3 rounded-full bg-gray-500 border-2 border-card absolute left-0 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 transition-all duration-200 hover:bg-gray-500 hover:w-4 hover:h-4 hover:shadow-[0_0_5px_2px_rgba(59,130,246,0.3)]"
          isConnectable={isConnectable}
        />
      )}
      <div className="overflow-hidden rounded-lg">
        <Card className="bg-node rounded-none overflow-hidden border-none">
          <CardHeader className="p-3 bg-node flex flex-row items-center space-x-2 rounded-t-sm">
            <div className={cn(
              "flex items-center justify-center h-8 w-8 rounded-lg text-primary",
              isInProgress ? "gradient-animation" : iconColor
            )}>
              {icon}
            </div>
            <div className="text-title font-semibold text-primary">
              {name || "Custom Component"}
            </div>
          </CardHeader>
          {description && (
            <div className="px-3 py-2 text-subtitle text-primary text-left">
              {description}
            </div>
          )}
          {children}
        </Card>
      </div>
      {hasRightHandle && (
        <Handle
          type="source"
          position={Position.Right}
          className="w-3 h-3 rounded-full bg-gray-500 border-2 border-card absolute right-0 top-1/2 translate-x-1/2 -translate-y-1/2 z-10 transition-all duration-200 hover:bg-gray-500 hover:w-4 hover:h-4 hover:shadow-[0_0_5px_2px_rgba(59,130,246,0.3)]"
          isConnectable={isConnectable}
        />
      )}
    </div>
  );
}
