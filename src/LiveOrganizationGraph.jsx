import { useMemo, useState } from 'react';

const KIND_ORDER = ['work_order', 'agent', 'task', 'artifact', 'approval'];
const KIND_LABELS = { work_order: 'Work order', agent: 'AI entities', task: 'Tasks', artifact: 'Artifacts', approval: 'Human gates' };

function placeNodes(nodes) {
  const columns = Object.fromEntries(KIND_ORDER.map((kind) => [kind, nodes.filter((node) => node.kind === kind)]));
  const xByKind = { work_order: 80, agent: 270, task: 520, artifact: 790, approval: 940 };
  return nodes.map((node) => {
    const column = columns[node.kind];
    const index = column.findIndex((item) => item.id === node.id);
    const spacing = Math.min(76, 610 / Math.max(column.length, 1));
    return { ...node, x: xByKind[node.kind] || 500, y: 55 + spacing * (index + 0.5) };
  });
}

function shortLabel(value, limit = 24) {
  return value.length > limit ? `${value.slice(0, limit - 1)}…` : value;
}

export default function LiveOrganizationGraph({ topology, onOpenTask }) {
  const [selectedId, setSelectedId] = useState(topology.nodes[0]?.id || '');
  const [visibleKinds, setVisibleKinds] = useState(new Set(KIND_ORDER));
  const positioned = useMemo(() => placeNodes(topology.nodes), [topology]);
  const nodes = positioned.filter((node) => visibleKinds.has(node.kind));
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const edges = topology.edges.filter((edge) => byId.has(edge.source) && byId.has(edge.target));
  const selected = positioned.find((node) => node.id === selectedId);

  const toggleKind = (kind) => setVisibleKinds((current) => {
    const next = new Set(current);
    if (next.has(kind) && next.size > 1) next.delete(kind); else next.add(kind);
    return next;
  });

  return <div className="live-graph-shell">
    <div className="graph-toolbar" aria-label="Graph filters">
      {KIND_ORDER.map((kind) => <button key={kind} className={visibleKinds.has(kind) ? `kind-${kind} active` : ''} aria-pressed={visibleKinds.has(kind)} onClick={() => toggleKind(kind)}>{KIND_LABELS[kind]}</button>)}
      <span className="live-indicator"><i /> Live · refresh 5s</span>
    </div>
    <div className="live-graph-workspace">
      <div className="graph-canvas-wrap"><svg className="live-graph" viewBox="0 0 1020 700" role="img" aria-labelledby="live-graph-title live-graph-desc">
        <title id="live-graph-title">Live AI organization topology</title><desc id="live-graph-desc">Work order, AI agents, tasks, artifacts and human approval gates connected by operational relationships.</desc>
        <defs><filter id="node-glow"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
        <g className="graph-edges">{edges.map((edge, index) => { const source = byId.get(edge.source); const target = byId.get(edge.target); const active = edge.source === selectedId || edge.target === selectedId; return <path key={`${edge.source}-${edge.target}-${edge.kind}-${index}`} className={`${edge.kind} ${active ? 'active' : ''}`} d={`M ${source.x} ${source.y} C ${(source.x + target.x) / 2} ${source.y}, ${(source.x + target.x) / 2} ${target.y}, ${target.x} ${target.y}`}><title>{edge.kind.replaceAll('_', ' ')}</title></path>; })}</g>
        <g className="graph-nodes">{nodes.map((node) => <g key={node.id} className={`live-node kind-${node.kind} status-${node.status} ${node.id === selectedId ? 'selected' : ''}`} transform={`translate(${node.x} ${node.y})`} role="button" tabIndex="0" aria-label={`${KIND_LABELS[node.kind]} ${node.label}, ${node.status}`} onClick={() => setSelectedId(node.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedId(node.id); } }}><circle className="node-aura" r="22"/><circle className="node-core" r={node.kind === 'work_order' ? 14 : 10}/><text x="0" y="30" textAnchor="middle">{shortLabel(node.label)}</text><title>{node.label}</title></g>)}</g>
      </svg></div>
      <aside className="graph-inspector" aria-live="polite">{selected ? <><span className={`entity-kind kind-${selected.kind}`}>{KIND_LABELS[selected.kind]}</span><h3>{selected.label}</h3><span className={`ops-status status-${selected.status}`}>{selected.status.replaceAll('_', ' ')}</span><p>{selected.detail || 'No operational detail.'}</p><dl><dt>ID</dt><dd><code>{selected.id}</code></dd>{selected.current_task && <><dt>Current task</dt><dd>{selected.current_task}</dd></>}{selected.risk && <><dt>Risk</dt><dd>{selected.risk}</dd></>}</dl>{selected.kind === 'task' && <button onClick={() => onOpenTask(selected.id)}>Open task details</button>}</> : <p>Select an entity to inspect it.</p>}</aside>
    </div>
    <div className="graph-relationship-legend"><span>Solid: workflow</span><span>Dotted: reporting</span><span>Amber: approval gate</span><span>Selected: connected path</span><time>Snapshot {new Date(topology.generated_at).toLocaleTimeString()}</time></div>
  </div>;
}
