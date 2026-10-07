# 评测集说明

运行 `vitak generate-eval` 会生成 80 道分层问题，覆盖图谱关系、多跳路径、无证据拒答和安全边界。

运行 `vitak evaluate` 会比较：

- 纯文本向量检索。
- 纯图谱检索。
- 图谱增强混合检索。

评测结果写入 `data/eval/report.json`，包括 Recall@5、MRR@10、nDCG@10、引用准确率和 P95 延迟。

