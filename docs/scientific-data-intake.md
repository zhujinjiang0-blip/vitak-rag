# 科研数据接入模板与校验

## 1. 目的与边界

本规范用于接收论文和预答辩所需的六类补充材料：

1. OWL 类、Domain/Range 与实体关系映射。
2. 248 条内部证据与外部证据的审核匹配表。
3. 效应量、CI、单位、模型口径及敏感性分析。
4. 30-50 道金标准问题。
5. 科研负责人签认。
6. 5-10 条真实用户反馈。

对应空模板位于 `data/templates/scientific-inputs/`，校验器为
`scripts/validate-scientific-inputs.py`。

本工具只做输入结构和跨表一致性检查，不生成、补写或推断科研数据。它不是 OWL DL
推理器，也不替代科研负责人、医学专业人员或统计人员的人工审核。

## 2. 目录与文件

将九个模板复制到受控数据目录后填写。校验器要求所有文件位于同一个输入目录：

```text
scientific-inputs/
  ontology-classes.csv
  ontology-properties.csv
  entity-relation-mappings.csv
  internal-external-matches.csv
  effect-estimates.csv
  sensitivity-analyses.csv
  gold-questions.csv
  scientific-signoffs.csv
  user-feedback.csv
```

`data/templates/scientific-inputs/` 中的文件只有表头，没有正式记录。任何演示记录都必须：

- 在 ID、说明或 IRI 中使用 `EXAMPLE_`、`EXAMPLE` 或 `示例` 标记。
- 使用 `--allow-examples` 校验。
- 不得复制到正式数据目录。

正式校验默认拒绝示例标记。

## 3. 字段设计

“必填”表示该列必须存在。个别条件字段允许整列为空，但在指定条件下必须有值，例如
`no_external_match` 行的 `external_evidence_id`。

### 3.1 `ontology-classes.csv`

| 字段 | 状态 | 说明 |
| --- | --- | --- |
| `class_id` | 必填 | 稳定类 ID，全表唯一 |
| `class_iri` | 必填 | OWL 类 IRI，必须以 `http://`、`https://` 或 `urn:` 开头 |
| `label` | 必填 | 中文或英文类名 |
| `parent_class_id` | 可选 | 父类 ID；若填写，必须存在于本表 |
| `status` | 必填 | 必须为 `approved`、`draft` 或 `rejected`；正式校验要求 `approved` |
| `description` | 可选 | 定义、边界和来源说明 |

### 3.2 `ontology-properties.csv`

| 字段 | 状态 | 说明 |
| --- | --- | --- |
| `property_id` | 必填 | 稳定属性 ID，全表唯一 |
| `property_iri` | 必填 | OWL 属性 IRI |
| `label` | 必填 | 属性名称 |
| `property_kind` | 必填 | `object` 或 `datatype` |
| `domain_class_id` | 必填 | 必须存在于类表 |
| `range_spec` | 必填 | 对象属性填类 ID；数据类型属性填 `string`、`integer`、`decimal`、`boolean`、`date`、`datetime` 或 `uri` |
| `status` | 必填 | 正式校验要求 `approved` |
| `description` | 可选 | 属性含义、方向和适用条件 |

当前校验器检查 Domain/Range 的显式类和数据类型合法性，不做 subclass 推理。若 OWL
依赖父类推断合法 Domain/Range，应在科研方批准的映射表中显式写出最终类，或另配正式
OWL 推理流程。

### 3.3 `entity-relation-mappings.csv`

| 字段 | 状态 | 说明 |
| --- | --- | --- |
| `mapping_id` | 必填 | 映射记录 ID，全表唯一 |
| `subject_label` | 必填 | 原始主体名称 |
| `subject_class_id` | 必填 | 必须与属性的 Domain 一致 |
| `relation_id` | 必填 | 必须存在于属性表 |
| `object_kind` | 必填 | `class` 或 `literal` |
| `object_label` | 必填 | 原始客体名或字面值 |
| `object_class_id` | 条件必填 | `object_kind=class` 时必填，且必须与 Range 一致；literal 时必须为空 |
| `status` | 必填 | 正式校验要求 `approved` |
| `evidence_id` | 必填 | 绑定来源证据 ID |
| `reviewer_id` | 必填 | 映射审核人 |
| `reviewed_at` | 可选 | 审核日期，建议 ISO-8601 |
| `notes` | 可选 | 别名、规范化或争议说明 |

### 3.4 `internal-external-matches.csv`

| 字段 | 状态 | 说明 |
| --- | --- | --- |
| `match_id` | 必填 | 匹配记录 ID，全表唯一 |
| `internal_evidence_id` | 必填 | 内部证据 ID |
| `external_evidence_id` | 条件必填 | `match_status=matched` 时必填；`no_external_match` 时为空 |
| `match_status` | 必填 | `matched`、`no_external_match` 或 `excluded` |
| `direction` | 必填 | `same`、`opposite` 或 `not_applicable` |
| `significance_status` | 必填 | `concordant`、`discordant` 或 `not_applicable` |
| `review_status` | 必填 | 正式校验要求 `approved` |
| `reviewer_id` | 必填 | 审核人 |
| `reviewed_at` | 必填 | ISO-8601 日期或时间 |
| `context` | 可选 | 人群、模型、时间窗和可比条件 |
| `notes` | 可选 | 差异说明 |

默认要求至少覆盖 248 个不同的 `internal_evidence_id`。一条内部证据允许对应多条外部
证据，因此总行数可以大于 248，但唯一内部证据 ID 数必须为 248。

`no_external_match` 必须同时填写 `direction=not_applicable` 和
`significance_status=not_applicable`。

### 3.5 `effect-estimates.csv`

| 字段 | 状态 | 说明 |
| --- | --- | --- |
| `estimate_id` | 必填 | 效应量记录 ID，全表唯一 |
| `evidence_id` | 必填 | 来源证据 ID |
| `effect_measure` | 必填 | 如 OR、HR、RR、beta、mean_difference |
| `effect_size` | 必填 | 有限数值 |
| `ci_low` / `ci_high` | 必填 | 置信区间上下界，必须为有限数值 |
| `unit` | 必填 | 明确单位；比值型指标可填 `ratio` |
| `model_type` | 必填 | 模型名称 |
| `model_context` | 必填 | 协变量、分层、时间窗或分析条件 |
| `status` | 必填 | 正式校验要求 `approved` |
| `reviewer_id` | 必填 | 统计或科研审核人 |
| `sensitivity_required` | 可选 | `true` 或 `false` |
| `sensitivity_analysis_id` | 条件必填 | `sensitivity_required=true` 时必须填写 |
| `reviewed_at` | 可选 | 审核日期 |
| `notes` | 可选 | 模型限制和解释 |

校验规则：

- `effect_size`、`ci_low`、`ci_high` 必须是有限数值。
- `ci_low <= ci_high`。
- `effect_size` 必须位于 CI 上下界之间。
- 单位不能为空。
- 引用的敏感性分析必须存在。

### 3.6 `sensitivity-analyses.csv`

| 字段 | 状态 | 说明 |
| --- | --- | --- |
| `sensitivity_id` | 必填 | 敏感性分析 ID，全表唯一 |
| `base_estimate_id` | 必填 | 必须存在于效应量表 |
| `analysis_type` | 必填 | 缺失值、异常值、替代模型等 |
| `model_type` | 必填 | 敏感性分析模型 |
| `result_summary` | 必填 | 客观摘要，不得生成新结论 |
| `supports_primary` | 必填 | `true` 或 `false` |
| `status` | 必填 | 正式校验要求 `approved` |
| `reviewer_id` | 必填 | 审核人 |
| `reviewed_at` | 可选 | 审核日期 |
| `notes` | 可选 | 差异和解释 |

### 3.7 `gold-questions.csv`

| 字段 | 状态 | 说明 |
| --- | --- | --- |
| `question_id` | 必填 | 题目 ID，全表唯一 |
| `question` | 必填 | 问题原文 |
| `expected_intent` | 必填 | 预期意图 |
| `expected_evidence_ids` | 条件必填 | 非拒答题必须提供；多条 ID 建议用分号分隔 |
| `expect_abstain` | 必填 | `true` 或 `false` |
| `safety_case` | 必填 | `true` 或 `false` |
| `review_status` | 必填 | 正式校验要求 `approved` |
| `reviewer_id` | 必填 | 科研审核人 |
| `boundary_notes` | 可选 | 证据层级、因果和临床边界 |

题量必须为 30-50 道。`expect_abstain=false` 的题目必须有预期证据 ID。

### 3.8 `scientific-signoffs.csv`

| 字段 | 状态 | 说明 |
| --- | --- | --- |
| `signoff_id` | 必填 | 签认记录 ID，全表唯一 |
| `artifact_type` | 必填 | 见下方允许值 |
| `artifact_id` | 必填 | 文件、批次或交付物 ID |
| `decision` | 必填 | 正式校验要求 `approved` |
| `signed_by` | 必填 | 签认人或受控人员 ID |
| `role` | 必填 | 科研负责人、统计负责人、医学审核人等 |
| `signed_at` | 必填 | ISO-8601 日期或时间 |
| `artifact_sha256` | 必填 | 被签认交付物的 64 位 SHA-256 |
| `scope` | 可选 | 签认覆盖范围 |
| `comments` | 可选 | 条件、保留意见或修改要求 |

`artifact_type` 允许：

```text
ontology
entity_relation_mapping
internal_external_match
effect_estimate
gold_set
user_feedback
```

正式校验要求上述每一种类型至少有一条 `approved` 记录。当前校验器检查格式和状态，
不验证签认人的真实身份或数字签名。

### 3.9 `user-feedback.csv`

| 字段 | 状态 | 说明 |
| --- | --- | --- |
| `feedback_id` | 必填 | 反馈 ID，全表唯一 |
| `participant_code` | 必填 | 假名代码，不得使用真实身份信息 |
| `task_id` | 必填 | 用户实际完成的任务 |
| `consent_status` | 必填 | 必须为 `granted` |
| `collected_at` | 必填 | 收集日期或时间 |
| `rating_usefulness` | 必填 | 1-5 整数 |
| `rating_clarity` | 必填 | 1-5 整数 |
| `rating_trust` | 必填 | 1-5 整数 |
| `anonymous` | 必填 | 必须为 `true` |
| `moderation_status` | 必填 | 必须为 `approved` |
| `comment` | 可选 | 已脱敏的自由文本 |
| `follow_up` | 可选 | 已脱敏的后续行动 |

必须有 5-10 条反馈。以下类别的表头会被拒绝：

- 姓名、手机号、电话、邮箱。
- 微信、地址、住址。
- 身份证、护照、病历号。
- 设备 ID、IP 地址或其他直接身份字段。

校验器还会扫描类似邮箱、中国大陆手机号或 18 位身份证号的字段值。自由文本中的姓名、
机构名和罕见身份线索无法仅靠正则可靠识别，仍需人工脱敏和审核。

## 4. 跨表规则

| 规则 | 检查方式 |
| --- | --- |
| 类 ID 唯一 | 检查 `class_id` |
| 属性 ID 唯一 | 检查 `property_id` |
| 映射 ID 唯一 | 检查 `mapping_id` |
| Domain 合法 | `domain_class_id` 或 `subject_class_id` 必须存在于类表并匹配属性 |
| Range 合法 | 对象属性必须引用存在的类；数据类型属性必须使用允许的数据类型 |
| 匹配数量 | 默认 248 个唯一内部证据 ID |
| 匹配方向 | matched/no_match 的方向和显著性字段必须符合条件 |
| CI 合法 | 上下界顺序正确，效应量在区间内 |
| 单位完整 | `unit` 不得为空 |
| 敏感性分析 | 引用的分析必须存在 |
| 金标准题量 | 30-50 道 |
| 金标准签认 | 每题 `review_status=approved` |
| 科研签认 | 六类 artifact 各至少一条 approved |
| 用户反馈 | 5-10 条，匿名、授权、审核通过 |
| 敏感数据 | 拒绝敏感表头和明显身份号码 |
| 示例隔离 | 正式模式拒绝 `EXAMPLE` 或 `示例` |

## 5. 使用命令

### 5.1 校验空模板

```bash
python3 scripts/validate-scientific-inputs.py \
  --input-dir data/templates/scientific-inputs
```

空模板应返回 `FAIL`，这是预期行为，用于证明工具不会把空表误判为完成。

失败示例：

```text
FAIL: data/templates/scientific-inputs
  ontology-classes.csv: 0 row(s)
  ontology-properties.csv: 0 row(s)
  entity-relation-mappings.csv: 0 row(s)
  internal-external-matches.csv: 0 row(s)
  effect-estimates.csv: 0 row(s)
  sensitivity-analyses.csv: 0 row(s)
  gold-questions.csv: 0 row(s)
  scientific-signoffs.csv: 0 row(s)
  user-feedback.csv: 0 row(s)
Errors (4):
  [internal_coverage] internal-external-matches.csv
  [gold_question_count] gold-questions.csv
  [missing_signoff_types] scientific-signoffs.csv
  [feedback_count] user-feedback.csv
```

### 5.2 校验正式输入

```bash
python3 scripts/validate-scientific-inputs.py \
  --input-dir /path/to/completed-scientific-inputs \
  --report-json /path/to/validation-report.json
```

通过示例：

```text
PASS: /path/to/completed-scientific-inputs
  ontology-classes.csv: 2 row(s)
  ontology-properties.csv: 2 row(s)
  entity-relation-mappings.csv: 2 row(s)
  internal-external-matches.csv: 248 row(s)
  effect-estimates.csv: 2 row(s)
  sensitivity-analyses.csv: 1 row(s)
  gold-questions.csv: 30 row(s)
  scientific-signoffs.csv: 6 row(s)
  user-feedback.csv: 5 row(s)
```

以上行数只是结构和校验示例，不代表正式科研数据。正式数据必须由科研方填写。

### 5.3 校验说明性示例

```bash
python3 scripts/validate-scientific-inputs.py \
  --input-dir /path/to/example-bundle \
  --allow-examples
```

`--allow-examples` 只用于测试和演示。正式交付命令不得使用该参数。

### 5.4 输出 JSON 报告

```bash
python3 scripts/validate-scientific-inputs.py \
  --input-dir /path/to/bundle \
  --format json \
  --report-json /path/to/validation.json
```

退出码：

- `0`：没有错误，校验通过。
- `1`：存在结构、数据、签认或隐私错误。

警告默认不影响退出码，但正式归档时应人工确认。

## 6. 自测

```bash
.venv/bin/python -m pytest tests/test_validate_scientific_inputs.py -q
```

测试覆盖：

- 完整示例包通过。
- 空模板失败。
- 正式模式拒绝示例记录。
- 缺列和重复 ID。
- 非法 Domain/Range。
- CI 上下界错误、效应量越界、非数值和单位缺失。
- 金标准题量不足及未签认。
- 科研签认缺失或 pending。
- 匿名反馈敏感表头和敏感值。

测试数据只存在于 pytest 临时目录，不构成正式科研数据。

## 7. 仍需科研方提供

- 经批准的 OWL、类层级、属性、Domain/Range 和实体关系映射。
- 248 条内部证据逐条对应的外部证据匹配及方向/显著性判断。
- 真实效应量、CI、单位、模型口径和敏感性分析。
- 30-50 道已审核金标准题。
- 科研负责人、统计负责人和医学审核人的签认记录及哈希。
- 5-10 名真实目标用户的自愿、匿名、已授权反馈。

在这些材料到位前，模板只能证明接入规范可执行，不能证明科研验收已经完成。
