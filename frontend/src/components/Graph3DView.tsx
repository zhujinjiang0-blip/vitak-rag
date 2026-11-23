import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { graphDomainColor, graphRelationTheme } from "../lib/graphTheme";
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
  handle?: THREE.Mesh;
  bendOffset: THREE.Vector3;
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

    const overview = nodes.length > 300;
    const showEdgeHandles = edges.length <= 350;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(48, 1, 1, 2400);
    camera.position.set(
      overview ? 620 : 170,
      overview ? 420 : 115,
      overview ? 1050 : 360
    );

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.setAttribute(
      "aria-label",
      showEdgeHandles
        ? "可旋转、缩放、拖拽节点和关系曲线控制点、点击选择节点的三维知识图谱"
        : "可旋转、缩放和点击选择节点的全量三维知识图谱"
    );
    renderer.domElement.dataset.interactionReady = showEdgeHandles
      ? "node-edge"
      : "node";
    root.replaceChildren(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.minDistance = overview ? 180 : 90;
    controls.maxDistance = overview ? 2600 : 760;
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
    const explicitCenter = nodes.find((node) => node.id === selectedId);
    const center = explicitCenter ?? (overview ? null : nodes[0]);
    if (center) positions.set(center.id, new THREE.Vector3(0, 0, 0));
    const others = center
      ? nodes.filter((node) => node.id !== center.id)
      : nodes;
    const radius = overview
      ? Math.max(330, Math.min(660, 220 + Math.sqrt(others.length) * 20))
      : Math.max(150, Math.min(245, 115 + others.length * 4.4));

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
    if (center) persistentLabels.add(center.id);
    nodes.forEach((node) => {
      const point = positions.get(node.id);
      if (!point) return;
      const isCenter = node.id === center?.id;
      const baseRadius = isCenter ? 10.5 : overview ? 3.4 : 6.2;
      const geometry = new THREE.SphereGeometry(
        baseRadius,
        overview ? 10 : 24,
        overview ? 8 : 18
      );
      const color = new THREE.Color(graphDomainColor(node.domain));
      const material = new THREE.MeshPhysicalMaterial({
        color,
        emissive: color,
        emissiveIntensity: isCenter ? 0.3 : overview ? 0.04 : 0.1,
        roughness: 0.18,
        metalness: 0.08,
        transparent: true,
        opacity: isCenter ? 0.86 : overview ? 0.58 : 0.7,
        transmission: overview ? 0 : 0.28,
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

      if (!overview || isCenter) {
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
      }

      if (!overview || persistentLabels.has(node.id)) {
        const label = nodeLabel(node.name);
        label.position.copy(point).add(new THREE.Vector3(0, baseRadius + 8, 0));
        label.visible = persistentLabels.has(node.id);
        label.userData.persistent = persistentLabels.has(node.id);
        scene.add(label);
        mesh.userData.label = label;
      }
    });

    const edgeObjects: EdgeObject[] = [];
    function updateEdgeCurve(edgeObject: EdgeObject) {
      const source = positions.get(edgeObject.edge.source);
      const target = positions.get(edgeObject.edge.target);
      if (!source || !target) return;
      const controlPoint = source
        .clone()
        .add(target)
        .multiplyScalar(0.5)
        .add(edgeObject.bendOffset);
      const curve = new THREE.QuadraticBezierCurve3(source, controlPoint, target);
      edgeObject.line.geometry.dispose();
      edgeObject.line.geometry = new THREE.BufferGeometry().setFromPoints(
        curve.getPoints(20)
      );
      edgeObject.handle?.position.copy(controlPoint);
    }

    edges.forEach((edge, index) => {
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      if (!source || !target) return;
      const relationTheme = graphRelationTheme(edge.predicate);
      const bendOffset = new THREE.Vector3(
        ((index % 3) - 1) * 4,
        7 + (index % 3) * 3,
        (index % 2 === 0 ? 1 : -1) * 7
      );
      const material = new THREE.LineBasicMaterial({
        color: relationTheme.color,
        transparent: true,
        opacity: overview ? 0.1 : edge.is_demo ? 0.24 : 0.48,
        depthWrite: false
      });
      const line = new THREE.Line(new THREE.BufferGeometry(), material);
      scene.add(line);
      let handle: THREE.Mesh | undefined;
      if (showEdgeHandles) {
        handle = new THREE.Mesh(
          new THREE.SphereGeometry(3, 12, 8),
          new THREE.MeshBasicMaterial({
            color: relationTheme.color,
            transparent: true,
            opacity: 0.42,
            depthWrite: false
          })
        );
        handle.userData.edgeId = edge.id;
        handle.renderOrder = 1;
        scene.add(handle);
      }
      const edgeObject = { edge, line, handle, bendOffset };
      updateEdgeCurve(edgeObject);
      edgeObjects.push(edgeObject);
    });
    edgeObjectsRef.current = edgeObjects;
    const edgeHandles = () =>
      edgeObjects.flatMap((item) => (item.handle ? [item.handle] : []));

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const dragPlane = new THREE.Plane();
    const planeNormal = new THREE.Vector3();
    const intersection = new THREE.Vector3();
    type DragState =
      | {
          mode: "node";
          nodeId: string;
          moved: boolean;
          start: THREE.Vector3;
        }
      | {
          mode: "edge";
          edgeObject: EdgeObject;
          moved: boolean;
          start: THREE.Vector3;
        };
    let dragState: DragState | null = null;

    function updatePointer(event: PointerEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    }

    function beginPlaneDrag(point: THREE.Vector3) {
      camera.getWorldDirection(planeNormal);
      dragPlane.setFromNormalAndCoplanarPoint(planeNormal, point);
    }

    function updateAllEdgeCurves() {
      edgeObjects.forEach(updateEdgeCurve);
    }

    function handlePointerDown(event: PointerEvent) {
      if (event.button !== 0) return;
      updatePointer(event);
      raycaster.setFromCamera(pointer, camera);
      const edgeHit = raycaster.intersectObjects(edgeHandles())[0];
      const nodeHit = raycaster.intersectObjects([...nodeMeshes.values()])[0];

      if (edgeHit) {
        const edgeObject = edgeObjects.find(
          (item) => item.edge.id === edgeHit.object.userData.edgeId
        );
        if (!edgeObject) return;
        if (!edgeObject.handle) return;
        beginPlaneDrag(edgeObject.handle.position);
        dragState = {
          mode: "edge",
          edgeObject,
          moved: false,
          start: edgeObject.handle.position.clone(),
        };
        renderer.domElement.dataset.activeDrag = "edge";
        controls.enabled = false;
        renderer.domElement.style.cursor = "grabbing";
        renderer.domElement.setPointerCapture?.(event.pointerId);
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }

      const nodeId = nodeHit?.object.userData.nodeId as string | undefined;
      const nodeMesh = nodeId ? nodeMeshes.get(nodeId) : undefined;
      if (nodeId && nodeMesh) {
        beginPlaneDrag(nodeMesh.position);
        dragState = {
          mode: "node",
          nodeId,
          moved: false,
          start: nodeMesh.position.clone(),
        };
        renderer.domElement.dataset.activeDrag = "node";
        controls.enabled = false;
        renderer.domElement.style.cursor = "grabbing";
        renderer.domElement.setPointerCapture?.(event.pointerId);
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }

    function finishPointer(event: PointerEvent) {
      if (!dragState) return;
      if (dragState.moved) {
        renderer.domElement.dataset.lastDrag = dragState.mode;
      }
      if (dragState.mode === "node" && !dragState.moved) {
        const node = nodeById.get(dragState.nodeId);
        if (node) onSelectRef.current(node);
      }
      dragState = null;
      delete renderer.domElement.dataset.activeDrag;
      controls.enabled = true;
      renderer.domElement.style.cursor = "grab";
      renderer.domElement.releasePointerCapture?.(event.pointerId);
      event.preventDefault();
      event.stopImmediatePropagation();
    }

    function handlePointerMove(event: PointerEvent) {
      updatePointer(event);
      raycaster.setFromCamera(pointer, camera);

      if (dragState) {
        if (!raycaster.ray.intersectPlane(dragPlane, intersection)) return;
        if (dragState.mode === "node") {
          const nodeMesh = nodeMeshes.get(dragState.nodeId);
          if (!nodeMesh) return;
          dragState.moved =
            dragState.moved ||
            intersection.distanceTo(dragState.start) > 0.25;
          nodeMesh.position.copy(intersection);
          positions.set(dragState.nodeId, intersection.clone());
          const label = nodeMesh.userData.label as THREE.Sprite | undefined;
          if (label) {
            const radius = Number(nodeMesh.userData.baseRadius ?? 7.2);
            label.position.copy(intersection).add(new THREE.Vector3(0, radius + 8, 0));
          }
          updateAllEdgeCurves();
        } else {
          const { edgeObject } = dragState;
          const source = positions.get(edgeObject.edge.source);
          const target = positions.get(edgeObject.edge.target);
          if (!source || !target) return;
          dragState.moved =
            dragState.moved ||
            intersection.distanceTo(dragState.start) > 0.2;
          const midpoint = source.clone().add(target).multiplyScalar(0.5);
          edgeObject.bendOffset.copy(intersection).sub(midpoint);
          updateEdgeCurve(edgeObject);
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }

      const nodeHit = raycaster.intersectObjects([...nodeMeshes.values()])[0];
      const edgeHit = raycaster.intersectObjects(edgeHandles())[0];
      const hoveredId = nodeHit?.object.userData.nodeId as string | undefined;
      renderer.domElement.style.cursor = edgeHit
        ? "grab"
        : hoveredId
          ? "pointer"
          : "grab";
      edgeObjects.forEach(({ handle }) => {
        if (!handle) return;
        const material = handle.material as THREE.MeshBasicMaterial;
        material.opacity =
          edgeHit?.object === handle
            ? 0.95
            : edgeObjectsRef.current.some(
                  (item) =>
                    item.edge.id === handle.userData.edgeId &&
                    (item.edge.source === selectedIdRef.current ||
                      item.edge.target === selectedIdRef.current)
                )
              ? 0.68
              : 0.42;
      });
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

    renderer.domElement.addEventListener("pointerdown", handlePointerDown, true);
    renderer.domElement.addEventListener("pointerup", finishPointer, true);
    renderer.domElement.addEventListener("pointermove", handlePointerMove, true);
    renderer.domElement.addEventListener("pointercancel", finishPointer, true);
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
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown, true);
      renderer.domElement.removeEventListener("pointerup", finishPointer, true);
      renderer.domElement.removeEventListener("pointermove", handlePointerMove, true);
      renderer.domElement.removeEventListener("pointercancel", finishPointer, true);
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
    const denseGraph = edgeObjectsRef.current.length > 350;
    edgeObjectsRef.current.forEach(({ edge, line, handle }) => {
      const active = edge.source === selectedId || edge.target === selectedId;
      const material = line.material as THREE.LineBasicMaterial;
      const theme = graphRelationTheme(edge.predicate);
      material.opacity = active ? 0.92 : denseGraph ? 0.1 : edge.is_demo ? 0.24 : 0.48;
      material.color.set(theme.color);
      const handleMaterial = handle?.material as THREE.MeshBasicMaterial | undefined;
      if (handleMaterial) {
        handleMaterial.opacity = active ? 0.88 : 0.42;
      }
    });
  }, [selectedId]);

  return <div className="graph-3d-canvas" ref={containerRef} />;
}

export default Graph3DView;
