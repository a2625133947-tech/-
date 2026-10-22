import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import {
  ArrowDownUp,
  ArrowRightLeft,
  ChevronDown,
  Focus,
  Grid3X3,
  LayoutDashboard,
  Map,
  Maximize2,
  RotateCcw,
} from 'lucide-react';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LayoutDirection } from '@/services/flow-layout';

interface FlowViewportControlsProps {
  onFitView: () => void;
  onResetView: () => void;
  onCenterSelection?: () => void;
  onAutoLayout: (direction: LayoutDirection) => void;
  snapToGrid: boolean;
  onToggleSnapToGrid: () => void;
  showMiniMap: boolean;
  onToggleMiniMap: () => void;
  hasSelection?: boolean;
  className?: string;
  id?: string;
}

export const FlowViewportControls: React.FC<FlowViewportControlsProps> = ({
  onFitView,
  onResetView,
  onCenterSelection,
  onAutoLayout,
  snapToGrid,
  onToggleSnapToGrid,
  showMiniMap,
  onToggleMiniMap,
  hasSelection = false,
  className = '',
  id,
}) => {
  const { t } = useTranslation();
  const [layoutOpen, setLayoutOpen] = useState(false);

  return (
    <div
      id={id}
      className={cn(
        "z-20 flex items-center gap-1 p-1 rounded-lg bg-zinc-900/90 border border-zinc-700/80 shadow-xl backdrop-blur-md",
        className
      )}
    >
      {/* Auto Layout Direct Action Split Button */}
      <div className="flex items-center rounded-md bg-zinc-800/80 hover:bg-zinc-800 border border-zinc-700/60 transition-colors">
        {/* Main Click Button -> Runs Auto Layout IMMEDIATELY */}
        <button
          type="button"
          onClick={() => onAutoLayout('LR')}
          className="h-8 px-2.5 gap-1.5 text-xs text-zinc-200 hover:text-white flex items-center transition-colors cursor-pointer"
          title={`${t('flow.auto_layout', { defaultValue: '自动布局整理' })} (左到右)`}
        >
          <LayoutDashboard size={14} className="text-emerald-400" />
          <span className="font-medium hidden sm:inline">
            {t('flow.auto_layout', { defaultValue: '自动布局' })}
          </span>
        </button>

        {/* Dropdown chevron to pick direction */}
        <Popover open={layoutOpen} onOpenChange={setLayoutOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="h-8 px-1 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700/50 rounded-r border-l border-zinc-700/60 flex items-center justify-center cursor-pointer"
              title="选择布局流向"
              aria-label="Layout Options"
            >
              <ChevronDown size={12} />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-48 p-1 bg-zinc-900 border-zinc-700 text-zinc-100 text-xs shadow-xl space-y-0.5">
            <button
              onClick={() => { onAutoLayout('LR'); setLayoutOpen(false); }}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded hover:bg-zinc-800 text-left transition-colors cursor-pointer"
            >
              <ArrowRightLeft size={14} className="text-emerald-400" />
              <span>{t('flow.layout_lr', { defaultValue: '水平流向 (左到右)' })}</span>
            </button>
            <button
              onClick={() => { onAutoLayout('TB'); setLayoutOpen(false); }}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded hover:bg-zinc-800 text-left transition-colors cursor-pointer"
            >
              <ArrowDownUp size={14} className="text-blue-400" />
              <span>{t('flow.layout_tb', { defaultValue: '垂直流向 (上到下)' })}</span>
            </button>
          </PopoverContent>
        </Popover>
      </div>

      <div className="w-px h-4 bg-zinc-700/80 my-auto" />

      {/* Fit View */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onFitView}
        className="h-8 w-8 p-0 text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800"
        title={`${t('flow.fit_view', { defaultValue: '适应画布' })} (⌘0)`}
        aria-label="Fit View"
      >
        <Maximize2 size={14} />
      </Button>

      {/* Center Selection */}
      {hasSelection && onCenterSelection && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onCenterSelection}
          className="h-8 w-8 p-0 text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800"
          title={t('flow.center_selection', { defaultValue: '居中选中内容' })}
          aria-label="Center Selection"
        >
          <Focus size={14} className="text-emerald-400" />
        </Button>
      )}

      {/* Reset View (zoom 1:1) */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onResetView}
        className="h-8 w-8 p-0 text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800"
        title={t('flow.reset_view', { defaultValue: '重置视图 (1:1)' })}
        aria-label="Reset View"
      >
        <RotateCcw size={14} />
      </Button>

      <div className="w-px h-4 bg-zinc-700/80 my-auto" />

      {/* Snap to Grid Toggle */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onToggleSnapToGrid}
        className={cn(
          "h-8 w-8 p-0 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors",
          snapToGrid && "text-emerald-400 bg-emerald-500/15 border border-emerald-500/30"
        )}
        title={`${t('flow.snap_to_grid', { defaultValue: '网格吸附' })}: ${snapToGrid ? 'ON' : 'OFF'}`}
        aria-label="Toggle Snap to Grid"
      >
        <Grid3X3 size={14} />
      </Button>

      {/* MiniMap Toggle */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onToggleMiniMap}
        className={cn(
          "h-8 w-8 p-0 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors",
          showMiniMap && "text-blue-400 bg-blue-500/15 border border-blue-500/30"
        )}
        title={`${t('flow.minimap', { defaultValue: '小地图' })}: ${showMiniMap ? 'ON' : 'OFF'}`}
        aria-label="Toggle MiniMap"
      >
        <Map size={14} />
      </Button>
    </div>
  );
};
