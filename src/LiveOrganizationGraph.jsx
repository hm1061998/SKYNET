import { memo, useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';

const KIND_ORDER = ['work_order', 'agent', 'skill', 'task', 'artifact', 'approval'];
const KIND_LABELS = { work_order: 'Work order', agent: 'AI entities', skill: 'Skills', task: 'Tasks', artifact: 'Artifacts', approval: 'Human gates' };
const COLORS = { work_order: 0x4fe3ff, agent: 0x50f6c8, skill: 0xff75d8, task: 0x8a70ff, artifact: 0x4fa4d8, approval: 0xffbd59 };
const VIEW_STORAGE_KEY = 'javis.organizationGraph.view.v1';

function loadViewState() {
  try {
    const value = JSON.parse(sessionStorage.getItem(VIEW_STORAGE_KEY) || 'null');
    if (value && [value.rotationX, value.rotationY, value.zoom].every(Number.isFinite)) return value;
  } catch { /* Session storage is optional. */ }
  return { rotationX: -.08, rotationY: 0, zoom: 7.4 };
}

function storeViewState(value) {
  try { sessionStorage.setItem(VIEW_STORAGE_KEY, JSON.stringify(value)); } catch { /* Session storage is optional. */ }
}

function seededUnit(index) {
  const value = Math.sin(index * 12.9898 + 78.233) * 43758.5453;
  return value - Math.floor(value);
}

function brainPoint(index, count) {
  const side = index % 2 ? 1 : -1;
  const i = Math.floor(index / 2); const n = Math.max(1, Math.ceil(count / 2));
  const phi = Math.acos(1 - (2 * (i + .5)) / n); const theta = Math.PI * (1 + Math.sqrt(5)) * i;
  return new THREE.Vector3(side * (.72 + Math.abs(Math.sin(phi) * Math.cos(theta)) * 1.35), Math.cos(phi) * 1.55, Math.sin(phi) * Math.sin(theta) * 1.2);
}

function layout(nodes, edges) {
  const positions = new Map();
  const agents = nodes.filter((node) => node.kind === 'agent');
  agents.forEach((node, index) => positions.set(node.id, brainPoint(index, agents.length)));
  nodes.filter((node) => node.kind === 'work_order').forEach((node) => positions.set(node.id, new THREE.Vector3(0, 0, 0)));
  const assignedAgent = new Map(edges.filter((edge) => edge.kind === 'assigned_to').map((edge) => [edge.target, edge.source]));
  const tasks = nodes.filter((node) => node.kind === 'task');
  tasks.forEach((node, index) => {
    const anchor = positions.get(assignedAgent.get(node.id)) || brainPoint(index, tasks.length).multiplyScalar(.65);
    positions.set(node.id, anchor.clone().multiplyScalar(1.38).add(new THREE.Vector3(0, .12, .18)));
  });
  const skillOwner = new Map(edges.filter((edge) => edge.kind === 'uses_skill').map((edge) => [edge.target, edge.source]));
  nodes.filter((node) => node.kind === 'skill').forEach((node, index) => {
    const anchor = positions.get(skillOwner.get(node.id)) || new THREE.Vector3(); const angle = index * 1.35 + .4;
    positions.set(node.id, anchor.clone().add(new THREE.Vector3(Math.cos(angle) * .72, .38 + index % 2 * .22, Math.sin(angle) * .62)));
  });
  const sourceTask = new Map(edges.filter((edge) => edge.kind === 'produces').map((edge) => [edge.target, edge.source]));
  const artifacts = nodes.filter((node) => node.kind === 'artifact');
  artifacts.forEach((node, index) => {
    const anchor = positions.get(sourceTask.get(node.id)); const angle = (index / Math.max(artifacts.length, 1)) * Math.PI * 2;
    positions.set(node.id, anchor ? anchor.clone().multiplyScalar(1.34) : new THREE.Vector3(Math.cos(angle) * 3.5, Math.sin(angle) * 2.2, Math.sin(angle * 2) * .7));
  });
  nodes.filter((node) => node.kind === 'approval').forEach((node, index) => positions.set(node.id, new THREE.Vector3(0, 2.75 + index * .35, .25)));
  return nodes.map((node) => ({ ...node, position: positions.get(node.id) || new THREE.Vector3() }));
}

function labelSprite(text, color) {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  canvas.width = 320; canvas.height = 48;
  context.beginPath(); context.roundRect(3, 5, 314, 38, 19);
  context.fillStyle = 'rgba(3,8,20,.68)'; context.fill();
  context.strokeStyle = `#${color.toString(16).padStart(6, '0')}`; context.globalAlpha = .45; context.stroke(); context.globalAlpha = 1;
  context.fillStyle = '#dff8ff'; context.font = '18px Consolas'; context.textAlign = 'center'; context.textBaseline = 'middle';
  const compact = text.length > 23 ? `${text.slice(0, 22)}…` : text;
  context.fillText(compact, 160, 25);
  const texture = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, opacity: .48, depthWrite: false }));
  sprite.scale.set(.86, .13, 1); sprite.position.y = -.24; sprite.userData.texture = texture;
  return sprite;
}

function dispose(root) {
  root.traverse((child) => {
    child.geometry?.dispose();
    const materials = Array.isArray(child.material) ? child.material : [child.material];
    materials.filter(Boolean).forEach((material) => { material.map?.dispose(); material.dispose(); });
  });
}

function ThreeOrganizationGraph({ nodes, edges, selectedId, onSelect, debugLinks, activity }) {
  const hostRef = useRef(null);
  const runtimeRef = useRef(null);
  const viewStateRef = useRef(loadViewState());
  const animationEpochRef = useRef(performance.now());
  const activityRef = useRef(activity);
  activityRef.current = activity;
  const structureSignature = JSON.stringify({
    nodes: nodes.map((node) => [node.id, node.kind, node.subkind]),
    edges: edges.map((edge) => [edge.source, edge.target, edge.kind]),
  });

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

    const neuralBridge = new THREE.Group();
    const callosum = new THREE.Mesh(new THREE.TorusGeometry(.62, .012, 6, 72, Math.PI * 1.72), new THREE.MeshBasicMaterial({ color: 0x50f6c8, transparent: true, opacity: .18, blending: THREE.AdditiveBlending }));
    callosum.rotation.set(0, Math.PI / 2, -.15); neuralBridge.add(callosum);
    for (let index = 0; index < 7; index += 1) {
      const y = -1.2 + index * .4;
      const curve = new THREE.QuadraticBezierCurve3(new THREE.Vector3(-1.15, y, Math.sin(index) * .28), new THREE.Vector3(0, y * .55, .45 + Math.cos(index) * .12), new THREE.Vector3(1.15, y, -Math.sin(index) * .28));
      const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(30));
      neuralBridge.add(new THREE.Line(geometry, new THREE.LineBasicMaterial({ color: index % 2 ? 0x4fe3ff : 0x8a70ff, transparent: true, opacity: .12, blending: THREE.AdditiveBlending })));
    }
    graph.add(neuralBridge);

    const cortexPositions = new Float32Array(950 * 3);
    for (let index = 0; index < 950; index += 1) {
      const point = brainPoint(index, 950); const jitter = .82 + seededUnit(index) * .42;
      cortexPositions.set([point.x * jitter, point.y * jitter, point.z * jitter], index * 3);
    }
    const cortexGeometry = new THREE.BufferGeometry(); cortexGeometry.setAttribute('position', new THREE.BufferAttribute(cortexPositions, 3));
    const cortex = new THREE.Points(cortexGeometry, new THREE.PointsMaterial({ color: 0x4fe3ff, size: .026, transparent: true, opacity: .4, blending: THREE.AdditiveBlending, depthWrite: false }));
    graph.add(cortex);

    const core = new THREE.Mesh(new THREE.IcosahedronGeometry(.34, 3), new THREE.MeshBasicMaterial({ color: 0x50f6c8, wireframe: true, transparent: true, opacity: .72 }));
    const coreAura = new THREE.Mesh(new THREE.SphereGeometry(.58, 24, 16), new THREE.MeshBasicMaterial({ color: 0x4fe3ff, transparent: true, opacity: .075, side: THREE.BackSide, blending: THREE.AdditiveBlending }));
    graph.add(core, coreAura);

    const fiberPoints = [];
    for (let index = 0; index < 150; index += 1) {
      const from = brainPoint(index, 150); const to = brainPoint((index + 11 + index % 9) % 150, 150);
      if (Math.sign(from.x) !== Math.sign(to.x)) to.x *= -1;
      fiberPoints.push(from.x, from.y, from.z, to.x, to.y, to.z);
    }
    const fiberGeometry = new THREE.BufferGeometry(); fiberGeometry.setAttribute('position', new THREE.Float32BufferAttribute(fiberPoints, 3));
    graph.add(new THREE.LineSegments(fiberGeometry, new THREE.LineBasicMaterial({ color: 0x247c93, transparent: true, opacity: .14, blending: THREE.AdditiveBlending })));

    const starsGeometry = new THREE.BufferGeometry();
    const stars = new Float32Array(900);
    for (let index = 0; index < stars.length; index += 3) {
      stars[index] = (seededUnit(index) - .5) * 15; stars[index + 1] = (seededUnit(index + 1) - .5) * 9; stars[index + 2] = (seededUnit(index + 2) - .5) * 6;
    }
    starsGeometry.setAttribute('position', new THREE.BufferAttribute(stars, 3));
    graph.add(new THREE.Points(starsGeometry, new THREE.PointsMaterial({ color: 0x2b7995, size: .018, transparent: true, opacity: .34 })));

    const nodeMeshes = new Map();
    nodes.forEach((node, index) => {
      const color = COLORS[node.kind] || 0x4fe3ff;
      const group = new THREE.Group(); group.position.copy(node.position); group.userData.nodeId = node.id;
      const radius = node.kind === 'work_order' ? .25 : node.kind === 'agent' ? .14 : .09;
      const core = new THREE.Mesh(new THREE.IcosahedronGeometry(radius, 2), new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: node.status === 'waiting_approval' || node.status === 'pending' ? 3.8 : 2.1, roughness: .2 }));
      core.userData.nodeId = node.id; group.add(core);
      const halo = new THREE.Mesh(new THREE.SphereGeometry(radius * 2.3, 18, 12), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .08, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.BackSide }));
      halo.userData.nodeId = node.id; group.add(halo);
      if (node.kind === 'agent' || node.kind === 'approval' || node.kind === 'skill') group.add(labelSprite(node.label, color));
      if (node.kind === 'agent') {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(radius * 1.9, .012, 6, 48), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .55 }));
        ring.rotation.x = Math.PI / 2; group.userData.processRing = ring; group.add(ring);
      }
      if (node.subkind === 'worker') {
        core.material.color.setHex(0xff9650); core.material.emissive.setHex(0xff9650);
        group.userData.worker = true;
      }
      const orbitRadius = node.kind === 'work_order' ? 0 : Math.max(.55, Math.hypot(node.position.x, node.position.z));
      group.userData.phase = index * .73; group.userData.core = core; group.userData.halo = halo;
      group.userData.baseColor = color; group.userData.processState = node.processState || 'idle';
      group.userData.label = group.children.find((child) => child.isSprite) || null;
      group.userData.orbit = { radius: orbitRadius, angle: Math.atan2(node.position.z, node.position.x), y: node.position.y, speed: .045 + index % 5 * .012 };
      nodeMeshes.set(node.id, group); graph.add(group);
    });

    const edgeLines = []; const signalCurves = [];
    edges.forEach((edge) => {
      const source = nodeMeshes.get(edge.source); const target = nodeMeshes.get(edge.target);
      if (!source || !target) return;
      const middle = source.position.clone().lerp(target.position, .5); middle.z += .35;
      const curve = new THREE.QuadraticBezierCurve3(source.position, middle, target.position);
      if (edge.kind !== 'reports_to') signalCurves.push(curve);
      const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(30));
      const color = edge.kind === 'gated_by' ? 0xffbd59 : edge.kind === 'uses_skill' ? 0xff75d8 : edge.kind === 'handoff_to' ? 0x50f6c8 : edge.kind === 'reports_to' ? 0x876dba : 0x285c72;
      const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color, transparent: true, opacity: debugLinks ? .28 : 0 }));
      line.userData.edge = edge; line.userData.baseColor = color; line.userData.curve = curve;
      edgeLines.push(line); graph.add(line);
    });
    const signalCount = Math.min(22, Math.max(8, signalCurves.length));
    const signalGeometry = new THREE.BufferGeometry();
    signalGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(signalCount * 3), 3));
    const signals = new THREE.Points(signalGeometry, new THREE.PointsMaterial({ color: 0x9ffff0, size: .035, transparent: true, opacity: .66, blending: THREE.AdditiveBlending, depthWrite: false }));
    graph.add(signals);
    runtimeRef.current = { nodeMeshes, edgeLines };

    let dragging = false; let dragDistance = 0; let px = 0; let py = 0; let targetZoom = viewStateRef.current.zoom;
    const pointer = new THREE.Vector2(); const raycaster = new THREE.Raycaster();
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let reduceMotion = prefersReducedMotion; let resumeMotionTimer;
    const pauseMotion = () => { reduceMotion = true; window.clearTimeout(resumeMotionTimer); resumeMotionTimer = window.setTimeout(() => { reduceMotion = prefersReducedMotion; }, 12000); };
    const rememberView = () => { viewStateRef.current = { rotationX: graph.rotation.x, rotationY: graph.rotation.y, zoom: targetZoom }; };
    const pointerDown = (event) => { dragging = true; pauseMotion(); dragDistance = 0; px = event.clientX; py = event.clientY; renderer.domElement.setPointerCapture(event.pointerId); };
    const pointerMove = (event) => { if (!dragging) return; const dx = event.clientX - px; const dy = event.clientY - py; dragDistance += Math.hypot(dx, dy); graph.rotation.y += dx * .006; graph.rotation.x = THREE.MathUtils.clamp(graph.rotation.x + dy * .004, -.7, .7); px = event.clientX; py = event.clientY; rememberView(); };
    const pointerUp = (event) => { dragging = false; rememberView(); storeViewState(viewStateRef.current); if (dragDistance > 6) return; const rect = renderer.domElement.getBoundingClientRect(); pointer.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1); raycaster.setFromCamera(pointer, camera); const hits = raycaster.intersectObjects([...nodeMeshes.values()], true); const nodeId = hits[0]?.object.userData.nodeId || hits[0]?.object.parent?.userData.nodeId; if (nodeId) onSelect(nodeId); };
    const wheel = (event) => { event.preventDefault(); pauseMotion(); targetZoom = THREE.MathUtils.clamp(targetZoom + event.deltaY * .006, 4.5, 11.5); rememberView(); storeViewState(viewStateRef.current); };
    renderer.domElement.addEventListener('pointerdown', pointerDown); renderer.domElement.addEventListener('pointermove', pointerMove); renderer.domElement.addEventListener('pointerup', pointerUp); renderer.domElement.addEventListener('wheel', wheel, { passive: false });
    const resize = () => { const width = host.clientWidth; const height = host.clientHeight; camera.aspect = width / Math.max(height, 1); camera.updateProjectionMatrix(); renderer.setSize(width, height, false); };
    const observer = new ResizeObserver(resize); observer.observe(host); resize();

    let animationId; const started = animationEpochRef.current;
    const activityColors = { idle: new THREE.Color(0x50f6c8), listening: new THREE.Color(0x4fe3ff), typing: new THREE.Color(0x4fe3ff), thinking: new THREE.Color(0x9a70ff), working: new THREE.Color(0xff9650), speaking: new THREE.Color(0x78f0dc) };
    const animate = (now) => { animationId = requestAnimationFrame(animate); const time = (now - started) / 1000; const state = activityRef.current; const energy = state === 'thinking' ? 2 : state === 'working' ? 1.8 : state === 'typing' ? 1.45 : state === 'speaking' ? 1.6 : 1; const activeColor = activityColors[state] || activityColors.idle; camera.position.z += (targetZoom - camera.position.z) * .1; if (!dragging && !reduceMotion) graph.rotation.y += .0008 * energy; core.rotation.x = time * .18 * energy; core.rotation.y = time * .28 * energy; core.scale.setScalar(1 + Math.sin(time * 2.4 * energy) * .07 * energy); core.material.color.lerp(activeColor, .08); coreAura.material.color.lerp(activeColor, .06); coreAura.material.opacity = .075 + (energy - 1) * .07 + Math.max(0, Math.sin(time * 2.8)) * .025; coreAura.scale.setScalar(1 + Math.sin(time * 1.6 * energy) * .1 * energy); signals.material.color.lerp(activeColor, .08); signals.material.size = .035 + (energy - 1) * .018; callosum.material.opacity = .14 + Math.max(0, Math.sin(time * 2.1 * energy)) * .1 * energy; neuralBridge.rotation.z = Math.sin(time * .3 * energy) * .018; nodeMeshes.forEach((item) => { const pulse = .5 + Math.sin(time * 2.2 * energy + item.userData.phase) * .5; const orbit = item.userData.orbit; if (orbit.radius && !reduceMotion) { const angle = orbit.angle + time * orbit.speed * energy; item.position.set(Math.cos(angle) * orbit.radius, orbit.y + Math.sin(time * .45 * energy + item.userData.phase) * .08, Math.sin(angle) * orbit.radius * .72); } item.userData.core.rotation.x += .006 * energy; item.userData.core.rotation.y += .01 * energy; item.userData.halo.scale.setScalar(1 + pulse * (item.userData.worker ? .28 : .16) * energy); }); edgeLines.forEach((line) => { if (line.material.opacity <= 0) return; const source = nodeMeshes.get(line.userData.edge.source); const target = nodeMeshes.get(line.userData.edge.target); if (!source || !target) return; const curve = line.userData.curve; curve.v0.copy(source.position); curve.v2.copy(target.position); curve.v1.copy(source.position).lerp(target.position, .5); curve.v1.z += .35; const attribute = line.geometry.attributes.position; for (let pointIndex = 0; pointIndex < attribute.count; pointIndex += 1) { const point = curve.getPoint(pointIndex / (attribute.count - 1)); attribute.setXYZ(pointIndex, point.x, point.y, point.z); } attribute.needsUpdate = true; }); const signalPositions = signalGeometry.attributes.position; for (let index = 0; index < signalCount; index += 1) { const curve = signalCurves[index % Math.max(signalCurves.length, 1)]; const point = curve ? curve.getPoint((time * (.09 + index % 4 * .015) * energy + index / signalCount) % 1) : new THREE.Vector3(); signalPositions.setXYZ(index, point.x, point.y, point.z); } signalPositions.needsUpdate = true; renderer.render(scene, camera); };
    animationId = requestAnimationFrame(animate);
    return () => { viewStateRef.current = { rotationX: graph.rotation.x, rotationY: graph.rotation.y, zoom: targetZoom }; storeViewState(viewStateRef.current); window.clearTimeout(resumeMotionTimer); runtimeRef.current = null; cancelAnimationFrame(animationId); observer.disconnect(); renderer.domElement.removeEventListener('pointerdown', pointerDown); renderer.domElement.removeEventListener('pointermove', pointerMove); renderer.domElement.removeEventListener('pointerup', pointerUp); renderer.domElement.removeEventListener('wheel', wheel); dispose(graph); renderer.dispose(); renderer.domElement.remove(); };
  }, [structureSignature, onSelect]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime) return;
    const latestStates = new Map(nodes.map((node) => [node.id, node.processState || 'idle']));
    runtime.nodeMeshes.forEach((item, id) => {
      item.userData.processState = latestStates.get(id) || 'idle';
      const active = id === selectedId;
      item.scale.setScalar(active ? 1.22 : 1);
      item.userData.halo.material.opacity = active ? .34 : .08;
      if (item.userData.label) item.userData.label.material.opacity = active ? 1 : .48;
    });
    runtime.edgeLines.forEach((line) => {
      const edge = line.userData.edge;
      const active = edge.source === selectedId || edge.target === selectedId;
      const sourceState = runtime.nodeMeshes.get(edge.source)?.userData.processState;
      const workflowEdge = ['assigned_to', 'handoff_to', 'uses_skill'].includes(edge.kind) && (['active', 'planned'].includes(sourceState) || edge.kind === 'handoff_to');
      line.material.color.setHex(active ? 0xdffcff : line.userData.baseColor);
      line.material.opacity = active ? .92 : workflowEdge ? (sourceState === 'active' ? .82 : .24) : debugLinks ? .28 : 0;
    });
  }, [selectedId, nodes, edges, debugLinks]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime) return;
    const latest = new Map(nodes.map((node) => [node.id, node]));
    runtime.nodeMeshes.forEach((item, id) => {
      const node = latest.get(id);
      if (!node) return;
      const attention = node.status === 'active' || node.status === 'waiting_approval' || node.status === 'pending' || node.status === 'blocked' || node.status === 'failed';
      const processState = node.processState || 'idle';
      item.userData.processState = processState;
      const active = processState === 'active'; const planned = processState === 'planned'; const completed = processState === 'completed';
      item.scale.setScalar(id === selectedId ? 1.22 : active ? 1.34 : planned ? 1.08 : completed ? .88 : 1);
      item.userData.core.material.emissiveIntensity = active ? 5.5 : planned ? 3 : attention ? 3.8 : completed ? 1.15 : 2.1;
      item.userData.core.material.opacity = completed ? .58 : 1; item.userData.core.material.transparent = completed;
      item.userData.halo.material.opacity = id === selectedId ? .34 : active ? .32 : planned ? .14 : attention ? .14 : completed ? .025 : .08;
      if (item.userData.processRing) { item.userData.processRing.material.color.setHex(active ? 0xffffff : planned ? 0x9a70ff : item.userData.baseColor); item.userData.processRing.material.opacity = active ? 1 : planned ? .72 : completed ? .18 : .4; item.userData.processRing.scale.setScalar(active ? 1.45 : planned ? 1.15 : 1); }
    });
  }, [nodes, selectedId, debugLinks]);

  return <div ref={hostRef} className="organization-3d-stage" aria-label="Interactive 3D graph of the live AI organization" />;
}

const MemoThreeOrganizationGraph = memo(ThreeOrganizationGraph);

function LiveOrganizationGraph({ topology, onOpenTask, activity = 'idle', activeAgentId = '', workflowActive = false, runtimeSkills = [] }) {
  const [selectedId, setSelectedId] = useState('');
  const [visibleKinds, setVisibleKinds] = useState(new Set(KIND_ORDER));
  const [debugLinks, setDebugLinks] = useState(false);
  const augmented = useMemo(() => {
    const taskOwners = new Map(topology.edges.filter((edge) => edge.kind === 'assigned_to').map((edge) => [edge.target, edge.source]));
    const handoffs = topology.edges.filter((edge) => edge.kind === 'depends_on').map((edge) => ({ source: taskOwners.get(edge.source), target: taskOwners.get(edge.target), kind: 'handoff_to' })).filter((edge) => edge.source && edge.target && edge.source !== edge.target).filter((edge, index, values) => values.findIndex((item) => item.source === edge.source && item.target === edge.target) === index);
    const skills = runtimeSkills.map((name, index) => ({ id: `runtime-skill-${name}`, kind: 'skill', label: name, status: index === runtimeSkills.length - 1 && workflowActive ? 'active' : 'completed', detail: 'Runtime skill observed in execution logs' }));
    const skillEdges = skills.map((skill) => ({ source: activeAgentId || 'developer', target: skill.id, kind: 'uses_skill' }));
    return { nodes: [...topology.nodes, ...skills], edges: [...topology.edges, ...handoffs, ...skillEdges] };
  }, [topology, runtimeSkills.join('|'), activeAgentId, workflowActive]);
  const topologySignature = JSON.stringify({ nodes: augmented.nodes, edges: augmented.edges });
  const positioned = useMemo(() => layout(augmented.nodes.filter((node) => visibleKinds.has(node.kind)), augmented.edges), [topologySignature, visibleKinds]);
  const ids = new Set(positioned.map((node) => node.id));
  const edges = useMemo(() => augmented.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)), [topologySignature, positioned]);
  const sceneNodes = useMemo(() => positioned.filter((node) => node.kind !== 'artifact').map((node) => {
    if (node.kind !== 'agent') return node;
    const processState = node.id === activeAgentId ? 'active' : workflowActive && node.current_task ? 'planned' : node.status === 'completed' ? 'completed' : ['blocked', 'failed'].includes(node.status) ? 'blocked' : node.current_task ? 'planned' : 'idle';
    return { ...node, processState };
  }), [positioned, activeAgentId, workflowActive]);
  const sceneIds = new Set(sceneNodes.map((node) => node.id));
  const sceneEdges = useMemo(() => edges.filter((edge) => sceneIds.has(edge.source) && sceneIds.has(edge.target)), [edges, sceneNodes]);
  const selected = augmented.nodes.find((node) => node.id === selectedId);
  const toggleKind = (kind) => setVisibleKinds((current) => { const next = new Set(current); if (next.has(kind) && next.size > 1) next.delete(kind); else next.add(kind); return next; });

  return <div className="live-graph-shell">
    <div className="graph-toolbar" aria-label="Graph filters">{KIND_ORDER.map((kind) => <button key={kind} className={visibleKinds.has(kind) ? `kind-${kind} active` : ''} aria-pressed={visibleKinds.has(kind)} onClick={() => toggleKind(kind)}>{KIND_LABELS[kind]}</button>)}<button className={debugLinks ? 'active' : ''} aria-pressed={debugLinks} onClick={() => setDebugLinks((value) => !value)}>Debug links</button><span className={`live-indicator activity-${activity}`}><i /> {activity === 'typing' ? 'Listening to your prompt' : activity === 'thinking' ? 'Collective mind thinking' : activity === 'working' ? 'Agents executing' : activity === 'speaking' ? 'Responding' : 'Collective mind online'}</span></div>
    <div className="live-graph-workspace"><MemoThreeOrganizationGraph nodes={sceneNodes} edges={sceneEdges} selectedId={selectedId} onSelect={setSelectedId} debugLinks={debugLinks} activity={activity}/><div className="agent-process-legend" aria-label="Agent workflow states"><span className="active">Active</span><span className="planned">In workflow</span><span className="completed">Completed</span></div><div className="graph-gesture-hint" aria-hidden="true">Drag to orbit · Scroll to zoom · Select to inspect</div><details className="entity-index"><summary>Entities <span>{positioned.length}</span></summary><div className="accessible-entities"><strong>Keyboard entity list</strong>{positioned.map((node) => <button key={node.id} className={node.id === selectedId ? 'selected' : ''} onClick={() => setSelectedId(node.id)}>{node.label}</button>)}</div></details>{selected && <aside className="graph-inspector" aria-live="polite"><button className="graph-inspector-close" onClick={() => setSelectedId('')} aria-label="Close inspector">×</button><span className={`entity-kind kind-${selected.kind}`}>{KIND_LABELS[selected.kind]}</span><h3>{selected.label}</h3><span className={`ops-status status-${selected.status}`}>{selected.status.replaceAll('_', ' ')}</span>{selected.kind === 'agent' && <span className={`agent-process-state state-${sceneNodes.find((node) => node.id === selected.id)?.processState || 'idle'}`}>{sceneNodes.find((node) => node.id === selected.id)?.processState || 'idle'}</span>}<p>{selected.detail || 'No operational detail.'}</p><dl><dt>ID</dt><dd><code>{selected.id}</code></dd>{selected.current_task && <><dt>Current task</dt><dd>{selected.current_task}</dd></>}{selected.risk && <><dt>Risk</dt><dd>{selected.risk}</dd></>}</dl>{selected.kind === 'task' && <button onClick={() => onOpenTask(selected.id)}>Open task details</button>}</aside>}</div>
    <div className="graph-relationship-legend"><span>Neural core: company mind</span><span>Green: agent handoff</span><span>Pink: active skill</span><span>Orange: temporary workers</span><span>Amber: approval junction</span><time>Snapshot {new Date(topology.generated_at).toLocaleTimeString()}</time></div>
  </div>;
}

const sameTopology = (previous, next) => previous === next || JSON.stringify([previous.nodes, previous.edges]) === JSON.stringify([next.nodes, next.edges]);
const sameGraphProps = (previous, next) => sameTopology(previous.topology, next.topology) && previous.activity === next.activity && previous.activeAgentId === next.activeAgentId && previous.workflowActive === next.workflowActive && previous.onOpenTask === next.onOpenTask && previous.runtimeSkills.join('|') === next.runtimeSkills.join('|');
export default memo(LiveOrganizationGraph, sameGraphProps);
