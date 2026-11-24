# VitaK-RAG V2.0 T04-01 十题基线报告

- 生成时间：2026-11-24T15:04:55.937Z
- 数据版本：real-public-2026.11-structured
- 问题数量：10
- 平均耗时：531 ms
- P95 耗时：567 ms
- Claim 引用覆盖率：100.0%

## 汇总

| 指标 | 数值 |
| --- | ---: |
| 自动通过 | 10 |
| 部分通过 | 0 |
| 未通过 | 0 |
| 错误 | 0 |
| 有 Claim 的回答 | 10 |
| 有图谱路径的回答 | 10 |
| 有证据差异说明的回答 | 3 |
| 已完成初步复核 | 10 |
| 初步复核通过 | 10 |

> 自动状态用于初筛；`pass` 表示必需内容组和 Claim 引用覆盖达标，仍需人工科研复核。

## 关键缺口

- 无

## 逐题结果

| ID | 类别 | 自动状态 | Claim | 引用 | 路径 | 对比 | 耗时 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Q01 | 定义与形式 | pass | 3 | 3 | 3 | 0 | 532 ms |
| Q02 | 亚型与代谢 | pass | 3 | 3 | 3 | 0 | 539 ms |
| Q03 | 机制 | pass | 2 | 2 | 2 | 0 | 567 ms |
| Q04 | 药物相互作用 | pass | 5 | 4 | 4 | 0 | 526 ms |
| Q05 | 临床研究 | pass | 3 | 3 | 3 | 2 | 526 ms |
| Q06 | 阴性证据 | pass | 3 | 3 | 3 | 0 | 513 ms |
| Q07 | 交互与协同 | pass | 2 | 2 | 2 | 0 | 526 ms |
| Q08 | 研究差异 | pass | 3 | 3 | 3 | 1 | 527 ms |
| Q09 | 因果边界 | pass | 3 | 3 | 3 | 2 | 526 ms |
| Q10 | 检测解释 | pass | 3 | 3 | 3 | 0 | 524 ms |

## 回答记录

### Q01 维生素K1和K2有哪些主要区别？

- 意图：comparison
- 证据充分度：sufficient
- Claim 类型：general、mechanism
- 科学边界 Claim：1
- 引用：3
- 图谱路径：3
- 人工复核：approved

维生素K1和维生素K2都属于维生素K家族，但它们是不同形式，来源和体内行为并不完全相同。

维生素K1又称叶绿醌，是植物性食物中的主要形式，常见于深绿色叶菜和植物油。维生素K2是一组甲萘醌类形式，包括MK-4和MK-7，常见于肉类、蛋类、奶酪和纳豆等食物。两类形式都参与维生素K依赖蛋白的羧化，但侧链长度、半衰期和组织分布存在差异。

实际比较时不能简单判断哪一种更好，还要看食物来源、吸收、半衰期和具体健康目标。

证据：
- VK0064:9541523 · external/public · A · PMID 9541523 | Phylloquinone (vitamin K1), the predominant form in the diet, is present in high concentrations in leafy green vegetables and certain oils [38].
- VK0297:24835435 · external/public · A · PMID 24835435 | Two forms of Vitamin K are found in our diet: vitamin K1 (phylloquinone, found in leafy green vegetables) and vitamin K2 (menaquinones, found in cheese, meat, eggs, etc.).
- VK0412:29882816 · external/public · B- · PMID 29882816 | Vitamin K2 is distinguished from K1 by the presence of unsaturated side chain units varying in length from 1 to 14 repeats, hence named menaquinone-4, menaquinone-7 etc.

### Q02 MK-4和MK-7在人体内的代谢和生物学作用有什么区别？

- 意图：comparison
- 证据充分度：sufficient
- Claim 类型：general、mechanism
- 科学边界 Claim：1
- 引用：3
- 图谱路径：3
- 人工复核：approved

MK-4和MK-7都属于维生素K2，但它们的食物来源、半衰期和体内暴露特征不同，不能按同一种补充形式互换理解。

MK-4主要与动物性食物相关，而MK-7更常见于纳豆和部分发酵食品。MK-7通常具有更长半衰期和更高生物利用度，因此血清水平更稳定。两者都能参与维生素K依赖蛋白的羧化，但组织分布和具体生物学效应仍需结合研究条件解释。

现有证据支持两者在代谢特征和暴露稳定性上存在差异，但不能简单推导出哪一种在所有人身上效果更好。

证据：
- VK0351:26908424 · external/public · B · PMID 26908424 | Food sources of phylloquinone are green vegetables and several plant oils, whereas menaquinones are primarily found in meat and egg yolk (short-chain MK-4) and in fermented foods such as cheese and curd (MK-7 through MK-10, also referred to as the long-chain menaquinones).
- VK0676:41393956 · external/public · A · PMID 41393956 | Unlike other forms of vitamin K2, MK-7 derived from fermented soy has a long half-life and superior bioavailability, allowing for sustained carboxylation of Vitamin K–dependent proteins in extrahepatic tissues such as bone.
- VK0092:10874601 · external/public · C · PMID 10874601 | MK-7 has been shown to have anabolic effects on bone calcification as does MK-4.

### Q03 MK-7与骨钙素羧化有什么关系？

- 意图：general
- 证据充分度：sufficient
- Claim 类型：mechanism
- 科学边界 Claim：2
- 引用：2
- 图谱路径：2
- 人工复核：approved

从现有真实证据看，可以确认的信息如下。

MK-7参与骨钙素的活化或羧化。现有文献记录了MK-7与骨钙素之间的关系。

以上内容仅代表当前真实证据能够支持的范围。

证据：
- VK0676:41393956 · external/public · A · PMID 41393956 | Natto, a traditional Japanese fermented soybean food, is the richest natural source of menaquinone-7 (MK-7), a form of vitamin K2 involved in osteocalcin activation and bone mineralization.
- VK0092:10874601 · external/public · C · PMID 10874601 | Vitamin K2 is essential for the γ-carboxylation of osteocalcin, a bone matrix protein containing γ2-carboxyglutamic acid, which is synthesized in osteoblasts in bone tissues.

### Q04 维生素K与华法林之间有什么相互作用？

- 意图：drug_interactions
- 证据充分度：sufficient
- Claim 类型：mechanism
- 科学边界 Claim：5
- 引用：4
- 图谱路径：4
- 人工复核：approved

华法林与维生素 K 属于明确的药理学拮抗关系，需要结合机制、饮食和 INR 监测理解。

华法林通过抑制 VKORC1，阻断维生素 K 环氧化物还原，减少活性维生素 K 的再生，并影响维生素 K 依赖凝血因子的活化。两者是明确的药理学拮抗关系：维生素 K 摄入或补充会影响华法林的抗凝强度，需要结合 INR 和用药情况管理。富含维生素 K 的食物，例如菠菜、羽衣甘蓝等深绿色叶菜，可能降低 INR。华法林抗凝过度时，维生素 K 可在专业评估下用于纠正凝血状态，具体处理取决于 INR、出血情况和临床背景。华法林使用期间需要按医嘱监测 INR，并尽量保持日常维生素 K 摄入相对稳定，不应自行改变补充剂或摄入量。

以上结论由真实外部文献证据合成，具体剂量调整、停药或抗凝过度处理必须由医生或药师评估。

证据：
- VK0336:26433837 · external/public · A · PMID 26433837 | Warfarin exerts its anticoagulant effect by acting as a VKORC1 inhibitor, preventing the production of reduced Vitamin K, which is essential for the synthesis of blood clotting factors and other regulatory proteins.
- UNKNOWN_wadhera2014 · external/public · C · PMID NA | Certain foods that contain large amounts of Vitamin K (such as dark green leafy vegetables including spinach, brussel sprouts, and kale) can lower the INR, whereas certain medications (including many antibiotics) can increase the INR.
- UNKNOWN_unknown_Love DG_1999:10364766 · external/public · B- · PMID 10364766 | With minor INR elevation (INR <6) and no bleeding, simply stopping or reducing warfarin and monitoring may be sufficient. More excessive anticoagulation (INR 6-10) or minor bleeding can be managed with low-dose Vitamin K (1-5 mg subcutaneously or orally).
- UNKNOWN_phillips2010 · external/public · A · PMID NA | Warfarin therapy requires vigilant coagulation monitoring, clinical surveillance, and continuous patient education (Table 1).

### Q05 MK-7与胰岛素抵抗之间有哪些临床研究证据？

- 意图：research
- 证据充分度：sufficient
- Claim 类型：negative、conflict
- 科学边界 Claim：3
- 引用：3
- 图谱路径：3
- 人工复核：approved

现有公开证据还不能支持“补充MK-7一定能够降低HOMA-IR”这一结论。

叶绿醌摄入与空腹胰岛素、血糖、HOMA-IR和HbA1c没有显著关联。另有随机对照研究显示，两组HOMA-IR没有显著差异。但也有研究报告部分男性在补充后HOMA-IR下降，说明研究结果并不完全一致，且不能直接外推为MK-7的确定疗效。

这些研究并没有形成一致、可直接外推的MK-7干预结论。观察性关联或叶绿醌研究不能自动等同于MK-7的因果效果。

证据：
- VK0177:18614743 · external/public · B · PMID 18614743 | Phylloquinone intake was not associated with fasting insulin and glucose concentrations, HOMA-IR, or HbA1c.
- VK0223:20881072 · external/public · A · PMID 20881072 | HOMA-IR was similar in the 2 groups (1.52 ± 0.23 in the placebo-treated group compared with 2.24 ± 0.54 in the phylloquinone-treated group; P = NS).
- VK0261:23034962 · external/public · A · PMID 23034962 | the HOMA-IR significantly decreased during the intervention in men in the supplemented group.

### Q06 有没有研究发现维生素K与代谢指标无显著关联？

- 意图：negative_evidence
- 证据充分度：sufficient
- Claim 类型：negative
- 科学边界 Claim：3
- 引用：3
- 图谱路径：3
- 人工复核：approved

有。当前真实文献中保留了与代谢指标相关的阴性或未观察到显著关联的结果。

一项随机对照研究显示，叶绿醌补充没有显著影响CRP、IL-6、sVCAM-1、sICAM-1、总胆固醇或LDL-C。另一项研究显示，叶绿醌摄入与空腹胰岛素、血糖、HOMA-IR和HbA1c没有显著关联。还有研究报告两组HOMA-IR没有显著差异。

阴性结果不等于证明维生素K对所有指标完全无效，它说明在特定人群、剂量、时间和结局下没有观察到显著效应。

证据：
- VK0182:18807108 · external/public · A · PMID 18807108 | Compared to placebo, daily supplementation with 500 μg of phylloquinone did not affect inflammatory markers (CRP, IL-6, sVCAM-1 and sICAM-1), fibrinolytic activity (factor VIIc, fibrinogen-c and PAI-1), TC or LDL-C (Table 2). The supplementation did however result in a 15% increase in TG (P = 0.015) and a near-significant 5% decrease in HDL-C (P = 0.06).
- VK0177:18614743 · external/public · B · PMID 18614743 | Phylloquinone intake was not associated with fasting insulin and glucose concentrations, HOMA-IR, or HbA1c.
- VK0223:20881072 · external/public · A · PMID 20881072 | HOMA-IR was similar in the 2 groups (1.52 ± 0.23 in the placebo-treated group compared with 2.24 ± 0.54 in the phylloquinone-treated group; P = NS).

### Q07 MK-7与维生素D是否存在协同作用？

- 意图：functions
- 证据充分度：sufficient
- Claim 类型：general
- 科学边界 Claim：0
- 引用：2
- 图谱路径：2
- 人工复核：approved

现有公开证据不足以确认MK-7和维生素D之间存在明确的协同或统计交互作用。

已有随机干预研究把钙、维生素D3和MK-7作为联合营养背景，但研究目的并不是单独验证两者的统计交互。联合补充可同时提高维生素K2和25-羟基维生素D水平，但生物标志物升高不等于两者发生协同作用。

联合补充后两种营养素水平升高，只能说明暴露或依从性变化，不能单独证明协同效应。是否优于单独补充仍需针对交互结局的对照研究。

证据：
- VK0248:22392526 · external/public · B · PMID 22392526 | The objective of the present study was to examine the effect of dairy products enriched with calcium, vitamin D3, and phylloquinone (vitamin K1) or menaquinone-7 (vitamin K2) on parameters of bone metabolism in postmenopausal women following a 12-month intervention.
- VK0203:19959915 · external/public · A · PMID 19959915 | Menatetrenone with calcium and vitamin D supplementation increased the serum levels of vitamin K2 and 25-hydroxyvitamin D.

### Q08 不同研究关于维生素K与血脂的结论是否一致？

- 意图：comparison
- 证据充分度：sufficient
- Claim 类型：intervention、general、conflict
- 科学边界 Claim：2
- 引用：3
- 图谱路径：3
- 人工复核：approved

现有研究关于维生素K与血脂的结论并不完全一致，差异还会随血脂指标、维生素K形式和人群而变化。

一项随机对照研究显示，叶绿醌补充未显著改变总胆固醇和LDL-C，但甘油三酯增加约15%，HDL-C出现接近显著的变化。观察性研究则发现，循环叶绿醌与甘油三酯和LDL胆固醇呈正相关。另有研究提示较高甲萘醌摄入与HDL胆固醇/总胆固醇比值较高有关，说明不同血脂结局的方向并不一致。

因此不能把不同研究简单合并成一个统一方向。需要分别比较甘油三酯、总胆固醇、LDL-C和HDL-C，并区分干预研究与观察性关联。

证据：
- VK0182:18807108 · external/public · A · PMID 18807108 | Compared to placebo, daily supplementation with 500 μg of phylloquinone did not affect inflammatory markers (CRP, IL-6, sVCAM-1 and sICAM-1), fibrinolytic activity (factor VIIc, fibrinogen-c and PAI-1), TC or LDL-C (Table 2). The supplementation did however result in a 15% increase in TG (P = 0.015) and a near-significant 5% decrease in HDL-C (P = 0.06).
- VK0461:32359159 · external/public · A · PMID 32359159 | Circulating phylloquinone was significantly positively correlated with triglycerides, LDL cholesterol, systolic blood pressure, hypertension, and β-carotene intake (all P ≤ 0.03) and inversely correlated with CRP (P < 0.001).
- VK0215:20424220 · external/public · B · PMID 20424220 | The HDL cholesterol-to-total cholesterol ratio was higher with higher menaquinones intake (? 0.003 ± 0.001; P =0.034).

### Q09 有没有证据证明补充MK-7能够降低HOMA-IR？

- 意图：research
- 证据充分度：sufficient
- Claim 类型：negative、conflict
- 科学边界 Claim：3
- 引用：3
- 图谱路径：3
- 人工复核：approved

现有公开证据还不能支持“补充MK-7一定能够降低HOMA-IR”这一结论。

叶绿醌摄入与空腹胰岛素、血糖、HOMA-IR和HbA1c没有显著关联。另有随机对照研究显示，两组HOMA-IR没有显著差异。但也有研究报告部分男性在补充后HOMA-IR下降，说明研究结果并不完全一致，且不能直接外推为MK-7的确定疗效。

这些研究并没有形成一致、可直接外推的MK-7干预结论。观察性关联或叶绿醌研究不能自动等同于MK-7的因果效果。

证据：
- VK0177:18614743 · external/public · B · PMID 18614743 | Phylloquinone intake was not associated with fasting insulin and glucose concentrations, HOMA-IR, or HbA1c.
- VK0223:20881072 · external/public · A · PMID 20881072 | HOMA-IR was similar in the 2 groups (1.52 ± 0.23 in the placebo-treated group compared with 2.24 ± 0.54 in the phylloquinone-treated group; P = NS).
- VK0261:23034962 · external/public · A · PMID 23034962 | the HOMA-IR significantly decreased during the intervention in men in the supplemented group.

### Q10 血清MK-7浓度多少属于低、中、高？

- 意图：general
- 证据充分度：sufficient
- Claim 类型：general
- 科学边界 Claim：0
- 引用：3
- 图谱路径：3
- 人工复核：approved

目前没有可普遍用于临床判读的血清MK-7低、中、高统一阈值，研究通常按人群分布、四分位数或检测方法来分组。

不同地区人群的血清MK-7差异很大，例如东京绝经后女性的水平可比英国女性高约14倍，主要与纳豆摄入有关。研究可测量血浆维生素K1、MK-4和MK-7浓度，但测量本身不等于建立了统一的低、中、高临床范围。干预研究中的剂量和浓度分组均服务于特定研究设计，不能直接转换为面向所有人的临床阈值。

同一个MK-7浓度在不同地区、饮食背景、采样时间和检测平台下不能直接套用固定标签，更不应据此自行判断缺乏或决定补充剂量。

证据：
- VK0274:23828145 · external/public · A · PMID 23828145 | In fact, serum MK-7 is 14 times higher in postmenopausal women living in Tokyo than in English women, and this difference is largely attributable to intake of natto, a fermented soybean food.
- VK0350:26875489 · external/public · A · PMID 26875489 | Plasma vitamin K1, MK-4, and MK-7 concentrations were analyzed as described previously.
- VK0491:33159574 · external/public · A · PMID 33159574 | The vitamin K2 group received 180 μg vitamin K2 capsules in the form of MK-7 twice a day after breakfast and dinner for 12 weeks (3 months).
