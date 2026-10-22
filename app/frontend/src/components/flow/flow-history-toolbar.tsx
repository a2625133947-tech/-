import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Redo2, Undo2 } from 'lucide-react';
import React from 'react';
import { useTranslation } from 'react-i18next';

interface FlowHistoryToolbarProps {
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  className?: string;
  id?: string;
}

export const FlowHistoryToolbar: React.FC<FlowHistoryToolbarProps> = ({
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  className = '',
  id,
}) => {
  const { t } = useTranslation();
  const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform);

  const undoShortcut = isMac ? '⌘Z' : 'Ctrl+Z';
  const redoShortcut = isMac ? '⇧⌘Z' : 'Ctrl+Y / Ctrl+Shift+Z';

  return (
    <div
      id={id}
      className={cn(
        "z-20 flex items-center gap-1 p-1 rounded-lg bg-zinc-900/90 border border-zinc-700/80 shadow-xl backdrop-blur-md",
        className
      )}
    >
      {/* Undo Button */}
      <Button
        variant="ghost"
        size="sm"
        disabled={!canUndo}
        onClick={onUndo}
        className={cn(
          "h-8 px-2.5 gap-1.5 text-xs text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800 transition-colors",
          !canUndo && "opacity-40 cursor-not-allowed hover:bg-transparent hover:text-zinc-300"
        )}
        title={`${t('flow.undo', { defaultValue: '撤回' })} (${undoShortcut})`}
        aria-label="Undo"
      >
        <Undo2 size={14} className={canUndo ? "text-emerald-400" : "text-zinc-500"} />
        <span className="font-medium hidden sm:inline">{t('flow.undo', { defaultValue: '撤回' })}</span>
      </Button>

      <div className="w-px h-4 bg-zinc-700/80 my-auto" />

      {/* Redo Button */}
      <Button
        variant="ghost"
        size="sm"
        disabled={!canRedo}
        onClick={onRedo}
        className={cn(
          "h-8 px-2.5 gap-1.5 text-xs text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800 transition-colors",
          !canRedo && "opacity-40 cursor-not-allowed hover:bg-transparent hover:text-zinc-300"
        )}
        title={`${t('flow.redo', { defaultValue: '重做' })} (${redoShortcut})`}
        aria-label="Redo"
      >
        <Redo2 size={14} className={canRedo ? "text-emerald-400" : "text-zinc-500"} />
        <span className="font-medium hidden sm:inline">{t('flow.redo', { defaultValue: '重做' })}</span>
      </Button>
    </div>
  );
};
