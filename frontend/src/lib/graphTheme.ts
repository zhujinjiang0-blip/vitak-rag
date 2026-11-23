export const DOMAIN_COLORS: Record<string, string> = {
  生理代谢: "#0f766e",
  食物营养: "#ca8a04",
  药物相互作用: "#be123c",
  临床疾病: "#b45309",
  检测评估: "#0369a1",
  指南与RCT: "#6d28d9"
};

export function graphDomainColor(domain: string): string {
  return DOMAIN_COLORS[domain] ?? "#64748b";
}
