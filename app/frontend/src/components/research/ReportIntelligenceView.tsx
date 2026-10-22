import React, { useEffect, useRef, useState } from 'react';
import { SecuritySearchInput } from '@/components/common/SecuritySearchInput';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { formatResearchText } from '@/utils/research-text';
import { ResearchCitation, ResearchClaim, ResearchIntelligence, ResearchPeriod, ResearchTask, ResearchValue, reportIntelligenceApi, safeResearchLink } from '@/services/report-intelligence-api';

const STAGES: Record<string, string> = { PENDING: '等待执行', DISCOVERING: '发现研报', DOWNLOADING: '下载原文',
  PARSING: '解析正文与去重', SUMMARIZING: '提取观点', VERIFYING: '核验引用', COMPLETED: '完成', PARTIAL: '部分完成', FAILED: '失败' };
const PERIODS: [ResearchPeriod, string][] = [['week', '过去一周'], ['month', '过去一月'], ['year', '过去一年'], ['custom', '自定义']];

export const ReportIntelligenceView: React.FC = () => {
  const [query, setQuery] = useState('600519');
  const [period, setPeriod] = useState<ResearchPeriod>('month');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [useLlm, setUseLlm] = useState(false);
  const [task, setTask] = useState<ResearchTask | null>(null);
  const [result, setResult] = useState<ResearchIntelligence | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [citation, setCitation] = useState<ResearchCitation | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);
  const cancelView = () => { controller.current?.abort(); setBusy(false); setTask(null); setResult(null); setError(''); };
  const updateDate = (field: 'start' | 'end', value: string) => {
    if (value === (field === 'start' ? start : end)) return;
    cancelView();
    if (field === 'start') setStart(value); else setEnd(value);
  };

  const analyze = async (refresh = false, regenerate = false) => {
    controller.current?.abort();
    const current = new AbortController(); controller.current = current;
    setBusy(true); setError(''); setResult(null); setTask(null);
    try {
      let next = await reportIntelligenceApi.start(query, { period, ...(period === 'custom' ? { start, end } : {}),
        use_llm: useLlm, refresh_discovery: refresh, regenerate_summary: regenerate }, current.signal);
      while (!current.signal.aborted) {
        setTask(next);
        if (['COMPLETED', 'PARTIAL', 'FAILED'].includes(next.status)) {
          if (next.result) setResult(next.result);
          else setError(next.errors.map(e => `${e.stage}: ${e.error}`).join('；') || '任务未生成可用结果');
          break;
        }
        await new Promise<void>(resolve => {
          const done = () => { clearTimeout(timer); current.signal.removeEventListener('abort', done); resolve(); };
          const timer = setTimeout(done, 1000); current.signal.addEventListener('abort', done, { once: true });
        });
        if (!current.signal.aborted) next = await reportIntelligenceApi.task(next.task_id, current.signal);
      }
    } catch (err) {
      if (!current.signal.aborted) setError(err instanceof Error ? err.message : String(err));
    } finally { if (!current.signal.aborted) setBusy(false); }
  };

  const refs = (ids: string[]) => ids.map(id => {
    const evidence = result?.citations.find(c => c.citation_id === id);
    if (!evidence) return null;
    const index = (result?.reports.findIndex(r => r.canonical_report_id === evidence.report_id) ?? -1) + 1;
    return <button type="button" key={id} className="inline-block whitespace-nowrap text-emerald-400 underline text-xs ml-2" onClick={() => setCitation(evidence)}>[R{index} · {evidence.page ? `p${evidence.page}` : '段落'}]</button>;
  });

  const claims = (title: string, values: ResearchClaim[]) => <Card>
    <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>
    <CardContent>{values.length ? <ul className="space-y-3">{values.map((v, i) => <li key={i} className="text-sm leading-relaxed whitespace-normal break-words text-left">{formatResearchText(v.claim)}{refs(v.citations)}</li>)}</ul>
      : <p className="text-sm text-muted-foreground">INSUFFICIENT_EVIDENCE · 当前原文不足以支持这一结论。</p>}</CardContent>
  </Card>;

  const values = (title: string, rows: ResearchValue[]) => <Card>
    <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>
    <CardContent>{rows.length ? <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left border-b"><th className="p-2">机构</th><th>指标</th><th>年度</th><th>原始值</th><th>证据</th></tr></thead>
      <tbody>{rows.map((v, i) => <tr key={i} className="border-b"><td className="p-2">{result?.citations.find(c => c.citation_id === v.citations[0])?.institution}</td><td>{v.metric}</td><td>{v.year ?? '未明确'}</td><td>{typeof v.value === 'string' ? formatResearchText(v.value) : v.value} {v.unit}</td><td>{refs(v.citations)}</td></tr>)}</tbody></table></div>
      : <p className="text-muted-foreground text-sm">原文没有可核实的明确数据。</p>}</CardContent>
  </Card>;

  return <div className="space-y-5 pb-12">
    <Card><CardHeader><CardTitle>研报分析 · Research Intelligence</CardTitle></CardHeader><CardContent>
      <form className="flex flex-wrap gap-3 items-center" onSubmit={e => { e.preventDefault(); void analyze(); }}>
        <div className="min-w-[250px] flex-1 max-w-md"><SecuritySearchInput value={query} onChange={value => { cancelView(); setQuery(value); }}
          onSelectSecurity={security => { cancelView(); setQuery(security.canonical_symbol); }} placeholder="股票代码或名称，如 600519 / 贵州茅台 / Apple" /></div>
        <Button type="submit" disabled={busy || !query.trim() || (period === 'custom' && (!start || !end))}>检索与分析</Button>
        <Button type="button" variant="outline" disabled={busy} onClick={() => void analyze(true)}>更新来源</Button>
        <Button type="button" variant="outline" disabled={busy} onClick={() => void analyze(false, true)}>重新生成摘要</Button>
      </form>
      <div className="flex flex-wrap items-center gap-2 mt-4">{PERIODS.map(([value, label]) => <Button key={value} type="button" size="sm" variant={period === value ? 'default' : 'outline'}
        onClick={() => { cancelView(); setPeriod(value); }}>{label}</Button>)}
        {period === 'custom' && <><input aria-label="开始日期" type="date" value={start} onChange={e => updateDate('start', e.target.value)} onInput={e => updateDate('start', e.currentTarget.value)} onBlur={e => updateDate('start', e.currentTarget.value)} className="bg-transparent border rounded p-1" />
          <span>至</span><input aria-label="结束日期" type="date" value={end} onChange={e => updateDate('end', e.target.value)} onInput={e => updateDate('end', e.currentTarget.value)} onBlur={e => updateDate('end', e.currentTarget.value)} className="bg-transparent border rounded p-1" /></>}
        <label className="text-xs text-muted-foreground ml-auto flex gap-2"><input type="checkbox" checked={useLlm} onChange={e => { cancelView(); setUseLlm(e.target.checked); }} />使用已配置模型提取原文观点</label>
      </div>
      <p className="text-xs text-muted-foreground mt-3">只使用成功读取的研报原文。默认保留可核实摘录；引用可展开查看页码与原文。A 股使用东方财富，美股研报需要已配置的授权来源。</p>
      {task && <div role="status" className="mt-4 text-sm">{STAGES[task.status] || task.status} · {task.progress.completed}/{task.progress.total} · 任务 {task.task_id.slice(0, 8)}</div>}
      {error && <p role="alert" className="mt-3 text-red-400">{error}</p>}
    </CardContent></Card>

    {result && <>
      <Card><CardHeader><CardTitle>{result.company_name} / {result.ticker} / {result.exchange}</CardTitle></CardHeader><CardContent>
        <p>{result.period.start} ～ {result.period.end} · Evidence Coverage: <strong>{result.coverage.level}</strong> · {result.status}</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">{[
          ['发现', result.coverage.discovered], ['去重后', result.coverage.unique_reports], ['全文', result.coverage.full_text], ['仅摘要', result.coverage.abstract_only],
          ['无法读取', result.coverage.failed], ['重复', result.coverage.duplicates], ['分析研报', result.report_count], ['机构', result.institutions.length],
        ].map(([label, value]) => <div key={label} className="border rounded p-3"><span className="text-xs text-muted-foreground">{label}</span><div className="text-xl">{value}</div></div>)}</div>
        <p className="mt-3 text-sm">证据覆盖 {(result.coverage.evidence_coverage * 100).toFixed(1)}% · 来源多样性 {(result.coverage.source_diversity * 100).toFixed(1)}% · 观点一致性：{result.coverage.source_agreement === null ? '证据不足，未计算' : result.coverage.source_agreement} · 有研报日期占比 {(result.coverage.time_coverage * 100).toFixed(1)}%</p>
        {!result.coverage.discovery_complete && <p className="text-amber-400 text-sm mt-2">来源检索不完整，详见错误记录。</p>}
        <details className="mt-3 text-xs text-muted-foreground"><summary>覆盖度计算方法</summary>{Object.entries(result.coverage.formulas).map(([key, formula]) => <p key={key} className="mt-2">{key}: {formula}</p>)}</details>
      </CardContent></Card>
      {claims('市场共识', result.consensus)}
      {claims('分歧观点', result.disagreements)}
      {values('原始评级', result.ratings)}
      {values('明确目标价', result.target_prices)}
      {Object.keys(result.target_price_statistics).length > 0 && <Card><CardHeader><CardTitle className="text-base">目标价统计</CardTitle></CardHeader><CardContent>{Object.entries(result.target_price_statistics).map(([key, s]) => <p key={key} className="text-sm">{s.currency} · {s.year ?? '年度未明确'} · {s.count} 篇 · 最低 {s.min} · 最高 {s.max} · 均值 {s.mean.toFixed(2)} · 中位数 {s.median}{refs(s.citations)}</p>)}</CardContent></Card>}
      {values('盈利预测对照', result.earnings_forecasts)}
      {claims('高频主题与核心观点摘录', result.themes)}
      {claims('催化剂', result.catalysts)}
      {claims('主要风险', result.risks)}
      {claims('同机构同口径观点变化证据', result.changes)}
      <Card><CardHeader><CardTitle className="text-base">时间线</CardTitle></CardHeader><CardContent><div className="space-y-3">{result.timeline.map(item => <div key={item.report_id} className="border-l-2 border-emerald-600 pl-3"><p className="text-xs text-muted-foreground">{item.date} · {item.institution}</p>{item.claims.map((v, i) => <p key={i} className="text-sm leading-relaxed whitespace-normal break-words text-left mt-1">{formatResearchText(v.claim)}{refs(v.citations)}</p>)}</div>)}</div></CardContent></Card>
      <Card><CardHeader><CardTitle className="text-base">研报列表</CardTitle></CardHeader><CardContent><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left border-b"><th className="p-2">研报标题 / 原文</th><th>机构 / 分析师</th><th>原文日期</th><th>原始评级</th><th>目标价</th><th>来源</th><th>正文状态</th></tr></thead><tbody>
        {result.reports.map((r, i) => <tr key={r.canonical_report_id} className="border-b align-top"><td className="p-2 min-w-[240px]">[R{i + 1}] <a href={safeResearchLink(r.pdf_url || r.source_url)} target="_blank" rel="noopener noreferrer" className="text-emerald-400 underline">{r.title}</a>
          <details className="text-xs mt-1"><summary>全部来源</summary>{r.source_urls.map(url => <a key={url} href={safeResearchLink(url)} target="_blank" rel="noopener noreferrer" className="block break-all">{url}</a>)}</details></td>
          <td>{r.institution}<div className="text-xs">{r.analyst.join('、') || '未提供'}</div></td><td className="whitespace-nowrap">{r.published_at}{r.provider_published_at && r.provider_published_at !== r.published_at && <p className="text-xs text-muted-foreground">网站登记 {r.provider_published_at}</p>}</td>
          <td>{formatResearchText(String(result.ratings.find(v => v.citations.some(cid => result.citations.find(c => c.citation_id === cid)?.report_id === r.canonical_report_id))?.value || '未核实'))}</td>
          <td>{result.target_prices.filter(v => v.citations.some(cid => result.citations.find(c => c.citation_id === cid)?.report_id === r.canonical_report_id)).map(v => `${v.value}${v.unit}`).join(' / ') || '未提供'}</td>
          <td>{r.source_provider}</td><td>{r.content_kind === 'full_text' ? '全文' : r.content_kind === 'abstract' ? '仅摘要' : '读取失败'}</td></tr>)}
      </tbody></table></div></CardContent></Card>
      {result.errors.length > 0 && <Card><CardHeader><CardTitle className="text-base">来源与文档错误</CardTitle></CardHeader><CardContent>{result.errors.map((e, i) => <p key={i} className="text-sm text-amber-400">{e.provider} · {e.report_id} · {e.stage} · {e.error}</p>)}</CardContent></Card>}
      <details className="text-xs text-muted-foreground"><summary>数据范围与当前限制</summary>{result.limitations.map(item => <p key={item} className="mt-2">{item}</p>)}</details>
    </>}
    <Dialog open={!!citation} onOpenChange={open => { if (!open) setCitation(null); }}><DialogContent className="dark text-foreground max-w-2xl max-h-[85vh] overflow-y-auto"><DialogHeader><DialogTitle>研报引用证据</DialogTitle></DialogHeader>
      {citation && <div className="space-y-3 text-sm"><p className="font-semibold">{citation.title}</p><p>{citation.institution} · {citation.published_at} · {citation.analyst.join('、') || '分析师未提供'}</p>
        <p>{citation.page ? `PDF 第 ${citation.page} 页` : citation.section} · {citation.chunk_id}</p><blockquote className="border-l-2 border-emerald-500 pl-3 whitespace-pre-wrap">{citation.quote}</blockquote>
        <a className="text-emerald-400 underline" href={safeResearchLink(citation.source_url + (citation.page ? `#page=${citation.page}` : ''))} target="_blank" rel="noopener noreferrer">打开原文{citation.page ? `第 ${citation.page} 页` : ''}</a>
      </div>}
    </DialogContent></Dialog>
  </div>;
};
