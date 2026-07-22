import './dashboard.css';
import ThreeBrain from './ThreeBrain.jsx';
import ModelSettings from './ModelSettings.jsx';
import ConversationPanel from './ConversationPanel.jsx';
import { useAgentController } from './useAgentController.js';
import { AGENT_NAME } from './agentConfig.js';
import OrganizationDashboard from './OrganizationDashboard.jsx';
import { useEffect, useState } from 'react';

const STATUS = {
  idle: { label: 'Đang chờ', color: [80, 246, 200] },
  listening: { label: 'Sẵn sàng', color: [79, 227, 255] },
  thinking: { label: 'Đang suy nghĩ…', color: [150, 110, 255] },
  speaking: { label: 'Đang trả lời…', color: [120, 240, 220] },
  working: { label: 'Đang thực thi…', color: [255, 150, 80] }
};

const formatElapsed = (milliseconds) => {
  const totalSeconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
};

export default function App() {
  const controller = useAgentController();
  const [organizationMode, setOrganizationMode] = useState(null);
  useEffect(() => {
    fetch('/api/v1/configuration').then((response) => response.json())
      .then((payload) => setOrganizationMode(payload?.data?.feature_flags?.ui_mode === 'organization'))
      .catch(() => setOrganizationMode(false));
  }, []);
  const current = STATUS[controller.status] || STATUS.idle;
  const dotColor = `rgb(${current.color.join(',')})`;

  if (organizationMode === null) return <main className="ops-shell ops-loading" aria-busy="true">Loading dashboard…</main>;
  if (organizationMode) return <OrganizationDashboard controller={controller} onLegacy={() => setOrganizationMode(false)} />;
  return (
    <div id="app">
      <ThreeBrain />
      <header className="brand">
        <h1>{AGENT_NAME}</h1>
        <div className="state">
          <span className="dot" style={{ background: dotColor, boxShadow: `0 0 10px ${dotColor}` }} />
          <span>{current.label}</span>
        </div>
        {controller.executionActive && (
          <div className="execution-timer" aria-live="polite">
            Thời gian xử lý <strong>{formatElapsed(controller.executionElapsedMs)}</strong>
          </div>
        )}
      </header>
      <div className="badge" id="badge">…</div>
      <ModelSettings />
      <ConversationPanel controller={controller} />
      <button className="organization-mode-trigger" onClick={() => setOrganizationMode(true)}>Organization console</button>
    </div>
  );
}
