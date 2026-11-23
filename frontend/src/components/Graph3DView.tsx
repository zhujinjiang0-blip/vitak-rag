import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { graphDomainColor } from "../lib/graphTheme";
import type { GraphEdge, GraphNode } from "../lib/types";

interface Graph3DViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: string | null;
  onSelect: (node: GraphNode) => void;
}

interface EdgeObject {
  edge: GraphEdge;
  line: THREE.Line;
}

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

function nodeLabel(text: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  if (context) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.font =
      '700 38px "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif';
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.lineWidth = 8;
    context.strokeStyle = "rgba(255,255,255,0.96)";
    context.strokeText(text.slice(0, 22), canvas.width / 2, canvas.height / 2);
    context.fillStyle = "#243244";
    context.fillText(text.slice(0, 22), canvas.width / 2, canvas.height / 2);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(54, 13.5, 1);
  return sprite;
}

function Graph3DView({
  nodes,
  edges,
  selectedId,
  onSelect
}: Graph3DViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const nodeMeshesRef = useRef(new Map<string, THREE.Mesh>());
  const edgeObjectsRef = useRef<EdgeObject[]>([]);
  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    const root = containerRef.current!;
    if (!root || nodes.length === 0) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(48, 1, 1, 2400);
    camera.position.set(170, 115, 360);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.setAttribute(
      "aria-label",
      "可旋转、缩放和点击选择节点的三维知识图谱"
    );
    root.replaceChildren(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.minDistance = 90;
    controls.maxDistance = 760;
    controls.rotateSpeed = 0.65;
    controls.zoomSpeed = 0.8;

    scene.add(new THREE.HemisphereLight(0xffffff, 0xdbe6ee, 2.4));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.1);
    keyLight.position.set(180, 260, 240);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0x9ad7d0, 0.8);
    fillLight.position.set(-220, -120, -180);
    scene.add(fillLight);

    const positions = new Map<string, THREE.Vector3>();
    const center = nodes.find((node) => node.id === selectedId) ?? nodes[0];
    positions.set(center.id, new THREE.Vector3(0, 0, 0));
    const others = nodes.filter((node) => node.id !== center.id);
    const radius = Math.max(150, Math.min(245, 115 + others.length * 4.4));

    others.forEach((node, index) => {
      const fraction = (index + 0.5) / Math.max(1, others.length);
      const y = 1 - fraction * 2;
      const horizontal = Math.sqrt(Math.max(0, 1 - y * y));
      const theta = index * GOLDEN_ANGLE;
      const shell = index % 3 === 0 ? radius * 0.72 : radius;
      positions.set(
        node.id,
        new THREE.Vector3(
          Math.cos(theta) * horizontal * shell,
          y * shell * 0.76,
          Math.sin(theta) * horizontal * shell
        )
      );
    });

    const nodeMeshes = nodeMeshesRef.current;
    nodeMeshes.clear();
    const nodeById = new Map(nodes.map((node) => [node.id, node]));
    nodes.forEach((node) => {
      const point = positions.get(node.id);
      if (!point) return;
      const isCenter = node.id === center.id;
      const baseRadius = isCenter ? 12 : 7.2;
      const geometry = new THREE.SphereGeometry(baseRadius, 24, 18);
      const color = new THREE.Color(graphDomainColor(node.domain));
      const material = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: isCenter ? 0.42 : 0.15,
        roughness: 0.42,
        metalness: 0.08
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.copy(point);
      mesh.userData.nodeId = node.id;
      mesh.userData.baseRadius = baseRadius;
      scene.add(mesh);
      nodeMeshes.set(node.id, mesh);

      const label = nodeLabel(node.name);
      label.position.copy(point).add(new THREE.Vector3(0, baseRadius + 10, 0));
      scene.add(label);
    });

    const edgeObjects: EdgeObject[] = [];
    edges.forEach((edge) => {
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      if (!source || !target) return;
      const geometry = new THREE.BufferGeometry().setFromPoints([source, target]);
      const material = new THREE.LineBasicMaterial({
        color: edge.is_demo ? 0xaab7c4 : 0x2b9f94,
        transparent: true,
        opacity: edge.is_demo ? 0.24 : 0.38
      });
      const line = new THREE.Line(geometry, material);
      scene.add(line);
      edgeObjects.push({ edge, line });
    });
    edgeObjectsRef.current = edgeObjects;

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let pointerStart = { x: 0, y: 0 };

    function updatePointer(event: PointerEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    }

    function handlePointerDown(event: PointerEvent) {
      pointerStart = { x: event.clientX, y: event.clientY };
    }

    function handlePointerUp(event: PointerEvent) {
      if (
        Math.abs(event.clientX - pointerStart.x) +
          Math.abs(event.clientY - pointerStart.y) >
        5
      ) {
        return;
      }
      updatePointer(event);
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects([...nodeMeshes.values()])[0];
      const nodeId = hit?.object.userData.nodeId as string | undefined;
      const node = nodeId ? nodeById.get(nodeId) : undefined;
      if (node) onSelectRef.current(node);
    }

    function handlePointerMove(event: PointerEvent) {
      updatePointer(event);
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects([...nodeMeshes.values()])[0];
      renderer.domElement.style.cursor = hit ? "pointer" : "grab";
    }

    renderer.domElement.addEventListener("pointerdown", handlePointerDown);
    renderer.domElement.addEventListener("pointerup", handlePointerUp);
    renderer.domElement.addEventListener("pointermove", handlePointerMove);

    function resize() {
      const width = Math.max(1, root.clientWidth);
      const height = Math.max(1, root.clientHeight);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    }
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(root);
    resize();

    let animationFrame = 0;
    function animate() {
      animationFrame = requestAnimationFrame(animate);
      controls.update();
      renderer.domElement.dataset.cameraPosition = camera.position
        .toArray()
        .map((value) => value.toFixed(2))
        .join(",");
      renderer.render(scene, camera);
    }
    animate();

    return () => {
      cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);
      renderer.domElement.removeEventListener("pointerup", handlePointerUp);
      renderer.domElement.removeEventListener("pointermove", handlePointerMove);
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Line) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material)
            ? object.material
            : [object.material];
          materials.forEach((material) => material.dispose());
        }
        if (object instanceof THREE.Sprite) {
          object.material.map?.dispose();
          object.material.dispose();
        }
      });
      renderer.dispose();
      root.replaceChildren();
      nodeMeshes.clear();
      edgeObjectsRef.current = [];
    };
  }, [edges, nodes]);

  useEffect(() => {
    nodeMeshesRef.current.forEach((mesh, nodeId) => {
      const selected = nodeId === selectedId;
      const baseRadius = Number(mesh.userData.baseRadius ?? 7.2);
      mesh.scale.setScalar(selected ? 1.35 : 1);
      mesh.userData.displayRadius = baseRadius * (selected ? 1.35 : 1);
      const material = mesh.material as THREE.MeshStandardMaterial;
      material.emissiveIntensity = selected ? 0.8 : 0.15;
    });
    edgeObjectsRef.current.forEach(({ edge, line }) => {
      const active = edge.source === selectedId || edge.target === selectedId;
      const material = line.material as THREE.LineBasicMaterial;
      material.opacity = active ? 0.88 : edge.is_demo ? 0.24 : 0.38;
      material.color.set(active ? 0x0f766e : edge.is_demo ? 0xaab7c4 : 0x2b9f94);
    });
  }, [selectedId]);

  return <div className="graph-3d-canvas" ref={containerRef} />;
}

export default Graph3DView;
