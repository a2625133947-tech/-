# 研报智能分析功能完成度审计

审计日期：2026-10-02。目标：`/Users/niuyufei/ai-hedge-fund-2025` 当前工作树。
本轮修改前已检查 Git 状态、src、backend、frontend、tests、Docker、macOS 启动脚本、数据库和配置示例。机器上其他同名项目副本未作为本轮目标。

## 原有架构与复用依据

`src/data/security_master.py` 和 `/api/securities` 已有 A 股代码/名称解析；`SecuritySearchInput` 是共享证券选择器。
`src/tools/a_share.py` / `src/tools/api.py` 提供 BaoStock 行情、AKShare 财务、巨潮法定财报链接；法定财报不等于券商研报。
`app/backend/services/research_service.py`、`/api/research`、`ResearchDashboard` 为 Shadow 因子、投资人卡片与快照回放服务，没有券商 document/chunk/citation 链路。
`AgentState.data` 已支持字典合并；Web Graph 与 CLI 都经过 `src/main.start`。Portfolio Manager 已有财务证据包和最终投资报告。
数据库已有工作流、运行、API keys、模型目录，没有券商研报表。缓存已有行情缓存与 TTL 工具，没有研报长期原文缓存。
LLM 复用 `src/utils/llm.call_llm` 与现有模型/凭据接口。不得引入第二套金融工作流或证券搜索框。

## 修改前逐项结果

| 序号 | 模块 | 状态 | 依据 |
|---|---|---|---|
|1|证券解析|部分完成|已有 A 股 SecurityMaster，没有 US 名称解析|
|2|研报搜索|未完成|无券商研报 Discovery|
|3|研报来源|未完成|原接口用途为行情、财务和法定公告|
|4|网页研报抓取|未完成|无研报正文 Acquisition|
|5|PDF 研报获取|未完成|仅有法定财报链接|
|6|PDF/HTML 正文解析|未完成|无研报解析器|
|7|元数据|未完成|无统一券商研报模型|
|8|去重|未完成|金融数据缓存的去重不是转载去重|
|9|时间筛选|未完成|无研报 published_at 筛选|
|10|周度聚合|未完成|无研报周期聚合|
|11|月度聚合|未完成|同上|
|12|年度聚合|未完成|同上|
|13|长文分块|未完成|无原文 chunk 层|
|14|单篇摘要|未完成|投资 Agent 输出不等于来源约束摘要|
|15|多篇总结|未完成|无分层研报综合|
|16|引用|未完成|无 Claim-Citation-Evidence|
|17|研报原文链接|未完成|原有链接属于法定财报|
|18|引用定位|未完成|无研报页码/段落定位|
|19|无来源阻断|未完成|无研报专用校验|
|20|防幻觉|未完成|通用 LLM 接口没有研报事实核验|
|21|研报缓存|未完成|无原文、解析、分块、摘要、周期缓存|
|22|研报数据库|未完成|无研报持久化表|
|23|前端基础|部分完成|已有 Research 容器和共用组件|
|24|独立研报面板|未完成|现有 Research 服务于 Shadow|
|25|研报 API|未完成|无券商研报 API|
|26|下游研报接入|未完成|State 可扩展但未传 ResearchContext|
|27|ResearchContext|未完成|无该模型|
|28|研报测试|未完成|已有测试针对金融数据与 Shadow|
|29|研报错误容忍|未完成|无逐来源/逐文档错误记录|
|30|研报日志|未完成|只有通用 logging/progress|

计分规则：已完成=1、部分完成=0.5、未完成=0；30 项等权。
修改前 **1/30=3.3%**，仅衡量本次券商研报需求。获取、解析、Grounding、总结、引用与下游研报模块为 0%；证券解析和前端基础可部分复用。

## 设计与实施顺序

1. Provider Adapter + 独立 Discovery / Acquisition，优先复用东方财富来源体系。
2. 原始 bytes + normalized text + page/offset chunks + structured values + summaries，保存在原 SQLAlchemy 数据库的新表。
3. 标题/机构/日期候选去重，正文/PDF hash 再去重，保留转载来源。
4. 日历周/月/年/自定义，解析后按原文发布日期二次过滤。网站登记日期单独保留。
5. 分块模型输入、单篇摘要、主题分组、周期聚合。安全模式只接受原文摘录，避免伪造语义归纳。
6. 程序检查 citation 集合、chunk、quote、URL、页码及 claim 是否为证据原文；失败则删除/证据不足。
7. 共用 Research UI 新增独立研报子页、任务进度、原文引用对话框和 Coverage。
8. 复用现有 start 节点和 AgentState，按角色投送，技术 Agent 不投送，历史分析限制未来上下文。
9. 分阶段测试、实源验收、真实模型验收和长文基准，分别记录，避免把模拟数量当作真实数量。

## 修改范围与保留内容

完整文件清单见 `research_intelligence_changes.json`。修改采用当前未提交文件内容作为基础，不 reset、不 stash、不覆盖整个旧项目，不复制 .env、原数据库或凭据。
数据库采用新增表的幂等兼容建表和 Alembic migration，不修改旧表列或删除旧行。
macOS 原启动脚本、端口和 Docker 启动入口保留；依赖通过 pyproject/lock 一致声明。
