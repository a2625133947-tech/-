import React, { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronRight, Code2, CheckCircle2, ShieldCheck, Database, FileText } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FinancialReportLink } from '@/components/common/FinancialReportLink';

interface AnalystDossierCardProps {
  agentName: string;
  signalData: any;
}

export const AnalystDossierCard: React.FC<AnalystDossierCardProps> = ({ agentName, signalData }) => {
  const [showRawJson, setShowRawJson] = useState(false);

  if (!signalData) return null;

  const signal = signalData.signal || 'neutral';
  const confidence = typeof signalData.confidence === 'number' ? signalData.confidence : 50;

  const getSignalBadge = (sig: string) => {
    if (sig === 'bullish') return <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">看多 Bullish</Badge>;
    if (sig === 'bearish') return <Badge className="bg-rose-500/20 text-rose-400 border-rose-500/30">看空 Bearish</Badge>;
    if (sig === 'insufficient_evidence') return <Badge variant="outline" className="text-amber-400 border-amber-500/40">证据不足 Insufficient</Badge>;
    return <Badge variant="outline" className="text-zinc-300">中性 Neutral</Badge>;
  };

  const summaryText = signalData.summary || (typeof signalData.reasoning === 'string' ? signalData.reasoning : '');
  const keyFindings: string[] = signalData.key_findings || [];
  const evidenceList: any[] = signalData.evidence || [];
  const bullCase: string[] = signalData.bull_case || signalData.strengths || [];
  const bearCase: string[] = signalData.bear_case || signalData.risks || [];
  const dataQuality = signalData.data_quality;

  // Determine what raw data to show in debug viewer
  const rawPayload = signalData._raw_reasoning || signalData.reasoning || signalData;

  return (
    <Card className="border border-border/60 bg-card/60 backdrop-blur-sm overflow-hidden shadow-sm">
      <CardHeader className="bg-muted/40 py-3 px-4 border-b border-border/40">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base font-semibold text-foreground tracking-tight">
              {agentName}
            </CardTitle>
            {dataQuality?.source && (
              <Badge variant="secondary" className="text-[11px] px-2 py-0.5 font-normal text-muted-foreground flex items-center gap-1">
                <Database size={10} />
                {dataQuality.source}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            {getSignalBadge(signal)}
            <Badge variant="outline" className="font-mono text-xs">
              置信度 {confidence.toFixed(0)}%
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-4 space-y-4">
        {/* Human-readable Narrative / Summary */}
        {summaryText && (
          <div className="text-sm leading-relaxed text-foreground bg-muted/40 p-3.5 rounded-lg border border-border">
            <p className="whitespace-pre-line font-medium leading-relaxed">{summaryText}</p>
          </div>
        )}

        {/* Key Findings List */}
        {keyFindings.length > 0 && (
          <div className="space-y-1.5">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <CheckCircle2 size={13} className="text-emerald-500" /> 核心量化事实与推论
            </h4>
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
              {keyFindings.map((finding, idx) => (
                <li key={idx} className="flex items-start gap-1.5 p-2.5 rounded-md bg-muted/30 border border-border text-zinc-800 dark:text-zinc-200">
                  <span className="text-muted-foreground font-mono font-bold">{idx + 1}.</span>
                  <span className="leading-normal">{finding}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Official Filing Citation (if available) */}
        {(signalData.latest_report || (signalData.sources && signalData.sources.length > 0)) && (
          <div className="space-y-1.5 p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20 text-xs">
            <span className="font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
              <FileText size={13} /> 法定披露依据与财报原文 (Official Filing Source)
            </span>
            <div className="pt-1">
              <FinancialReportLink
                report={signalData.latest_report || signalData.sources[0]}
                mode="compact"
              />
            </div>
          </div>
        )}

        {/* Structured Evidence Table/Cards */}
        {evidenceList.length > 0 && (
          <div className="space-y-1.5">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck size={13} className="text-blue-500" /> 专业指标证据矩阵
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {evidenceList.map((item, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-card border border-border flex flex-col justify-between shadow-xs">
                  <div className="flex items-center justify-between gap-1 text-[11px] text-muted-foreground">
                    <span className="font-semibold truncate text-foreground">{item.metric}</span>
                    <span className="text-[10px] text-muted-foreground/80">{item.source || '基础数据'}</span>
                  </div>
                  <div className="my-1.5 text-base font-bold text-foreground font-mono">
                    {item.value}
                  </div>
                  <div className="text-[11px] text-muted-foreground line-clamp-1">
                    {item.interpretation}
                  </div>
                  {item.report_ref && (
                    <div className="pt-2 mt-1 border-t border-border/40 text-[10px]">
                      <FinancialReportLink report={item.report_ref} mode="compact" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Bull & Bear Drivers */}
        {(bullCase.length > 0 || bearCase.length > 0) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1 text-xs">
            {bullCase.length > 0 && (
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                <span className="font-semibold text-emerald-700 dark:text-emerald-400 block mb-1">多头支撑要点：</span>
                <ul className="space-y-1 text-zinc-800 dark:text-zinc-200">
                  {bullCase.map((b, i) => <li key={i} className="flex items-start gap-1"><span className="text-emerald-600 font-bold">•</span> {b}</li>)}
                </ul>
              </div>
            )}
            {bearCase.length > 0 && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30">
                <span className="font-semibold text-rose-700 dark:text-rose-400 block mb-1">空头/风险关注：</span>
                <ul className="space-y-1 text-zinc-800 dark:text-zinc-200">
                  {bearCase.map((b, i) => <li key={i} className="flex items-start gap-1"><span className="text-rose-600 font-bold">•</span> {b}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Raw Machine JSON Section (Collapsible, default closed) */}
        <div className="pt-2 border-t border-border/40">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowRawJson(!showRawJson)}
            className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground gap-1.5"
          >
            <Code2 size={13} />
            <span>原始分析数据 (Raw Analysis JSON)</span>
            {showRawJson ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
          </Button>

          {showRawJson && (
            <div className="mt-2 rounded-md overflow-hidden border border-zinc-800 text-xs">
              <SyntaxHighlighter
                language="json"
                style={vscDarkPlus}
                customStyle={{
                  margin: 0,
                  padding: '12px',
                  fontSize: '0.75rem',
                  lineHeight: '1.4',
                  backgroundColor: '#0d1117'
                }}
              >
                {JSON.stringify(rawPayload, null, 2)}
              </SyntaxHighlighter>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
