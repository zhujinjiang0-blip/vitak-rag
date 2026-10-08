# 维生素 K 项目数据来源与分类

## 数据来源总览

项目数据分为外部文献数据和内部干预队列数据两大类。

| 类别 | 内容 | 规模 | 处理方式 | 数据来源标签 |
| --- | --- | ---: | --- | --- |
| 外部数据 | 已发表维生素 K 相关研究文献 | 564 篇，13,118 条对齐三元组，6,297 个唯一实体 | 大模型抽取、标准化、本体对齐 | `external` |
| 内部数据 | 项目组 395 人干预队列研究 | 395 名参与者的标准化个体证据 | 结构化读取和统计分析 | `internal` |

外部数据提供“已发表研究说了什么”的文献证据，内部数据提供“本项目队列发现了什么”的个体化证据。

## 外部数据

外部数据来自 564 篇维生素 K 研究文献。抽取结果保存为 `aligned_triples.csv`，每行是一条知识三元组，包含：

| 字段 | 含义 |
| --- | --- |
| `record_id` | 文献编号，例如 `VK0350` |
| `pmid` | PubMed ID，例如 `26875489` |
| `subject` | 主语原始名称 |
| `subject_normalized` | 主语标准化名称 |
| `subject_matched_class` | 主语匹配的本体类 |
| `subject_match_type` | 主语匹配类型 |
| `predicate` | 关系类型，例如 `improves`、`decreases`、`increases` |
| `object` | 宾语原始名称 |
| `object_normalized` | 宾语标准化名称 |
| `object_matched_class` | 宾语匹配的本体类 |
| `object_match_type` | 宾语匹配类型 |
| `source_sentence` | 文献中的原文支持句 |
| `evidence_score` | 证据等级分数 |
| `evidence_grade` | 证据等级标签 |
| `confidence_score` | 抽取置信度分数 |
| `confidence_grade` | 置信度等级 |

当前本体匹配覆盖率为 99.86%：

| 匹配类型 | 数量 | 占比 |
| --- | ---: | ---: |
| 精确匹配 | 234 | 3.7% |
| 别名匹配 | 20 | 0.3% |
| 语义匹配 | 124 | 2.0% |
| 类型类兜底 | 5,910 | 93.9% |
| 候选新类 | 9 | 0.1% |

高比例的类型类兜底说明当前图谱已经覆盖大部分实体，但细粒度本体子类仍需继续精化。

导入命令：

```bash
cd backend
../.venv/bin/python -m app.cli import-external-triples path/to/aligned_triples.csv
```

导入器会：

- 保留全部 17 个字段及原文支持句。
- 将来源标记为 `data_origin=external`、`access_scope=public`。
- 设置 `source_classification=external_literature_triple`。
- 按 `subject_normalized + subject_matched_class` 和 `object_normalized + object_matched_class` 生成稳定实体 ID。
- 将 `evidence_grade` 和 `confidence_score` 写入证据边。
- 生成新的版本快照，不会直接覆盖当前数据。

## 内部数据

内部数据来自项目组开展的前瞻性 395 人干预队列研究。数据的特点是格式统一、变量定义明确、无需再次抽取，并且每条证据具有强度标签。

内部数据导入时必须使用：

- `data_origin=internal`
- `access_scope=private`
- `data_owner=毕业设计内部资料` 或实际项目组名称
- `source_classification=internal_rct`、`internal_database` 或 `internal_document`

通用内部文档导入示例：

```bash
cd backend
../.venv/bin/python -m app.cli ingest path/to/internal-data.csv \
  --source-type rct \
  --data-origin internal \
  --data-owner "维生素K项目组" \
  --access-scope private \
  --source-classification internal_rct
```

395 人队列中“参与者、变量、关系、结局指标、效应值和证据强度”的最终列名映射，需要在拿到实际导出表后按列确认，不能仅凭现有描述猜测。

## 回答中的来源标识

后端 `Citation` 和前端证据卡会同时展示：

- `data_origin`：内部、外部、公开或合成。
- `source_classification`：更细的数据类型。
- `data_owner`：资料所属团队、机构或公开来源方。
- `access_scope`：数据访问范围。

这样用户在查看任何回答时，都能判断证据是来自已发表文献、本项目内部队列，还是演示数据。

