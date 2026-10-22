import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import {
  AlignEndHorizontal,
  AlignEndVertical,
  AlignHorizontalDistributeCenter,
  AlignHorizontalJustifyCenter,
  AlignLeft,
  AlignStartHorizontal,
  AlignStartVertical,
  AlignVerticalDistributeCenter,
  Copy,
  CopyPlus,
  LayoutGrid,
  Trash2,
} from 'lucide-react';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlignmentType, DistributionAxis } from '@/services/flow-layout';

interface FlowSelectionToolbarProps {
  selectedCount: number;
  onCopy: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onAlign?: (alignment: AlignmentType) => void;
  onDistribute?: (axis: DistributionAxis) => void;
  onLayoutSelection?: () => void;
  className?: string;
}

export const FlowSelectionToolbar: React.FC<FlowSelectionToolbarProps> = ({
  selectedCount,
  onCopy,
  onDuplicate,
  onDelete,
  onAlign,
  onDistribute,
  onLayoutSelection,
  className = '',
}) => {
  const { t } = useTranslation();
  const [alignOpen, setAlignOpen] = useState(false);
  const [distributeOpen, setDistributeOpen] = useState(false);

  if (selectedCount < 2) return null;

  return (
    <div
      className={cn(
        "z-30 flex items-center gap-1.5 p-1.5 rounded-xl bg-zinc-900/95 border border-zinc-700/80 shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-top-2 duration-150",
        className
      )}
    >
      {/* Selected count pill */}
      <div className="px-2.5 py-1 rounded-md bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-semibold flex items-center gap-1">
        <span>{selectedCount}</span>
        <span className="font-normal text-[11px] text-zinc-300">
          {t('flow.selected_count', { defaultValue: '已选中' })}
        </span>
      </div>

      <div className="w-px h-4 bg-zinc-700 mx-0.5" />

      {/* Copy */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onCopy}
        className="h-7 px-2 gap-1 text-xs text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800"
        title={`${t('flow.copy', { defaultValue: '复制' })} (⌘C)`}
      >
        <Copy size={13} />
        <span className="hidden md:inline">{t('flow.copy', { defaultValue: '复制' })}</span>
      </Button>

      {/* Duplicate */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onDuplicate}
        className="h-7 px-2 gap-1 text-xs text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800"
        title={`${t('flow.duplicate', { defaultValue: '创建副本' })} (⌘D)`}
      >
        <CopyPlus size={13} />
        <span className="hidden md:inline">{t('flow.duplicate', { defaultValue: '创建副本' })}</span>
      </Button>

      {/* Align Popover */}
      {onAlign && (
        <Popover open={alignOpen} onOpenChange={setAlignOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 gap-1 text-xs text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800"
              title={t('flow.align', { defaultValue: '对齐' })}
            >
              <AlignLeft size={13} />
              <span className="hidden md:inline">{t('flow.align', { defaultValue: '对齐' })}</span>
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-44 p-1 bg-zinc-900 border-zinc-700 text-zinc-100 text-xs shadow-xl space-y-0.5">
            <button
              onClick={() => { onAlign('left'); setAlignOpen(false); }}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800 text-left transition-colors cursor-pointer"
            >
              <AlignStartHorizontal size={14} className="text-zinc-400" />
              <span>{t('flow.align_left', { defaultValue: '左对齐' })}</span>
            </button>
            <button
              onClick={() => { onAlign('center'); setAlignOpen(false); }}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800 text-left transition-colors cursor-pointer"
            >
              <AlignHorizontalJustifyCenter size={14} className="text-zinc-400" />
              <span>{t('flow.align_center', { defaultValue: '水平居中' })}</span>
            </button>
            <button
              onClick={() => { onAlign('right'); setAlignOpen(false); }}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800 text-left transition-colors cursor-pointer"
            >
              <AlignEndHorizontal size={14} className="text-zinc-400" />
              <span>{t('flow.align_right', { defaultValue: '右对齐' })}</span>
            </button>
            <div className="h-px bg-zinc-800 my-1" />
            <button
              onClick={() => { onAlign('top'); setAlignOpen(false); }}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800 text-left transition-colors cursor-pointer"
            >
              <AlignStartVertical size={14} className="text-zinc-400" />
              <span>{t('flow.align_top', { defaultValue: '顶部对齐' })}</span>
            </button>
            <button
              onClick={() => { onAlign('middle'); setAlignOpen(false); }}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800 text-left transition-colors cursor-pointer"
            >
              <AlignVerticalDistributeCenter size={14} className="text-zinc-400" />
              <span>{t('flow.align_middle', { defaultValue: '垂直居中' })}</span>
            </button>
            <button
              onClick={() => { onAlign('bottom'); setAlignOpen(false); }}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800 text-left transition-colors cursor-pointer"
            >
              <AlignEndVertical size={14} className="text-zinc-400" />
              <span>{t('flow.align_bottom', { defaultValue: '底部对齐' })}</span>
            </button>
          </PopoverContent>
        </Popover>
      )}

      {/* Distribute Popover (requires >= 3 nodes) */}
      {onDistribute && selectedCount >= 3 && (
        <Popover open={distributeOpen} onOpenChange={setDistributeOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 gap-1 text-xs text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800"
              title={t('flow.distribute', { defaultValue: '等间距分布' })}
            >
              <AlignHorizontalDistributeCenter size={13} />
              <span className="hidden md:inline">{t('flow.distribute', { defaultValue: '分布' })}</span>
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-44 p-1 bg-zinc-900 border-zinc-700 text-zinc-100 text-xs shadow-xl space-y-0.5">
            <button
              onClick={() => { onDistribute('horizontal'); setDistributeOpen(false); }}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800 text-left transition-colors cursor-pointer"
            >
              <AlignHorizontalDistributeCenter size={14} className="text-zinc-400" />
              <span>{t('flow.distribute_horizontally', { defaultValue: '水平等距分布' })}</span>
            </button>
            <button
              onClick={() => { onDistribute('vertical'); setDistributeOpen(false); }}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800 text-left transition-colors cursor-pointer"
            >
              <AlignVerticalDistributeCenter size={14} className="text-zinc-400" />
              <span>{t('flow.distribute_vertically', { defaultValue: '垂直等距分布' })}</span>
            </button>
          </PopoverContent>
        </Popover>
      )}

      {/* Layout Selection */}
      {onLayoutSelection && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onLayoutSelection}
          className="h-7 px-2 gap-1 text-xs text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800"
          title={t('flow.layout_selection', { defaultValue: '整理选中节点' })}
        >
          <LayoutGrid size={13} />
          <span className="hidden md:inline">{t('flow.layout_selection', { defaultValue: '整理' })}</span>
        </Button>
      )}

      <div className="w-px h-4 bg-zinc-700 mx-0.5" />

      {/* Batch Delete */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onDelete}
        className="h-7 px-2 gap-1 text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-950/40"
        title={`${t('flow.delete_selection', { defaultValue: '删除选中项' })} (⌫ / Delete)`}
      >
        <Trash2 size={13} />
        <span>{t('flow.delete', { defaultValue: '删除' })}</span>
      </Button>
    </div>
  );
};
