import i18n from '@/i18n';
import { driver, DriveStep } from 'driver.js';
import 'driver.js/dist/driver.css';

export type TourType = 'quick' | 'feature';

export const ensureResearchDashboardActive = () => {
  const researchBtn = document.getElementById('tour-topbar-research');
  if (researchBtn) {
    researchBtn.click();
  }
};

export const startTour = (type: TourType = 'quick', onComplete?: () => void) => {
  const isEn = i18n.language === 'en-US';

  // 1. Immediately ensure Research Dashboard is active before starting tour
  ensureResearchDashboardActive();

  const quickSteps: DriveStep[] = [
    {
      element: '#tour-topbar-research',
      popover: {
        title: i18n.t('tour.quick_steps.step1_title'),
        description: i18n.t('tour.quick_steps.step1_desc'),
        side: 'bottom',
        align: 'start',
      },
      onHighlightStarted: () => {
        ensureResearchDashboardActive();
      },
    },
    {
      element: '#tour-research-search',
      popover: {
        title: i18n.t('tour.quick_steps.step2_title'),
        description: i18n.t('tour.quick_steps.step2_desc'),
        side: 'bottom',
        align: 'center',
      },
      onHighlightStarted: () => {
        ensureResearchDashboardActive();
      },
    },
    {
      element: '#tour-research-submit',
      popover: {
        title: i18n.t('tour.quick_steps.step3_title'),
        description: i18n.t('tour.quick_steps.step3_desc'),
        side: 'bottom',
        align: 'center',
      },
    },
    {
      element: '#tour-investor-grid',
      popover: {
        title: i18n.t('tour.quick_steps.step4_title'),
        description: i18n.t('tour.quick_steps.step4_desc'),
        side: 'top',
        align: 'center',
      },
    },
    {
      element: '#tour-user-guide',
      popover: {
        title: i18n.t('tour.quick_steps.step5_title'),
        description: i18n.t('tour.quick_steps.step5_desc'),
        side: 'bottom',
        align: 'end',
      },
    },
  ];

  const featureSteps: DriveStep[] = [
    {
      element: '#tour-topbar-research',
      popover: {
        title: i18n.t('tour.steps.research_tab.title'),
        description: i18n.t('tour.steps.research_tab.description'),
        side: 'bottom',
        align: 'start',
      },
      onHighlightStarted: () => {
        ensureResearchDashboardActive();
      },
    },
    {
      element: '#tour-research-search',
      popover: {
        title: i18n.t('tour.steps.stock_input.title'),
        description: i18n.t('tour.steps.stock_input.description'),
        side: 'bottom',
        align: 'center',
      },
    },
    {
      element: '#tour-investor-grid',
      popover: {
        title: i18n.t('tour.steps.investor_cards.title'),
        description: i18n.t('tour.steps.investor_cards.description'),
        side: 'top',
        align: 'center',
      },
    },
    {
      element: '#tour-corpus-health-tab',
      popover: {
        title: i18n.t('research.tabs.corpus_health'),
        description: i18n.t('research.corpus_health.subtitle'),
        side: 'bottom',
        align: 'start',
      },
    },
    {
      element: '#tour-snapshot-history-tab',
      popover: {
        title: i18n.t('research.tabs.snapshot_history'),
        description: i18n.t('research.snapshots.subtitle'),
        side: 'bottom',
        align: 'start',
      },
    },
    {
      element: '#tour-sidebar-toggle-left',
      popover: {
        title: i18n.t('topbar.toggle_left_sidebar'),
        description: i18n.t('flow.search_flows'),
        side: 'bottom',
        align: 'center',
      },
    },
    {
      element: '#tour-sidebar-toggle-right',
      popover: {
        title: i18n.t('topbar.toggle_right_sidebar'),
        description: i18n.t('flow.components_tip'),
        side: 'bottom',
        align: 'center',
      },
    },
    {
      element: '#tour-sidebar-toggle-bottom',
      popover: {
        title: i18n.t('topbar.toggle_bottom_panel'),
        description: i18n.t('bottom_panel.output.empty'),
        side: 'bottom',
        align: 'center',
      },
    },
    {
      element: '#tour-settings-btn',
      popover: {
        title: i18n.t('tour.steps.settings_tab.title'),
        description: i18n.t('tour.steps.settings_tab.description'),
        side: 'bottom',
        align: 'center',
      },
    },
    {
      element: '#tour-language-switcher',
      popover: {
        title: i18n.t('tour.steps.lang_switch.title'),
        description: i18n.t('tour.steps.lang_switch.description'),
        side: 'bottom',
        align: 'end',
      },
    },
    {
      element: '#tour-user-guide',
      popover: {
        title: i18n.t('tour.steps.help_btn.title'),
        description: i18n.t('tour.steps.help_btn.description'),
        side: 'bottom',
        align: 'end',
      },
    },
  ];

  const steps = type === 'quick' ? quickSteps : featureSteps;

  const driverObj = driver({
    animate: true,
    allowClose: true,
    overlayColor: 'rgba(0, 0, 0, 0.75)',
    stagePadding: 4,
    stageRadius: 6,
    smoothScroll: true,
    waitForElement: 3000,
    skipMissingElement: false,
    showProgress: true,
    nextBtnText: i18n.t('tour.controls.next', { defaultValue: isEn ? 'Next' : '下一步' }),
    prevBtnText: i18n.t('tour.controls.prev', { defaultValue: isEn ? 'Back' : '上一步' }),
    doneBtnText: i18n.t('tour.controls.done', { defaultValue: isEn ? 'Done' : '完成指引' }),
    progressText: '{{current}} / {{total}}',
    popoverClass: 'ai-hedge-fund-tour-popover',
    steps: steps,
    onDestroyed: () => {
      onComplete?.();
    },
  });

  // Short delay to allow React to mount the Research tab DOM if it was on a different tab
  setTimeout(() => {
    driverObj.drive();
  }, 120);
};
