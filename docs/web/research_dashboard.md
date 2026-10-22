# AI Hedge Fund - 策略研究工作台 (Research Dashboard) 用户手册

本文档说明策略研究工作台（Web Research Dashboard）与 CLI SHADOW 模式的操作方式、核心架构与关键指标定义。

---

## 1. 如何启动 Web 工作台

### 方式 A：标准自动化脚本（推荐）

在项目根目录下执行：

```bash
bash app/run.sh
```

该脚本将自动完成：
1. 依赖与环境核查（Python 3.11+、Poetry、Node.js 18+、npm）；
2. 启动 FastAPI 后端服务（运行于 `http://127.0.0.1:8000`）；
3. 启动 Vite 前端服务（运行于 `http://127.0.0.1:5173`）；
4. 自动打开浏览器直达系统页面。

### 方式 B：手动分步启动

**终端 1（Backend）：**
```bash
poetry run uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000
```

**终端 2（Frontend）：**
```bash
cd app/frontend
npm run dev
```

### 方式 C：Docker Compose 容器部署

```bash
# 启动 Web 后端服务
docker compose -f compose.web.yaml up -d
```

CLI 原生调试命令保持完全兼容：
```bash
docker compose run app python src/main.py --tickers 600519
```

---

## 2. LEGACY 与 SHADOW 的核心区别

| 维度 | LEGACY（生产默认模式） | SHADOW（研究影子模式） |
| :--- | :--- | :--- |
| **系统定位** | 实盘决策与交易执行流水线 | 离线量化策略研究与前瞻验证 |
| **交易执行影响** | **真实主导** Risk Manager 与 Portfolio Manager 交易指令 | **严格隔离**，任何 New 信号与置信度均不参与实盘执行 |
| **投资人模型** | 离散财务指标硬阈值打分规则（ROE、PE、PB、营收增长等） | 连续因子引擎（Factor Engine v1）、策略门槛与代理验证（StrategyEvaluator） |
| **因子粒度** | 离散打分（-1, 0, 1） | 连续归一化分值（-1.0 ~ +1.0），包含权重加权与贡献度拆解 |
| **置信度计算** | 简单可用指标数量与均值加权 | 结合覆盖率（Coverage Score）、证据质量（Quality）与特定封顶约束（Caps） |

---

## 3. Web Research Mode 的含义与安全边界

在 Web 界面与 CLI 顶部均展示明确的警示标识：
> **RESEARCH MODE · Shadow results are not production trading decisions. 生产交易状态：LEGACY**

### 核心安全准则：
1. **决策隔离**：无论 SHADOW 模型对某只股票输出多么强烈的看多（Bullish）或看空（Bearish）信号，最终生产交易决策（Production Decision）始终由 LEGACY 引擎驱动。
2. **零 LLM 额外调用**：打开 Web 页面、查询股票或刷新图表，均直接通过本地确定性 Python 因子引擎与快照数据库完成计算，绝不在页面加载时产生额外的 DeepSeek / GPT API 调用。

---

## 4. 置信度（Confidence）的定义

在本项目研究模型中，置信度有严格的量化定义：

> **“置信度表示当前策略判断的数据支撑与证据完备程度，不代表上涨概率、盈利概率或交易胜率。”**

### 置信度拆解要素：
1. **Evidence Coverage Score（证据覆盖分）**：核心因子与支撑因子的综合完备度。
2. **Evidence Quality（证据质量分）**：数据源可信度与调整模式权值。
3. **Caps（约束上限）**：
   - `core_missing_cap`：关键核心因子缺失时的上限拦截；
   - `strategy_evidence_cap`：策略关键证据不足时的硬顶约束；
   - `proxy_cap`：使用代理指标（如低预期代理）时的置信度硬顶（例如 60.0%）。

---

## 5. 前瞻快照语料库（Snapshot Corpus）的用途

前瞻快照语料库用于实现**完全不依赖事后偏见（Look-ahead Bias）的离线策略回放与漂移检测**：
- **Point-in-Time 真实性**：记录捕获时刻的数据可见状态，确保后续研究绝不包含未来数据。
- **因子漂移检测**：实时监控数据源覆盖率骤降、因子大面积不可用等异常。
- **策略分布监控**：自动识别单一投资人产生 100% 极值信号（SIGNAL_MONOPOLY）、置信度异常虚高（CONFIDENCE_INFLATION）或整体坍塌（CONFIDENCE_COLLAPSE）。

---

## 6. NOT_READY 的含义与处理规则

在 12 位投资人策略原型中，有 10 位已完成因子引擎重构并达到 `SHADOW_READY` 状态：
- 张坤 (v2)
- 冯柳 (v1)
- 傅鹏博 (v1)
- 段永平 (v1)
- 邓晓峰 (v1)
- 朱少醒 (v1)
- 刘彦春 (v1)
- 谢治宇 (v1)
- 董承非 (v1)
- 陈光明 (v1)

剩余 2 位当前处于 `NOT_READY` 状态：
1. **王亚伟**：缺少重组重仓、筹码集中度与席位流向数据；
2. **林园**：缺少细分垄断壁垒、成瘾性产品与自主定价权量化代理。

### 规则边界：
对于 `NOT_READY` 策略：
- 系统界面明确展示 `NOT READY` 标签与具体缺失原因；
- 界面可提供原有 Legacy 视角参考；
- **严格禁止伪造、合成或猜测 New Factor Engine 评估数据**。

---

## 7. CLI 命令参考

### 查看人类可读的结构化研究拆解（几十至百行内清晰展现）：
```bash
A_SHARE_INVESTOR_MODE=shadow poetry run python src/main.py --tickers 600519 --show-reasoning
```

### 导出完整底层图状态与原始 JSON（用于机器排查与调试）：
```bash
poetry run python src/main.py --tickers 600519 --debug-state
```

### 普通生产运行（保持极简干净体验）：
```bash
poetry run python src/main.py --tickers 600519
```
