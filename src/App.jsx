import { useEffect } from 'react';
import './dashboard.css';
import { initializeLegacyEngine } from './legacyEngine.js';
import ThreeBrain from './ThreeBrain.jsx';

/**
 * React owns the dashboard structure. During the incremental migration the
 * canvas, voice, conversation and approval engine lives in legacyEngine.js;
 * it no longer reads or executes the backup HTML at runtime.
 */
export default function App() {
  useEffect(() => {
    initializeLegacyEngine();
  }, []);

  return (
    <div id="app">
      <ThreeBrain />

      <header className="brand">
        <h1>JAVIS</h1>
        <div className="state">
          <span className="dot" id="dot" />
          <span id="stateLabel">Đang chờ</span>
        </div>
      </header>

      <div className="badge" id="badge">…</div>
      <aside className="transcript" id="transcript" aria-live="polite" />
      <div className="wakehint" id="wakehint" />

      <div className="composer">
        <button type="button" className="icon" id="mic" title="Bật nghe rảnh tay" aria-label="Bật nghe rảnh tay">🎙️</button>
        <input type="text" id="inp" autoComplete="off" aria-label="Tin nhắn" />
        <button type="button" className="icon on" id="tts" title="Đọc bằng giọng nói" aria-label="Bật hoặc tắt đọc bằng giọng nói">🔊</button>
        <button type="button" className="icon send" id="send" title="Gửi" aria-label="Gửi tin nhắn">➤</button>
      </div>
    </div>
  );
}
