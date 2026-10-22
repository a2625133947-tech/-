import { afterEach, describe, expect, it, vi } from 'vitest';
import { reportIntelligenceApi, safeResearchLink } from '../services/report-intelligence-api';
import { formatResearchText } from '../utils/research-text';

afterEach(() => { vi.unstubAllGlobals(); });
describe('Report intelligence API and untrusted source links', () => {
  it('blocks executable and credential-bearing document links', () => {
    expect(safeResearchLink('javascript:alert(1)')).toBeUndefined();
    expect(safeResearchLink('file:///etc/passwd')).toBeUndefined();
    expect(safeResearchLink('https://user:secret@example.com/')).toBeUndefined();
    expect(safeResearchLink('https://pdf.dfcfw.com/report.pdf#page=14')).toContain('#page=14');
  });
  it('sends the selected dates and refresh options rather than discarding them', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ task_id: 'one', status: 'PENDING' }) });
    vi.stubGlobal('fetch', fetcher);
    await reportIntelligenceApi.start('贵州茅台', { period: 'custom', start: '2026-09-01', end: '2026-09-30', refresh_discovery: true });
    const [url, request] = fetcher.mock.calls[0];
    expect(url).toContain(encodeURIComponent('贵州茅台'));
    expect(JSON.parse(request.body)).toEqual({ period: 'custom', start: '2026-09-01', end: '2026-09-30', refresh_discovery: true });
  });
  it('surfaces server errors instead of rendering them as a completed report', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: 'ambiguous security' }) }));
    await expect(reportIntelligenceApi.start('未知股票', { period: 'month' })).rejects.toThrow('ambiguous security');
  });
});

describe('Research reading text preserves financial content', () => {
  it('reflows an actual PDF extract without indentation or Chinese word gaps', () => {
    const raw = '茅台 终端价格体系松动     后 ，公司放量补价迎合市场需求        ，产品结构调整和渠道变革\n                       带来的吨价下行压力     ， 拖累利润增长    ，公司毛利率    89.56%/-1.74pct。';
    expect(formatResearchText(raw)).toBe('茅台终端价格体系松动后，公司放量补价迎合市场需求，产品结构调整和渠道变革带来的吨价下行压力，拖累利润增长，公司毛利率89.56%/-1.74pct。');
  });
  it('cleans PDF bullets and quoted Chinese while preserving mixed English and numbers', () => {
    expect(formatResearchText('\uF06C 渠道转型   “ 全面向   C” ，i茅台平台收入    大 增 274%至  402.64亿元\n消费需求恢复。')).toBe('渠道转型“全面向C”，i茅台平台收入大增274%至402.64亿元消费需求恢复。');
    expect(formatResearchText('强烈推荐 （ 维持 评级）')).toBe('强烈推荐（维持评级）');
  });
  it('retains English word and numeric separators, decimals, signs and units', () => {
    expect(formatResearchText('New\nYork  EPS\t65.14  P/E  19.7  2026  2027')).toBe('New York EPS 65.14 P/E 19.7 2026 2027');
    expect(formatResearchText('同比 -1.74pct ，净利润 81,424.00 百万元')).toBe('同比-1.74pct，净利润81,424.00百万元');
  });
});
