# VitaK-RAG 发布前独立审计（最终同步）

审计日期：2026-11-25
文档同步时间：2026-11-25 01:13 CST
审计范围：工作区、冻结记录、PRD 管理口径、前端产品入口、公网包、评测产物

## 最终结论

### 预答辩

**有条件通过。**

当前系统具备可演示的完整主链路：

- 公网版使用独立公开入口，只加载外部公开证据。
- 本地全栈版可展示外部证据、授权内部研究页、数据治理和证据追溯。
- 问答页固定领域知识模式，回答包含 Claim、Citation、图谱路径和安全边界。
- 最新开发冻结记录 40 项后端测试通过，前端类型检查和生产构建通过。
- 10 题内部研究专项、20 题金标准结构和 80 题两组评测均已运行。

预答辩时必须说明：自动化通过不是科学语义、临床结论或用户反馈的最终签认。

### 最终科研交付

**暂不通过。**

主要剩余阻断：

1. 工作区未提交，尚无与当前实现完全一致的 release commit。
2. 最新冻结记录未绑定 commit、完整产物哈希和工作区 clean 状态。
3. PRD 仍有 13 项部分完成、2 项待外部输入。
4. 问答页三模式入口已移除，T02-04 降为部分完成。
5. 80 题两组运行尚未纳入机器冻结和科研负责人验收。
6. OWL、审核匹配表、真实 CI/单位、用户反馈和最终发布复现仍需外部输入。

## 工作区状态

| 项目 | 当前状态 |
| --- | --- |
| 分支 | `main` |
| HEAD | `b46470edbbeeffb5f73ecf95ef792138b44e3c42` |
| 与远端 | `main...origin/main [ahead 1]` |
| 已跟踪修改 | 39 个文件 |
| 未跟踪路径 | 115 个 |
| Git 状态 | 不干净 |
| 最新冻结 | `data/eval/development-freeze-2026-11-25.json` |

当前工作区不能直接作为不可变最终交付基线。

## 产品口径

### 问答页

- 问答页固定使用 `domain`，即领域知识/外部公开证据。
- 前端不再显示“领域知识 / 内部研究 / 内外对照”三模式切换框。
- 后端 `/api/v1/qa/query` 和流式接口仍保留三种 `mode`，并执行服务端权限检查。
- 内部研究页继续提供内部证据筛选、统计详情和内部专题图谱。
- 面向用户的完整三模式入口未完成，因此 T02-04 为“部分完成”。

### 运行时模型

- `.env.example` 默认：`VITAK_RUNTIME_LLM_ENABLED=false`，API Key 为空。
- 当前本地 `.env`：已启用 DeepSeek `deepseek-chat`，API Key 非空但不展示。
- 模型不是自由生成；只做问题结构解析和证据约束语言改写。
- 每条生成 Claim 必须绑定确定性答案中的 Citation。
- 失败、超时或关键 Claim 校验不通过时整题回退确定性回答。
- 最新冻结记录：离线契约测试 5 项通过，DeepSeek 连通性、真实问答和越界拒答通过。
- 科研负责人仍需签认模型改写后的科学语义。

## 工程验证

### 后端

| 检查 | 结果 |
| --- | --- |
| `ruff check app tests` | 通过 |
| 最新冻结后端测试 | `40 passed` |
| 内部研究专项隔离测试 | `3 passed` |
| 真实快照研究评测 | `10/10` |

独立审计期间如 API 正在运行，研究快照测试会因 Kuzu 文件锁跳过；隔离快照复跑已通过。

### 前端

| 检查 | 结果 |
| --- | --- |
| TypeScript | 通过 |
| 默认本地生产构建 | 通过 |
| `VITE_STATIC_DEMO=true pnpm build` | 通过 |
| 公网自动扫描 | `valid: true` |
| 公网浏览器冒烟 | 通过 |

公网扫描结果：

```text
evidence_records: 5335
public_nodes: 1547
public_edges: 5335
overview_records: 5335
scanned_build_files: 8
errors: []
```

浏览器冒烟结果：

```text
forbiddenRequests: 0
consoleErrors: 0
mobileOverflow: false
```

## 已关闭的旧发布阻断

### 公网概览内部汇总

**已关闭。**

`frontend/public/project-overview.json` 已脱敏，当前只包含：

- 5,335 条公开证据。
- 1,547 个公开实体。
- 5,335 条公开关系。
- 外部文献和外部结构化数据两类数据集。

不再包含内部 248 条、395 人队列或内部审核状态。

### 公网内部接口和私有标签

**已关闭。**

静态构建使用独立公开入口，不再打入完整研究、治理、登录和导入模块。

对当前 `dist` 的扫描未发现：

- `/internal/v1`
- `/api/v1/research`
- `/api/v1/auth`
- `internal/private`
- `internal_rct_evidence`
- `internal_records`
- `INT-SRC-*`
- 内部边 ID 或内部审核状态

### 公网静态包浏览器功能

**已关闭。**

静态生产包已验证：

- 公网概览可加载。
- 问答可返回 Citation。
- 知识图谱可加载局部图。
- 证据检索可返回外部证据。
- 页面没有请求受控接口。
- 移动端没有横向溢出。

## 最新评测事实

### 十题外部基线

| 指标 | 结果 |
| --- | ---: |
| 题目数 | 10 |
| 自动通过 | 10 |
| 开发阶段人工初核 | 10/10 |
| 最终科研签认 | 待签认 |

### 二十题金标准

| 指标 | 结果 |
| --- | ---: |
| 结构校验 | 20/20 valid |
| 自动通过 | 20/20 |
| Claim 引用覆盖 | 100% |
| 意图准确率 | 100% |
| 拒答准确率 | 100% |
| 精确短语覆盖 | 25%，仅诊断 |

### 内部研究专项

| 指标 | 结果 |
| --- | ---: |
| 题目数 | 10 |
| 自动通过 | 10 |
| 失败/错误 | 0/0 |
| 科学负责人签认 | 待签认 |

### 80 题两组评测

报告：`data/eval/report-two-group-2026-11-25.json`

| 指标 | 普通 RAG | KG 混合 |
| --- | ---: | ---: |
| Recall@5 | 0.5657 | 0.5500 |
| MRR@10 | 0.4338 | 0.5314 |
| nDCG@10 | 0.4950 | 0.5161 |
| Citation Accuracy | 0.0886 | 0.4387 |
| Path Hit Rate | 不适用 | 0.7 |
| P95 | 343.3 ms | 626.5 ms |

无证据/安全题准确率为 1.0。该运行已验证并保留严格过滤结果，但尚未进入最新冻结记录，
T05-04 仍为部分完成。

## PRD 管理口径

PRD 共 43 项：

| 状态 | 数量 |
| --- | ---: |
| 已完成 | 26 |
| 部分完成 | 13 |
| 待外部输入 | 2 |
| 不新增 | 2 |

T02-04 已从“已完成”降为“部分完成”，原因是问答页不再向用户展示三种模式切换。

## 仍需外部输入

1. 科研方批准的完整 OWL、Domain/Range、实体/关系字典和映射矩阵。
2. 248 条内部证据的审核内外部匹配表及方向/显著性差异解释。
3. 真实 CI、单位、模型口径、敏感性分析字段和科研签认。
4. 30 至 50 题最终金标准及科研负责人逐题签认。
5. 五维科研回答人工评分、错误修复复测和最终签认。
6. 5 至 10 名真实目标用户的匿名任务反馈。
7. 正式发布环境的托管模型凭据、成本/配额授权和密钥管理。
8. 正式域名、备份恢复演练、独立环境复现签认和论文交付包确认。

## 仍存文档冲突

1. `data/eval/development-freeze-2026-11-25.json` 的浏览器检查仍记录
   “three evidence modes”，与当前问答页固定领域模式不一致。机器冻结文件本轮未修改。
2. `docs/data-sources.md` 仍写数据入口需要“内部接口令牌”，当前实现使用管理员 HttpOnly 会话。
3. `docs/pre-defense-demo.md` 仍把账号体系列为后续工作，当前已有研究员/管理员角色。
4. 最新冻结没有记录 80 题两组报告和题集哈希，因而不能证明二者属于同一冻结批次。
5. 工作区源码和冻结记录均未形成 release commit，最终发布必须重新冻结。

## 可复现命令

```bash
# 后端
cd backend
../.venv/bin/ruff check app tests
../.venv/bin/pytest -q

# 前端
cd ../frontend
PATH="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" \
  /Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm exec tsc -b

PATH="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" \
VITE_STATIC_DEMO=true \
  /Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm build

PATH="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" \
  node ../scripts/check-public-bundle.mjs
```

## 建议的发布步骤

1. 修正仍存的文档冲突，特别是冻结中的三模式描述。
2. 确认最终提交范围，排除 `.env`、认证数据库、个人路径和运行时快照。
3. 创建发布分支并提交当前实现。
4. 在 clean checkout 重跑后端、前端、金标准、研究评测、两组评测和公网扫描。
5. 新冻结记录绑定 commit、快照 manifest、题集、运行文件、构建资源和环境状态。
6. 通过 PR 合并并触发 GitHub Pages。
7. 部署后复跑公网浏览器冒烟，确认匿名包无内部请求和内部记录。
8. 完成科研负责人、医学专业人员和项目负责人签认后再标记最终交付。

本次文档同步未执行 commit。

## 最终判定

| 判定项 | 结论 |
| --- | --- |
| 预答辩可用性 | 有条件通过 |
| 最终科研交付 | 暂不通过 |
| 公网静态脱敏 | 通过 |
| 公网问答、图谱、概览 | 通过 |
| 公网内部接口隔离 | 通过 |
| 代码质量门 | 通过 |
| PRD 全部完成 | 未通过 |
| 科研最终签认 | 未通过 |
| 可追溯 release baseline | 未通过 |
