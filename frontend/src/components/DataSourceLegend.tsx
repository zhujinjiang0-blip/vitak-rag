interface DataSourceLegendProps {
  compact?: boolean;
}

const ORIGINS = [
  {
    key: "internal",
    label: "内部私有",
    description: "395 人干预队列证据，仅在本地私有快照中使用"
  },
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

function DataSourceLegend({ compact = false }: DataSourceLegendProps) {
  return (
    <div className={`origin-legend ${compact ? "compact" : ""}`}>
      {ORIGINS.map((origin) => (
        <div className="origin-legend-item" key={origin.key}>
          <span className={`origin-pill ${origin.key}`}>{origin.label}</span>
          {!compact && <span>{origin.description}</span>}
        </div>
      ))}
    </div>
  );
}

export default DataSourceLegend;
