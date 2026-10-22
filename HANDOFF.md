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

## 上传记录与当前状态

- 完整源码已通过用户登录后的 GitHub 网页分批提交到 main；原 README 历史保留。源码核对提交：`7dbffafef78617a0b63c93896898ac475c680220`。
- 2026-10-22 全量 GitHub Git Tree 对照：457 个文件，缺失 0、内容 blob SHA 不一致 0。包含 src、app、tests、docs、scripts、docker、证券主表、pyproject.toml、poetry.lock 和前端依赖锁。
- Git HTTPS 缺少登录凭据，GitHub 插件写入返回 403；SSH 连接超时。
- 已准备独立发布 checkout：`/tmp/aihf-github-publication-20261022`，基于远程 main，避免带入大型历史语料。
- 用户已完成 Playwright 独立 Chrome 登录；未提取或保存浏览器凭据。
- 第三批出现连接错误及无效提交，未作为成功计数；刷新后按较小批次重传，最终以远程文件清单与 blob SHA 核对为准。
- 本轮未强制推送、重写远程历史，也未改动其他 Playground 工作树。默认仍不自动 Push，后续上传需按用户授权范围执行。

## 已知限制与下一步

- GitHub 网页上传会使用普通文件模式，不保留源文件的 5 个 shell 脚本可执行位。README 已提供 chmod 命令；也可使用 `bash app/run.sh` 等方式。未来通过正式 Git 写入通道可恢复可执行位。
- 被排除的大型固定历史语料仍保存在原本地 Git 工作树中；某些 SHADOW 回放测试依赖这些原始快照与目录，发布副本没有它们时不能直接运行全套历史回放测试。新采集数据不能替代旧日期基准。
- 后续如需继续同步，先读取本记录和 Git 状态；线上基线以目标仓库 main 为准。临时发布 checkout 中的 6d8acd8 是准备快照，真实线上提交由网页生成，不要直接用本地旧分支覆盖 main。
