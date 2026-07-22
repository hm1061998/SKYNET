import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';

const KIND_ORDER = ['work_order', 'agent', 'task', 'artifact', 'approval'];
const KIND_LABELS = { work_order: 'Work order', agent: 'AI entities', task: 'Tasks', artifact: 'Artifacts', approval: 'Human gates' };
const COLORS = { work_order: 0x4fe3ff, agent: 0x50f6c8, task: 0x8a70ff, artifact: 0x4fa4d8, approval: 0xffbd59 };

function layout(nodes) {
  const x = { work_order: -4.2, agent: -2.2, task: 0, artifact: 2.4, approval: 4.35 };
  return nodes.map((node) => {
    const peers = nodes.filter((item) => item.kind === node.kind);
    const index = peers.findIndex((item) => item.id === node.id);
    const y = peers.length === 1 ? 0 : 2.8 - (5.6 * index) / (peers.length - 1);
    return { ...node, position: new THREE.Vector3(x[node.kind] || 0, y, Math.sin(index * 1.7) * .55) };
  });
}

function labelSprite(text, color) {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  canvas.width = 512; canvas.height = 72;
  context.fillStyle = 'rgba(3,8,20,.82)'; context.fillRect(0, 0, 512, 72);
  context.strokeStyle = `#${color.toString(16).padStart(6, '0')}`; context.strokeRect(1, 1, 510, 70);
  context.fillStyle = '#e9fbff'; context.font = '24px Consolas'; context.textAlign = 'center'; context.textBaseline = 'middle';
  const compact = text.length > 31 ? `${text.slice(0, 30)}…` : text;
  context.fillText(compact, 256, 37);
  const texture = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false }));
  sprite.scale.set(2.15, .3, 1); sprite.position.y = -.35; sprite.userData.texture = texture;
  return sprite;
}

function dispose(root) {
  root.traverse((child) => {
    child.geometry?.dispose();
    const materials = Array.isArray(child.material) ? child.material : [child.material];
    materials.filter(Boolean).forEach((material) => { material.map?.dispose(); material.dispose(); });
  });
}

function ThreeOrganizationGraph({ nodes, edges, selectedId, onSelect }) {
  const hostRef = useRef(null);
  const runtimeRef = useRef(null);
  const viewStateRef = useRef({ rotationX: -.08, rotationY: 0, zoom: 12.5 });

  useEffect(() => {
    const host = hostRef.current;
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020711, .055);
    const camera = new THREE.PerspectiveCamera(48, 1, .1, 100);
    camera.position.set(0, .1, viewStateRef.current.zoom);
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      const fallback = document.createElement('p');
      fallback.className = 'webgl-fallback';
      fallback.textContent = '3D rendering is unavailable. Use the keyboard entity list to inspect the organization.';
      host.appendChild(fallback);
      return () => fallback.remove();
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x020711, 0); renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    const graph = new THREE.Group();
    graph.rotation.x = viewStateRef.current.rotationX;
    graph.rotation.y = viewStateRef.current.rotationY;
    scene.add(graph);
    scene.add(new THREE.AmbientLight(0x79bfff, .7));
    const key = new THREE.PointLight(0x50f6c8, 18, 25); key.position.set(0, 1, 5); scene.add(key);

    const starsGeometry = new THREE.BufferGeometry();
    const stars = new Float32Array(900);
    for (let index = 0; index < stars.length; index += 3) {
      stars[index] = (Math.random() - .5) * 15; stars[index + 1] = (Math.random() - .5) * 9; stars[index + 2] = (Math.random() - .5) * 6;
    }
    starsGeometry.setAttribute('position', new THREE.BufferAttribute(stars, 3));
    graph.add(new THREE.Points(starsGeometry, new THREE.PointsMaterial({ color: 0x2b7995, size: .018, transparent: true, opacity: .34 })));

    const nodeMeshes = new Map();
    nodes.forEach((node, index) => {
      const color = COLORS[node.kind] || 0x4fe3ff;
      const group = new THREE.Group(); group.position.copy(node.position); group.userData.nodeId = node.id;
      const radius = node.kind === 'work_order' ? .19 : node.kind === 'agent' ? .14 : .11;
      const core = new THREE.Mesh(new THREE.IcosahedronGeometry(radius, 2), new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: node.status === 'waiting_approval' || node.status === 'pending' ? 3.8 : 2.1, roughness: .2 }));
      core.userData.nodeId = node.id; group.add(core);
      const halo = new THREE.Mesh(new THREE.SphereGeometry(radius * 2.3, 18, 12), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .08, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.BackSide }));
      halo.userData.nodeId = node.id; group.add(halo, labelSprite(node.label, color));
      if (node.kind === 'agent') {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(radius * 1.9, .012, 6, 48), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .55 }));
        ring.rotation.x = Math.PI / 2; group.add(ring);
      }
      group.userData.phase = index * .73; group.userData.core = core; group.userData.halo = halo;
      nodeMeshes.set(node.id, group); graph.add(group);
    });

    const edgeLines = [];
    edges.forEach((edge) => {
      const source = nodeMeshes.get(edge.source); const target = nodeMeshes.get(edge.target);
      if (!source || !target) return;
      const middle = source.position.clone().lerp(target.position, .5); middle.z += .35;
      const curve = new THREE.QuadraticBezierCurve3(source.position, middle, target.position);
      const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(30));
      const color = edge.kind === 'gated_by' ? 0xffbd59 : edge.kind === 'reports_to' ? 0x876dba : 0x285c72;
      const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color, transparent: true, opacity: .34 }));
      line.userData.edge = edge; line.userData.baseColor = color;
      edgeLines.push(line); graph.add(line);
    });
    runtimeRef.current = { nodeMeshes, edgeLines };

    let dragging = false; let dragDistance = 0; let px = 0; let py = 0; let targetZoom = viewStateRef.current.zoom;
    const pointer = new THREE.Vector2(); const raycaster = new THREE.Raycaster();
    const pointerDown = (event) => { dragging = true; dragDistance = 0; px = event.clientX; py = event.clientY; renderer.domElement.setPointerCapture(event.pointerId); };
    const pointerMove = (event) => { if (!dragging) return; const dx = event.clientX - px; const dy = event.clientY - py; dragDistance += Math.hypot(dx, dy); graph.rotation.y += dx * .006; graph.rotation.x = THREE.MathUtils.clamp(graph.rotation.x + dy * .004, -.7, .7); px = event.clientX; py = event.clientY; };
    const pointerUp = (event) => { dragging = false; if (dragDistance > 6) return; const rect = renderer.domElement.getBoundingClientRect(); pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1); raycaster.setFromCamera(pointer, camera); const hits = raycaster.intersectObjects([...nodeMeshes.values()], true); const nodeId = hits[0]?.object.userData.nodeId || hits[0]?.object.parent?.userData.nodeId; if (nodeId) onSelect(nodeId); };
    const wheel = (event) => { event.preventDefault(); targetZoom = THREE.MathUtils.clamp(targetZoom + event.deltaY * .006, 7.5, 18); };
    renderer.domElement.addEventListener('pointerdown', pointerDown); renderer.domElement.addEventListener('pointermove', pointerMove); renderer.domElement.addEventListener('pointerup', pointerUp); renderer.domElement.addEventListener('wheel', wheel, { passive: false });
    const resize = () => { const width = host.clientWidth; const height = host.clientHeight; camera.aspect = width / Math.max(height, 1); camera.updateProjectionMatrix(); renderer.setSize(width, height, false); };
    const observer = new ResizeObserver(resize); observer.observe(host); resize();

    let animationId; const started = performance.now();
    const animate = (now) => { animationId = requestAnimationFrame(animate); const time = (now - started) / 1000; camera.position.z += (targetZoom - camera.position.z) * .1; if (!dragging) graph.rotation.y += .0008; nodeMeshes.forEach((item) => { const pulse = .5 + Math.sin(time * 2.2 + item.userData.phase) * .5; item.userData.core.rotation.x += .006; item.userData.core.rotation.y += .01; item.userData.halo.scale.setScalar(1 + pulse * .16); }); renderer.render(scene, camera); };
    animationId = requestAnimationFrame(animate);
    return () => { viewStateRef.current = { rotationX: graph.rotation.x, rotationY: graph.rotation.y, zoom: targetZoom }; runtimeRef.current = null; cancelAnimationFrame(animationId); observer.disconnect(); renderer.domElement.removeEventListener('pointerdown', pointerDown); renderer.domElement.removeEventListener('pointermove', pointerMove); renderer.domElement.removeEventListener('pointerup', pointerUp); renderer.domElement.removeEventListener('wheel', wheel); dispose(graph); renderer.dispose(); renderer.domElement.remove(); };
  }, [nodes, edges, onSelect]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime) return;
    runtime.nodeMeshes.forEach((item, id) => {
      const active = id === selectedId;
      item.scale.setScalar(active ? 1.22 : 1);
      item.userData.halo.material.opacity = active ? .34 : .08;
    });
    runtime.edgeLines.forEach((line) => {
      const edge = line.userData.edge;
      const active = edge.source === selectedId || edge.target === selectedId;
      line.material.color.setHex(active ? 0xdffcff : line.userData.baseColor);
      line.material.opacity = active ? .92 : .34;
    });
  }, [selectedId, nodes, edges]);

  return <div ref={hostRef} className="organization-3d-stage" aria-label="Interactive 3D graph of the live AI organization" />;
}

export default function LiveOrganizationGraph({ topology, onOpenTask }) {
  const [selectedId, setSelectedId] = useState(topology.nodes[0]?.id || '');
  const [visibleKinds, setVisibleKinds] = useState(new Set(KIND_ORDER));
  const topologySignature = JSON.stringify({ nodes: topology.nodes, edges: topology.edges });
  const positioned = useMemo(() => layout(topology.nodes.filter((node) => visibleKinds.has(node.kind))), [topologySignature, visibleKinds]);
  const ids = new Set(positioned.map((node) => node.id));
  const edges = useMemo(() => topology.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)), [topologySignature, positioned]);
  const selected = topology.nodes.find((node) => node.id === selectedId);
  const toggleKind = (kind) => setVisibleKinds((current) => { const next = new Set(current); if (next.has(kind) && next.size > 1) next.delete(kind); else next.add(kind); return next; });

  return <div className="live-graph-shell">
    <div className="graph-toolbar" aria-label="Graph filters">{KIND_ORDER.map((kind) => <button key={kind} className={visibleKinds.has(kind) ? `kind-${kind} active` : ''} aria-pressed={visibleKinds.has(kind)} onClick={() => toggleKind(kind)}>{KIND_LABELS[kind]}</button>)}<span className="live-indicator"><i /> Live · refresh 5s</span></div>
    <div className="live-graph-workspace"><ThreeOrganizationGraph nodes={positioned} edges={edges} selectedId={selectedId} onSelect={setSelectedId}/><aside className="graph-inspector" aria-live="polite">{selected ? <><span className={`entity-kind kind-${selected.kind}`}>{KIND_LABELS[selected.kind]}</span><h3>{selected.label}</h3><span className={`ops-status status-${selected.status}`}>{selected.status.replaceAll('_', ' ')}</span><p>{selected.detail || 'No operational detail.'}</p><dl><dt>ID</dt><dd><code>{selected.id}</code></dd>{selected.current_task && <><dt>Current task</dt><dd>{selected.current_task}</dd></>}{selected.risk && <><dt>Risk</dt><dd>{selected.risk}</dd></>}</dl>{selected.kind === 'task' && <button onClick={() => onOpenTask(selected.id)}>Open task details</button>}</> : <p>Select an entity to inspect it.</p>}<div className="accessible-entities"><strong>Keyboard entity list</strong>{positioned.map((node) => <button key={node.id} className={node.id === selectedId ? 'selected' : ''} onClick={() => setSelectedId(node.id)}>{node.label}</button>)}</div></aside></div>
    <div className="graph-relationship-legend"><span>Drag: rotate</span><span>Wheel: zoom</span><span>Click node: inspect</span><span>Amber: approval gate</span><time>Snapshot {new Date(topology.generated_at).toLocaleTimeString()}</time></div>
  </div>;
}
