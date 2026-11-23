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

function nodeLabel(text: string, color: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 160;
  const context = canvas.getContext("2d");
  if (context) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.font =
      '650 34px "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif';
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillStyle = "rgba(5, 13, 26, 0.78)";
    context.strokeStyle = color;
    context.lineWidth = 4;
    context.beginPath();
    context.roundRect(24, 30, 592, 100, 24);
    context.fill();
    context.stroke();
    context.fillStyle = "#f4f8ff";
    context.fillText(text.slice(0, 22), canvas.width / 2, canvas.height / 2);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    opacity: 0.94,
    depthWrite: false
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(62, 15.5, 1);
  return sprite;
}

function glowSprite(color: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const context = canvas.getContext("2d");
  if (context) {
    const gradient = context.createRadialGradient(128, 128, 0, 128, 128, 128);
    gradient.addColorStop(0, "rgba(255, 255, 255, 0.96)");
    gradient.addColorStop(0.14, color);
    gradient.addColorStop(0.42, `${color}55`);
    gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
    context.fillStyle = gradient;
    context.fillRect(0, 0, 256, 256);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    opacity: 0.46,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  return new THREE.Sprite(material);
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
  const selectedIdRef = useRef(selectedId);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  useEffect(() => {
    const root = containerRef.current!;
    if (!root || nodes.length === 0) return;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x07111f, 0.0015);
    const camera = new THREE.PerspectiveCamera(48, 1, 1, 2400);
    camera.position.set(170, 115, 360);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.12;
    renderer.setClearColor(0x07111f, 1);
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

    scene.add(new THREE.HemisphereLight(0xb8ddff, 0x07111f, 1.7));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.6);
    keyLight.position.set(180, 260, 240);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0x6ee7d8, 1.1);
    fillLight.position.set(-220, -120, -180);
    scene.add(fillLight);
    const grid = new THREE.GridHelper(920, 46, 0x1d5364, 0x14323f);
    grid.position.y = -210;
    grid.material.transparent = true;
    grid.material.opacity = 0.2;
    scene.add(grid);

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
      const domainColor = graphDomainColor(node.domain);
      const color = new THREE.Color(domainColor);
      const material = new THREE.MeshPhysicalMaterial({
        color,
        emissive: color,
        emissiveIntensity: isCenter ? 0.62 : 0.34,
        roughness: 0.16,
        metalness: 0.2,
        transparent: true,
        opacity: isCenter ? 0.92 : 0.8,
        clearcoat: 1,
        clearcoatRoughness: 0.1
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.copy(point);
      mesh.userData.nodeId = node.id;
      mesh.userData.baseRadius = baseRadius;
      mesh.userData.baseOpacity = material.opacity;
      mesh.renderOrder = 2;
      scene.add(mesh);
      nodeMeshes.set(node.id, mesh);

      const glow = glowSprite(domainColor);
      const glowSize = baseRadius * 5.7;
      glow.scale.set(glowSize, glowSize, 1);
      glow.renderOrder = 1;
      glow.userData.baseScale = glowSize;
      glow.userData.baseOpacity = isCenter ? 0.58 : 0.38;
      mesh.add(glow);
      mesh.userData.glow = glow;

      const label = nodeLabel(node.name, domainColor);
      label.position.copy(point).add(new THREE.Vector3(0, baseRadius + 12, 0));
      scene.add(label);
      mesh.userData.label = label;
    });

    const edgeObjects: EdgeObject[] = [];
    edges.forEach((edge) => {
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      if (!source || !target) return;
      const midpoint = source
        .clone()
        .add(target)
        .multiplyScalar(0.5)
        .add(new THREE.Vector3(0, 8, 4));
      const curve = new THREE.QuadraticBezierCurve3(source, midpoint, target);
      const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(18));
      const material = new THREE.LineBasicMaterial({
        color: edge.is_demo ? 0x52667a : 0x2dd4bf,
        transparent: true,
        opacity: edge.is_demo ? 0.12 : 0.22,
        depthWrite: false
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
    const clock = new THREE.Clock();
    function animate() {
      animationFrame = requestAnimationFrame(animate);
      controls.update();
      const selectedMesh = selectedIdRef.current
        ? nodeMeshes.get(selectedIdRef.current)
        : undefined;
      const glow = selectedMesh?.userData.glow as THREE.Sprite | undefined;
      if (glow) {
        const baseScale = Number(glow.userData.baseScale ?? 30);
        const pulse = 1 + Math.sin(clock.getElapsedTime() * 2.4) * 0.08;
        glow.scale.set(baseScale * pulse, baseScale * pulse, 1);
      }
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
      const material = mesh.material as THREE.MeshPhysicalMaterial;
      material.emissiveIntensity = selected ? 0.9 : 0.34;
      material.opacity = selected
        ? 0.98
        : Number(mesh.userData.baseOpacity ?? 0.8);
      const glow = mesh.userData.glow as THREE.Sprite | undefined;
      const glowMaterial = glow?.material as THREE.SpriteMaterial | undefined;
      if (glowMaterial) {
        glowMaterial.opacity = selected
          ? 0.78
          : Number(glow?.userData.baseOpacity ?? 0.38);
      }
      const label = mesh.userData.label as THREE.Sprite | undefined;
      const labelMaterial = label?.material as THREE.SpriteMaterial | undefined;
      if (labelMaterial) labelMaterial.opacity = selected ? 1 : 0.92;
    });
    edgeObjectsRef.current.forEach(({ edge, line }) => {
      const active = edge.source === selectedId || edge.target === selectedId;
      const material = line.material as THREE.LineBasicMaterial;
      material.opacity = active ? 0.72 : edge.is_demo ? 0.12 : 0.22;
      material.color.set(active ? 0x5eead4 : edge.is_demo ? 0x52667a : 0x2dd4bf);
    });
  }, [selectedId]);

  return <div className="graph-3d-canvas" ref={containerRef} />;
}

export default Graph3DView;
