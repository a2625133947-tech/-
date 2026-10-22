import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { CircleHelp, FlaskConical, PanelBottom, PanelLeft, PanelRight, Settings } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { HelpDialog } from '../guide/help-dialog';
import { LanguageSwitcher } from './language-switcher';

interface TopBarProps {
  isLeftCollapsed: boolean;
  isRightCollapsed: boolean;
  isBottomCollapsed: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onToggleBottom: () => void;
  onSettingsClick: () => void;
  onResearchClick?: () => void;
}

export function TopBar({
  isLeftCollapsed,
  isRightCollapsed,
  isBottomCollapsed,
  onToggleLeft,
  onToggleRight,
  onToggleBottom,
  onSettingsClick,
  onResearchClick,
}: TopBarProps) {
  const { t } = useTranslation();
  const [isHelpOpen, setIsHelpOpen] = useState(false);

  return (
    <>
      <div className="absolute top-0 right-0 z-40 flex items-center gap-1.5 py-1 px-2.5 bg-panel/85 backdrop-blur-sm border-b border-border/40">
        {/* Research Dashboard Button */}
        {onResearchClick && (
          <Button
            id="tour-topbar-research"
            variant="ghost"
            size="sm"
            onClick={onResearchClick}
            className="h-8 px-2.5 gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/40 border border-emerald-500/30 transition-colors mr-0.5"
            aria-label={t('topbar.research_dashboard')}
            title={t('topbar.research_dashboard_desc')}
          >
            <FlaskConical size={14} className="text-emerald-400" />
            <span className="font-medium hidden sm:inline">{t('topbar.research_dashboard')}</span>
          </Button>
        )}

        {/* User Guide / Help Button */}
        <Button
          id="tour-user-guide"
          variant="ghost"
          size="sm"
          onClick={() => setIsHelpOpen(true)}
          className="h-8 px-2 gap-1.5 text-xs text-amber-400 hover:text-amber-300 hover:bg-amber-950/30 border border-amber-500/20 transition-colors"
          aria-label={t('topbar.user_guide')}
          title={t('topbar.user_guide_tooltip')}
        >
          <CircleHelp size={14} className="text-amber-400" />
          <span className="font-medium hidden md:inline">{t('topbar.user_guide')}</span>
        </Button>

        {/* Language Switcher */}
        <LanguageSwitcher />

        {/* Divider */}
        <div className="w-px h-4 bg-ramp-grey-700 mx-0.5" />

        {/* Left Sidebar Toggle */}
        <Button
          id="tour-sidebar-toggle-left"
          variant="ghost"
          size="sm"
          onClick={onToggleLeft}
          className={cn(
            "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
            !isLeftCollapsed && "text-foreground bg-ramp-grey-800"
          )}
          aria-label={t('topbar.toggle_left_sidebar')}
          title={t('topbar.toggle_left_sidebar')}
        >
          <PanelLeft size={16} />
        </Button>

        {/* Bottom Panel Toggle */}
        <Button
          id="tour-sidebar-toggle-bottom"
          variant="ghost"
          size="sm"
          onClick={onToggleBottom}
          className={cn(
            "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
            !isBottomCollapsed && "text-foreground bg-ramp-grey-800"
          )}
          aria-label={t('topbar.toggle_bottom_panel')}
          title={t('topbar.toggle_bottom_panel')}
        >
          <PanelBottom size={16} />
        </Button>

        {/* Right Sidebar Toggle */}
        <Button
          id="tour-sidebar-toggle-right"
          variant="ghost"
          size="sm"
          onClick={onToggleRight}
          className={cn(
            "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
            !isRightCollapsed && "text-foreground bg-ramp-grey-800"
          )}
          aria-label={t('topbar.toggle_right_sidebar')}
          title={t('topbar.toggle_right_sidebar')}
        >
          <PanelRight size={16} />
        </Button>

        {/* Divider */}
        <div className="w-px h-4 bg-ramp-grey-700 mx-0.5" />

        {/* Settings */}
        <Button
          id="tour-settings-btn"
          variant="ghost"
          size="sm"
          onClick={onSettingsClick}
          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
          aria-label={t('topbar.settings')}
          title={t('topbar.settings')}
        >
          <Settings size={16} />
        </Button>
      </div>

      <HelpDialog
        isOpen={isHelpOpen}
        onOpenChange={setIsHelpOpen}
      />
    </>
  );
}
