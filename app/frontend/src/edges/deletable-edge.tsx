import {
  BaseEdge,
  EdgeLabelRenderer,
  EdgeProps,
  getBezierPath,
  useReactFlow,
} from '@xyflow/react';
import { Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export function DeletableEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  selected,
}: EdgeProps) {
  const { t } = useTranslation();
  const { deleteElements } = useReactFlow();

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    deleteElements({ edges: [{ id }] });
  };

  return (
    <>
      <BaseEdge path={edgePath} markerEnd={markerEnd} style={style} />
      {selected && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
            }}
            className="nodrag nopan z-30"
          >
            <button
              onClick={handleDelete}
              className="h-6 w-6 rounded-full bg-zinc-900 border border-zinc-700 hover:border-red-500 hover:bg-red-950/80 text-zinc-400 hover:text-red-400 flex items-center justify-center shadow-lg transition-all duration-150 active:scale-90 cursor-pointer group"
              title={t('flow.delete_edge', { defaultValue: '删除连线' })}
              aria-label="Delete edge"
            >
              <Trash2 size={12} className="group-hover:scale-110 transition-transform" />
            </button>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
