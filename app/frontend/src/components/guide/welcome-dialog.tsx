import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ONBOARDING_COMPLETED_KEY } from '@/i18n';
import { Bot, Compass, Play, Sparkles } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { startTour, TourType } from './tour-service';

interface WelcomeDialogProps {
  onStartTour?: (type: TourType) => void;
}

export const WelcomeDialog: React.FC<WelcomeDialogProps> = ({ onStartTour }) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    try {
      const hasCompleted = localStorage.getItem(ONBOARDING_COMPLETED_KEY);
      if (!hasCompleted) {
        // Show welcome dialog on first visit
        setIsOpen(true);
      }
    } catch (e) {
      console.warn('Unable to read onboarding status from localStorage', e);
    }
  }, []);

  const handleDismiss = () => {
    try {
      localStorage.setItem(ONBOARDING_COMPLETED_KEY, 'true');
    } catch (e) {
      console.warn('Unable to save onboarding status', e);
    }
    setIsOpen(false);
  };

  const handleStart = (type: TourType) => {
    handleDismiss();
    setTimeout(() => {
      if (onStartTour) {
        onStartTour(type);
      } else {
        startTour(type);
      }
    }, 300);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleDismiss()}>
      <DialogContent className="max-w-md bg-zinc-900 border border-zinc-700 text-zinc-100 shadow-2xl">
        <DialogHeader className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge className="bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 gap-1 text-xs">
              <Sparkles size={12} />
              {t('tour.welcome_modal.badge')}
            </Badge>
          </div>
          <DialogTitle className="text-xl font-bold tracking-tight text-zinc-100">
            {t('tour.welcome_modal.title')}
          </DialogTitle>
          <DialogDescription className="text-xs text-zinc-400">
            {t('tour.welcome_modal.subtitle')}
          </DialogDescription>
        </DialogHeader>

        <div className="py-3 text-sm text-zinc-300 leading-relaxed border-y border-zinc-800 my-2">
          <p>{t('tour.welcome_modal.description')}</p>
          <div className="grid grid-cols-2 gap-2.5 mt-3 pt-2">
            <div className="p-2.5 rounded-md bg-zinc-850/80 border border-zinc-800 text-xs text-zinc-400 flex items-start gap-2">
              <Bot size={16} className="text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>10+ Shadow 投资人策略与传统分析师 Agent</span>
            </div>
            <div className="p-2.5 rounded-md bg-zinc-850/80 border border-zinc-800 text-xs text-zinc-400 flex items-start gap-2">
              <Compass size={16} className="text-blue-400 flex-shrink-0 mt-0.5" />
              <span>前瞻因子评测与交互式 Flow 编排流水线</span>
            </div>
          </div>
        </div>

        <DialogFooter className="flex flex-col sm:flex-row gap-2 pt-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDismiss}
            className="text-xs text-zinc-400 hover:text-zinc-200"
          >
            {t('tour.welcome_modal.skip_btn')}
          </Button>
          <div className="flex items-center gap-2 ml-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleStart('feature')}
              className="text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border-zinc-700 gap-1.5"
            >
              <Compass size={14} />
              {t('tour.welcome_modal.feature_tour_btn')}
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => handleStart('quick')}
              className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white gap-1.5"
            >
              <Play size={14} />
              {t('tour.welcome_modal.quick_start_btn')}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
