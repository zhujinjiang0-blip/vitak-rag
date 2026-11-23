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
  canvas.height = 96;
  const context = canvas.getContext("2d");
  if (context) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.font =
      '650 30px "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif';
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.lineWidth = 6;
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
    opacity: 0.92,
    depthWrite: false
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(43, 8.1, 1);
  return sprite;
}

function glowSprite(color: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const context = canvas.getContext("2d");
  if (context) {
    const gradient = context.createRadialGradient(128, 128, 0, 128, 128, 128);
    gradient.addColorStop(0, "rgba(255, 255, 255, 0.78)");
    gradient.addColorStop(0.22, `${color}aa`);
    gradient.addColorStop(0.52, `${color}35`);
    gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
    context.fillStyle = gradient;
    context.fillRect(0, 0, 256, 256);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      opacity: 0.2,
      depthWrite: false
    })
  );
}

function selectionRing(color: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const context = canvas.getContext("2d");
  if (context) {
    context.strokeStyle = color;
    context.lineWidth = 8;
    context.beginPath();
    context.arc(128, 128, 90, 0, Math.PI * 2);
    context.stroke();
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      opacity: 0.92,
      depthWrite: false
    })
  );
  sprite.visible = false;
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
    const degree = new Map<string, number>();
    edges.forEach((edge) => {
      degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
      degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
    });
    const persistentLabels = new Set(
      [...nodes]
        .sort(
          (left, right) =>
            (degree.get(right.id) ?? 0) - (degree.get(left.id) ?? 0)
        )
        .slice(0, 9)
        .map((node) => node.id)
    );
    persistentLabels.add(center.id);
    nodes.forEach((node) => {
      const point = positions.get(node.id);
      if (!point) return;
      const isCenter = node.id === center.id;
      const baseRadius = isCenter ? 10.5 : 6.2;
      const geometry = new THREE.SphereGeometry(baseRadius, 24, 18);
      const color = new THREE.Color(graphDomainColor(node.domain));
      const material = new THREE.MeshPhysicalMaterial({
        color,
        emissive: color,
        emissiveIntensity: isCenter ? 0.3 : 0.1,
        roughness: 0.18,
        metalness: 0.08,
        transparent: true,
        opacity: isCenter ? 0.86 : 0.7,
        transmission: 0.28,
        thickness: 1.4,
        clearcoat: 1,
        clearcoatRoughness: 0.12
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.copy(point);
      mesh.userData.nodeId = node.id;
      mesh.userData.baseRadius = baseRadius;
      mesh.userData.baseOpacity = material.opacity;
      mesh.renderOrder = 2;
      scene.add(mesh);
      nodeMeshes.set(node.id, mesh);

      const glow = glowSprite(graphDomainColor(node.domain));
      const glowSize = baseRadius * 3.2;
      glow.scale.set(glowSize, glowSize, 1);
      glow.userData.baseScale = glowSize;
      glow.userData.baseOpacity = isCenter ? 0.3 : 0.16;
      const glowMaterial = glow.material as THREE.SpriteMaterial;
      glowMaterial.opacity = glow.userData.baseOpacity;
      glow.renderOrder = 1;
      mesh.add(glow);
      mesh.userData.glow = glow;

      const ring = selectionRing(graphDomainColor(node.domain));
      const ringSize = baseRadius * 2.75;
      ring.scale.set(ringSize, ringSize, 1);
      ring.renderOrder = 3;
      mesh.add(ring);
      mesh.userData.ring = ring;

      const label = nodeLabel(node.name);
      label.position.copy(point).add(new THREE.Vector3(0, baseRadius + 8, 0));
      label.visible = persistentLabels.has(node.id);
      label.userData.persistent = persistentLabels.has(node.id);
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
        .add(new THREE.Vector3(0, 6, 3));
      const curve = new THREE.QuadraticBezierCurve3(source, midpoint, target);
      const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(18));
      const material = new THREE.LineBasicMaterial({
        color: edge.is_demo ? 0xaab7c4 : 0x2b9f94,
        transparent: true,
        opacity: edge.is_demo ? 0.18 : 0.3,
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
      const hoveredId = hit?.object.userData.nodeId as string | undefined;
      renderer.domElement.style.cursor = hoveredId ? "pointer" : "grab";
      nodeMeshes.forEach((mesh, nodeId) => {
        const label = mesh.userData.label as THREE.Sprite | undefined;
        if (!label) return;
        label.visible =
          nodeId === hoveredId ||
          nodeId === selectedIdRef.current ||
          Boolean(label.userData.persistent);
      });
    }

    function handlePointerLeave() {
      renderer.domElement.style.cursor = "grab";
      nodeMeshes.forEach((nodeMesh, nodeId) => {
        const label = nodeMesh.userData.label as THREE.Sprite | undefined;
        if (!label) return;
        label.visible =
          nodeId === selectedIdRef.current || Boolean(label.userData.persistent);
      });
    }

    renderer.domElement.addEventListener("pointerdown", handlePointerDown);
    renderer.domElement.addEventListener("pointerup", handlePointerUp);
    renderer.domElement.addEventListener("pointermove", handlePointerMove);
    renderer.domElement.addEventListener("pointerleave", handlePointerLeave);

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
      renderer.domElement.removeEventListener("pointerleave", handlePointerLeave);
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
      mesh.scale.setScalar(selected ? 1.22 : 1);
      mesh.userData.displayRadius = baseRadius * (selected ? 1.22 : 1);
      const material = mesh.material as THREE.MeshPhysicalMaterial;
      material.emissiveIntensity = selected ? 0.62 : 0.1;
      material.opacity = selected
        ? 0.94
        : Number(mesh.userData.baseOpacity ?? 0.7);
      const glow = mesh.userData.glow as THREE.Sprite | undefined;
      const glowMaterial = glow?.material as THREE.SpriteMaterial | undefined;
      if (glowMaterial) {
        glowMaterial.opacity = selected
          ? 0.42
          : Number(glow?.userData.baseOpacity ?? 0.16);
      }
      const ring = mesh.userData.ring as THREE.Sprite | undefined;
      if (ring) ring.visible = selected;
      const label = mesh.userData.label as THREE.Sprite | undefined;
      if (label) {
        label.visible = selected || Boolean(label.userData.persistent);
      }
    });
    edgeObjectsRef.current.forEach(({ edge, line }) => {
      const active = edge.source === selectedId || edge.target === selectedId;
      const material = line.material as THREE.LineBasicMaterial;
      material.opacity = active ? 0.72 : edge.is_demo ? 0.18 : 0.3;
      material.color.set(active ? 0x0f766e : edge.is_demo ? 0xaab7c4 : 0x2b9f94);
    });
  }, [selectedId]);

  return <div className="graph-3d-canvas" ref={containerRef} />;
}

export default Graph3DView;
