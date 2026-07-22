import { useEffect, useRef } from "react";
import * as THREE from "three";
import { AGENT_VISUAL_EVENT } from "./agentConfig.js";

const PALETTES = {
  idle: [0x50f6c8, 0x4fe3ff],
  listening: [0x4fe3ff, 0x50f6c8],
  thinking: [0x9a70ff, 0xe85cff],
  speaking: [0x78f0dc, 0x4fe3ff],
  working: [0xff9650, 0xffcf6b],
};

function brainPoint(index, count) {
  const side = index % 2 ? 1 : -1;
  const i = Math.floor(index / 2);
  const n = Math.ceil(count / 2);
  const phi = Math.acos(1 - (2 * (i + 0.5)) / n);
  const theta = Math.PI * (1 + Math.sqrt(5)) * i;
  return new THREE.Vector3(
    side * (0.34 + Math.abs(Math.sin(phi) * Math.cos(theta)) * 1.25),
    Math.cos(phi) * 1.38,
    Math.sin(phi) * Math.sin(theta) * 1.12,
  );
}

function makeOrbit(position, index = 0, speed = 0.12) {
  const normal = position.clone().normalize();
  const tangent = new THREE.Vector3()
    .crossVectors(
      normal,
      Math.abs(normal.y) < 0.88
        ? new THREE.Vector3(0, 1, 0)
        : new THREE.Vector3(1, 0, 0),
    )
    .normalize();
  const bitangent = new THREE.Vector3()
    .crossVectors(normal, tangent)
    .normalize();
  return {
    anchor: position.clone(),
    tangent,
    bitangent,
    speed,
    amplitude: 0.035 + (index % 4) * 0.012,
    wobble: Math.random() * Math.PI * 2,
  };
}

function moveOnOrbit(item, time, activity = 0) {
  const orbit = item.orbit;
  if (!orbit) return;
  const activeBoost = 1 + activity * 1.8;
  const angle = time * orbit.speed * 8 * activeBoost + orbit.wobble;
  const amplitude = orbit.amplitude * (1 + activity * 1.7);
  item.position
    .copy(orbit.anchor)
    .addScaledVector(orbit.tangent, Math.cos(angle) * amplitude)
    .addScaledVector(orbit.bitangent, Math.sin(angle * 1.37) * amplitude)
    .multiplyScalar(1 - Math.min(activity, 1) * 0.045);
  item.mesh.position.copy(item.position);
}

function makeTaskOrbit(index) {
  return {
    radius: 1.72 + (index % 2) * 0.18,
    height: 0.48 - index * 0.16,
    angle: Math.PI + index * 1.9,
    speed: 0.16 + (index % 3) * 0.018,
  };
}

function moveTaskOnOrbit(task, time) {
  const orbit = task.orbit;
  const angle = orbit.angle + time * orbit.speed;
  task.position.set(
    Math.cos(angle) * orbit.radius,
    orbit.height,
    Math.sin(angle) * orbit.radius * 0.58,
  );
  task.mesh.position.copy(task.position);
}

function makeThoughtOrbit(index) {
  return {
    radius: 0.78 + index * 0.13,
    height: 0.2 + index * 0.1,
    angle: 0.65 + index * 1.8,
    speed: 0.2 + (index % 3) * 0.018,
  };
}

function moveThoughtOnOrbit(thought, time) {
  const orbit = thought.orbit;
  const angle = orbit.angle + time * orbit.speed;
  thought.position.set(
    Math.cos(angle) * orbit.radius,
    orbit.height,
    Math.sin(angle) * orbit.radius * 0.64,
  );
  thought.mesh.position.copy(thought.position);
}

function createLocalOrbitLine(orbit, color, opacity = 0.1) {
  const points = Array.from({ length: 64 }, (_, index) => {
    const angle = (index / 64) * Math.PI * 2;
    return orbit.anchor
      .clone()
      .addScaledVector(orbit.tangent, Math.cos(angle) * orbit.amplitude)
      .addScaledVector(orbit.bitangent, Math.sin(angle) * orbit.amplitude);
  });
  return new THREE.LineLoop(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
}

function createPlanarOrbitLine(orbit, color, opacity = 0.16) {
  const points = Array.from({ length: 96 }, (_, index) => {
    const angle = (index / 96) * Math.PI * 2;
    return new THREE.Vector3(
      Math.cos(angle) * orbit.radius,
      orbit.height,
      Math.sin(angle) * orbit.radius * 0.58,
    );
  });
  return new THREE.LineLoop(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
}

function makeLabel(stage, text, kind = "skill") {
  const el = document.createElement("div");
  el.className = `graph-label ${kind}`;
  el.textContent = text;
  stage.appendChild(el);
  return el;
}

function compactNodeLabel(text, limit = 28) {
  const value = String(text || "Node").replace(/\s+/g, " ").trim();
  return value.length > limit ? `${value.slice(0, limit - 1)}…` : value;
}

function createSatelliteNode(color, index) {
  // Skill nodes are deliberately rendered as luminous points rather than solids.
  const geometry = new THREE.SphereGeometry(0.052, 18, 12);
  const material = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 1,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const node = new THREE.Mesh(geometry, material);
  const haloMaterials = [];
  [
    [0.12, 0.16],
    [0.22, 0.045],
  ].forEach(([radius, opacity]) => {
    const haloMaterial = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.BackSide,
    });
    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 18, 12),
      haloMaterial,
    );
    node.add(halo);
    haloMaterials.push(haloMaterial);
  });
  node.userData.satellite = { haloMaterials };
  return node;
}

function disposeObject(object) {
  object.traverse((child) => {
    child.geometry?.dispose();
    if (Array.isArray(child.material))
      child.material.forEach((material) => material.dispose());
    else child.material?.dispose();
  });
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
      new THREE.IcosahedronGeometry(0.34, 3),
      new THREE.MeshBasicMaterial({
        color: 0x50f6c8,
        wireframe: true,
        transparent: true,
        opacity: 0.42,
      }),
    );
    graph.add(core);
    const aura = new THREE.Mesh(
      new THREE.SphereGeometry(0.52, 32, 20),
      new THREE.MeshBasicMaterial({
        color: 0x4fe3ff,
        transparent: true,
        opacity: 0.055,
        side: THREE.BackSide,
      }),
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
    particleGeo.setAttribute(
      "position",
      new THREE.BufferAttribute(particles, 3),
    );
    const particleMat = new THREE.PointsMaterial({
      color: 0x4fe3ff,
      size: 0.026,
      transparent: true,
      opacity: 0.38,
      blending: THREE.AdditiveBlending,
    });
    const cloud = new THREE.Points(particleGeo, particleMat);
    graph.add(cloud);

    // Curved local dendrites form the anatomical substrate of both hemispheres.
    const fiberPositions = [];
    const fiberPaths = [];
    const fiberCount = 190;
    for (let i = 0; i < fiberCount; i++) {
      const from = brainPoint(i, fiberCount);
      const to = brainPoint((i + 7 + (i % 11)) % fiberCount, fiberCount);
      if (Math.sign(from.x) !== Math.sign(to.x)) to.x *= -1;
      const control = from.clone().lerp(to, 0.5).multiplyScalar(0.72);
      control.z += Math.sin(i * 2.17) * 0.18;
      const curve = new THREE.QuadraticBezierCurve3(from, control, to);
      const points = curve.getPoints(5);
      fiberPaths.push(curve);
      for (let p = 1; p < points.length; p++)
        fiberPositions.push(
          points[p - 1].x,
          points[p - 1].y,
          points[p - 1].z,
          points[p].x,
          points[p].y,
          points[p].z,
        );
    }
    const fiberGeo = new THREE.BufferGeometry();
    fiberGeo.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(fiberPositions, 3),
    );
    const fiberMat = new THREE.LineBasicMaterial({
      color: 0x247c93,
      transparent: true,
      opacity: 0.105,
      blending: THREE.AdditiveBlending,
    });
    const neuralFibers = new THREE.LineSegments(fiberGeo, fiberMat);
    graph.add(neuralFibers);

    const signalCount = 46;
    const signalPositions = new Float32Array(signalCount * 3);
    const signalGeo = new THREE.BufferGeometry();
    signalGeo.setAttribute(
      "position",
      new THREE.BufferAttribute(signalPositions, 3),
    );
    const signalMat = new THREE.PointsMaterial({
      color: 0x7fffe2,
      size: 0.045,
      transparent: true,
      opacity: 0.78,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const neuralSignals = new THREE.Points(signalGeo, signalMat);
    graph.add(neuralSignals);

    const hemisphereBridge = new THREE.Mesh(
      new THREE.TorusGeometry(0.57, 0.012, 6, 72, Math.PI * 1.72),
      new THREE.MeshBasicMaterial({
        color: 0x50f6c8,
        transparent: true,
        opacity: 0.16,
        blending: THREE.AdditiveBlending,
      }),
    );
    hemisphereBridge.rotation.set(0, Math.PI / 2, -0.15);
    graph.add(hemisphereBridge);

    const taskSignal = new THREE.Mesh(
      new THREE.SphereGeometry(0.045, 10, 8),
      new THREE.MeshBasicMaterial({
        color: 0xffcf6b,
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
      }),
    );
    graph.add(taskSignal);

    let state = "idle";
    let voiceImpulse = 0;
    let skillObjects = [];
    let taskObjects = [];
    let thoughtObjects = [];
    let resultObjects = [];
    let activityLinks = null;
    let usedSkillNames = [];
    let currentSkillName = null;
    let dragging = false;
    let px = 0;
    let py = 0;
    let dragDistance = 0;
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const minCameraZ = 4.15;
    const maxCameraZ = 10.5;
    let targetCameraZ = camera.position.z;

    const detailPanel = document.createElement("aside");
    detailPanel.className = "node-detail";
    detailPanel.hidden = true;
    const detailTitle = document.createElement("strong");
    const detailText = document.createElement("p");
    const closeDetail = document.createElement("button");
    closeDetail.type = "button";
    closeDetail.className = "node-detail-close";
    closeDetail.textContent = "×";
    closeDetail.setAttribute("aria-label", "Đóng chi tiết node");
    closeDetail.addEventListener("click", () => { detailPanel.hidden = true; });
    detailPanel.append(closeDetail, detailTitle, detailText);
    host.appendChild(detailPanel);

    const showDetail = (item) => {
      detailTitle.textContent = item.kind === "task" ? "Yêu cầu đang xử lý" : "Kỹ năng";
      detailText.textContent = item.detail || item.name || "Không có thông tin chi tiết.";
      detailPanel.hidden = false;
    };

    const clearSkills = () => {
      skillObjects.forEach(({ mesh, orbitLine, label }) => {
        graph.remove(mesh, orbitLine);
        label.remove();
        disposeObject(mesh);
        disposeObject(orbitLine);
      });
      skillObjects = [];
      if (activityLinks) {
        graph.remove(activityLinks);
        activityLinks.geometry.dispose();
        activityLinks.material.dispose();
        activityLinks = null;
      }
    };

    const setSkills = (names) => {
      clearSkills();
      const list = names?.length ? names : ["get_video_info", "detect_scenes"];
      list.forEach((name, index) => {
        const position = brainPoint(index, list.length);
        const color =
          index % 3 === 0 ? 0x50f6c8 : index % 3 === 1 ? 0x4fe3ff : 0x8a6cff;
        const mesh = createSatelliteNode(color, index);
        mesh.position.copy(position);
        const orbit = makeOrbit(position, index, 0.09 + (index % 5) * 0.012);
        const orbitLine = createLocalOrbitLine(orbit, color);
        graph.add(mesh, orbitLine);
        const label = makeLabel(host, compactNodeLabel(name, 22));
        skillObjects.push({
          name,
          detail: name,
          kind: "skill",
          mesh,
          orbitLine,
          label,
          position,
          orbit,
          phase: Math.random() * Math.PI * 2,
          activity: 0,
          activityState: "idle",
        });
      });
      const badge = document.getElementById("badge");
      if (badge) badge.textContent = `${list.length} kỹ năng • neural graph`;
    };

    const rebuildActivityLinks = () => {
      if (activityLinks) {
        graph.remove(activityLinks);
        activityLinks.geometry.dispose();
        activityLinks.material.dispose();
        activityLinks = null;
      }
      const points = [];
      for (let index = 1; index < usedSkillNames.length; index++) {
        const from = skillObjects.find(
          (item) => item.name === usedSkillNames[index - 1],
        );
        const to = skillObjects.find(
          (item) => item.name === usedSkillNames[index],
        );
        if (from && to)
          points.push(
            from.position.x,
            from.position.y,
            from.position.z,
            to.position.x,
            to.position.y,
            to.position.z,
          );
      }
      if (!points.length) return;
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(points, 3),
      );
      activityLinks = new THREE.LineSegments(
        geometry,
        new THREE.LineBasicMaterial({
          color: 0xffcf6b,
          transparent: true,
          opacity: 0.85,
          blending: THREE.AdditiveBlending,
        }),
      );
      graph.add(activityLinks);
    };

    const updateActivityLinkPositions = () => {
      if (!activityLinks) return;
      const attribute = activityLinks.geometry.attributes.position;
      let cursor = 0;
      for (let index = 1; index < usedSkillNames.length; index++) {
        const from = skillObjects.find(
          (item) => item.name === usedSkillNames[index - 1],
        );
        const to = skillObjects.find(
          (item) => item.name === usedSkillNames[index],
        );
        if (!from || !to) continue;
        attribute.setXYZ(
          cursor++,
          from.position.x,
          from.position.y,
          from.position.z,
        );
        attribute.setXYZ(cursor++, to.position.x, to.position.y, to.position.z);
      }
      attribute.needsUpdate = true;
    };

    const rebuildTaskLinks = (taskName) => {
      const task = taskObjects.find((item) => item.name === taskName);
      if (!task) return;
      const vertices = [
        task.position.x,
        task.position.y,
        task.position.z,
        0,
        0,
        0,
      ];
      usedSkillNames.forEach((name) => {
        const skill = skillObjects.find((item) => item.name === name);
        if (skill)
          vertices.push(
            task.position.x,
            task.position.y,
            task.position.z,
            skill.position.x,
            skill.position.y,
            skill.position.z,
          );
      });
      const requiredCount = vertices.length / 3;
      const current = task.links.geometry.attributes.position;
      if (!current || current.count !== requiredCount) {
        task.links.geometry.dispose();
        task.links.geometry = new THREE.BufferGeometry();
        task.links.geometry.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(vertices, 3),
        );
      } else {
        current.array.set(vertices);
        current.needsUpdate = true;
      }
    };

    const activateSkill = (detail) => {
      let skill = skillObjects.find((item) => item.name === detail.skill);
      if (!skill) {
        const names = [...skillObjects.map((item) => item.name), detail.skill];
        setSkills(names);
        skill = skillObjects.find((item) => item.name === detail.skill);
      }
      if (!skill) return;
      currentSkillName =
        detail.phase === "active"
          ? detail.skill
          : currentSkillName === detail.skill
            ? null
            : currentSkillName;
      usedSkillNames = detail.usedSkills?.length
        ? detail.usedSkills
        : [...new Set([...usedSkillNames, detail.skill])];
      skill.activity = detail.phase === "active" ? 1 : 0.55;
      skill.activityState = detail.phase;
      skill.label.classList.add("active");
      skill.label.dataset.phase = detail.phase;
      skill.label.textContent = `${detail.phase === "active" ? "●" : detail.phase === "complete" ? "✓" : detail.phase === "error" ? "×" : "○"} ${detail.skill}`;
      skill.label.textContent = `${detail.phase === "active" ? "●" : detail.phase === "complete" ? "✓" : detail.phase === "error" ? "×" : "○"} ${compactNodeLabel(detail.skill, 22)}`;
      rebuildActivityLinks();
      rebuildTaskLinks(detail.task);
    };

    const addThought = (detail) => {
      const labelText = String(detail.label || "Đang xử lý").trim();
      if (!labelText) return;
      const index = thoughtObjects.length;
      const orbit = makeThoughtOrbit(index);
      const position = new THREE.Vector3(
        Math.cos(orbit.angle) * orbit.radius,
        orbit.height,
        Math.sin(orbit.angle) * orbit.radius * 0.64,
      );
      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(0.06, 20, 14),
        new THREE.MeshStandardMaterial({
          color: 0xe85cff,
          emissive: 0x9a36d8,
          emissiveIntensity: 3.6,
          roughness: 0.16,
        }),
      );
      mesh.position.copy(position);
      const glow = new THREE.Mesh(
        new THREE.SphereGeometry(0.135, 18, 12),
        new THREE.MeshBasicMaterial({
          color: 0xe85cff,
          transparent: true,
          opacity: 0.12,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
          side: THREE.BackSide,
        }),
      );
      mesh.add(glow);
      const orbitLine = createPlanarOrbitLine(orbit, 0xe85cff, 0.2);
      const label = makeLabel(
        host,
        labelText.length > 52 ? `${labelText.slice(0, 52)}…` : labelText,
        "thought",
      );
      graph.add(mesh, orbitLine);
      thoughtObjects.push({
        mesh,
        glow,
        orbitLine,
        label,
        position,
        orbit,
        born: performance.now(),
        phase: Math.random() * 6,
      });
      while (thoughtObjects.length > 5) {
        const old = thoughtObjects.shift();
        graph.remove(old.mesh, old.orbitLine);
        old.label.remove();
        disposeObject(old.mesh);
        disposeObject(old.orbitLine);
      }
      rebuildTaskLinks(detail.task);
    };

    const removeResult = (result) => {
      graph.remove(result.mesh, result.ring, result.orbitLine, result.link);
      result.label.remove();
      result.mesh.geometry.dispose();
      result.mesh.material.dispose();
      result.ring.geometry.dispose();
      result.ring.material.dispose();
      result.orbitLine.geometry.dispose();
      result.orbitLine.material.dispose();
      result.link.geometry.dispose();
      result.link.material.dispose();
      resultObjects = resultObjects.filter((item) => item !== result);
    };

    const clearThoughts = () => {
      thoughtObjects.forEach((item) => {
        graph.remove(item.mesh, item.orbitLine);
        item.label.remove();
        disposeObject(item.mesh);
        disposeObject(item.orbitLine);
      });
      thoughtObjects = [];
    };

    const addResult = (detail) => {
      clearThoughts();
      const matchingTasks = taskObjects.filter(
        (item) => !detail.task || item.name === detail.task,
      );
      matchingTasks.forEach(removeTask);
      const index = resultObjects.length;
      const position = new THREE.Vector3(
        1.15 + index * 0.32,
        -0.72 - index * 0.32,
        0.55,
      );
      const error = detail.status === "error";
      const color = error ? 0xff5b6e : 0x50f6c8;
      const mesh = new THREE.Mesh(
        new THREE.DodecahedronGeometry(0.16, 1),
        new THREE.MeshStandardMaterial({
          color,
          emissive: color,
          emissiveIntensity: 2.8,
          roughness: 0.22,
        }),
      );
      mesh.position.copy(position);
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(0.25, 0.014, 8, 48),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7 }),
      );
      ring.position.copy(position);
      const linkGeometry = new THREE.BufferGeometry();
      linkGeometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(
          [0, 0, 0, position.x, position.y, position.z],
          3,
        ),
      );
      const link = new THREE.LineSegments(
        linkGeometry,
        new THREE.LineBasicMaterial({
          color,
          transparent: true,
          opacity: 0.72,
          blending: THREE.AdditiveBlending,
        }),
      );
      const orbit = makeOrbit(position, index + 47, 0.17);
      const orbitLine = createLocalOrbitLine(orbit, color, 0.2);
      const text = String(detail.label || "Đã có kết quả")
        .replace(/\s+/g, " ")
        .trim();
      const label = makeLabel(
        host,
        `${error ? "×" : "✓"} Kết quả: ${text.length > 62 ? `${text.slice(0, 62)}…` : text}`,
        "result",
      );
      label.dataset.status = detail.status;
      graph.add(mesh, ring, orbitLine, link);
      resultObjects.push({
        mesh,
        ring,
        orbitLine,
        link,
        label,
        position,
        orbit,
        phase: Math.random() * 6,
      });
      while (resultObjects.length > 3) removeResult(resultObjects[0]);
    };

    const clearFlow = () => {
      clearThoughts();
      [...resultObjects].forEach(removeResult);
      if (activityLinks) {
        graph.remove(activityLinks);
        activityLinks.geometry.dispose();
        activityLinks.material.dispose();
        activityLinks = null;
      }
      usedSkillNames = [];
      currentSkillName = null;
      skillObjects.forEach((item) => {
        item.activity = 0;
        item.activityState = "idle";
        item.label.classList.remove("active");
        delete item.label.dataset.phase;
        item.label.textContent = item.name;
      });
    };

    const removeTask = (task) => {
      if (!taskObjects.includes(task)) return;
      graph.remove(task.mesh, task.ring, task.orbitLine, task.links);
      task.label.remove();
      task.mesh.geometry.dispose();
      task.mesh.material.dispose();
      task.ring.geometry.dispose();
      task.ring.material.dispose();
      task.orbitLine.geometry.dispose();
      task.orbitLine.material.dispose();
      task.links.geometry.dispose();
      task.links.material.dispose();
      taskObjects = taskObjects.filter((item) => item !== task);
    };

    const upsertTask = (detail) => {
      let task = taskObjects.find((item) => item.name === detail.task);
      if (!task) {
        const index = taskObjects.length;
        const orbit = makeTaskOrbit(index);
        const position = new THREE.Vector3(
          Math.cos(orbit.angle) * orbit.radius,
          orbit.height,
          Math.sin(orbit.angle) * orbit.radius * 0.58,
        );
        const mesh = new THREE.Mesh(
          new THREE.SphereGeometry(0.09, 24, 18),
          new THREE.MeshStandardMaterial({
            color: 0xffcf6b,
            emissive: 0xff6828,
            emissiveIntensity: 3.2,
            roughness: 0.18,
          }),
        );
        mesh.position.copy(position);
        const ring = new THREE.Mesh(
          new THREE.SphereGeometry(0.19, 20, 14),
          new THREE.MeshBasicMaterial({
            color: 0xff9650,
            transparent: true,
            opacity: 0.13,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
            side: THREE.BackSide,
          }),
        );
        ring.position.copy(position);
        const orbitLine = createPlanarOrbitLine(orbit, 0xff9650, 0.2);
        const vertices = [position.x, position.y, position.z, 0, 0, 0];
        const linksGeo = new THREE.BufferGeometry();
        linksGeo.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(vertices, 3),
        );
        const links = new THREE.LineSegments(
          linksGeo,
          new THREE.LineBasicMaterial({
            color: 0xff9650,
            transparent: true,
            opacity: 0.42,
          }),
        );
        const label = makeLabel(host, compactNodeLabel(detail.task || "Task", 34), "task");
        graph.add(mesh, ring, orbitLine, links);
        task = {
          name: detail.task,
          detail: detail.task,
          kind: "task",
          mesh,
          ring,
          orbitLine,
          links,
          label,
          position,
          orbit,
          status: detail.status,
        };
        taskObjects.push(task);
      }
      task.status = detail.status;
      const colors =
        detail.status === "error"
          ? [0xff5b6e, 0xff203c]
          : detail.status === "done"
            ? [0x50f6c8, 0x148f72]
            : [0xffcf6b, 0xff6828];
      task.mesh.material.color.setHex(colors[0]);
      task.mesh.material.emissive.setHex(colors[1]);
      task.ring.material.color.setHex(colors[0]);
      task.orbitLine.material.color.setHex(colors[0]);
      task.label.dataset.status = detail.status;
      task.detail = detail.task;
      task.label.textContent = `${detail.status === "running" ? "● " : detail.status === "done" ? "✓ " : detail.status === "error" ? "× " : "○ "}${detail.task}`;
      task.label.textContent = `${detail.status === "running" ? "● " : detail.status === "done" ? "✓ " : detail.status === "error" ? "× " : "○ "}${compactNodeLabel(detail.task, 34)}`;
      if (detail.status === "done" || detail.status === "error")
        window.setTimeout(() => removeTask(task), 5000);
    };

    const onVisual = ({ detail }) => {
      if (detail.type === "state") {
        state = detail.state;
        if (state === "speaking") voiceImpulse = Math.max(voiceImpulse, 0.55);
      }
      if (detail.type === "voice-pulse")
        voiceImpulse = Math.max(voiceImpulse, detail.strength || 1);
      if (detail.type === "skills") setSkills(detail.skills);
      if (detail.type === "task") {
        if (detail.status === "running") clearThoughts();
        upsertTask(detail);
      }
      if (detail.type === "skill-activity") activateSkill(detail);
      if (detail.type === "thought") addThought(detail);
      if (detail.type === "result") addResult(detail);
      if (detail.type === "flow-start") clearFlow();
      if (detail.type === "plan-ready") clearThoughts();
      if (detail.type === "flash") {
        key.color.setRGB(
          detail.color[0] / 255,
          detail.color[1] / 255,
          detail.color[2] / 255,
        );
        key.intensity = 32;
      }
    };
    window.addEventListener(AGENT_VISUAL_EVENT, onVisual);
    setSkills(["get_video_info", "detect_scenes"]);

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

    const pointerDown = (event) => {
      dragging = true;
      px = event.clientX;
      py = event.clientY;
      dragDistance = 0;
      renderer.domElement.setPointerCapture(event.pointerId);
    };
    const pointerMove = (event) => {
      if (!dragging) return;
      dragDistance += Math.hypot(event.clientX - px, event.clientY - py);
      graph.rotation.y += (event.clientX - px) * 0.006;
      graph.rotation.x = THREE.MathUtils.clamp(
        graph.rotation.x + (event.clientY - py) * 0.004,
        -0.8,
        0.8,
      );
      px = event.clientX;
      py = event.clientY;
    };
    const pointerUp = (event) => {
      dragging = false;
      if (dragDistance > 6) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1,
      );
      raycaster.setFromCamera(pointer, camera);
      const items = [...taskObjects, ...skillObjects];
      const hit = raycaster.intersectObjects(items.map((item) => item.mesh), true)[0];
      const selected = hit && items.find((item) => item.mesh === hit.object || item.mesh.children.includes(hit.object));
      if (selected) showDetail(selected);
    };
    const onWheel = (event) => {
      event.preventDefault();
      const zoomStep = THREE.MathUtils.clamp(
        event.deltaY * 0.0045,
        -0.75,
        0.75,
      );
      targetCameraZ = THREE.MathUtils.clamp(
        targetCameraZ + zoomStep,
        minCameraZ,
        maxCameraZ,
      );
    };
    renderer.domElement.addEventListener("pointerdown", pointerDown);
    renderer.domElement.addEventListener("pointermove", pointerMove);
    renderer.domElement.addEventListener("pointerup", pointerUp);
    renderer.domElement.addEventListener("wheel", onWheel, { passive: false });

    const startedAt = performance.now();
    let animationId;
    const animate = (now) => {
      animationId = requestAnimationFrame(animate);
      const time = (now - startedAt) / 1000;
      camera.position.z += (targetCameraZ - camera.position.z) * 0.12;
      const palette = PALETTES[state] || PALETTES.idle;
      const energy =
        state === "working"
          ? 1.8
          : state === "thinking"
            ? 1.45
            : state === "listening"
              ? 1.2
              : 0.8;
      const voiceWave =
        state === "speaking" ? Math.max(0, Math.sin(time * 11.5)) * 0.34 : 0;
      const voicePulse = Math.min(1.25, voiceWave + voiceImpulse);
      voiceImpulse *= 0.86;
      if (!dragging) graph.rotation.y += 0.0015 * energy;
      core.rotation.x = time * 0.22 * energy;
      core.rotation.y = time * 0.32 * energy;
      core.scale.setScalar(
        1 + Math.sin(time * 2.4) * 0.06 * energy + voicePulse * 0.32,
      );
      aura.scale.setScalar(1 + Math.sin(time * 1.5) * 0.08 + voicePulse * 0.48);
      aura.material.opacity = 0.055 + voicePulse * 0.16;
      core.material.color.lerp(new THREE.Color(palette[0]), 0.06);
      aura.material.color.lerp(new THREE.Color(palette[1]), 0.06);
      particleMat.color.lerp(new THREE.Color(palette[1]), 0.04);
      fiberMat.color.lerp(new THREE.Color(palette[1]), 0.018);
      fiberMat.opacity =
        0.075 + energy * 0.025 + Math.max(0, Math.sin(time * 1.7)) * 0.025;
      neuralFibers.rotation.y = Math.sin(time * 0.12) * 0.025;
      hemisphereBridge.material.opacity =
        0.12 + Math.max(voicePulse, Math.max(0, Math.sin(time * 2.1)) * 0.05);
      hemisphereBridge.rotation.z = -0.15 + Math.sin(time * 0.3) * 0.025;
      const signalAttribute = signalGeo.attributes.position;
      for (let i = 0; i < signalCount; i++) {
        const curve = fiberPaths[(i * 17) % fiberPaths.length];
        const point = curve.getPoint(
          (time * (0.075 + (i % 5) * 0.012) + i / signalCount) % 1,
        );
        signalAttribute.setXYZ(i, point.x, point.y, point.z);
      }
      signalAttribute.needsUpdate = true;
      signalMat.opacity = 0.42 + energy * 0.18;
      key.color.lerp(new THREE.Color(palette[0]), 0.035);
      key.intensity += (12 * energy - key.intensity) * 0.04;
      skillObjects.forEach((item) => {
        const isCurrent = item.name === currentSkillName;
        // Activity is communicated by the halo, not by a distracting shake.
        moveOnOrbit(item, time, item.activity * 0.12);
        item.mesh.scale.setScalar(
          1 + Math.sin(time * 2.2 + item.phase) * 0.025 + item.activity * 0.04,
        );
        const satellite = item.mesh.userData.satellite;
        if (satellite) {
          satellite.haloMaterials[0].opacity = isCurrent
            ? 0.42
            : 0.16 + item.activity * 0.12;
          satellite.haloMaterials[1].opacity = isCurrent
            ? 0.16
            : 0.045 + item.activity * 0.05;
        }
        item.orbitLine.material.opacity = isCurrent
          ? 0.48
          : 0.06 + item.activity * 0.14;
        if (!isCurrent) item.activity *= 0.992;
      });
      thoughtObjects.forEach((thought, index) => {
        moveThoughtOnOrbit(thought, time);
        const pulse =
          0.5 + Math.max(0, Math.sin(time * 4.2 + thought.phase)) * 0.5;
        thought.mesh.scale.setScalar(1 + pulse * 0.16);
        thought.glow.scale.setScalar(1 + pulse * 0.28);
        thought.glow.material.opacity = 0.07 + pulse * 0.11;
        thought.orbitLine.material.opacity = 0.12 + pulse * 0.13;
      });
      resultObjects.forEach((result, index) => {
        moveOnOrbit(result, time, 0.25);
        result.ring.position.copy(result.position);
        result.mesh.rotation.x += 0.018;
        result.mesh.rotation.y += 0.026;
        result.ring.rotation.z = time * (1.1 + index * 0.12);
        result.ring.scale.setScalar(
          1 + Math.sin(time * 3.2 + result.phase) * 0.1,
        );
        const positions = result.link.geometry.attributes.position;
        positions.setXYZ(
          1,
          result.position.x,
          result.position.y,
          result.position.z,
        );
        positions.needsUpdate = true;
      });
      if (activityLinks)
        activityLinks.material.opacity =
          0.55 + Math.max(0, Math.sin(time * 5)) * 0.4;
      taskObjects.forEach((task, index) => {
        moveTaskOnOrbit(task, time);
        task.ring.position.copy(task.position);
        const pulse = 0.5 + Math.max(0, Math.sin(time * 3.4 + index)) * 0.5;
        task.mesh.scale.setScalar(1 + pulse * 0.16);
        task.ring.scale.setScalar(1 + pulse * 0.24);
        task.ring.material.opacity = 0.075 + pulse * 0.11;
        task.orbitLine.material.opacity = 0.14 + pulse * 0.14;
      });
      updateActivityLinkPositions();
      taskObjects.forEach((task) => rebuildTaskLinks(task.name));

      const currentSkill = skillObjects.find(
        (item) => item.name === currentSkillName,
      );
      if (currentSkill) {
        const progress = (time * 1.15) % 1;
        const arc = new THREE.Vector3()
          .copy(currentSkill.position)
          .multiplyScalar(progress);
        arc.y += Math.sin(progress * Math.PI) * 0.22;
        taskSignal.position.copy(arc);
        taskSignal.material.opacity =
          0.55 + Math.sin(progress * Math.PI) * 0.45;
        taskSignal.scale.setScalar(1 + Math.sin(progress * Math.PI) * 0.75);
      } else taskSignal.material.opacity *= 0.84;

      graph.updateMatrixWorld();
      const width = host.clientWidth,
        height = host.clientHeight;
      [
        ...skillObjects,
        ...taskObjects,
        ...thoughtObjects,
        ...resultObjects,
      ].forEach((item) => {
        const projected = item.mesh.position
          .clone()
          .applyMatrix4(graph.matrixWorld)
          .project(camera);
        item.label.style.transform = `translate(-50%,-50%) translate(${(projected.x * 0.5 + 0.5) * width}px,${(-projected.y * 0.5 + 0.5) * height}px)`;
        const isSemantic =
          item.label.classList.contains("active") ||
          item.label.classList.contains("task") ||
          item.label.classList.contains("result") ||
          item.label.classList.contains("thought");
        const depthOpacity = THREE.MathUtils.clamp(
          0.28 + (1 - projected.z) * 0.28,
          0.2,
          0.82,
        );
        item.label.style.opacity =
          projected.z < 1 && projected.z > -1
            ? String(isSemantic ? Math.max(0.86, depthOpacity) : depthOpacity)
            : "0";
      });
      renderer.render(scene, camera);
    };
    animationId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener(AGENT_VISUAL_EVENT, onVisual);
      resizeObserver.disconnect();
      renderer.dispose();
      renderer.domElement.removeEventListener("pointerdown", pointerDown);
      renderer.domElement.removeEventListener("pointermove", pointerMove);
      renderer.domElement.removeEventListener("pointerup", pointerUp);
      renderer.domElement.removeEventListener("wheel", onWheel);
      renderer.domElement.remove();
      host.querySelectorAll(".graph-label").forEach((label) => label.remove());
      detailPanel.remove();
    };
  }, []);

  return (
    <div
      ref={hostRef}
      id="scene"
      className="brain-stage"
      aria-label="Đồ thị 3D kiến trúc não AI, kỹ năng và tác vụ"
    />
  );
}
