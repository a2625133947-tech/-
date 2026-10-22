# 工作流运行历史与 SQLite

已保存工作流的页面分析和回测会自动写入 `app/backend/hedge_fund.db`。
前端将当前工作流 ID 放入请求的 `flow_id` 字段；不存在的 ID 返回 404。
旧版或独立 API 请求不提供 `flow_id` 时保持原有行为，不建立关联运行记录。
CLI 不通过这组 Web 接口，因此不写入这两张工作流历史表。

## 保存内容

- `hedge_fund_flow_runs`：每次请求的配置、开始/结束时间、状态、初始/最终组合和结果。
- `hedge_fund_flow_run_cycles`：一次分析的一条完成周期，或回测每轮完成的交易日数据；包含日期、行情、信号、决策、模拟成交、组合状态和绩效。
- 运行状态：`IN_PROGRESS` → `COMPLETE`、`ERROR` 或 `CANCELLED`。
- 回测某天分析报错或结果无法解析时，记录 `ERROR` 周期并停止回测；之前完成的周期保留。不会把分析错误转换为成功的空决策。
- 服务启动时，将上次遗留的 `IN_PROGRESS` 标为 `ERROR`。此恢复机制面向当前桌面单进程后端。
- 保存参数与结果时移除结构化 API Key/Token 字段。错误记录只保存异常类型，不复制包含密钥的异常内容。
- 浏览器取消或断开会结束流并记录 `CANCELLED`。已在线程中执行的同步模型/数据请求可能继续到自身结束，但终止的记录不会被后续完成结果覆盖。

此功能从启用后的新运行开始积累，不会补造过去的历史数据，也不改变行情快照库。

## API 查询

- `GET /flows/{flow_id}/runs/`：运行列表。
- `GET /flows/{flow_id}/runs/latest`：最新运行。
- `GET /flows/{flow_id}/runs/count`：运行次数。
- `GET /flows/{flow_id}/runs/{run_id}`：配置、结果和组合详情。
- `GET /flows/{flow_id}/runs/{run_id}/cycles?limit=100&offset=0`：按周期顺序分页读取，默认 100，最大 1000。
- 流开始的 SSE `start` 事件带 `run_id`，可用于定位记录。

删除运行时会删除所属周期；删除工作流时会删除所属运行与周期。

## SQL 查看

以只读方式打开：

```bash
sqlite3 -readonly "/Users/niuyufei/ai-hedge-fund-2025/app/backend/hedge_fund.db"
```

```sql
.headers on
.mode column

SELECT r.id, f.name, r.trading_mode, r.status, r.started_at, r.completed_at
FROM hedge_fund_flow_runs AS r
JOIN hedge_fund_flows AS f ON f.id = r.flow_id
ORDER BY r.id DESC;

SELECT flow_run_id, cycle_number, status,
       json_extract(market_conditions, '$.date') AS trading_date,
       json_extract(portfolio_snapshot, '$.portfolio_value') AS portfolio_value,
       json_extract(portfolio_snapshot, '$.cash') AS cash
FROM hedge_fund_flow_run_cycles
ORDER BY flow_run_id DESC, cycle_number;
```

## 隔离验证

`poetry run pytest -q tests/test_flow_run_persistence.py` 使用临时 SQLite 和假的模型/行情输入，验证真实 SSE 接口到数据库的链路，不写入正式数据库。

前端请求验证：`npm test -- --run src/tests/run-persistence-request.test.ts`。
