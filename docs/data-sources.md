# 维生素 K 项目数据来源与分类

## 数据口径

项目按“两种来源、三张全量三元组表”组织数据：

| 数据类型 | 文件 | 行数 | 来源标签 | 说明 |
| --- | --- | ---: | --- | --- |
| 外部结构化／半结构化 | `structured_triples_final.csv` | 60,030 | `external/public` | FDC、USDA、PubChem、FooDB、KEGG、ClinicalTrials 等来源实例化后的逻辑关系 |
| 外部文献 | `literature_triples_final.csv` | 13,118 | `external/public` | 保留研究编号、PMID、来源定位、关系等级和审核状态 |
| 内部 RCT 证据 | `internal_evidence_final.csv` | 248 | `internal/private` | 395 人队列的横断面、纵向、餐后、交互、剂量、中介及反向探索测试证据 |

三张表合并后共 73,396 条记录。外部数据回答“已发表研究和公开数据库说了什么”，内部数据回答“本项目队列发现了什么”。

`aligned_triples.csv` 是早期外部文献抽取产物，可作为历史中间文件；当前统一导入入口使用 42 列三表格式。

## 部署数据边界

| 运行环境 | 外部数据 | 内部数据 | 用途 |
| --- | --- | --- | --- |
| GitHub Pages 公网版 | 1,012 条已审核外部文献 + 3,123 条公开结构化问答关系 + 1,200 条仅研究检索记录 | 不发布 | 导师可直接访问的真实外部证据演示 |
| 本地 FastAPI 全栈版 | 73,148 条外部证据 | 248 条真实内部队列证据，`internal/private` | 完整内外数据联合检索与预答辩演示 |

公网数据包由 [`scripts/export-public-evidence.py`](../scripts/export-public-evidence.py) 生成。脚本读取外部文献表，并合并审核通过的结构化语义关系：

- 正式回答证据：`accepted` 或 `adopted_with_warning`，且 `input_status=adopted`。
- 结构化节点先用 `Name`、`Description`、`skos:altLabel` 等已审核属性补全，再将 `contains`、`VitaminKContent`、`CookingMethod` 等语义关系纳入公网问答。
- `URI`、`Category`、`Source` 等纯属性声明用于节点补全，不直接当作可回答的医学关系。
- 研究检索证据：最多 1,200 条 `manual_pending` 或 `provisional` 记录，明确标记为不可用于正式回答。
- 不读取、不打包任何内部 CSV。

## 统一 42 列字段

### 三元组核心

| 字段 | 含义 |
| --- | --- |
| `edge_id` | 全局唯一关系标识 |
| `subject_id` | 规范主体实体 ID |
| `subject_label` | 主体规范名称 |
| `subject_type` | 主体实体类别 |
| `predicate` | 本体关系词 |
| `object_id` | 规范客体实体 ID；字面值可为空 |
| `object_label` | 客体名称或原始值 |
| `object_type` | 客体实体类别或字面值类型 |

当 `object_id` 为空时，导入器使用 `object_label + object_type` 生成稳定字面值节点。

### 来源追踪

| 字段 | 含义 |
| --- | --- |
| `source_type` | `structured`、`literature` 或 `internal` |
| `source_record_id` | 原始记录编号 |
| `source_locator` | 原字段定位或 `PMID｜原文证据句` |
| `source_version` | 来源文件及版本标识 |
| `source_sha256` | 来源文件哈希 |
| `source_file` | 原始结果表名称 |
| `source_row_value` | 原始结果表行号 |

### 证据信息

| 字段 | 含义 |
| --- | --- |
| `evidence_score` | 原始证据评分 |
| `evidence_grade` | 原始等级，如 A、B、C、Negative |
| `confidence_score` | 抽取或匹配置信度 |
| `effect_size` | β、OR、HR、相关系数等效应量 |
| `ci_low` / `ci_high` | 效应量置信区间 |
| `p_value` | 原始 P 值 |
| `q_value` | FDR 校正值 |
| `sample_n` | 模型或研究有效样本量 |
| `model_type` | OLS、robust、混合效应、交互、中介等 |

### 上下文

| 字段 | 含义 |
| --- | --- |
| `population_context` | 人群、物种或基线特征 |
| `dose_context` | 剂量、频次和干预方式 |
| `time_context` | 基线、纵向、餐后或随访时间窗 |
| `test_family` | 横断面、纵向、餐后、交互等分析族 |
| `analysis_context` | 具体分析语境 |
| `qualifiers_json` | 源字段、原始对象、映射状态及来源特有属性 |

### 融合与审核

| 字段 | 含义 |
| --- | --- |
| `fusion_status` | `accepted`、`provisional`、`conflict` 或 `merged` |
| `retention_status` | 内部证据的保留方式 |
| `conflict_id` | 对应冲突记录编号 |
| `review_status` | 审核状态 |
| `review_reason` | 暂定、冲突或复核原因 |
| `input_status` | 输入采纳、延迟或合并状态 |
| `modification_codes` | 规范化、合并或扩展记录 |
| `merged_into` | 被合并到的目标关系 |
| `evidence_status` | 阳性、阴性、候选或模型不一致等状态 |
| `core_48_flag` | 是否为 48 条核心展示证据 |
| `graph_display_role` | 核心边、次要证据、阴性对照或附录证据 |

## 内外部来源映射

导入器按每行 `source_type` 自动生成来源标签：

| `source_type` | `data_origin` | `access_scope` | `source_classification` |
| --- | --- | --- | --- |
| `internal` | `internal` | `private` | `internal_rct_evidence` |
| `literature` | `external` | `public` | `external_literature_triple` |
| `structured` | `external` | `public` | `external_structured_triple` |

前端证据卡会同时展示来源标签、访问范围和来源细分类型。

## 回答资格

- `accepted`、`adopted_with_warning`、`accepted_internal_ledger` 和已采纳的内部冲突保留证据可进入正式回答。
- `manual_pending`、`provisional`、`deferred` 等记录保留在研究检索和审计数据中，但默认不进入正式回答。
- `merged_duplicate` 保留原始证据行，但不重复创建图谱关系边。
- 内部负向证据会保留为“未观察到显著关系”，不会转换成正向健康结论。

## 导入与审计

先执行 dry-run，只解析、校验和输出统计，不写入数据库：

```bash
cd backend
../.venv/bin/python -m app.cli audit-evidence-tables \
  path/to/internal_evidence_final.csv \
  path/to/literature_triples_final.csv \
  path/to/structured_triples_final.csv
```

确认后写入独立私有快照：

```bash
../.venv/bin/python -m app.cli import-evidence-tables \
  --version vitak-real-next \
  path/to/internal_evidence_final.csv \
  path/to/literature_triples_final.csv \
  path/to/structured_triples_final.csv
```

本地页面 `http://127.0.0.1:5173/#/import` 也支持逐表上传 42 列 CSV，但需要同时运行 FastAPI，并提交内部接口令牌。

生成本地演示使用的完整内外数据快照后，执行：

```bash
../.venv/bin/python -m app.cli snapshot-validate vitak-real-2026.11
../.venv/bin/python -m app.cli snapshot-activate vitak-real-2026.11
```

生成公网真实外部证据包：

```bash
../.venv/bin/python ../scripts/export-public-evidence.py \
  path/to/literature_triples_final.csv \
  path/to/structured_triples_final.csv
```

输出文件为 `frontend/public/real-evidence.json`，包含可公开的外部文献和结构化语义关系，不包含内部证据。

## 当前审计结果

| 指标 | 结果 |
| --- | ---: |
| 总记录 | 73,396 |
| 图谱实体 | 36,638 |
| 图谱关系边 | 73,279 |
| 来源记录 | 566 |
| 字面值节点 | 25,527 |
| 合并重复证据 | 117 |
| 正式回答可用 | 54,249 |
| 仅研究检索 | 19,147 |
| 空必填字段 | 0 |
| 重复 `edge_id` | 0 |

内部证据卡会展示 `internal/private`、审核状态、分析语境、模型类型、样本量、效应量和 P 值。原始 CSV、内部证据、全量私有快照和审计明细只保存在本机，不进入 GitHub、GitHub Pages 或飞书。
