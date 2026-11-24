# 评测集说明

运行 `vitak generate-eval` 会生成 80 道分层问题，覆盖图谱关系、多跳路径、无证据拒答和安全边界。

运行 `vitak evaluate` 会按 PRD V2 比较两组：

- 普通 RAG：关键词与语义检索融合，不启用显式图谱查询。
- KG 混合检索：相同基础检索加图谱关系与路径。

V2 评测默认写入 `data/eval/report-two-group.json`，包括 Recall@5、MRR@10、
nDCG@10、引用准确率和 P95 延迟。

`data/eval/report.json` 是旧版三组实验的历史结果，不能与 V2 两组结果混合报告。

本次 2026-11-25 正式两组运行使用隔离快照
`data/snapshots/eval-two-group-repro-2026-11-25`，不修改或激活当前快照。题目集固定为
`data/eval/two-group-questions-2026-11-25.jsonl`，报告为
`data/eval/report-two-group-2026-11-25.json`，报告哈希清单为
`data/eval/report-two-group-2026-11-25.manifest.json`。

该题目集包含内部证据 ID，属于受控评测材料；对外发布前必须按内部/私有权限审核，
不得直接进入 GitHub Pages 或公开交付包。

复现命令：

```bash
cd backend
../.venv/bin/python -m app.cli snapshot-clone \
  vitak-research-2026.11-t02 eval-two-group-repro-2026-11-25
PYTHONHASHSEED=0 \
../.venv/bin/python -m app.cli generate-eval \
  --snapshot eval-two-group-repro-2026-11-25 \
  --output ../data/eval/two-group-questions-2026-11-25.jsonl
PYTHONHASHSEED=0 \
../.venv/bin/python -m app.cli evaluate \
  --snapshot eval-two-group-repro-2026-11-25 \
  --questions ../data/eval/two-group-questions-2026-11-25.jsonl \
  --output ../data/eval/report-two-group-2026-11-25.json \
  --manifest-output ../data/eval/report-two-group-2026-11-25.manifest.json
cd ..
VITAK_TWO_GROUP_BASELINE=/tmp/vitak-two-group-stable1.json \
  node scripts/validate-two-group-report.mjs
```

本次运行结果（80 题，70 道检索有效题，10 道拒答/安全题不计入检索分母）：

| 组别 | Recall@5 | MRR@10 | nDCG@10 | 路径命中 | P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 普通 RAG | 0.5000 | 0.3355 | 0.4175 | N/A | 458.92 ms |
| KG 混合 | 0.6179 | 0.5714 | 0.5864 | 1.0000 | 878.75 ms |

路径指标只统计数据中明确提供 `expected_path_evidence_ids` 的题。普通 RAG 不输出
显式路径，报告为 `null`；`q-070` 冻结时没有可验证路径预期，因此路径为 `null`，
不再计入分母。KG 混合的有效路径分母为 9，命中 9/9。
拒答题单独报告 `no_evidence_accuracy=1.0`：10/10 题均正确拒答。

连续两次运行的汇总指标和逐题判定完全一致，仅 `generated_at`、单题 `elapsed_ms`
和汇总 `p95_ms` 不同。稳定顺序固定为：题集按 JSONL 输入顺序；关键词按
`bm25, evidence_id`；向量按分数降序、`evidence_id`；RRF 融合按分数降序、
`evidence_id`；评测期间的 KG FTS 和短语检索也固定到 `evidence_id` 次序。

正式报告 SHA-256：
`ce5258381e26b9eab78734f36072132b85c92d5d6c9d1fe404fd9d8f88c19c97`。
清单同时记录快照、题集、QA/编排/评测源码哈希和生成命令。报告结构及双运行比较校验见
`scripts/validate-two-group-report.mjs`。

## PRD T04-01 固定十题基线

在当前本地前端运行后执行：

```bash
PATH="/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" \
VITAK_WEB_URL=http://127.0.0.1:5173 \
VITAK_EXPECT_VERSION=real-public-2026.11-structured \
node scripts/baseline-10.mjs
```

脚本会隔离每个问题的浏览器会话，并生成：

- `baseline-10-external-2026.11.json`：完整回答、Claim、引用、图谱路径、耗时和自动初筛结果。
- `baseline-10-external-2026.11.md`：便于人工复核的科研基线报告。

自动状态仅用于初筛。`pass` 表示必需内容组和 Claim 引用覆盖达标，最终科研正确性仍需人工复核。

当前十题的开发阶段初步复核记录：

- `baseline-10-manual-review.json`
- `baseline-10-manual-review.md`

初步复核通过 10 题，但最终科研负责人签认状态仍为 `pending_scientific_owner`。

## V2 金标准测试集

`gold-questions-v2.jsonl` 包含 20 道初步人工标注问题，覆盖定义、亚型、机制、食物来源、药物相互作用、阴性证据、研究差异、因果边界、检测解释、医疗安全和无证据拒答。

校验金标准：

```bash
node scripts/validate-gold-set.mjs
```

运行当前本地系统：

```bash
VITAK_WEB_URL=http://127.0.0.1:5173 \
node scripts/evaluate-gold-set.mjs
```

产物：

- `gold-20-validation.json`：金标准结构、证据 ID、权限和拒答配置校验。
- `gold-20-run.json`：当前系统逐题运行结果和汇总指标。

当前自动结果中，20/20 题通过证据命中、Claim 引用和拒答检查；意图准确率为 100%，精确短语覆盖率为诊断项，不作为科学语义最终评分。金标准答案仍需科研负责人进行最终内容复核。

## 内部研究专项验收

`research-questions-v1.jsonl` 包含 10 道内部队列验收题，覆盖核心关联、阴性证据、冲突保留、纵向、餐后、维生素K×维生素D、性别、肥胖、剂量反应和反向探索。

```bash
VITAK_API_URL=http://127.0.0.1:8000 \
VITAK_RESEARCH_USER=admin \
VITAK_RESEARCH_PASSWORD='本地测试密码' \
node scripts/evaluate-research-set.mjs
```

脚本验证内部/私有来源边界、Claim 与引用覆盖、分析族、结果状态和关键术语。输出写入 `research-run-2026.11.json`。自动通过不等同于科研负责人对统计解释和临床边界的最终签认。

## 开发阶段冻结

`development-freeze-2026-11-24.json` 记录了本轮本地生产构建、20 题金标准、
前后端自动化测试和浏览器回归结果，以及知识库与评测文件哈希。

`development-freeze-2026-11-24-t02.json` 记录内部研究闭环版本：研究快照、
10 题内部专项验收、权限边界、前后端测试、浏览器回归和研究文件哈希。

该冻结版本只用于开发验收，没有触发 GitHub Pages 部署。科研负责人签认前，
自动化通过不能被解释为临床正确性的最终结论。
