import { useEffect, useRef } from 'react';
import * as THREE from 'three';

const PALETTES = {
  idle: [0x50f6c8, 0x4fe3ff], listening: [0x4fe3ff, 0x50f6c8],
  thinking: [0x9a70ff, 0xe85cff], speaking: [0x78f0dc, 0x4fe3ff],
  working: [0xff9650, 0xffcf6b]
};

function brainPoint(index, count) {
  const side = index % 2 ? 1 : -1;
  const i = Math.floor(index / 2);
  const n = Math.ceil(count / 2);
  const phi = Math.acos(1 - 2 * (i + 0.5) / n);
  const theta = Math.PI * (1 + Math.sqrt(5)) * i;
  return new THREE.Vector3(
    side * (0.34 + Math.abs(Math.sin(phi) * Math.cos(theta)) * 1.25),
    Math.cos(phi) * 1.38,
    Math.sin(phi) * Math.sin(theta) * 1.12
  );
}

function makeLabel(stage, text, kind = 'skill') {
  const el = document.createElement('div');
  el.className = `graph-label ${kind}`;
  el.textContent = text;
  stage.appendChild(el);
  return el;
}

export default function ThreeBrain() {
  const hostRef = useRef(null);

  useEffect(() => {
    const host = hostRef.current;
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x02030a, 0.075);
    const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
    camera.position.set(0, 0.15, 7.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x02030a, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.prepend(renderer.domElement);

    const graph = new THREE.Group();
    graph.rotation.x = -0.12;
    scene.add(graph);

    const ambient = new THREE.AmbientLight(0x74bfff, 0.55);
    const key = new THREE.PointLight(0x50f6c8, 12, 12);
    key.position.set(0, 0, 2.5);
    scene.add(ambient, key);

    const core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.48, 3),
      new THREE.MeshBasicMaterial({ color: 0x50f6c8, wireframe: true, transparent: true, opacity: 0.42 })
    );
    graph.add(core);
    const aura = new THREE.Mesh(
      new THREE.SphereGeometry(0.7, 32, 20),
      new THREE.MeshBasicMaterial({ color: 0x4fe3ff, transparent: true, opacity: 0.055, side: THREE.BackSide })
    );
    graph.add(aura);

    const particleCount = 950;
    const particles = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i++) {
      const p = brainPoint(i, particleCount);
      const jitter = 0.82 + Math.random() * 0.42;
      particles.set([p.x * jitter, p.y * jitter, p.z * jitter], i * 3);
    }
    const particleGeo = new THREE.BufferGeometry();
    particleGeo.setAttribute('position', new THREE.BufferAttribute(particles, 3));
    const particleMat = new THREE.PointsMaterial({ color: 0x4fe3ff, size: 0.026, transparent: true, opacity: 0.38, blending: THREE.AdditiveBlending });
    const cloud = new THREE.Points(particleGeo, particleMat);
    graph.add(cloud);

    let state = 'idle';
    let voiceImpulse = 0;
    let skillObjects = [];
    let taskObjects = [];
    let edgeLines = null;
    let dragging = false;
    let px = 0;
    let py = 0;

    const clearSkills = () => {
      skillObjects.forEach(({ mesh, label }) => { graph.remove(mesh); label.remove(); mesh.geometry.dispose(); mesh.material.dispose(); });
      skillObjects = [];
      if (edgeLines) { graph.remove(edgeLines); edgeLines.geometry.dispose(); edgeLines.material.dispose(); edgeLines = null; }
    };

    const setSkills = (names) => {
      clearSkills();
      const list = names?.length ? names : ['get_video_info', 'detect_scenes'];
      const edgePositions = [];
      list.forEach((name, index) => {
        const position = brainPoint(index, list.length);
        const material = new THREE.MeshStandardMaterial({
          color: index % 3 === 0 ? 0x50f6c8 : index % 3 === 1 ? 0x4fe3ff : 0x8a6cff,
          emissive: index % 2 ? 0x164b68 : 0x165b4a,
          emissiveIntensity: 1.5,
          roughness: 0.3
        });
        const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.075, 16, 12), material);
        mesh.position.copy(position);
        graph.add(mesh);
        const label = makeLabel(host, name);
        skillObjects.push({ mesh, label, position, phase: Math.random() * Math.PI * 2 });
        edgePositions.push(0, 0, 0, position.x, position.y, position.z);
        if (index > 1) {
          const previous = brainPoint(index - 2, list.length);
          edgePositions.push(previous.x, previous.y, previous.z, position.x, position.y, position.z);
        }
      });
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(edgePositions, 3));
      edgeLines = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: 0x4fe3ff, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending }));
      graph.add(edgeLines);
      const badge = document.getElementById('badge');
      if (badge) badge.textContent = `${list.length} kỹ năng • neural graph`;
    };

    const removeTask = (task) => {
      graph.remove(task.mesh, task.ring, task.links);
      task.label.remove();
      task.mesh.geometry.dispose(); task.mesh.material.dispose();
      task.ring.geometry.dispose(); task.ring.material.dispose();
      task.links.geometry.dispose(); task.links.material.dispose();
      taskObjects = taskObjects.filter((item) => item !== task);
    };

    const upsertTask = (detail) => {
      let task = taskObjects.find((item) => item.name === detail.task);
      if (!task) {
        const index = taskObjects.length;
        const position = new THREE.Vector3(index % 2 ? 2.35 : -2.35, 0.65 - index * 0.45, 0.15);
        const mesh = new THREE.Mesh(new THREE.OctahedronGeometry(0.18, 1), new THREE.MeshStandardMaterial({ color: 0xffcf6b, emissive: 0xff6828, emissiveIntensity: 1.8 }));
        mesh.position.copy(position);
        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.3, 0.018, 8, 48), new THREE.MeshBasicMaterial({ color: 0xff9650, transparent: true, opacity: 0.75 }));
        ring.position.copy(position);
        const vertices = [position.x, position.y, position.z, 0, 0, 0];
        skillObjects.slice(0, 3).forEach(({ position: p }) => vertices.push(position.x, position.y, position.z, p.x, p.y, p.z));
        const linksGeo = new THREE.BufferGeometry();
        linksGeo.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
        const links = new THREE.LineSegments(linksGeo, new THREE.LineBasicMaterial({ color: 0xff9650, transparent: true, opacity: 0.42 }));
        const label = makeLabel(host, detail.task || 'Task', 'task');
        graph.add(mesh, ring, links);
        task = { name: detail.task, mesh, ring, links, label, position, status: detail.status };
        taskObjects.push(task);
      }
      task.status = detail.status;
      const colors = detail.status === 'error' ? [0xff5b6e, 0xff203c] : detail.status === 'done' ? [0x50f6c8, 0x148f72] : [0xffcf6b, 0xff6828];
      task.mesh.material.color.setHex(colors[0]);
      task.mesh.material.emissive.setHex(colors[1]);
      task.label.dataset.status = detail.status;
      task.label.textContent = `${detail.status === 'running' ? '● ' : detail.status === 'done' ? '✓ ' : detail.status === 'error' ? '× ' : '○ '}${detail.task}`;
      if (detail.status === 'done' || detail.status === 'error') window.setTimeout(() => removeTask(task), 5000);
    };

    const onVisual = ({ detail }) => {
      if (detail.type === 'state') {
        state = detail.state;
        if (state === 'speaking') voiceImpulse = Math.max(voiceImpulse, 0.55);
      }
      if (detail.type === 'voice-pulse') voiceImpulse = Math.max(voiceImpulse, detail.strength || 1);
      if (detail.type === 'skills') setSkills(detail.skills);
      if (detail.type === 'task') upsertTask(detail);
      if (detail.type === 'flash') {
        key.color.setRGB(detail.color[0] / 255, detail.color[1] / 255, detail.color[2] / 255);
        key.intensity = 32;
      }
    };
    window.addEventListener('javis:visual', onVisual);
    setSkills(['get_video_info', 'detect_scenes']);

    const resize = () => {
      const width = host.clientWidth;
      const height = host.clientHeight;
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);
    resize();

    const pointerDown = (event) => { dragging = true; px = event.clientX; py = event.clientY; renderer.domElement.setPointerCapture(event.pointerId); };
    const pointerMove = (event) => {
      if (!dragging) return;
      graph.rotation.y += (event.clientX - px) * 0.006;
      graph.rotation.x = THREE.MathUtils.clamp(graph.rotation.x + (event.clientY - py) * 0.004, -0.8, 0.8);
      px = event.clientX; py = event.clientY;
    };
    const pointerUp = () => { dragging = false; };
    renderer.domElement.addEventListener('pointerdown', pointerDown);
    renderer.domElement.addEventListener('pointermove', pointerMove);
    renderer.domElement.addEventListener('pointerup', pointerUp);

    const startedAt = performance.now();
    let animationId;
    const animate = (now) => {
      animationId = requestAnimationFrame(animate);
      const time = (now - startedAt) / 1000;
      const palette = PALETTES[state] || PALETTES.idle;
      const energy = state === 'working' ? 1.8 : state === 'thinking' ? 1.45 : state === 'listening' ? 1.2 : 0.8;
      const voiceWave = state === 'speaking' ? Math.max(0, Math.sin(time * 11.5)) * 0.34 : 0;
      const voicePulse = Math.min(1.25, voiceWave + voiceImpulse);
      voiceImpulse *= 0.86;
      if (!dragging) graph.rotation.y += 0.0015 * energy;
      core.rotation.x = time * 0.22 * energy;
      core.rotation.y = time * 0.32 * energy;
      core.scale.setScalar(1 + Math.sin(time * 2.4) * 0.06 * energy + voicePulse * 0.32);
      aura.scale.setScalar(1 + Math.sin(time * 1.5) * 0.08 + voicePulse * 0.48);
      aura.material.opacity = 0.055 + voicePulse * 0.16;
      core.material.color.lerp(new THREE.Color(palette[0]), 0.06);
      aura.material.color.lerp(new THREE.Color(palette[1]), 0.06);
      particleMat.color.lerp(new THREE.Color(palette[1]), 0.04);
      key.color.lerp(new THREE.Color(palette[0]), 0.035);
      key.intensity += (12 * energy - key.intensity) * 0.04;
      skillObjects.forEach((item, index) => {
        item.mesh.scale.setScalar(1 + Math.sin(time * 2.2 + item.phase) * 0.18 + (state === 'working' && index < 3 ? 0.35 : 0));
      });
      taskObjects.forEach((task, index) => { task.mesh.rotation.y += 0.025; task.ring.rotation.z = time * (0.8 + index * 0.1); task.ring.scale.setScalar(1 + Math.sin(time * 3) * 0.09); });

      graph.updateMatrixWorld();
      const width = host.clientWidth, height = host.clientHeight;
      [...skillObjects, ...taskObjects].forEach((item) => {
        const projected = item.mesh.position.clone().applyMatrix4(graph.matrixWorld).project(camera);
        item.label.style.transform = `translate(-50%,-50%) translate(${(projected.x * 0.5 + 0.5) * width}px,${(-projected.y * 0.5 + 0.5) * height}px)`;
        item.label.style.opacity = projected.z < 1 && projected.z > -1 ? String(0.45 + (1 - projected.z) * 0.25) : '0';
      });
      renderer.render(scene, camera);
    };
    animationId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('javis:visual', onVisual);
      resizeObserver.disconnect();
      renderer.dispose();
      renderer.domElement.remove();
      host.querySelectorAll('.graph-label').forEach((label) => label.remove());
    };
  }, []);

  return <div ref={hostRef} id="scene" className="brain-stage" aria-label="Đồ thị 3D kiến trúc não AI, kỹ năng và tác vụ" />;
}
