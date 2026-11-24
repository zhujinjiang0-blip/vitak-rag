import { PUBLIC_BUILD } from "../lib/buildMode";

interface DataSourceLegendProps {
  compact?: boolean;
}

const PUBLIC_ORIGINS = [
  {
    key: "external",
    label: "真实外部",
    description: "已发表维生素 K 文献与公开数据库的真实三元组"
  },
  {
    key: "public",
    label: "公开参考",
    description: "公开网页、指南和事实条目"
  }
];

const AUTHENTICATED_ORIGINS = [
  {
    key: "internal",
    label: "内部私有",
    description: "395 人干预队列证据，仅在本地私有快照中使用"
  },
  ...PUBLIC_ORIGINS
];

function DataSourceLegend({ compact = false }: DataSourceLegendProps) {
  const origins = PUBLIC_BUILD ? PUBLIC_ORIGINS : AUTHENTICATED_ORIGINS;
  return (
    <div className={`origin-legend ${compact ? "compact" : ""}`}>
      {origins.map((origin) => (
        <div className="origin-legend-item" key={origin.key}>
          <span className={`origin-pill ${origin.key}`}>{origin.label}</span>
          {!compact && <span>{origin.description}</span>}
        </div>
      ))}
    </div>
  );
}

export default DataSourceLegend;
