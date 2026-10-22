import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { translateAction, translateSignal, formatPercent } from '@/utils/formatters';
import { getActionColor, getDisplayName, getSignalColor, getStatusIcon } from './output-tab-utils';
import { ReasoningContent } from './reasoning-content';

// Progress Section Component
function ProgressSection({ sortedAgents }: { sortedAgents: [string, any][] }) {
  const { t } = useTranslation();
  if (sortedAgents.length === 0) return null;

  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">{t('bottom_panel.output.progress')}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {sortedAgents.map(([agentId, data]) => {
            const { icon: StatusIcon, color } = getStatusIcon(data.status);
            const displayName = getDisplayName(agentId);
            
            return (
              <div key={agentId} className="flex items-center gap-2">
                <StatusIcon className={cn("h-4 w-4 flex-shrink-0", color)} />
                <span className="font-medium">{displayName}</span>
                {data.ticker && (
                  <span>[{data.ticker}]</span>
                )}
                <span className={cn("flex-1", color)}>
                  {data.message || data.status}
                </span>
                {data.timestamp && (
                  <span className="text-muted-foreground text-xs">
                    {new Date(data.timestamp).toLocaleTimeString()}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

// Summary Section Component
function SummarySection({ outputData }: { outputData: any }) {
  const { t } = useTranslation();
  if (!outputData) return null;

  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">{t('bottom_panel.output.summary')}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('nodes.investment_report.ticker')}</TableHead>
              <TableHead>{t('nodes.investment_report.action')}</TableHead>
              <TableHead>{t('nodes.investment_report.quantity')}</TableHead>
              <TableHead>{t('nodes.investment_report.confidence')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(outputData.decisions).map(([ticker, decision]: [string, any]) => (
              <TableRow key={ticker}>
                <TableCell className="font-medium">{ticker}</TableCell>
                <TableCell>
                  <span className={cn("font-medium", getActionColor(decision.action || ''))}>
                    {translateAction(decision.action)}
                  </span>
                </TableCell>
                <TableCell>{decision.quantity || 0}</TableCell>
                <TableCell>{formatPercent(decision.confidence, 1)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// Analysis Results Section Component
function AnalysisResultsSection({ outputData }: { outputData: any }) {
  const { t } = useTranslation();
  const [selectedTicker, setSelectedTicker] = useState<string>('');
  
  const tickers = outputData?.decisions ? Object.keys(outputData.decisions) : [];
  
  useEffect(() => {
    if (tickers.length > 0 && !selectedTicker) {
      setSelectedTicker(tickers[0]);
    }
  }, [tickers, selectedTicker]);

  if (!outputData) return null;
  if (tickers.length === 0) return null;

  return (
    <Card className="bg-transparent">
      <CardHeader>
        <CardTitle className="text-lg">{t('bottom_panel.output.analysis_results')}</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={selectedTicker} onValueChange={setSelectedTicker} className="w-full">
          <TabsList className="flex space-x-1 bg-muted p-1 rounded-lg mb-4">
            {tickers.map((ticker) => (
              <TabsTrigger 
                key={ticker} 
                value={ticker} 
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md transition-colors data-[state=active]:active-bg data-[state=active]:text-emerald-400 data-[state=active]:shadow-sm text-primary hover:text-primary hover-bg"
              >
                {ticker}
              </TabsTrigger>
            ))}
          </TabsList>
          
          {tickers.map((ticker) => {
            const decision = outputData.decisions![ticker];
            
            return (
              <TabsContent key={ticker} value={ticker} className="space-y-4">
                {/* Agent Analysis */}
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Agent</TableHead>
                      <TableHead>Signal</TableHead>
                      <TableHead>{t('nodes.investment_report.confidence')}</TableHead>
                      <TableHead>{t('nodes.investment_report.reasoning')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Object.entries(outputData.analyst_signals || {})
                      .filter(([agent, signals]: [string, any]) => 
                        ticker in signals && !agent.includes("risk_management")
                      )
                      .sort(([agentA], [agentB]) => agentA.localeCompare(agentB))
                      .map(([agent, signals]: [string, any]) => {
                        const signal = signals[ticker];
                        const signalType = signal.signal?.toLowerCase() || 'unknown';
                        const signalColor = getSignalColor(signalType);
                        
                        return (
                          <TableRow key={agent}>
                            <TableCell className="font-medium">
                              {getDisplayName(agent)}
                            </TableCell>
                            <TableCell>
                              <span className={cn("font-medium", signalColor)}>
                                {translateSignal(signalType)}
                              </span>
                            </TableCell>
                            <TableCell>{formatPercent(signal.confidence, 1)}</TableCell>
                            <TableCell className="max-w-md">
                              <ReasoningContent content={signal.reasoning} />
                            </TableCell>
                          </TableRow>
                        );
                      })}
                  </TableBody>
                </Table>
                
                {/* Risk Management Analysis */}
                {outputData.analyst_signals?.risk_management_agent?.[ticker] && (
                  <div>
                    <h4 className="text-md font-medium mb-2">Risk Management</h4>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Signal</TableHead>
                          <TableHead>{t('nodes.investment_report.confidence')}</TableHead>
                          <TableHead>{t('nodes.investment_report.reasoning')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(() => {
                          const riskSignal = outputData.analyst_signals.risk_management_agent[ticker];
                          const signalType = riskSignal.signal?.toLowerCase() || 'unknown';
                          const signalColor = getSignalColor(signalType);
                          
                          return (
                            <TableRow>
                              <TableCell>
                                <span className={cn("font-medium", signalColor)}>
                                  {translateSignal(signalType)}
                                </span>
                              </TableCell>
                              <TableCell>{formatPercent(riskSignal.confidence, 1)}</TableCell>
                              <TableCell className="max-w-md">
                                <ReasoningContent content={riskSignal.reasoning} />
                              </TableCell>
                            </TableRow>
                          );
                        })()}
                      </TableBody>
                    </Table>
                  </div>
                )}
                
                {/* Portfolio Manager Decision */}
                <div>
                  <h4 className="text-md font-medium mb-2">{t('nodes.portfolio_manager.title')}</h4>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('nodes.investment_report.action')}</TableHead>
                        <TableHead>{t('nodes.investment_report.quantity')}</TableHead>
                        <TableHead>{t('nodes.investment_report.confidence')}</TableHead>
                        <TableHead>{t('nodes.investment_report.reasoning')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      <TableRow>
                        <TableCell>
                          <span className={cn("font-medium", getActionColor(decision.action || ''))}>
                            {translateAction(decision.action)}
                          </span>
                        </TableCell>
                        <TableCell>{decision.quantity || 0}</TableCell>
                        <TableCell>{formatPercent(decision.confidence, 1)}</TableCell>
                        <TableCell className="max-w-md">
                          <ReasoningContent content={decision.reasoning} />
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>
            );
          })}
        </Tabs>
      </CardContent>
    </Card>
  );
}

interface RegularOutputProps {
  sortedAgents: [string, any][];
  outputData: any;
}

export function RegularOutput({ sortedAgents, outputData }: RegularOutputProps) {
  return (
    <div className="space-y-4">
      <ProgressSection sortedAgents={sortedAgents} />
      <SummarySection outputData={outputData} />
      <AnalysisResultsSection outputData={outputData} />
    </div>
  );
}
