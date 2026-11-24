import type {
  Answer,
  Claim,
  ClaimType,
  EvidenceComparison
} from "./types";

const NEGATIVE_RELATIONS = new Set([
  "does_not_affect",
  "does_not_cause",
  "has_no_effect_on",
  "no_significant_association_observed_with",
  "no_significant_interaction_observed_with",
  "no_supported_mediation_via"
]);

const ASSOCIATION_RELATIONS = new Set([
  "associated_with",
  "cross_sectionally_associated_with",
  "deficiency_causes",
  "excess_causes",
  "has_outcome_biomarker",
  "indicates_risk_of",
  "relateddisease"
]);

const INTERVENTION_RELATIONS = new Set([
  "decreases",
  "has_longitudinal_effect_on",
  "improves",
  "increases",
  "is_effective_for",
  "prevents",
  "reduces",
  "supports",
  "treats"
]);

const MECHANISM_RELATIONS = new Set([
  "activates",
  "activates_protein",
  "can_alter",
  "inhibits",
  "is_absorbed_in",
  "is_carboxylated_by",
  "is_cofactor_of",
  "is_converted_to",
  "is_metabolized_in",
  "is_synthesized_by",
  "participates_in_cycle",
  "regulates_expression_of",
  "targets_tissue",
  "warfarin_vitamin_k_synthesis"
]);

const INTERACTION_RELATIONS = new Set([
  "interacts_with",
  "is_antagonized_by",
  "moderates_effect_on",
  "shows_dose_response_with"
]);

const EXPLORATORY_RELATIONS = new Set([
  "metabolic_status_affects",
  "modulates_postprandial_kinetics_of"
]);

export const CLAIM_TYPE_LABELS: Record<ClaimType, string> = {
  general: "知识证据",
  association: "研究关联",
  intervention: "干预或方向性证据",
  mechanism: "机制证据",
  negative: "阴性结果",
  exploratory: "探索性发现",
  interaction: "交互或剂量反应",
  conflict: "研究结论差异"
};

export const COMPARISON_STATUS_LABELS: Record<string, string> = {
  significance_difference: "显著性差异",
  direction_difference: "方向差异",
  evidence_layer_difference: "证据层级差异",
  context_difference: "研究条件差异",
  reported_difference: "研究结论差异"
};

const BOUNDARY_NOTES: Partial<Record<ClaimType, string>> = {
  association: "这是观察性关联或风险提示，不等同于干预会产生相同效果。",
  intervention:
    "方向性结果需结合研究设计、人群、剂量和对照解释，不等同于普遍治疗结论。",
  mechanism: "机制证据说明潜在生物学路径，不能直接推导出临床疗效。",
  negative: "未观察到显著关系不等于证明该关系不存在或证明干预无效。",
  exploratory: "该结果为探索性分析，仍需独立研究和外部验证。",
  interaction: "交互或剂量反应结果需结合暴露水平及研究条件解释。",
  conflict: "不同研究或分析存在结论差异，应按研究条件和证据层级分别解释。"
};

const DIRECTION_UP = new Set([
  "activates",
  "activates_protein",
  "improves",
  "increases",
  "promotes",
  "supports"
]);

const DIRECTION_DOWN = new Set([
  "decreases",
  "inhibits",
  "no_supported_mediation_via",
  "reduces"
]);

export function claimScienceProfile(claim: Claim): {
  claimType: ClaimType;
  boundaryNote: string | null;
} {
  const relation = (claim.relation ?? "").trim().toLowerCase();
  let claimType: ClaimType;
  if (
    NEGATIVE_RELATIONS.has(relation) ||
    /未观察到|无显著|没有显著|未发现|无影响|不表示/.test(claim.text)
  ) {
    claimType = "negative";
  } else if (
    /不一致|并不完全一致|不完全一致|相反|互相矛盾|contradictory|结论冲突/.test(
      claim.text
    )
  ) {
    claimType = "conflict";
  } else if (
    EXPLORATORY_RELATIONS.has(relation) ||
    /探索性|中介|反向|模型不一致/.test(claim.text)
  ) {
    claimType = "exploratory";
  } else if (INTERACTION_RELATIONS.has(relation)) {
    claimType = "interaction";
  } else if (MECHANISM_RELATIONS.has(relation)) {
    claimType = "mechanism";
  } else if (ASSOCIATION_RELATIONS.has(relation)) {
    claimType = "association";
  } else if (INTERVENTION_RELATIONS.has(relation)) {
    claimType = "intervention";
  } else if (/降低|改善|减少|增加|预防|疗效|有效/.test(claim.text)) {
    claimType = "intervention";
  } else if (/机制|参与|调节|活化|羧化|通路|代谢/.test(claim.text)) {
    claimType = "mechanism";
  } else {
    claimType = "general";
  }
  return {
    claimType,
    boundaryNote: BOUNDARY_NOTES[claimType] ?? null
  };
}

export function enrichAnswerClaims(answer: Answer): Answer {
  const claims = answer.claims.map((claim) => {
    const profile = claimScienceProfile(claim);
    return {
      ...claim,
      claim_type: claim.claim_type ?? profile.claimType,
      boundary_note: claim.boundary_note ?? profile.boundaryNote
    };
  });
  const comparisons =
    answer.comparisons && answer.comparisons.length > 0
      ? answer.comparisons
      : buildEvidenceComparisons(claims, answer.citations);
  return {
    ...answer,
    claims,
    comparisons
  };
}

function buildEvidenceComparisons(
  claims: Claim[],
  citations: Answer["citations"]
): EvidenceComparison[] {
  const comparisons: EvidenceComparison[] = [];
  const conflictClaims = claims.filter(
    (claim) => claim.claim_type === "conflict"
  );
  if (conflictClaims.length > 0) {
    comparisons.push({
      id: "comparison-reported-conflict",
      status: "reported_difference",
      summary:
        "现有研究报告了不一致或相反的结果，应结合研究设计、暴露、人群和结局分别解释，不能强行合并成单一结论。",
      claim_ids: conflictClaims.map((claim) => claim.id),
      evidence_ids: uniqueEvidenceIds(conflictClaims)
    });
  }
  const negativeClaims = claims.filter(
    (claim) => claim.claim_type === "negative"
  );
  const nonNegativeClaims = claims.filter(
    (claim) => claim.claim_type !== "negative"
  );
  if (negativeClaims.length > 0 && nonNegativeClaims.length > 0) {
    const selected = [...negativeClaims, ...nonNegativeClaims];
    comparisons.push({
      id: "comparison-significance",
      status: "significance_difference",
      summary:
        "回答同时保留了阳性或方向性证据与阴性证据。未观察到显著关系不等于证明该关系不存在或证明干预无效。",
      claim_ids: selected.map((claim) => claim.id),
      evidence_ids: uniqueEvidenceIds(selected)
    });
  }

  const upClaims = claims.filter((claim) =>
    DIRECTION_UP.has((claim.relation ?? "").trim().toLowerCase())
  );
  const downClaims = claims.filter((claim) =>
    DIRECTION_DOWN.has((claim.relation ?? "").trim().toLowerCase())
  );
  if (upClaims.length > 0 && downClaims.length > 0) {
    const selected = [...upClaims, ...downClaims];
    comparisons.push({
      id: "comparison-direction",
      status: "direction_difference",
      summary:
        "当前证据包含不同方向的关联或效应。需结合暴露亚型、研究设计、人群和结局分别解释。",
      claim_ids: selected.map((claim) => claim.id),
      evidence_ids: uniqueEvidenceIds(selected)
    });
  }

  const mechanismClaims = claims.filter(
    (claim) => claim.claim_type === "mechanism"
  );
  const clinicalClaims = claims.filter((claim) =>
    ["association", "intervention", "interaction"].includes(
      claim.claim_type ?? "general"
    )
  );
  if (mechanismClaims.length > 0 && clinicalClaims.length > 0) {
    const selected = [...mechanismClaims, ...clinicalClaims];
    comparisons.push({
      id: "comparison-layer",
      status: "evidence_layer_difference",
      summary:
        "机制证据与临床关联或干预证据属于不同证据层级，机制发现不能直接等同于临床效果。",
      claim_ids: selected.map((claim) => claim.id),
      evidence_ids: uniqueEvidenceIds(selected)
    });
  }

  const contexts = new Set(
    citations
      .map((citation) =>
        [
          citation.analysis_context?.trim(),
          citation.model_type?.trim(),
          citation.sample_n?.trim()
        ]
          .filter(Boolean)
          .join("|")
      )
      .filter(Boolean)
  );
  if (contexts.size > 1) {
    comparisons.push({
      id: "comparison-context",
      status: "context_difference",
      summary:
        "这些证据来自不同分析场景、模型或样本条件，应并列查看，不能直接合并为单一效应。",
      claim_ids: claims.map((claim) => claim.id),
      evidence_ids: uniqueEvidenceIds(claims)
    });
  }
  return comparisons.slice(0, 3);
}

function uniqueEvidenceIds(claims: Claim[]) {
  return [...new Set(claims.flatMap((claim) => claim.evidence_ids))];
}
