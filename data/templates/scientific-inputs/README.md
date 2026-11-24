# 科研数据接入空模板

该目录只包含 CSV 表头，不包含正式科研数据。所有示例记录必须在 ID 或说明字段中带有
`EXAMPLE_` 或 `示例` 标记，并且只能使用 `--allow-examples` 进行演示性校验。

文件与用途：

| 文件 | 用途 |
| --- | --- |
| `ontology-classes.csv` | OWL 类、IRI、父类和签认状态 |
| `ontology-properties.csv` | 对象/数据类型属性及 Domain/Range |
| `entity-relation-mappings.csv` | 原始实体关系向规范类和属性的映射 |
| `internal-external-matches.csv` | 248 条内部证据与外部证据的人工匹配 |
| `effect-estimates.csv` | 效应量、CI、单位、模型及敏感性分析关联 |
| `sensitivity-analyses.csv` | 敏感性分析的模型、结论和签认 |
| `gold-questions.csv` | 30-50 道金标准题及审核状态 |
| `scientific-signoffs.csv` | 科研负责人对各类交付物的签认 |
| `user-feedback.csv` | 5-10 条匿名、授权、已审核的真实用户反馈 |

字段状态：

| 文件 | 必填列 | 可选列 | 条件字段 |
| --- | --- | --- | --- |
| `ontology-classes.csv` | `class_id`, `class_iri`, `label`, `status` | `parent_class_id`, `description` | `parent_class_id` 填写时必须引用现有类 |
| `ontology-properties.csv` | `property_id`, `property_iri`, `label`, `property_kind`, `domain_class_id`, `range_spec`, `status` | `description` | 对象属性的 `range_spec` 必须是类 ID；数据类型属性必须使用允许的数据类型 |
| `entity-relation-mappings.csv` | `mapping_id`, `subject_label`, `subject_class_id`, `relation_id`, `object_kind`, `object_label`, `status`, `evidence_id`, `reviewer_id` | `object_class_id`, `reviewed_at`, `notes` | `object_kind=class` 时 `object_class_id` 必填；`object_kind=literal` 时必须为空 |
| `internal-external-matches.csv` | `match_id`, `internal_evidence_id`, `external_evidence_id`, `match_status`, `direction`, `significance_status`, `review_status`, `reviewer_id`, `reviewed_at` | `context`, `notes` | `matched` 时外部证据 ID 必填；`no_external_match` 时可留空 |
| `effect-estimates.csv` | `estimate_id`, `evidence_id`, `effect_measure`, `effect_size`, `ci_low`, `ci_high`, `unit`, `model_type`, `model_context`, `status`, `reviewer_id` | `sensitivity_required`, `sensitivity_analysis_id`, `reviewed_at`, `notes` | `sensitivity_required=true` 时必须填写敏感性分析 ID |
| `sensitivity-analyses.csv` | `sensitivity_id`, `base_estimate_id`, `analysis_type`, `model_type`, `result_summary`, `supports_primary`, `status`, `reviewer_id` | `reviewed_at`, `notes` | `base_estimate_id` 必须引用现有效应量 |
| `gold-questions.csv` | `question_id`, `question`, `expected_intent`, `expected_evidence_ids`, `expect_abstain`, `safety_case`, `review_status`, `reviewer_id` | `boundary_notes` | `expect_abstain=false` 时预期证据 ID 必填 |
| `scientific-signoffs.csv` | `signoff_id`, `artifact_type`, `artifact_id`, `decision`, `signed_by`, `role`, `signed_at`, `artifact_sha256` | `scope`, `comments` | 六类 artifact 各需至少一条 `approved` 记录 |
| `user-feedback.csv` | `feedback_id`, `participant_code`, `task_id`, `consent_status`, `collected_at`, `rating_usefulness`, `rating_clarity`, `rating_trust`, `anonymous`, `moderation_status` | `comment`, `follow_up` | 必须为 5-10 条、匿名、授权且已审核反馈 |

完整字段定义、允许值和交叉校验规则见
[`docs/scientific-data-intake.md`](../../../docs/scientific-data-intake.md)。

校验命令：

```bash
python3 scripts/validate-scientific-inputs.py \
  --input-dir data/templates/scientific-inputs
```

空模板预期返回 `FAIL`，因为尚无正式数据、题量不足且没有科研签认。完整字段说明、交叉校验
规则和通过/失败示例见 `docs/scientific-data-intake.md`。
