from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ELIGIBLE_REVIEW_STATUSES = {
    "accepted",
    "adopted_with_warning",
}
RESEARCH_ONLY_STATUSES = {
    "manual_pending",
    "provisional",
}
STRUCTURED_QA_PREDICATES = {
    "contains",
    "VitaminKContent",
    "CookingMethod",
    "MeasurementUnit",
    "has_outcome_biomarker",
    "has_exposure_intervention",
    "RelatedDisease",
}
STRUCTURED_METADATA_PREDICATES = {
    "Name",
    "Description",
    "skos:altLabel",
    "URI",
    "Category",
    "Source",
}

CURATED_ALIASES = {
    "vitamin k": ["维生素K", "维K", "Vitamin K"],
    "vitamin k1": ["维生素K1", "叶绿醌", "K1"],
    "phylloquinone": ["维生素K1", "叶绿醌"],
    "vitamin k2": ["维生素K2", "甲萘醌", "K2"],
    "menaquinone": ["维生素K2", "甲萘醌"],
    "mk-7": ["维生素K2", "MK-7", "甲萘醌-7"],
    "mk-4": ["维生素K2", "MK-4", "甲萘醌-4"],
    "warfarin": ["华法林", "Warfarin"],
    "osteocalcin": ["骨钙素", "Osteocalcin"],
    "matrix gla protein": ["基质Gla蛋白", "MGP"],
    "dp-ucmgp": ["去磷酸化未羧化基质Gla蛋白", "dp-ucMGP"],
    "ucoc": ["未羧化骨钙素", "ucOC"],
    "pivka-ii": ["PIVKA-II", "异常凝血酶原"],
    "green leafy vegetables": ["绿叶蔬菜", "深绿色叶菜"],
    "vegetable oils": ["植物油"],
    "plant oil": ["植物油"],
    "ggcx": ["γ-谷氨酰羧化酶", "GGCX"],
    "vkorc1": ["维生素K环氧化物还原酶", "VKORC1"],
    "cyp4f2": ["CYP4F2"],
    "coagulation factors vii ix x": ["凝血因子VII、IX、X", "凝血因子"],
}

NODE_IDS = {
    "vitamin k": "vitamin-k",
    "vitamin k1": "vitamin-k1",
    "phylloquinone": "phylloquinone",
    "vitamin k2": "vitamin-k2",
    "mK-7".lower(): "mk-7",
    "mk-4": "mk-4",
    "warfarin": "warfarin",
    "osteocalcin": "osteocalcin",
}

STRUCTURED_NAME_OVERRIDES = {
    "vitamin k (phylloquinone)": "Phylloquinone",
    "vitamin k (dihydrophylloquinone)": "Dihydrophylloquinone",
    "vitamin k (menaquinone-4)": "Menaquinone-4",
    "vitamin k (menaquinone-7)": "Menaquinone-7",
}

STRUCTURED_ALIASES = {
    "kale": "羽衣甘蓝",
    "spinach": "菠菜",
    "broccoli": "西兰花",
    "natto": "纳豆",
    "fermented soy": "发酵豆制品",
    "vegetable oil": "植物油",
}


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def stable_node_id(label: str) -> str:
    normalized_label = normalized(label)
    if normalized_label in NODE_IDS:
        return NODE_IDS[normalized_label]
    digest = hashlib.sha1(normalized_label.encode("utf-8")).hexdigest()[:14]
    return f"real-{digest}"


def domain_for(label: str, entity_type: str) -> str:
    text = f"{label} {entity_type}".lower()
    if any(
        term in text
        for term in (
            "warfarin",
            "drug",
            "antagonist",
            "antibiotic",
            "anticoag",
        )
    ):
        return "药物相互作用"
    if any(
        term in text
        for term in (
            "food",
            "vegetable",
            "diet",
            "oil",
            "cheese",
            "spinach",
            "kale",
            "broccoli",
        )
    ):
        return "食物营养"
    if any(
        term in text
        for term in (
            "biomarker",
            "plasma",
            "serum",
            "ucoc",
            "pivka",
            "inr",
            "assay",
            "measure",
            "osteocalcin",
            "matrix gla",
            "dp-ucmgp",
        )
    ):
        return "检测评估"
    if any(
        term in text
        for term in (
            "deficiency",
            "disease",
            "bleeding",
            "fracture",
            "calcification",
            "cancer",
            "osteoporosis",
        )
    ):
        return "临床疾病"
    if any(
        term in text
        for term in (
            "trial",
            "randomized",
            "study",
            "cohort",
            "guideline",
            "outcome",
        )
    ):
        return "指南与RCT"
    return "生理代谢"


def parse_locator(value: str) -> tuple[str, str, str]:
    if "|" in value:
        descriptor, sentence = value.split("|", 1)
    else:
        descriptor, sentence = "", value
    match = re.search(r"PMID\s*(\d+)", descriptor, re.IGNORECASE)
    pmid = match.group(1) if match else ""
    return descriptor.strip(), sentence.strip(), pmid


def confidence_value(value: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.5
    if parsed > 1:
        parsed /= 100
    return max(0.0, min(parsed, 1.0))


def is_eligible(row: dict[str, str]) -> bool:
    return (
        row.get("review_status", "") in ELIGIBLE_REVIEW_STATUSES
        and row.get("input_status", "") == "adopted"
    )


def rank_research_only(row: dict[str, str]) -> tuple[int, float, int]:
    sentence = row.get("source_locator", "").split("|", 1)[-1].strip()
    grade_rank = {"A": 3, "B": 2, "C": 1}.get(row.get("evidence_grade", ""), 0)
    return grade_rank, confidence_value(row.get("confidence_score", "")), len(sentence)


def structured_publisher(source_locator: str) -> str:
    lowered = source_locator.casefold()
    publishers = (
        ("usda", "USDA FoodData Central"),
        ("fdc", "USDA FoodData Central"),
        ("pubchem", "PubChem"),
        ("foodb", "FooDB"),
        ("kegg", "KEGG"),
        ("clinicaltrials", "ClinicalTrials"),
        ("中国食物成分表", "中国食物成分表"),
    )
    for marker, label in publishers:
        if marker in lowered:
            return label
    return "外部结构化数据"


def structured_node_label(
    row: dict[str, str],
    side: str,
    metadata: dict[tuple[str, str], dict[str, Any]],
) -> str:
    raw_label = row[f"{side}_label"].strip()
    raw_type = row[f"{side}_type"].strip()
    override = STRUCTURED_NAME_OVERRIDES.get(normalized(raw_label))
    if override:
        return override
    details = metadata.get((normalized(raw_label), raw_type), {})
    return str(details.get("name") or raw_label)


def structured_snippet(row: dict[str, str], subject: str, object_label: str) -> str:
    predicate = row["predicate"]
    if predicate == "VitaminKContent":
        return f"{subject}的维生素K含量记录值为{object_label}。"
    if predicate == "CookingMethod":
        return f"{subject}的烹饪方式记录为{object_label}。"
    if predicate == "Pathway":
        return f"{subject}对应的KEGG通路为{object_label}。"
    if predicate == "MeasurementUnit":
        return f"{subject}的计量单位记录为{object_label}。"
    if predicate == "has_outcome_biomarker":
        return f"{subject}相关记录涉及结局或生物标志物{object_label}。"
    if predicate == "has_exposure_intervention":
        return f"{subject}相关研究的暴露或干预为{object_label}。"
    if predicate == "RelatedDisease":
        return f"{subject}与疾病主题{object_label}存在结构化关联。"
    return f"{subject}含有{object_label}。"


def load_structured_rows(
    path: Path,
) -> tuple[list[dict[str, str]], dict[tuple[str, str], dict[str, Any]]]:
    selected: list[dict[str, str]] = []
    metadata: dict[tuple[str, str], dict[str, Any]] = {}
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="", errors="replace") as handle:
        for row in csv.DictReader(handle):
            edge_id = row.get("edge_id", "").strip()
            if not edge_id or edge_id in seen or not is_eligible(row):
                continue
            seen.add(edge_id)
            predicate = row.get("predicate", "").strip()
            if predicate in STRUCTURED_METADATA_PREDICATES:
                key = (
                    normalized(row.get("subject_label", "")),
                    row.get("subject_type", "").strip(),
                )
                details = metadata.setdefault(
                    key,
                    {
                        "name": "",
                        "description": "",
                        "aliases": set(),
                        "uri": "",
                        "categories": [],
                        "sources": [],
                    },
                )
                value = row.get("object_label", "").strip()
                if predicate == "Name" and value:
                    details["name"] = value
                elif predicate == "Description" and value:
                    details["description"] = value[:500]
                elif predicate == "skos:altLabel" and value:
                    details["aliases"].add(value)
                elif predicate == "URI" and value:
                    details["uri"] = value
                elif predicate == "Category" and value:
                    details["categories"].append(value)
                elif predicate == "Source" and value:
                    details["sources"].append(value)
            elif predicate in STRUCTURED_QA_PREDICATES:
                selected.append(row)
    return selected, metadata


def load_rows(path: Path, research_only_limit: int) -> tuple[list[dict[str, str]], int]:
    eligible: list[dict[str, str]] = []
    research_only: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="", errors="replace") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            edge_id = row.get("edge_id", "").strip()
            if not edge_id or edge_id in seen:
                continue
            seen.add(edge_id)
            if is_eligible(row):
                eligible.append(row)
            elif row.get("review_status", "") in RESEARCH_ONLY_STATUSES:
                research_only.append(row)
    research_only.sort(key=rank_research_only, reverse=True)
    selected = eligible + research_only[:research_only_limit]
    return selected, len(research_only[:research_only_limit])


def build_payload(
    rows: list[dict[str, str]],
    *,
    research_only_count: int,
    source_paths: list[Path],
    structured_metadata: dict[tuple[str, str], dict[str, Any]],
    eligible_structured_records: int,
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    registry_codes: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    predicates: Counter[str] = Counter()
    source_ids: set[str] = set()

    for row in rows:
        source_type = row.get("source_type", "").strip()
        raw_subject_label = row["subject_label"].strip()
        raw_object_label = row["object_label"].strip()
        subject_label = (
            structured_node_label(row, "subject", structured_metadata)
            if source_type == "structured"
            else raw_subject_label
        )
        object_label = (
            structured_node_label(row, "object", structured_metadata)
            if source_type == "structured"
            else raw_object_label
        )
        subject_id = stable_node_id(subject_label)
        object_id = stable_node_id(object_label)
        for node_id, label, entity_type, raw_label in (
            (subject_id, subject_label, row["subject_type"], raw_subject_label),
            (object_id, object_label, row["object_type"], raw_object_label),
        ):
            metadata_key = (normalized(raw_label), entity_type.strip())
            node_metadata = (
                structured_metadata.get(metadata_key, {})
                if source_type == "structured"
                else {}
            )
            aliases = {
                *CURATED_ALIASES.get(normalized(label), []),
                *CURATED_ALIASES.get(normalized(raw_label), []),
                *node_metadata.get("aliases", set()),
            }
            if source_type == "structured":
                searchable_label = normalized(label)
                aliases.update(
                    alias
                    for term, alias in STRUCTURED_ALIASES.items()
                    if term in searchable_label
                )
            if raw_label and raw_label != label:
                aliases.add(raw_label)
            if node_id not in nodes:
                nodes[node_id] = {
                    "id": node_id,
                    "name": label,
                    "type": entity_type or "LiteratureEntity",
                    "domain": domain_for(label, entity_type),
                    "summary": (
                        node_metadata.get("description")
                        or (
                            "来自已审核的真实外部结构化数据。"
                            if source_type == "structured"
                            else "来自已审核真实外部文献三元组。"
                        )
                    ),
                    "aliases": sorted(aliases),
                    "is_demo": False,
                }
            else:
                existing = nodes[node_id]
                existing["aliases"] = sorted({*existing.get("aliases", []), *aliases})
                if (
                    source_type == "structured"
                    and node_metadata.get("description")
                    and existing.get("summary", "").startswith("来自已审核真实外部文献")
                ):
                    existing["summary"] = node_metadata["description"]

        _descriptor, sentence, pmid = parse_locator(row["source_locator"])
        evidence_id = row["edge_id"]
        eligible = is_eligible(row)
        source_record_id = row["source_record_id"]
        source_ids.add(source_record_id)
        statuses[row["review_status"]] += 1
        predicates[row["predicate"]] += 1
        registry_codes[source_type] += 1
        if source_type == "structured":
            publisher = structured_publisher(row["source_locator"])
            source_title = f"{publisher} · 外部结构化证据"
            snippet = structured_snippet(row, subject_label, object_label)
        else:
            publisher = "PubMed" if pmid else "真实外部文献"
            source_title = (
                f"PMID {pmid} · 真实外部文献证据"
                if pmid
                else f"{source_record_id} · 真实外部文献证据"
            )
            snippet = sentence[:1200]
        evidence.append(
            {
                "id": evidence_id,
                "source_id": source_record_id,
                "source_title": source_title,
                "source_type": source_type,
                "source_classification": (
                    "external_structured_triple"
                    if source_type == "structured"
                    else "external_literature_triple"
                ),
                "data_origin": "external",
                "data_owner": (
                    "FDC、USDA、PubChem、FooDB、KEGG、ClinicalTrials 等外部结构化数据"
                    if source_type == "structured"
                    else "已发表维生素 K 研究文献"
                ),
                "access_scope": "public",
                "publisher": publisher,
                "published_at": "",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                "evidence_level": row["evidence_grade"]
                or ("structured" if source_type == "structured" else ""),
                "locator": row["source_locator"],
                "snippet": snippet,
                "is_demo": False,
                "document_id": evidence_id,
                "entity_ids": [subject_id, object_id],
                "review_status": row["review_status"],
                "input_status": row["input_status"],
                "fusion_status": row["fusion_status"],
                "answer_eligible": eligible,
                "evidence_status": row["evidence_status"],
                "source_version": row["source_version"],
                "source_locator": row["source_locator"],
                "analysis_context": row["analysis_context"],
                "effect_size": row["effect_size"],
                "p_value": row["p_value"],
                "q_value": row["q_value"],
                "sample_n": row["sample_n"],
                "model_type": row["model_type"],
                "predicate": row["predicate"],
            }
        )
        edges.append(
            {
                "id": evidence_id,
                "source": subject_id,
                "target": object_id,
                "predicate": row["predicate"],
                "evidence_ids": [evidence_id],
                "evidence_level": row["evidence_grade"],
                "confidence": confidence_value(row["confidence_score"]),
                "is_demo": False,
            }
        )

    eligible_count = sum(
        1
        for item in evidence
        if item["answer_eligible"] and item["source_type"] == "literature"
    )
    return {
        "version": {
            "version": "real-public-2026.11-structured",
            "created_at": datetime.now(UTC).isoformat(),
            "is_demo": False,
            "entity_count": len(nodes),
            "relation_count": len(edges),
            "source_count": len(source_ids),
            "chunk_count": len(evidence),
        },
        "export_metadata": {
            "scope": "external_public_only",
            "source_files": [path.name for path in source_paths],
            "source_file": ", ".join(path.name for path in source_paths),
            "eligible_literature_records": eligible_count,
            "eligible_structured_records": eligible_structured_records,
            "research_only_literature_records": research_only_count,
            "internal_records": 0,
            "review_statuses": dict(statuses),
            "source_types": dict(registry_codes),
            "top_predicates": predicates.most_common(40),
        },
        "nodes": list(nodes.values()),
        "edges": edges,
        "evidence": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export accepted public literature and structured triples "
            "for the static VitaK-RAG demo."
        )
    )
    parser.add_argument("literature_csv", type=Path)
    parser.add_argument(
        "structured_csv",
        type=Path,
        nargs="?",
        help="可选：42 列外部结构化三元组 CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("frontend/public/real-evidence.json"),
    )
    parser.add_argument("--research-only-limit", type=int, default=1200)
    args = parser.parse_args()

    literature_rows, research_only_count = load_rows(
        args.literature_csv,
        args.research_only_limit,
    )
    structured_rows: list[dict[str, str]] = []
    structured_metadata: dict[tuple[str, str], dict[str, Any]] = {}
    if args.structured_csv:
        structured_rows, structured_metadata = load_structured_rows(args.structured_csv)
    rows = [*structured_rows, *literature_rows]
    source_paths = [args.literature_csv]
    if args.structured_csv:
        source_paths.append(args.structured_csv)
    payload = build_payload(
        rows,
        research_only_count=research_only_count,
        source_paths=source_paths,
        structured_metadata=structured_metadata,
        eligible_structured_records=len(structured_rows),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "records": len(payload["evidence"]),
                "eligible": payload["export_metadata"]["eligible_literature_records"],
                "eligible_structured": payload["export_metadata"][
                    "eligible_structured_records"
                ],
                "research_only": research_only_count,
                "nodes": payload["version"]["entity_count"],
                "edges": payload["version"]["relation_count"],
                "size_bytes": args.output.stat().st_size,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
