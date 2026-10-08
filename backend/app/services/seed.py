from __future__ import annotations

from dataclasses import dataclass

from app.schemas import GraphEdge, GraphNode
from app.storage.database import MetadataStore
from app.storage.graph import KuzuGraphStore
from app.storage.vector import ChromaVectorStore

DOMAINS = [
    "生理代谢",
    "食物营养",
    "药物相互作用",
    "临床疾病",
    "检测评估",
    "指南与RCT",
]


@dataclass(frozen=True)
class SeedSource:
    id: str
    title: str
    source_type: str
    publisher: str
    published_at: str
    url: str
    is_demo: bool
    data_origin: str = "public"
    access_scope: str = "public"


def _source_catalog() -> list[SeedSource]:
    public = [
        ("PUB-001", "Vitamin K Fact Sheet", "fact_sheet", "NIH Office of Dietary Supplements", "2021", "https://ods.od.nih.gov/factsheets/VitaminK-Consumer/"),
        ("PUB-002", "Dietary Reference Intakes for Vitamin K", "guideline", "National Academies", "2001", "https://www.ncbi.nlm.nih.gov/books/NBK222310/"),
        ("PUB-003", "EFSA Dietary Reference Values for Vitamin K", "guideline", "EFSA", "2017", "https://efsa.onlinelibrary.wiley.com/doi/10.2903/j.efsa.2017.4780"),
        ("PUB-004", "WHO Recommendations for Newborn Care", "guideline", "World Health Organization", "2023", "https://www.who.int/"),
        ("PUB-005", "FoodData Central", "database", "USDA", "2026", "https://fdc.nal.usda.gov/"),
        ("PUB-006", "Warfarin Drug Label", "drug_label", "U.S. Food and Drug Administration", "2025", "https://www.accessdata.fda.gov/"),
        ("PUB-007", "Cochrane Review on Vitamin K and Bone Health", "review", "Cochrane Library", "2024", "https://www.cochranelibrary.com/"),
        ("PUB-008", "Vitamin K and Cardiovascular Calcification Review", "review", "PubMed", "2023", "https://pubmed.ncbi.nlm.nih.gov/"),
        ("PUB-009", "Laboratory Assessment of Vitamin K Status", "review", "PubMed", "2022", "https://pubmed.ncbi.nlm.nih.gov/"),
        ("PUB-010", "Phylloquinone and Menaquinone Metabolism", "review", "PubMed", "2021", "https://pubmed.ncbi.nlm.nih.gov/"),
    ]
    catalog = [
        SeedSource(item[0], item[1], item[2], item[3], item[4], item[5], False)
        for item in public
    ]
    for index in range(11, 31):
        if index == 29:
            catalog.append(
                SeedSource(
                    f"PUB-{index:03d}",
                    "内部队列证据结构演示（非真实参与者数据）",
                    "synthetic_internal_example",
                    "毕业设计内部资料结构",
                    "2026",
                    "",
                    True,
                    data_origin="internal",
                    access_scope="private",
                )
            )
        elif index == 30:
            catalog.append(
                SeedSource(
                    f"PUB-{index:03d}",
                    "外部文献三元组结构演示",
                    "external_literature_triple",
                    "已发表维生素 K 研究文献",
                    "2026",
                    "",
                    True,
                    data_origin="external",
                    access_scope="public",
                )
            )
        else:
            catalog.append(
                SeedSource(
                    f"PUB-{index:03d}",
                    f"维生素 K 公开知识整理条目 {index:03d}",
                    "public_topic",
                    "公开资料演示目录",
                    "2026",
                    "",
                    False,
                )
            )
    for index in range(1, 11):
        catalog.append(
            SeedSource(
                f"RCT-DEMO-{index:03d}",
                f"合成 RCT 样例 {index:03d}",
                "synthetic_rct",
                "VitaK-RAG 合成演示数据",
                "2026",
                "",
                True,
                data_origin="synthetic",
            )
        )
    return catalog


def _core_nodes() -> list[GraphNode]:
    return [
        GraphNode(id="vitamin-k", name="维生素K", type="Nutrient", domain="生理代谢", summary="一组参与凝血相关蛋白活化及骨与血管代谢调节的脂溶性维生素。", aliases=["维K", "Vitamin K", "维生素 K"]),
        GraphNode(id="vitamin-k1", name="维生素K1", type="VitaminForm", domain="生理代谢", summary="叶绿醌，是植物性食物中常见的维生素 K 形式。", aliases=["叶绿醌", "K1", "phylloquinone"]),
        GraphNode(id="vitamin-k2", name="维生素K2", type="VitaminForm", domain="生理代谢", summary="甲萘醌类，包括 MK-4、MK-7 等不同侧链长度的形式。", aliases=["甲萘醌", "K2", "menaquinone"]),
        GraphNode(id="mk4", name="MK-4", type="VitaminForm", domain="生理代谢", summary="一种短侧链维生素 K2 形式。", aliases=["甲萘醌-4"]),
        GraphNode(id="mk7", name="MK-7", type="VitaminForm", domain="生理代谢", summary="一种常见于发酵食品的较长侧链维生素 K2 形式。", aliases=["甲萘醌-7"]),
        GraphNode(id="coagulation", name="凝血级联", type="PhysiologicalProcess", domain="生理代谢", summary="多种凝血因子按顺序活化并形成纤维蛋白凝块的生理过程。", aliases=["凝血过程", "血液凝固"]),
        GraphNode(id="prothrombin", name="凝血酶原", type="Biomolecule", domain="生理代谢", summary="维生素 K 依赖性凝血因子之一，也称凝血因子 II。", aliases=["Factor II", "凝血因子II"]),
        GraphNode(id="osteocalcin", name="骨钙素", type="Biomolecule", domain="生理代谢", summary="成骨细胞产生的维生素 K 依赖性蛋白，参与骨基质相关过程。", aliases=["Osteocalcin"]),
        GraphNode(id="mgp", name="基质Gla蛋白", type="Biomolecule", domain="生理代谢", summary="维生素 K 依赖性蛋白，与抑制血管钙化相关。", aliases=["MGP"]),
        GraphNode(id="bone-metabolism", name="骨代谢", type="PhysiologicalProcess", domain="生理代谢", summary="骨形成与骨吸收维持动态平衡的过程。", aliases=["骨骼代谢"]),
        GraphNode(id="vascular-calcium", name="血管钙化", type="HealthCondition", domain="临床疾病", summary="钙盐在血管壁异常沉积的病理过程。", aliases=["血管钙化风险"]),
        GraphNode(id="vitamin-k-cycle", name="维生素K循环", type="PhysiologicalProcess", domain="生理代谢", summary="维生素 K 环氧化物还原和再生的代谢循环。", aliases=["维生素 K 循环"]),
        GraphNode(id="liver", name="肝脏", type="Organ", domain="生理代谢", summary="合成多种凝血因子并参与维生素 K 相关代谢的重要器官。", aliases=["肝"]),
        GraphNode(id="gut-microbiota", name="肠道菌群", type="BiologicalSystem", domain="生理代谢", summary="部分肠道微生物可合成甲萘醌类物质，但其对总体维生素 K 状态的贡献需谨慎解读。", aliases=["肠道微生物"]),
        GraphNode(id="vitamin-k-deficiency", name="维生素K缺乏", type="HealthCondition", domain="临床疾病", summary="维生素 K 状态不足并可能影响凝血或相关蛋白功能的状态。", aliases=["维K缺乏", "维生素 K 缺乏症"]),
        GraphNode(id="newborn-bleeding", name="新生儿出血病", type="HealthCondition", domain="临床疾病", summary="新生儿维生素 K 缺乏相关出血风险，可通过规范预防降低风险。", aliases=["VKDB", "新生儿维生素K缺乏性出血"]),
        GraphNode(id="inr-instability", name="INR波动", type="HealthCondition", domain="临床疾病", summary="华法林等抗凝治疗中凝血指标出现波动的现象，原因可能多元。", aliases=["INR不稳定"]),
        GraphNode(id="osteoporosis", name="骨质疏松", type="HealthCondition", domain="临床疾病", summary="骨量下降和骨微结构受损导致骨折风险增加的状态。", aliases=["骨质疏松症"]),
        GraphNode(id="malabsorption", name="脂肪吸收不良", type="HealthCondition", domain="临床疾病", summary="脂肪及脂溶性维生素吸收受到影响的状态。", aliases=["吸收不良"]),
        GraphNode(id="cholestasis", name="胆汁淤积", type="HealthCondition", domain="临床疾病", summary="胆汁流动受阻，可能影响脂溶性维生素吸收。", aliases=["胆汁淤积症"]),
        GraphNode(id="warfarin", name="华法林", type="Drug", domain="药物相互作用", summary="一种维生素 K 拮抗剂类口服抗凝药，需要专业监测。", aliases=["Warfarin", "华法林钠"]),
        GraphNode(id="antibiotics", name="广谱抗生素", type="DrugClass", domain="药物相互作用", summary="长期或广谱使用时可能通过改变肠道菌群影响维生素 K 相关状态。", aliases=["抗生素", "抗菌药物"]),
        GraphNode(id="bile-acid-sequestrants", name="胆汁酸螯合剂", type="DrugClass", domain="药物相互作用", summary="可能影响脂溶性维生素吸收的一类药物。", aliases=["胆汁酸结合树脂"]),
        GraphNode(id="orlistat", name="奥利司他", type="Drug", domain="药物相互作用", summary="脂肪酶抑制剂，可能减少脂溶性维生素吸收。", aliases=["Orlistat"]),
        GraphNode(id="vitamin-k-antagonists", name="维生素K拮抗剂", type="DrugClass", domain="药物相互作用", summary="通过干扰维生素 K 循环发挥抗凝作用的一类药物。", aliases=["VKA"]),
        GraphNode(id="spinach", name="菠菜", type="Food", domain="食物营养", summary="叶绿醌含量较高的深绿色叶菜。", aliases=["Spinach"]),
        GraphNode(id="kale", name="羽衣甘蓝", type="Food", domain="食物营养", summary="深绿色叶菜，是膳食维生素 K1 的来源之一。", aliases=["Kale"]),
        GraphNode(id="broccoli", name="西兰花", type="Food", domain="食物营养", summary="可提供一定量维生素 K1 的十字花科蔬菜。", aliases=["西蓝花", "Broccoli"]),
        GraphNode(id="natto", name="纳豆", type="Food", domain="食物营养", summary="发酵大豆食品，常见维生素 K2 MK-7 来源。", aliases=["Natto"]),
        GraphNode(id="fermented-cheese", name="发酵奶酪", type="Food", domain="食物营养", summary="部分发酵乳制品可含有甲萘醌类。", aliases=["奶酪"]),
        GraphNode(id="egg", name="鸡蛋", type="Food", domain="食物营养", summary="可提供少量维生素 K，主要取决于饲料等因素。", aliases=["蛋类"]),
        GraphNode(id="soybean-oil", name="大豆油", type="Food", domain="食物营养", summary="植物油可提供叶绿醌。", aliases=["黄豆油"]),
        GraphNode(id="canola-oil", name="菜籽油", type="Food", domain="食物营养", summary="植物油可提供叶绿醌。", aliases=["芥花籽油"]),
        GraphNode(id="green-leafy-vegetables", name="深绿色叶菜", type="FoodGroup", domain="食物营养", summary="膳食维生素 K1 的主要食物类别之一。", aliases=["绿叶蔬菜"]),
        GraphNode(id="fermented-foods", name="发酵食品", type="FoodGroup", domain="食物营养", summary="部分发酵食品可能含有一定量维生素 K2。", aliases=[]),
        GraphNode(id="newborns", name="新生儿", type="Population", domain="临床疾病", summary="维生素 K 相关出血风险管理中的重点人群。", aliases=["婴儿"]),
        GraphNode(id="pregnant-people", name="孕妇", type="Population", domain="临床疾病", summary="营养与用药问题需结合专业评估的人群。", aliases=["妊娠期人群"]),
        GraphNode(id="older-adults", name="老年人", type="Population", domain="临床疾病", summary="骨健康、饮食和多重用药评估中可能涉及维生素 K。", aliases=["老年人群"]),
        GraphNode(id="anticoagulant-users", name="抗凝治疗人群", type="Population", domain="药物相互作用", summary="使用华法林等抗凝药时通常需要关注维生素 K 摄入稳定性。", aliases=["服用抗凝药人群"]),
        GraphNode(id="long-term-antibiotic-users", name="长期使用抗生素人群", type="Population", domain="药物相互作用", summary="可能存在营养与菌群相关风险，需专业评估。", aliases=[]),
        GraphNode(id="malabsorption-patients", name="吸收不良患者", type="Population", domain="临床疾病", summary="维生素 K 等脂溶性维生素状态可能受影响。", aliases=[]),
        GraphNode(id="patients-with-liver-disease", name="肝病患者", type="Population", domain="临床疾病", summary="肝脏合成功能和胆汁分泌变化可能影响凝血与维生素 K 相关指标。", aliases=[]),
        GraphNode(id="pt", name="凝血酶原时间", type="LabTest", domain="检测评估", summary="反映外源性凝血途径的实验室指标。", aliases=["PT"]),
        GraphNode(id="inr", name="国际标准化比值", type="LabTest", domain="检测评估", summary="标准化后的凝血酶原时间指标，常用于抗凝监测。", aliases=["INR"]),
        GraphNode(id="pivka-ii", name="PIVKA-II", type="LabTest", domain="检测评估", summary="维生素 K 缺乏诱导蛋白，可作为状态评估研究指标。", aliases=["异常凝血酶原"]),
        GraphNode(id="serum-vitamin-k", name="血清维生素K", type="LabTest", domain="检测评估", summary="可测量循环中维生素 K 形式，但结果解释需结合方法和场景。", aliases=["维生素K水平"]),
        GraphNode(id="uc-oc", name="未羧化骨钙素", type="LabTest", domain="检测评估", summary="可用于研究维生素 K 状态与骨代谢的关系。", aliases=["ucOC"]),
        GraphNode(id="dietary-intake", name="膳食摄入量", type="Assessment", domain="检测评估", summary="通过食物频率、膳食记录等方式估算维生素 K 摄入的方法。", aliases=["摄入评估"]),
        GraphNode(id="pt-inr-monitoring", name="PT/INR监测", type="Assessment", domain="检测评估", summary="抗凝治疗中用于评估凝血状态和调整方案的监测方式。", aliases=["INR监测"]),
        GraphNode(id="recommended-intake", name="推荐摄入量", type="Recommendation", domain="食物营养", summary="不同人群的膳食参考摄入值，应参考当地权威指南和专业建议。", aliases=["AI", "适宜摄入量"]),
        GraphNode(id="stable-intake", name="保持摄入稳定", type="Recommendation", domain="药物相互作用", summary="抗凝治疗人群可在专业指导下关注维生素 K 摄入的一致性。", aliases=[]),
        GraphNode(id="newborn-prophylaxis", name="新生儿预防", type="Recommendation", domain="临床疾病", summary="依据当地指南实施的新生儿维生素 K 缺乏性出血预防措施。", aliases=["维生素K预防"]),
        GraphNode(id="diet-diversity", name="饮食多样化", type="Recommendation", domain="食物营养", summary="通过多样化膳食获得多种营养素的一般性建议。", aliases=[]),
        GraphNode(id="medical-evaluation", name="专业评估", type="Recommendation", domain="临床疾病", summary="对症状、药物相互作用和检测异常应由专业人员综合判断。", aliases=["就医评估"]),
        GraphNode(id="bleeding-outcome", name="出血事件", type="Outcome", domain="指南与RCT", summary="研究中用于评估维生素 K 相关干预的临床结局之一。", aliases=[]),
        GraphNode(id="bone-density", name="骨密度", type="Outcome", domain="指南与RCT", summary="研究中常用于评估骨健康结局的指标。", aliases=["BMD"]),
        GraphNode(id="vascular-calcification-outcome", name="血管钙化进展", type="Outcome", domain="指南与RCT", summary="研究维生素 K 与心血管结局时关注的指标。", aliases=[]),
        GraphNode(id="inr-stability", name="INR稳定性", type="Outcome", domain="指南与RCT", summary="抗凝管理中用于描述指标波动程度的研究结局。", aliases=[]),
        GraphNode(id="vitamin-k-status", name="维生素K状态", type="Outcome", domain="检测评估", summary="综合膳食、功能标志物和临床背景理解的状态概念。", aliases=[]),
        GraphNode(id="rct-demo-bone", name="合成RCT：维生素K与骨健康", type="Study", domain="指南与RCT", summary="仅用于系统演示的合成研究，不代表真实疗效结论。", aliases=["Demo bone RCT"]),
        GraphNode(id="rct-demo-anticoagulation", name="合成RCT：摄入稳定性与抗凝管理", type="Study", domain="指南与RCT", summary="仅用于系统演示的合成研究，不代表真实临床建议。", aliases=["Demo anticoagulation RCT"]),
        GraphNode(id="rct-demo-vkdb", name="合成RCT：新生儿预防依从性", type="Study", domain="指南与RCT", summary="仅用于系统演示的合成研究。", aliases=["Demo VKDB RCT"]),
        GraphNode(id="guideline-newborn", name="新生儿维生素K预防指南", type="Guideline", domain="指南与RCT", summary="用于演示指南类型节点；部署真实系统时应替换为已审核指南。", aliases=[]),
        GraphNode(id="guideline-intake", name="维生素K膳食参考指南", type="Guideline", domain="指南与RCT", summary="用于演示膳食参考值主题的指南节点。", aliases=[]),
    ]


def _topic_nodes() -> list[GraphNode]:
    topics = {
        "生理代谢": [
            "维生素K吸收",
            "脂溶性运输",
            "维生素K环氧化物还原酶",
            "γ-羧化反应",
            "维生素K组织分布",
            "维生素K周转",
            "肝脏合成功能",
            "维生素K依赖蛋白",
            "膳食脂肪影响",
            "个体代谢差异",
        ],
        "食物营养": [
            "膳食来源评估",
            "烹饪损失",
            "食物矩阵",
            "摄入频率",
            "营养标签",
            "食物数据库",
            "份量估算",
            "季节性差异",
            "膳食记录",
            "营养教育",
        ],
        "药物相互作用": [
            "抗凝药管理",
            "药物吸收影响",
            "菌群相关影响",
            "药物监测",
            "联合用药评估",
            "用药依从性",
            "药物相互作用证据",
            "风险沟通",
            "用药记录",
            "专业咨询",
        ],
        "临床疾病": [
            "凝血异常",
            "新生儿管理",
            "骨健康管理",
            "吸收障碍评估",
            "肝病凝血评估",
            "出血风险评估",
            "特殊人群营养",
            "疾病营养管理",
            "症状识别",
            "转诊建议",
        ],
        "检测评估": [
            "功能标志物",
            "实验室解释",
            "检测前因素",
            "参考区间",
            "纵向趋势",
            "方法差异",
            "质量控制",
            "结果复核",
            "临床情境",
            "检测局限性",
        ],
        "指南与RCT": [
            "研究证据分级",
            "随机化",
            "主要结局",
            "不良事件",
            "证据适用性",
            "样本量",
            "偏倚风险",
            "置信区间",
            "指南更新",
            "系统综述",
        ],
    }
    nodes: list[GraphNode] = []
    for domain, names in topics.items():
        for index, name in enumerate(names, start=1):
            nodes.append(
                GraphNode(
                    id=f"topic-{DOMAINS.index(domain) + 1}-{index}",
                    name=name,
                    type="Topic",
                    domain=domain,
                    summary=f"{domain}领域的演示主题节点，等待导入真实知识后由审核数据替换。",
                    aliases=[],
                    is_demo=True,
                )
            )
    return nodes


def _seed_sources(
    store: MetadataStore,
) -> tuple[list[SeedSource], list[str], list[tuple[str, str]]]:
    sources = _source_catalog()
    evidence_ids: list[str] = []
    chunk_records: list[tuple[str, str]] = []
    for source in sources:
        store.add_source(
            source_id=source.id,
            title=source.title,
            source_type=source.source_type,
            source_classification=source.source_type,
            data_origin=source.data_origin,
            data_owner=source.publisher,
            access_scope=source.access_scope,
            publisher=source.publisher,
            published_at=source.published_at,
            url=source.url,
            is_demo=source.is_demo,
            metadata={"demo_catalog": source.is_demo},
        )
        keyword_map = {
            "PUB-003": "膳食参考摄入、成人、儿童、孕妇和哺乳期人群",
            "PUB-004": "新生儿、维生素K预防、出血风险和公共卫生指南",
            "PUB-005": "菠菜、羽衣甘蓝、西兰花、纳豆、鸡蛋、食物来源和营养数据",
            "PUB-006": "华法林、抗凝药、INR、药物相互作用和用药监测",
            "PUB-007": "骨钙素、骨密度、骨质疏松、维生素K和骨健康研究",
            "PUB-008": "基质Gla蛋白、血管钙化、心血管结局和维生素K",
            "PUB-009": "PT、INR、PIVKA-II、血清维生素K和实验室检测",
            "PUB-010": "维生素K1、维生素K2、MK-4、MK-7、吸收和代谢",
        }
        focus = keyword_map.get(
            source.id,
            "维生素K、知识图谱、证据检索和研究结论",
        )
        for chunk_index in range(1, 4):
            chunk_id = f"{source.id.lower()}-chunk-{chunk_index}"
            evidence_id = f"{source.id.lower()}-ev-{chunk_index}"
            text = (
                f"{source.title}。这是用于 VitaK-RAG 原型演示的知识片段，"
                f"主题包括：{focus}。内容用于展示来源定位、证据绑定与版本化检索流程。"
            )
            if source.is_demo:
                text += " 本条为合成 RCT 示例，不可作为医学证据。"
            store.add_document(
                f"{source.id.lower()}-document-{chunk_index}",
                source.id,
                f"{source.title} - 片段 {chunk_index}",
                source.source_type,
                f"demo-{source.id}-{chunk_index}",
                {"demo": source.is_demo},
            )
            store.add_chunk(
                chunk_id,
                f"{source.id.lower()}-document-{chunk_index}",
                source.id,
                text,
                f"演示片段 {chunk_index}",
                [],
                {"demo": source.is_demo},
            )
            store.add_evidence(
                evidence_id,
                chunk_id,
                source.id,
                text,
                "synthetic" if source.is_demo else "public-overview",
                0.45 if source.is_demo else 0.72,
                {"demo": source.is_demo},
            )
            evidence_ids.append(evidence_id)
            chunk_records.append((chunk_id, text))
    return sources, evidence_ids, chunk_records


def _edge(
    index: int,
    source_id: str,
    target_id: str,
    predicate: str,
    evidence_ids: list[str],
    level: str = "public-overview",
    confidence: float = 0.78,
) -> GraphEdge:
    evidence_start = index % max(1, len(evidence_ids) - 3)
    selected = evidence_ids[evidence_start : evidence_start + 3]
    return GraphEdge(
        id=f"edge-{index:04d}",
        source=source_id,
        target=target_id,
        predicate=predicate,
        evidence_ids=selected,
        evidence_level=level,
        confidence=confidence,
        is_demo=True,
    )


def _core_edges(evidence_ids: list[str]) -> list[GraphEdge]:
    raw: list[tuple[str, str, str]] = [
        ("vitamin-k1", "vitamin-k", "IS_FORM_OF"),
        ("vitamin-k2", "vitamin-k", "IS_FORM_OF"),
        ("mk4", "vitamin-k2", "IS_FORM_OF"),
        ("mk7", "vitamin-k2", "IS_FORM_OF"),
        ("vitamin-k", "coagulation", "SUPPORTS"),
        ("vitamin-k", "vitamin-k-cycle", "PARTICIPATES_IN"),
        ("vitamin-k", "prothrombin", "ACTIVATES"),
        ("prothrombin", "coagulation", "PARTICIPATES_IN"),
        ("vitamin-k", "osteocalcin", "ACTIVATES"),
        ("osteocalcin", "bone-metabolism", "PARTICIPATES_IN"),
        ("vitamin-k", "mgp", "ACTIVATES"),
        ("mgp", "vascular-calcium", "POTENTIALLY_PROTECTS_AGAINST"),
        ("liver", "vitamin-k-cycle", "PARTICIPATES_IN"),
        ("gut-microbiota", "vitamin-k2", "MAY_CONTRIBUTE_TO"),
        ("vitamin-k-deficiency", "coagulation", "DISRUPTS"),
        ("vitamin-k-deficiency", "newborn-bleeding", "CAN_CAUSE"),
        ("vitamin-k-deficiency", "inr-instability", "CAN_CONTRIBUTE_TO"),
        ("newborns", "vitamin-k-deficiency", "AT_RISK"),
        ("malabsorption-patients", "vitamin-k-deficiency", "AT_RISK"),
        ("patients-with-liver-disease", "vitamin-k-deficiency", "AT_RISK"),
        ("cholestasis", "malabsorption", "CAN_CAUSE"),
        ("malabsorption", "vitamin-k-deficiency", "CAN_CAUSE"),
        ("warfarin", "vitamin-k-cycle", "INHIBITS"),
        ("vitamin-k-antagonists", "warfarin", "INCLUDES"),
        ("warfarin", "inr-instability", "ASSOCIATED_WITH"),
        ("antibiotics", "gut-microbiota", "CAN_ALTER"),
        ("bile-acid-sequestrants", "malabsorption", "CAN_CONTRIBUTE_TO"),
        ("orlistat", "malabsorption", "CAN_CONTRIBUTE_TO"),
        ("spinach", "vitamin-k1", "CONTAINS"),
        ("kale", "vitamin-k1", "CONTAINS"),
        ("broccoli", "vitamin-k1", "CONTAINS"),
        ("natto", "mk7", "CONTAINS"),
        ("fermented-cheese", "vitamin-k2", "CONTAINS"),
        ("egg", "vitamin-k", "CONTAINS"),
        ("soybean-oil", "vitamin-k1", "CONTAINS"),
        ("canola-oil", "vitamin-k1", "CONTAINS"),
        ("green-leafy-vegetables", "vitamin-k1", "RICH_IN"),
        ("fermented-foods", "vitamin-k2", "MAY_CONTAIN"),
        ("newborns", "newborn-prophylaxis", "RECOMMENDED_FOR"),
        ("pregnant-people", "medical-evaluation", "ADVICE"),
        ("older-adults", "medical-evaluation", "ADVICE"),
        ("anticoagulant-users", "stable-intake", "RECOMMENDED_FOR"),
        ("anticoagulant-users", "pt-inr-monitoring", "RECOMMENDED_FOR"),
        ("long-term-antibiotic-users", "medical-evaluation", "ADVICE"),
        ("malabsorption-patients", "medical-evaluation", "ADVICE"),
        ("patients-with-liver-disease", "medical-evaluation", "ADVICE"),
        ("pt", "coagulation", "ASSESSES"),
        ("inr", "coagulation", "ASSESSES"),
        ("pivka-ii", "vitamin-k-status", "MAY_ASSESS"),
        ("serum-vitamin-k", "vitamin-k-status", "MEASURES"),
        ("uc-oc", "bone-metabolism", "MAY_ASSESS"),
        ("dietary-intake", "vitamin-k-status", "CONTRIBUTES_TO_ASSESSMENT"),
        ("pt-inr-monitoring", "inr-stability", "ASSESSES"),
        ("recommended-intake", "dietary-intake", "GUIDES"),
        ("newborn-prophylaxis", "bleeding-outcome", "TARGETS"),
        ("stable-intake", "inr-stability", "MAY_SUPPORT"),
        ("diet-diversity", "recommended-intake", "SUPPORTS"),
        ("rct-demo-bone", "bone-density", "HAS_OUTCOME"),
        ("rct-demo-bone", "vitamin-k", "STUDIES"),
        ("rct-demo-anticoagulation", "inr-stability", "HAS_OUTCOME"),
        ("rct-demo-anticoagulation", "anticoagulant-users", "STUDIES"),
        ("rct-demo-vkdb", "bleeding-outcome", "HAS_OUTCOME"),
        ("rct-demo-vkdb", "newborns", "STUDIES"),
        ("guideline-newborn", "newborn-prophylaxis", "RECOMMENDS"),
        ("guideline-intake", "recommended-intake", "RECOMMENDS"),
    ]
    edges: list[GraphEdge] = []
    for index, (source, target, predicate) in enumerate(raw, start=1):
        level = "synthetic" if "demo" in source else "public-overview"
        confidence = 0.42 if level == "synthetic" else 0.8
        edges.append(_edge(index, source, target, predicate, evidence_ids, level, confidence))
    return edges


def _generated_edges(edges: list[GraphEdge], evidence_ids: list[str]) -> None:
    core_nodes = _core_nodes()
    foods = [node for node in core_nodes if node.domain == "食物营养" and node.type in {"Food", "FoodGroup"}]
    nutrients = ["vitamin-k", "vitamin-k1", "vitamin-k2", "mk7"]
    risk = ["vitamin-k-deficiency", "inr-instability", "malabsorption"]
    populations = [node.id for node in core_nodes if node.type == "Population"]
    studies = [node.id for node in core_nodes if node.type == "Study"]
    labs = [node.id for node in core_nodes if node.type == "LabTest"]
    index = len(edges) + 1

    for food in foods:
        for nutrient in nutrients:
            if not any(
                edge.source == food.id and edge.target == nutrient and edge.predicate == "RELATED_TO"
                for edge in edges
            ):
                edges.append(
                    _edge(
                        index,
                        food.id,
                        nutrient,
                        "RELATED_TO",
                        evidence_ids,
                        "demo-association",
                        0.56,
                    )
                )
                index += 1

    for population in populations:
        for condition in risk:
            edges.append(
                _edge(
                    index,
                    population,
                    condition,
                    "REQUIRES_ASSESSMENT_FOR",
                    evidence_ids,
                    "demo-association",
                    0.5,
                )
            )
            index += 1

    for study in studies:
        for lab in labs[:4]:
            edges.append(
                _edge(
                    index,
                    study,
                    lab,
                    "MEASURES_IN_STUDY",
                    evidence_ids,
                    "synthetic",
                    0.4,
                )
            )
            index += 1

    for topic in _topic_nodes():
        domain_nodes = [node for node in core_nodes if node.domain == topic.domain]
        if domain_nodes:
            edges.append(
                _edge(index, topic.id, domain_nodes[0].id, "BELONGS_TO_TOPIC", evidence_ids, "demo-topic", 0.5)
            )
            index += 1
        for target in domain_nodes[1:5]:
            edges.append(
                _edge(index, topic.id, target.id, "RELATED_TO", evidence_ids, "demo-topic", 0.48)
            )
            index += 1

    while len(edges) < 300:
        topic = _topic_nodes()[(len(edges) - 100) % len(_topic_nodes())]
        node = core_nodes[(len(edges) * 7) % len(core_nodes)]
        edges.append(
            _edge(index, topic.id, node.id, "DEMO_RELATED_TO", evidence_ids, "demo-topic", 0.35)
        )
        index += 1


def seed_demo_snapshot(
    metadata: MetadataStore,
    graph: KuzuGraphStore,
    vectors: ChromaVectorStore,
) -> dict[str, int]:
    metadata.initialize()
    graph.initialize()
    if metadata.has_demo_data():
        graph_stats = graph.stats()
        counts = metadata.counts()
        counts["nodes"] = graph_stats["nodes"]
        counts["edges"] = graph_stats["edges"]
        return counts

    sources, evidence_ids, chunk_records = _seed_sources(metadata)
    nodes = [*_core_nodes(), *_topic_nodes()]
    for node in nodes:
        graph.add_node(node)
    edges = _core_edges(evidence_ids)
    _generated_edges(edges, evidence_ids)
    for edge in edges:
        graph.add_edge(edge)

    for chunk_id, text in chunk_records:
        vectors.upsert(
            chunk_id,
            text,
            {"kind": "source_chunk", "is_demo": True},
        )

    source_ids = {source.id for source in sources}
    for chunk_id, text in _vector_documents(nodes, edges, source_ids):
        vectors.upsert(chunk_id, text, {"kind": "graph_summary", "is_demo": True})

    return {
        "sources": len(sources),
        "documents": len(sources) * 3,
        "chunks": len(sources) * 3,
        "evidence": len(evidence_ids),
        "nodes": len(nodes),
        "edges": len(edges),
    }


def _vector_documents(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    source_ids: set[str],
) -> list[tuple[str, str]]:
    node_by_id = {node.id: node for node in nodes}
    documents: list[tuple[str, str]] = []
    for index, edge in enumerate(edges):
        source = node_by_id.get(edge.source)
        target = node_by_id.get(edge.target)
        if not source or not target:
            continue
        text = (
            f"{source.name} {edge.predicate} {target.name}。"
            f"{source.summary} {target.summary}"
        )
        documents.append((f"graph-vector-{index:04d}", text))
    for source_id in sorted(source_ids):
        documents.append(
            (
                f"source-vector-{source_id.lower()}",
                f"{source_id} 是 VitaK-RAG 的演示来源节点，用于证据定位和混合检索。",
            )
        )
    return documents
