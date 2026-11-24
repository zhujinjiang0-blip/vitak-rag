import type { Edge as FlowEdge, Node as FlowNode } from "@xyflow/react";
import {
  DOMAIN_COLORS,
  RELATION_THEMES,
  graphDomainColor,
  graphRelationColor
} from "./graphTheme";
import type { GraphNode } from "./types";

export interface GraphExportMeta {
  mode: "2d" | "3d";
  scope: "all" | "focus" | "answer";
  entityCount: number;
  relationCount: number;
  dataVersion: string;
  focusName?: string | null;
}

const HEADER_HEIGHT = 96;
const FOOTER_HEIGHT = 104;
const GRAPH_PADDING = 180;

function roundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
) {
  const safeRadius = Math.min(radius, width / 2, height / 2);
  context.beginPath();
  context.moveTo(x + safeRadius, y);
  context.lineTo(x + width - safeRadius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + safeRadius);
  context.lineTo(x + width, y + height - safeRadius);
  context.quadraticCurveTo(
    x + width,
    y + height,
    x + width - safeRadius,
    y + height
  );
  context.lineTo(x + safeRadius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - safeRadius);
  context.lineTo(x, y + safeRadius);
  context.quadraticCurveTo(x, y, x + safeRadius, y);
  context.closePath();
}

function nodeSize(
  node: FlowNode,
  overview: boolean
): { width: number; height: number } {
  const style = node.style ?? {};
  return {
    width: typeof style.width === "number" ? style.width : overview ? 14 : 124,
    height:
      typeof style.height === "number"
        ? style.height
        : typeof style.minHeight === "number"
          ? style.minHeight
          : overview
            ? 14
            : 42
  };
}

function drawTitle(
  context: CanvasRenderingContext2D,
  width: number,
  meta: GraphExportMeta
) {
  const title =
    meta.scope === "all"
      ? "维K智问 · 维生素K知识图谱全图"
      : meta.scope === "answer"
        ? "维K智问 · 问答引用图谱路径"
        : `维K智问 · ${meta.focusName ?? "实体"}知识邻域`;
  context.fillStyle = "#172033";
  context.font = '700 22px "Noto Sans SC", "PingFang SC", sans-serif';
  context.fillText(title, 38, 40);
  context.fillStyle = "#64748b";
  context.font = '500 11px "Noto Sans SC", "PingFang SC", sans-serif';
  context.fillText(
    `${meta.entityCount.toLocaleString("zh-CN")} 个实体 · ` +
      `${meta.relationCount.toLocaleString("zh-CN")} 条关系 · ` +
      `${meta.mode.toUpperCase()} · 数据版本 ${meta.dataVersion}`,
    38,
    64
  );
  context.textAlign = "right";
  context.fillStyle = "#0f766e";
  context.font = '700 11px "Noto Sans SC", "PingFang SC", sans-serif';
  context.fillText("VitaK-RAG", width - 38, 40);
  context.fillStyle = "#8793a2";
  context.font = '500 10px "Noto Sans SC", "PingFang SC", sans-serif';
  context.fillText("证据驱动 · 本地确定性检索", width - 38, 60);
  context.textAlign = "left";
}

function drawLegend(
  context: CanvasRenderingContext2D,
  width: number,
  top: number
) {
  context.fillStyle = "#ffffff";
  context.fillRect(0, top, width, FOOTER_HEIGHT);
  context.strokeStyle = "#d9e1e8";
  context.beginPath();
  context.moveTo(0, top + 0.5);
  context.lineTo(width, top + 0.5);
  context.stroke();

  let x = 38;
  const entityY = top + 32;
  context.fillStyle = "#435166";
  context.font = '700 10px "Noto Sans SC", "PingFang SC", sans-serif';
  context.fillText("实体领域", x, entityY);
  x += 72;
  context.font = '500 10px "Noto Sans SC", "PingFang SC", sans-serif';
  Object.entries(DOMAIN_COLORS).forEach(([label, color]) => {
    context.fillStyle = color;
    context.beginPath();
    context.arc(x, entityY - 3, 4, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = "#64748b";
    context.fillText(label, x + 8, entityY);
    x += context.measureText(label).width + 34;
  });

  x = 38;
  const relationY = top + 67;
  context.fillStyle = "#435166";
  context.font = '700 10px "Noto Sans SC", "PingFang SC", sans-serif';
  context.fillText("关系类型", x, relationY);
  x += 72;
  context.font = '500 10px "Noto Sans SC", "PingFang SC", sans-serif';
  RELATION_THEMES.forEach((theme) => {
    context.strokeStyle = theme.color;
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(x, relationY - 3);
    context.lineTo(x + 14, relationY - 3);
    context.stroke();
    context.fillStyle = "#64748b";
    context.fillText(theme.label, x + 20, relationY);
    x += context.measureText(theme.label).width + 45;
  });
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("PNG 生成失败"));
    }, "image/png");
  });
}

function drawGrid(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number
) {
  context.save();
  context.beginPath();
  context.rect(x, y, width, height);
  context.clip();
  context.strokeStyle = "rgba(100, 116, 139, 0.08)";
  context.lineWidth = 1;
  for (let column = x; column <= x + width; column += 32) {
    context.beginPath();
    context.moveTo(column, y);
    context.lineTo(column, y + height);
    context.stroke();
  }
  for (let row = y; row <= y + height; row += 32) {
    context.beginPath();
    context.moveTo(x, row);
    context.lineTo(x + width, row);
    context.stroke();
  }
  context.restore();
}

export async function exportFlowGraphPng(
  nodes: FlowNode[],
  edges: FlowEdge[],
  graphNodes: GraphNode[],
  meta: GraphExportMeta
): Promise<Blob> {
  if (nodes.length === 0) throw new Error("当前没有可下载的图谱内容");

  const overview = meta.scope === "all" && nodes.length > 200;
  const graphNodeById = new Map(graphNodes.map((node) => [node.id, node]));
  const sizes = new Map(
    nodes.map((node) => [node.id, nodeSize(node, overview)])
  );
  const minX = Math.min(...nodes.map((node) => node.position.x));
  const minY = Math.min(...nodes.map((node) => node.position.y));
  const maxX = Math.max(
    ...nodes.map((node) => node.position.x + (sizes.get(node.id)?.width ?? 0))
  );
  const maxY = Math.max(
    ...nodes.map((node) => node.position.y + (sizes.get(node.id)?.height ?? 0))
  );
  const graphWidth = Math.max(1, maxX - minX);
  const graphHeight = Math.max(1, maxY - minY);
  const graphViewHeight = Math.max(620, graphHeight + GRAPH_PADDING);
  const logicalWidth = Math.max(1200, graphWidth + GRAPH_PADDING);
  const logicalHeight = HEADER_HEIGHT + graphViewHeight + FOOTER_HEIGHT;
  const scale = Math.min(
    2,
    4096 / logicalWidth,
    4096 / logicalHeight
  );

  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(logicalWidth * scale));
  canvas.height = Math.max(1, Math.round(logicalHeight * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("浏览器不支持 Canvas 导出");
  context.scale(scale, scale);

  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, logicalWidth, logicalHeight);
  drawTitle(context, logicalWidth, meta);
  context.fillStyle = "#f7f9fb";
  context.fillRect(0, HEADER_HEIGHT, logicalWidth, graphViewHeight);
  drawGrid(context, 0, HEADER_HEIGHT, logicalWidth, graphViewHeight);

  const offsetX = (logicalWidth - graphWidth) / 2 - minX;
  const offsetY =
    HEADER_HEIGHT + (graphViewHeight - graphHeight) / 2 - minY;
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const center = (nodeId: string) => {
    const node = nodeById.get(nodeId);
    const size = node ? sizes.get(nodeId) : undefined;
    if (!node || !size) return null;
    return {
      x: node.position.x + offsetX + size.width / 2,
      y: node.position.y + offsetY + size.height / 2
    };
  };

  edges.forEach((edge, index) => {
    const source = center(edge.source);
    const target = center(edge.target);
    if (!source || !target) return;
    const middleX = (source.x + target.x) / 2;
    const middleY = (source.y + target.y) / 2;
    const bend = ((index % 5) - 2) * (overview ? 3 : 7);
    context.strokeStyle = graphRelationColor(
      typeof edge.data?.predicate === "string"
        ? edge.data.predicate
        : typeof edge.label === "string"
          ? edge.label
          : ""
    );
    context.globalAlpha = overview ? 0.16 : 0.62;
    context.lineWidth = overview ? 0.7 : 1.25;
    context.beginPath();
    context.moveTo(source.x, source.y);
    context.quadraticCurveTo(middleX + bend, middleY - bend, target.x, target.y);
    context.stroke();
  });
  context.globalAlpha = 1;

  nodes.forEach((node) => {
    const size = sizes.get(node.id);
    if (!size) return;
    const entity = graphNodeById.get(node.id);
    const domainColor = graphDomainColor(entity?.domain ?? "");
    const x = node.position.x + offsetX;
    const y = node.position.y + offsetY;
    if (overview) {
      context.fillStyle = domainColor;
      context.beginPath();
      context.arc(x + size.width / 2, y + size.height / 2, 6, 0, Math.PI * 2);
      context.fill();
      context.strokeStyle = "rgba(255,255,255,0.92)";
      context.lineWidth = 1.4;
      context.stroke();
      return;
    }

    const isCenter = node.position.x === 0 && node.position.y === 0;
    roundedRect(context, x, y, size.width, size.height, 8);
    context.fillStyle = isCenter ? "#172033" : "rgba(255,255,255,0.96)";
    context.fill();
    context.strokeStyle = domainColor;
    context.lineWidth = isCenter ? 2 : 1.2;
    context.stroke();
    context.fillStyle = isCenter ? "#ffffff" : "#172033";
    context.font =
      `${isCenter ? 700 : 600} 10px "Noto Sans SC", "PingFang SC", sans-serif`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    const label = String(node.data?.label ?? entity?.name ?? node.id);
    context.fillText(label, x + size.width / 2, y + size.height / 2, size.width - 14);
  });
  context.textAlign = "left";
  context.textBaseline = "alphabetic";
  drawLegend(context, logicalWidth, HEADER_HEIGHT + graphViewHeight);
  return canvasToBlob(canvas);
}

export async function exportThreeGraphPng(
  sourceCanvas: HTMLCanvasElement,
  meta: GraphExportMeta
): Promise<Blob> {
  if (!sourceCanvas.width || !sourceCanvas.height) {
    throw new Error("三维画布尚未完成渲染");
  }
  const canvas = document.createElement("canvas");
  canvas.width = sourceCanvas.width;
  canvas.height = sourceCanvas.height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("浏览器不支持 Canvas 导出");
  context.fillStyle = "#f7f9fb";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(sourceCanvas, 0, 0);

  const uiScale = Math.max(1, canvas.width / 1200);
  const headerHeight = 74 * uiScale;
  context.fillStyle = "rgba(255,255,255,0.92)";
  context.fillRect(0, 0, canvas.width, headerHeight);
  context.strokeStyle = "#d9e1e8";
  context.lineWidth = uiScale;
  context.beginPath();
  context.moveTo(0, headerHeight);
  context.lineTo(canvas.width, headerHeight);
  context.stroke();

  context.fillStyle = "#172033";
  context.font = `700 ${16 * uiScale}px "Noto Sans SC", "PingFang SC", sans-serif`;
  const title =
    meta.scope === "all"
      ? "维K智问 · 维生素K知识图谱全图"
      : meta.scope === "answer"
        ? "维K智问 · 问答引用图谱路径"
        : `维K智问 · ${meta.focusName ?? "实体"}知识邻域`;
  context.fillText(title, 24 * uiScale, 30 * uiScale);
  context.fillStyle = "#64748b";
  context.font = `500 ${10 * uiScale}px "Noto Sans SC", "PingFang SC", sans-serif`;
  context.fillText(
    `${meta.entityCount.toLocaleString("zh-CN")} 个实体 · ` +
      `${meta.relationCount.toLocaleString("zh-CN")} 条关系 · 数据版本 ${meta.dataVersion}`,
    24 * uiScale,
    52 * uiScale
  );

  const footerHeight = 72 * uiScale;
  context.fillStyle = "rgba(255,255,255,0.92)";
  context.fillRect(0, canvas.height - footerHeight, canvas.width, footerHeight);
  let x = 24 * uiScale;
  context.font = `600 ${9 * uiScale}px "Noto Sans SC", "PingFang SC", sans-serif`;
  context.fillStyle = "#435166";
  context.fillText("实体领域", x, canvas.height - 49 * uiScale);
  x += 60 * uiScale;
  Object.entries(DOMAIN_COLORS).forEach(([label, color]) => {
    context.fillStyle = color;
    context.beginPath();
    context.arc(x, canvas.height - 52 * uiScale, 3.5 * uiScale, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = "#64748b";
    context.fillText(label, x + 7 * uiScale, canvas.height - 49 * uiScale);
    x += context.measureText(label).width + 24 * uiScale;
  });
  x = 24 * uiScale;
  context.fillStyle = "#435166";
  context.fillText("关系类型", x, canvas.height - 20 * uiScale);
  x += 60 * uiScale;
  RELATION_THEMES.forEach((theme) => {
    context.strokeStyle = theme.color;
    context.lineWidth = 2 * uiScale;
    context.beginPath();
    context.moveTo(x, canvas.height - 23 * uiScale);
    context.lineTo(x + 14 * uiScale, canvas.height - 23 * uiScale);
    context.stroke();
    context.fillStyle = "#64748b";
    context.fillText(theme.label, x + 19 * uiScale, canvas.height - 20 * uiScale);
    x += context.measureText(theme.label).width + 38 * uiScale;
  });
  return canvasToBlob(canvas);
}

export function downloadPng(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
