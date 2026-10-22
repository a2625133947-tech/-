import { cn } from '@/lib/utils';
import { getStatusColor } from '../utils';
import { useTranslation } from 'react-i18next';

interface OutputNodeStatusProps {
  isProcessing: boolean;
  isAnyAgentRunning: boolean;
  isOutputAvailable: boolean;
  isConnected: boolean;
  onViewOutput?: () => void;
  processingText?: string;
  completingText?: string;
  availableText?: string;
  idleText?: string;
}

export function OutputNodeStatus({
  isProcessing,
  isAnyAgentRunning,
  isOutputAvailable,
  isConnected: _isConnected,
  onViewOutput,
  processingText,
  completingText,
  availableText,
  idleText
}: OutputNodeStatusProps) {
  const { t } = useTranslation();

  const pText = processingText || t('nodes.output_status.in_progress');
  const cText = completingText || t('nodes.output_status.completing');
  const aText = availableText || t('nodes.output_status.view_output');
  const iText = idleText || t('nodes.output_status.idle');

  // Determine the current state and appropriate styling
  const isLocallyProcessing = isProcessing; // Connected agents are running
  const isGloballyProcessing = !isProcessing && isAnyAgentRunning; // Other agents running
  const hasGradientAnimation = isLocallyProcessing || isGloballyProcessing;
  const isClickable = isOutputAvailable && !isLocallyProcessing && !isGloballyProcessing;
  
  // Determine display text based on current state
  let displayText: string;
  if (isLocallyProcessing) {
    displayText = pText;
  } else if (isGloballyProcessing) {
    displayText = cText;
  } else if (isOutputAvailable) {
    displayText = aText;
  } else {
    displayText = iText;
  }

  const status = hasGradientAnimation ? 'IN_PROGRESS' : 'IDLE';

  return (
    <div 
      className={cn(
        "text-foreground text-xs rounded p-2 border border-status transition-colors",
        hasGradientAnimation ? "gradient-animation" : getStatusColor(status),
        isClickable && "bg-primary text-primary-foreground cursor-pointer hover:bg-primary/80",
        !isOutputAvailable && !hasGradientAnimation && "opacity-50"
      )}
      onClick={isClickable ? onViewOutput : undefined}
    >
      {hasGradientAnimation ? (
        <div className="flex items-center gap-2 justify-center">
          <span>{displayText}</span>
        </div>
      ) : (
        <span>{displayText}</span>
      )}
    </div>
  );
}
