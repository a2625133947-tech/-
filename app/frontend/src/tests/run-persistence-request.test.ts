import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../services/api';
import { backtestApi } from '../services/backtest-api';
import type { BacktestRequest } from '../services/types';

vi.mock('@/hooks/use-flow-connection', () => ({
  flowConnectionManager: {
    getConnection: vi.fn(() => ({ state: 'idle' })),
    setConnection: vi.fn(),
  },
}));

const fetchMock = vi.fn();
const nodeContext = {} as Parameters<typeof api.runHedgeFund>[1];

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async () => new Response(new ReadableStream({
    start(controller) { controller.close(); },
  })));
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe.each([
  ['analysis', api.runHedgeFund, '/hedge-fund/run'],
  ['backtest', backtestApi.runBacktest, '/hedge-fund/backtest'],
] as const)('%s request persistence', (_name, run, endpoint) => {
  const makeParams = (): BacktestRequest => ({
    tickers: ['600519'],
    graph_nodes: [],
    graph_edges: [],
    start_date: '2026-09-01',
    end_date: '2026-09-30',
  });

  it('sends the saved flow ID as a number without changing caller parameters', async () => {
    const params = Object.freeze(makeParams());
    run(params, nodeContext, '42');

    const [url, request] = fetchMock.mock.calls[0];
    expect(url).toContain(endpoint);
    expect(JSON.parse(request.body)).toEqual({ ...params, flow_id: 42 });
    expect(params).not.toHaveProperty('flow_id');
    await Promise.resolve();
  });

  it.each([null, '', 'temporary-flow', '0', '-1', '1.5', 'NaN', 'Infinity', '1e2', '9007199254740992'])
    ('omits invalid or unsaved flow ID %s', async (flowId) => {
      run(makeParams(), nodeContext, flowId);

      const request = JSON.parse(fetchMock.mock.calls[0][1].body);
      expect(request).not.toHaveProperty('flow_id');
      expect(request.tickers).toEqual(['600519']);
      await Promise.resolve();
    });
});
