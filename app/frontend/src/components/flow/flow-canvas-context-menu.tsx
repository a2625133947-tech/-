import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  ArrowRightLeft,
  Copy,
  CopyPlus,
  Maximize2,
  RotateCcw,
  SquareCheck,
  Trash2,
} from 'lucide-react';
import React, { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { LayoutDirection } from '@/services/flow-layout';

export interface ContextMenuTarget {
  type: 'node' | 'pane' | 'edge';
  id?: string;
  x: number;
  y: number;
}

interface FlowCanvasContextMenuProps {
  target: ContextMenuTarget | null;
  onClose: () => void;
  selectedCount: number;
  hasClipboard: boolean;
  onCopy: () => void;
  onPaste: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onSelectAll: () => void;
  onFitView: () => void;
  onResetView: () => void;
  onAutoLayout: (direction: LayoutDirection) => void;
}

export const FlowCanvasContextMenu: React.FC<FlowCanvasContextMenuProps> = ({
  target,
  onClose,
  selectedCount,
  hasClipboard,
  onCopy,
  onPaste,
  onDuplicate,
  onDelete,
  onSelectAll,
  onFitView,
  onResetView,
  onAutoLayout,
}) => {
  const { t } = useTranslation();
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (target) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [target, onClose]);

  if (!target) return null;

  const handleAction = (action: () => void) => {
    action();
    onClose();
  };

  // Adjust menu position to keep inside viewport
  const menuWidth = 190;
  const menuHeight = target.type === 'node' ? 140 : 210;
  const posX = Math.min(target.x, window.innerWidth - menuWidth - 10);
  const posY = Math.min(target.y, window.innerHeight - menuHeight - 10);

  return (
    <div
      ref={menuRef}
      className={cn(
        "fixed z-50 min-w-[190px] rounded-lg bg-zinc-900/95 border border-zinc-700/90 shadow-2xl backdrop-blur-md p-1 text-xs text-zinc-200",
        "animate-in fade-in-0 zoom-in-95 duration-100"
      )}
      style={{
        left: posX,
        top: posY,
      }}
    >
      {/* Node Context Menu */}
      {target.type === 'node' && (
        <div className="space-y-0.5">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-between h-7 px-2 text-zinc-200 hover:bg-zinc-800 hover:text-white"
            onClick={() => handleAction(onCopy)}
          >
            <span className="flex items-center gap-2">
              <Copy size={13} className="text-zinc-400" />
              <span>{t('flow.copy', { defaultValue: '复制' })}</span>
            </span>
            <kbd className="text-[10px] text-zinc-500 font-mono">⌘C</kbd>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-between h-7 px-2 text-zinc-200 hover:bg-zinc-800 hover:text-white"
            onClick={() => handleAction(onDuplicate)}
          >
            <span className="flex items-center gap-2">
              <CopyPlus size={13} className="text-zinc-400" />
              <span>{t('flow.duplicate', { defaultValue: '创建副本' })}</span>
            </span>
            <kbd className="text-[10px] text-zinc-500 font-mono">⌘D</kbd>
          </Button>

          <div className="w-full h-px bg-zinc-800 my-1" />

          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-between h-7 px-2 text-rose-400 hover:bg-rose-950/40 hover:text-rose-300"
            onClick={() => handleAction(onDelete)}
          >
            <span className="flex items-center gap-2">
              <Trash2 size={13} />
              <span>{selectedCount > 1 ? t('flow.delete_selection', { defaultValue: '删除选中项' }) : t('common.delete', { defaultValue: '删除' })}</span>
            </span>
            <kbd className="text-[10px] text-rose-500/70 font-mono">⌫</kbd>
          </Button>
        </div>
      )}

      {/* Edge Context Menu */}
      {target.type === 'edge' && (
        <div>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-between h-7 px-2 text-rose-400 hover:bg-rose-950/40 hover:text-rose-300"
            onClick={() => handleAction(onDelete)}
          >
            <span className="flex items-center gap-2">
              <Trash2 size={13} />
              <span>{t('flow.delete_edge', { defaultValue: '删除连线' })}</span>
            </span>
            <kbd className="text-[10px] text-rose-500/70 font-mono">⌫</kbd>
          </Button>
        </div>
      )}

      {/* Canvas Empty Area (Pane) Context Menu */}
      {target.type === 'pane' && (
        <div className="space-y-0.5">
          <Button
            variant="ghost"
            size="sm"
            disabled={!hasClipboard}
            className={cn(
              "w-full justify-between h-7 px-2 text-zinc-200 hover:bg-zinc-800 hover:text-white",
              !hasClipboard && "opacity-40 cursor-not-allowed hover:bg-transparent"
            )}
            onClick={() => handleAction(onPaste)}
          >
            <span className="flex items-center gap-2">
              <Copy size={13} className="text-zinc-400" />
              <span>{t('flow.paste', { defaultValue: '粘贴' })}</span>
            </span>
            <kbd className="text-[10px] text-zinc-500 font-mono">⌘V</kbd>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-between h-7 px-2 text-zinc-200 hover:bg-zinc-800 hover:text-white"
            onClick={() => handleAction(onSelectAll)}
          >
            <span className="flex items-center gap-2">
              <SquareCheck size={13} className="text-zinc-400" />
              <span>{t('flow.select_all', { defaultValue: '全选节点' })}</span>
            </span>
            <kbd className="text-[10px] text-zinc-500 font-mono">⌘A</kbd>
          </Button>

          <div className="w-full h-px bg-zinc-800 my-1" />

          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-between h-7 px-2 text-zinc-200 hover:bg-zinc-800 hover:text-white"
            onClick={() => handleAction(() => onAutoLayout('LR'))}
          >
            <span className="flex items-center gap-2">
              <ArrowRightLeft size={13} className="text-emerald-400" />
              <span>{t('flow.auto_layout', { defaultValue: '自动布局' })}</span>
            </span>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-between h-7 px-2 text-zinc-200 hover:bg-zinc-800 hover:text-white"
            onClick={() => handleAction(onFitView)}
          >
            <span className="flex items-center gap-2">
              <Maximize2 size={13} className="text-zinc-400" />
              <span>{t('flow.fit_view', { defaultValue: '适应画布' })}</span>
            </span>
            <kbd className="text-[10px] text-zinc-500 font-mono">⌘0</kbd>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-between h-7 px-2 text-zinc-200 hover:bg-zinc-800 hover:text-white"
            onClick={() => handleAction(onResetView)}
          >
            <span className="flex items-center gap-2">
              <RotateCcw size={13} className="text-zinc-400" />
              <span>{t('flow.reset_view', { defaultValue: '重置视图 (1:1)' })}</span>
            </span>
          </Button>
        </div>
      )}
    </div>
  );
};
