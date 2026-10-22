import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { BookOpen, CircleHelp, Command, Compass, Play } from 'lucide-react';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { startTour, TourType } from './tour-service';

interface HelpDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onStartTour?: (type: TourType) => void;
}

export const HelpDialog: React.FC<HelpDialogProps> = ({
  isOpen,
  onOpenChange,
  onStartTour,
}) => {
  const { t } = useTranslation();

  const handleLaunchTour = (type: TourType) => {
    onOpenChange(false);
    setTimeout(() => {
      if (onStartTour) {
        onStartTour(type);
      } else {
        startTour(type);
      }
    }, 300);
  };

  const faqItems = [
    {
      q: t('help_modal.faq_concepts.0.q'),
      a: t('help_modal.faq_concepts.0.a'),
    },
    {
      q: t('help_modal.faq_concepts.1.q'),
      a: t('help_modal.faq_concepts.1.a'),
    },
    {
      q: t('help_modal.faq_concepts.2.q'),
      a: t('help_modal.faq_concepts.2.a'),
    },
  ];

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-zinc-900 border border-zinc-700 text-zinc-100 shadow-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader className="space-y-1">
          <div className="flex items-center gap-2">
            <CircleHelp size={20} className="text-emerald-400" />
            <DialogTitle className="text-xl font-bold text-zinc-100">
              {t('help_modal.title')}
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-zinc-400">
            {t('help_modal.subtitle')}
          </DialogDescription>
        </DialogHeader>

        {/* Tour Launchers */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 my-3">
          <div className="p-4 rounded-lg bg-zinc-850/90 border border-zinc-700/80 hover:border-emerald-500/50 transition-all flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[11px]">
                  {t('topbar.quick_start')}
                </Badge>
              </div>
              <h4 className="font-semibold text-sm text-zinc-100 mb-1">
                {t('help_modal.quick_start_title')}
              </h4>
              <p className="text-xs text-zinc-400 leading-relaxed mb-4">
                {t('help_modal.quick_start_desc')}
              </p>
            </div>
            <Button
              size="sm"
              onClick={() => handleLaunchTour('quick')}
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs gap-1.5"
            >
              <Play size={13} />
              <span>{t('topbar.quick_start')}</span>
            </Button>
          </div>

          <div className="p-4 rounded-lg bg-zinc-850/90 border border-zinc-700/80 hover:border-blue-500/50 transition-all flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Badge className="bg-blue-500/20 text-blue-400 border border-blue-500/30 text-[11px]">
                  {t('topbar.feature_tour')}
                </Badge>
              </div>
              <h4 className="font-semibold text-sm text-zinc-100 mb-1">
                {t('help_modal.feature_tour_title')}
              </h4>
              <p className="text-xs text-zinc-400 leading-relaxed mb-4">
                {t('help_modal.feature_tour_desc')}
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleLaunchTour('feature')}
              className="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border-zinc-700 text-xs gap-1.5"
            >
              <Compass size={13} />
              <span>{t('topbar.feature_tour')}</span>
            </Button>
          </div>
        </div>

        {/* Shortcuts Cheat Sheet */}
        <div className="p-3.5 rounded-lg bg-zinc-950/60 border border-zinc-800 my-1">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300 mb-2">
            <Command size={14} className="text-zinc-400" />
            <span>快捷键导航 (Keyboard Shortcuts)</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-zinc-400">
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>撤回 (Undo)</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-emerald-400">⌘ Z</kbd>
            </div>
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>重做 (Redo)</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-emerald-400">⇧⌘ Z</kbd>
            </div>
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>复制 / 粘贴</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-zinc-300">⌘ C / V</kbd>
            </div>
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>创建副本</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-zinc-300">⌘ D</kbd>
            </div>
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>全选节点</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-zinc-300">⌘ A</kbd>
            </div>
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>适应画布</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-zinc-300">⌘ 0</kbd>
            </div>
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>删除选中项</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-rose-400">⌫ / 🗑</kbd>
            </div>
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>保存流程</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-zinc-300">⌘ S</kbd>
            </div>
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>左侧边栏</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-zinc-300">⌘ B</kbd>
            </div>
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>底部面板</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-zinc-300">⌘ J</kbd>
            </div>
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>右侧组件</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-zinc-300">⌘ I</kbd>
            </div>
            <div className="flex items-center justify-between p-1.5 rounded bg-zinc-900 border border-zinc-800">
              <span>系统设置</span>
              <kbd className="px-1.5 py-0.5 rounded bg-zinc-800 font-mono text-zinc-300">⌘ ,</kbd>
            </div>
          </div>
        </div>

        {/* FAQ Section */}
        <div className="mt-2 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
            <BookOpen size={14} className="text-zinc-400" />
            <span>{t('help_modal.faq_title')}</span>
          </div>
          <div className="space-y-2">
            {faqItems.map((item, idx) => (
              <div key={idx} className="p-3 rounded-md bg-zinc-850/60 border border-zinc-800">
                <h5 className="text-xs font-medium text-emerald-400 mb-1">{item.q}</h5>
                <p className="text-xs text-zinc-400 leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
