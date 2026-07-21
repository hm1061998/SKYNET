import './dashboard.css';
import ThreeBrain from './ThreeBrain.jsx';
import ModelSettings from './ModelSettings.jsx';
import ConversationPanel from './ConversationPanel.jsx';
import { useAgentController } from './useAgentController.js';
import { AGENT_NAME } from './agentConfig.js';

const STATUS = {
  idle: { label: 'Đang chờ', color: [80, 246, 200] },
  listening: { label: 'Sẵn sàng', color: [79, 227, 255] },
  thinking: { label: 'Đang suy nghĩ…', color: [150, 110, 255] },
  speaking: { label: 'Đang trả lời…', color: [120, 240, 220] },
  working: { label: 'Đang thực thi…', color: [255, 150, 80] }
};

export default function App() {
  const controller = useAgentController();
  const current = STATUS[controller.status] || STATUS.idle;
  const dotColor = `rgb(${current.color.join(',')})`;

  return (
    <div id="app">
      <ThreeBrain />
      <header className="brand">
        <h1>{AGENT_NAME}</h1>
        <div className="state">
          <span className="dot" style={{ background: dotColor, boxShadow: `0 0 10px ${dotColor}` }} />
          <span>{current.label}</span>
        </div>
      </header>
      <div className="badge" id="badge">…</div>
      <ModelSettings />
      <ConversationPanel controller={controller} />
    </div>
  );
}
