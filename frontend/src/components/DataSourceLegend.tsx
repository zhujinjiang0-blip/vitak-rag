interface DataSourceLegendProps {
  compact?: boolean;
}

const ORIGINS = [
  {
    key: "internal",
    label: "内部数据",
    description: "395 人干预队列产生的受控个体证据"
  },
  {
    key: "external",
    label: "外部数据",
    description: "已发表维生素 K 研究文献与对齐三元组"
  },
  {
    key: "public",
    label: "公开参考",
    description: "公开网页、指南和事实条目"
  },
  {
    key: "synthetic",
    label: "合成演示",
    description: "仅用于系统演示，不可作为医学证据"
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

