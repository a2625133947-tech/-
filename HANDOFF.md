# 项目交接记录

## 2026-10-22：完整源码发布准备

- 权威目录：`/Users/niuyufei/Documents/ChatGPT/ai-hedge-fund-2025`。原目录 `/Users/niuyufei/ai-hedge-fund-2025` 已不存在；以 Git 提交 6999ed9、d8211c8、3235ed3 和功能文件确认迁移后的项目。
- 来源分支：`codex/github-sync-20261010`。开始时工作区干净，无既有 HANDOFF.md。其他 Playground 副本有未提交修改，未改动。
- 目标仓库：`https://github.com/a2625133947-tech/-.git`，main；用户明确授权上传完整项目。保留 GitHub 既有 README 提交历史，不强推，不推送含历史大数据的本地完整历史。
- 发布范围：源码、前后端、配置模板、依赖锁、测试、脚本和文档；排除约 126 MB 的 `docs/baselines/shadow/live/` 历史语料、密钥、本地数据库、依赖目录、构建产物和临时文件。保留 `data/security_master.json` 作为必要的离线证券目录。
- README 更新发布范围、克隆步骤和初始无研究语料的说明。`.gitignore` 增加快照语料规则（已有本地跟踪记录不删除）。

## 本轮验证

- 常见真实密钥/私钥模式扫描：所选发布文件无匹配；不读取或输出正式数据库与 .env。
- `AI_HEDGE_FUND_SKIP_DOTENV=1 python -m pytest -q tests/test_flow_run_persistence.py tests/test_cli_presentation.py`：32 passed，33 warnings；使用已有 Poetry Python 环境，持久化测试使用临时 SQLite 和模拟输入。
- 前端 `npm test -- --run`：46 passed / 6 files。
- 前端 `npm run build`：成功；存在既有 Browserslist、字体资源、sourcemap 和大包提示。
- 未执行实时行情/收费模型联网验收、全套 Python 测试或容器运行验收。

## 上传状态与下一步

- 当前为待发布检查点，尚未确认完整源码已到 GitHub。
- Git HTTPS 缺少登录凭据，GitHub 插件写入返回 403；SSH 连接超时。
- 已准备独立发布 checkout：`/tmp/aihf-github-publication-20261022`，基于远程 main，避免带入大型历史语料。
- 已打开 Playwright 独立 Chrome 登录页，等待用户登录 a2625133947-tech；不要提取或保存浏览器凭据。
- 登录完成后发布目录文件，并核对远程路径与本地文件哈希；只有核对完成后才能报告上传成功，并更新本记录。
