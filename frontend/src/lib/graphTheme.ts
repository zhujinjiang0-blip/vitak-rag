export const DOMAIN_COLORS: Record<string, string> = {
  生理代谢: "#0f766e",
  食物营养: "#ca8a04",
  药物相互作用: "#be123c",
  临床疾病: "#b45309",
  检测评估: "#0369a1",
  指南与RCT: "#6d28d9"
};

export interface RelationTheme {
  id: string;
  label: string;
  color: string;
  predicates: readonly string[];
}

export const RELATION_THEMES: readonly RelationTheme[] = [
  {
    id: "nutrition",
    label: "食物与营养",
    color: "#d97706",
    predicates: [
      "CONTAINS",
      "RICH_IN",
      "MAY_CONTAIN",
      "VitaminKContent",
      "CookingMethod",
      "contains",
      "dish_contains",
      "is_provided_as",
      "is_provided_with",
      "is_synthesized_by"
    ]
  },
  {
    id: "drug",
    label: "药物与拮抗",
    color: "#dc2626",
    predicates: [
      "ANTAGONIZED_BY",
      "INTERACTS_WITH",
      "INHIBITS",
      "CAN_ALTER",
      "affects",
      "is_antagonized_by",
      "metabolic_status_affects"
    ]
  },
  {
    id: "risk",
    label: "疾病与风险",
    color: "#ea580c",
    predicates: [
      "INDICATES_RISK_OF",
      "DEFICIENCY_CAUSES",
      "EXCESS_CAUSES",
      "PREVENTS",
      "RelatedDisease",
      "ameliorates",
      "causes",
      "cross_sectionally_associated_with",
      "does_not_cause",
      "indicates_risk_of",
      "deficiency_causes",
      "excess_causes",
      "prevents",
      "increases_risk_of",
      "reduces_risk_of",
      "is_effective_for",
      "promotes",
      "treats"
    ]
  },
  {
    id: "measurement",
    label: "检测与指标",
    color: "#2563eb",
    predicates: [
      "HAS_OUTCOME_BIOMARKER",
      "MEASURED_BY",
      "REFLECTS_STATUS_OF",
      "MeasurementUnit",
      "detects",
      "has_outcome_biomarker",
      "measured_by",
      "reflects_status_of",
      "measured_vitamin_k_form"
    ]
  },
  {
    id: "mechanism",
    label: "机制与代谢",
    color: "#0f766e",
    predicates: [
      "REGULATES_EXPRESSION_OF",
      "ACTIVATES_PROTEIN",
      "PARTICIPATES_IN_CYCLE",
      "CARBOXYLATED_BY",
      "Pathway",
      "activates",
      "decreases",
      "does_not_affect",
      "gene_site_affects",
      "has_no_effect_on",
      "improves",
      "increases",
      "is_absorbed_in",
      "is_cofactor_of",
      "is_metabolized_in",
      "regulates_expression_of",
      "activates_protein",
      "participates_in_cycle",
      "is_carboxylated_by",
      "targets_tissue",
      "is_converted_to",
      "reduces"
    ]
  },
  {
    id: "research",
    label: "研究与证据",
    color: "#7c3aed",
    predicates: [
      "HAS_SUBJECT",
      "HAS_EXPOSURE_INTERVENTION",
      "HAS_EXPOSURE_DOSE_RECORD",
      "SUPPORTED_BY",
      "anthropometric_feature_affects",
      "contains_exposure",
      "has_subject",
      "has_exposure_intervention",
      "has_exposure_dose_record",
      "is_achievable_by",
      "supported_by",
      "requires",
      "defined_by_standard",
      "supports"
    ]
  },
  {
    id: "other",
    label: "其他关系",
    color: "#64748b",
    predicates: []
  }
] as const;

export function graphDomainColor(domain: string): string {
  return DOMAIN_COLORS[domain] ?? "#64748b";
}

export function graphRelationTheme(predicate: string): RelationTheme {
  const normalized = predicate.trim().toLowerCase();
  return (
    RELATION_THEMES.find((theme) =>
      theme.predicates.some((item) => item.toLowerCase() === normalized)
    ) ?? RELATION_THEMES[RELATION_THEMES.length - 1]
  );
}

export function graphRelationColor(predicate: string): string {
  return graphRelationTheme(predicate).color;
}
