import { useEffect, useState } from 'react';
import ConversationPanel from './ConversationPanel.jsx';
import LiveOrganizationGraph from './LiveOrganizationGraph.jsx';

const endpoints = ['organizations', 'work-orders', 'agents', 'topology', 'artifacts', 'approvals', 'events', 'metrics', 'configuration', 'session'];
const labels = { command: 'Command Center', organization: 'Organization', tasks: 'Task DAG', timeline: 'Timeline', approvals: 'Approvals', artifacts: 'Artifacts', metrics: 'Cost & Performance', config: 'Configuration' };

const api = async (path, options) => {
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
  return value.data;
};

function Status({ value }) { return <span className={`ops-status status-${value}`}>{String(value || 'unknown').replaceAll('_', ' ')}</span>; }
function Empty({ children }) { return <div className="ops-empty">{children}</div>; }

export default function OrganizationDashboard({ controller, onLegacy }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('command');
  const [selectedTask, setSelectedTask] = useState(null);
  const [busyApproval, setBusyApproval] = useState('');
  const [busyCommand, setBusyCommand] = useState('');
  const [chatOpen, setChatOpen] = useState(true);
  const [focusMode, setFocusMode] = useState(false);

  const load = async () => {
    setError('');
    try {
      const values = await Promise.all(endpoints.map((name) => api(`/api/v1/${name}`)));
      const next = Object.fromEntries(endpoints.map((name, index) => [name, values[index]]));
      const workOrder = next['work-orders'][0];
      next.tasks = workOrder ? await api(`/api/v1/work-orders/${workOrder.id}/tasks`) : [];
      setData(next);
    } catch (reason) { setError(reason.message); }
  };
  useEffect(() => { load(); const timer = setInterval(load, 5000); return () => clearInterval(timer); }, []);

  const decide = async (approval, decision) => {
    if (approval.risk === 'high' && !window.confirm(`${decision === 'approved' ? 'Approve' : 'Reject'} high-risk action ${approval.requested_action}?`)) return;
    setBusyApproval(approval.id);
    try {
      await api('/api/v1/approvals/decision', { method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.session.csrf_token},
        body: JSON.stringify({approval_id: approval.id, action_hash: approval.action_hash, decision}) });
      await load();
    } catch (reason) { setError(reason.message); }
    setBusyApproval('');
  };

  const command = async (path, payload, confirmation = '') => {
    if (confirmation && !window.confirm(confirmation)) return;
    setBusyCommand(path);
    try {
      await api(path, { method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': data.session.csrf_token}, body: JSON.stringify(payload) });
      await load();
    } catch (reason) { setError(reason.message); }
    setBusyCommand('');
  };

  if (error && !data) return <main className="ops-shell"><div className="ops-error" role="alert">Could not load organization state: {error}<button onClick={load}>Retry</button></div><button onClick={onLegacy}>Open legacy chat</button></main>;
  if (!data) return <main className="ops-shell ops-loading" aria-busy="true">Loading organization state…</main>;
  const workOrder = data['work-orders'][0];
  const pending = data.approvals.filter((item) => item.status === 'pending');
  const render = {
    command: <section><header className="ops-view-head"><div><span className="eyebrow">Active goal</span><h2>{workOrder?.goal || 'No active Work Order'}</h2></div>{workOrder && <Status value={workOrder.status}/>}</header>{!workOrder ? <Empty>Start from chat to create a Work Order.</Empty> : <><div className="operator-actions" aria-label="Work Order controls">{workOrder.status === 'paused' ? <button disabled={busyCommand} onClick={() => command('/api/v1/work-orders/control', {work_order_id: workOrder.id, action: 'resume'})}>Resume Work Order</button> : workOrder.status === 'waiting_approval' && <button disabled={busyCommand} onClick={() => command('/api/v1/work-orders/control', {work_order_id: workOrder.id, action: 'pause'})}>Pause Work Order</button>}{['waiting_approval','paused','blocked'].includes(workOrder.status) && <button className="danger" disabled={busyCommand} onClick={() => command('/api/v1/work-orders/control', {work_order_id: workOrder.id, action: 'cancel'}, 'Cancel this Work Order? This stops pending execution.')}>Cancel Work Order</button>}</div><div className="metric-grid"><article><span>Work Order</span><strong>{workOrder.title}</strong><small>Owner: {workOrder.accountable_owner}</small></article><article><span>Progress</span><strong>{Math.round(workOrder.progress * 100)}%</strong><progress value={workOrder.progress} max="1" /></article><article className={pending.length ? 'attention' : ''}><span>Approvals</span><strong>{pending.length}</strong><small>{workOrder.blockers.join(', ') || 'No blockers'}</small></article><article><span>Budget</span><strong>{workOrder.budget.tokens_used.toLocaleString()} tokens</strong><small>{workOrder.budget.tokens_remaining.toLocaleString()} remaining · {workOrder.budget.cost_units_used} cost</small></article></div><div className="ops-card"><h3>Latest deliverables</h3>{workOrder.latest_deliverables.map((item) => <code key={item}>{item}</code>)}</div></>}</section>,
    organization: <section><header className="ops-view-head"><div><span className="eyebrow">Live operational topology</span><h2>Living AI Organization</h2><p className="view-intro">Follow ownership, execution, dependencies, artifacts and human gates in one graph. Select any entity to inspect its current state.</p></div></header><LiveOrganizationGraph topology={data.topology} onOpenTask={(taskId) => { const task = data.tasks.find((item) => item.id === taskId); setSelectedTask(task || null); setTab('tasks'); }}/></section>,
    tasks: <section><header className="ops-view-head"><div><span className="eyebrow">Dependency order</span><h2>Task DAG</h2></div></header>{data.tasks.length ? <div className="task-list">{data.tasks.map((task) => <button key={task.id} onClick={() => setSelectedTask(task)} className="task-node"><span>{task.title}</span><Status value={task.status}/><small>{task.owner} · risk {task.risk} · retries {task.retry_count}</small><small>Depends: {task.dependencies.join(', ') || 'none'}</small></button>)}</div> : <Empty>No tasks for this Work Order.</Empty>}{selectedTask && <aside className="detail-panel"><button className="detail-close" onClick={() => setSelectedTask(null)} aria-label="Close details">×</button><h3>{selectedTask.title}</h3><pre>{JSON.stringify(selectedTask, null, 2)}</pre>{['failed','blocked'].includes(selectedTask.status) && <button className="retry-task" onClick={() => command('/api/v1/tasks/retry', {task_id: selectedTask.id})}>Retry task</button>}</aside>}</section>,
    timeline: <section><header className="ops-view-head"><h2>Activity Timeline</h2></header><ol className="timeline">{data.events.map((event) => <li key={event.id}><time>{event.occurred_at.slice(11,16)}</time><div><strong>{event.summary}</strong><small>{event.type}</small></div></li>)}</ol></section>,
    approvals: <section><header className="ops-view-head"><div><span className="eyebrow">Human control</span><h2>Approval Inbox</h2></div><strong className="approval-count">{pending.length} pending</strong></header>{data.approvals.map((approval) => <article className="approval-card" key={approval.id}><div><Status value={approval.status}/><span className="risk">{approval.risk} risk</span></div><h3>{approval.requested_action}</h3><p>{approval.reason}</p><dl><dt>Agent</dt><dd>{approval.requesting_agent}</dd><dt>Scope</dt><dd><code>{JSON.stringify(approval.scope)}</code></dd><dt>Hash</dt><dd><code>{approval.action_hash}</code></dd><dt>Expires</dt><dd>{approval.expires_at}</dd></dl>{approval.status === 'pending' && <div className="approval-actions"><button disabled={busyApproval === approval.id} onClick={() => decide(approval, 'approved')}>Approve</button><button disabled={busyApproval === approval.id} onClick={() => decide(approval, 'rejected')}>Reject</button></div>}</article>)}</section>,
    artifacts: <section><header className="ops-view-head"><h2>Artifact Center</h2></header><div className="artifact-list">{data.artifacts.map((item) => <details key={item.id}><summary><code>{item.path}</code><Status value={item.review_status}/></summary><dl><dt>Version</dt><dd>{item.version}</dd><dt>Producer</dt><dd>{item.producer}</dd><dt>Task</dt><dd>{item.source_task}</dd><dt>Approval</dt><dd>{item.approval_status}</dd><dt>Hash</dt><dd><code>{item.content_hash}</code></dd></dl><p>{item.preview}</p></details>)}</div></section>,
    metrics: <section><header className="ops-view-head"><h2>Cost & Performance</h2></header><pre className="safe-json">{JSON.stringify(data.metrics, null, 2)}</pre></section>,
    config: <section><header className="ops-view-head"><div><span className="eyebrow">Validated · read only</span><h2>Organization Configuration</h2></div></header><pre className="safe-json">{JSON.stringify(data.configuration, null, 2)}</pre></section>
  };
  const graphView = tab === 'organization';
  const layoutClass = ['ops-layout', chatOpen ? '' : 'chat-hidden', focusMode && graphView ? 'focus-mode' : ''].filter(Boolean).join(' ');
  return <main className="ops-shell"><header className="ops-top"><div><span className="eyebrow">Operations console</span><h1>AI Software Company</h1></div><div className="ops-top-actions">{graphView && <button aria-pressed={focusMode} onClick={() => setFocusMode((value) => !value)}>{focusMode ? 'Exit focus' : 'Focus graph'}</button>}<button aria-pressed={!chatOpen} onClick={() => setChatOpen((value) => !value)}>{chatOpen ? 'Hide chat' : 'Show chat'}</button><button onClick={onLegacy}>Chat mode</button><span className={pending.length ? 'approval-beacon active' : 'approval-beacon'}>{pending.length} approvals</span></div></header><div className={layoutClass}><nav aria-label="Dashboard views">{Object.entries(labels).map(([id,label]) => <button className={tab===id?'active':''} onClick={() => { setTab(id); setFocusMode(false); }} key={id}>{label}</button>)}</nav><div className="ops-content">{error && <div className="ops-error" role="alert">Refresh failed: {error}</div>}{render[tab]}</div><aside className="ops-chat" aria-hidden={!chatOpen || (focusMode && graphView)}><ConversationPanel controller={controller}/></aside></div></main>;
}
