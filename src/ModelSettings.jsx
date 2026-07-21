import { useEffect, useRef, useState } from 'react';
import { agentText } from './agentConfig.js';

const EMPTY_ROLES = {
  chat: { provider: 'openai', model: '' },
  work: { provider: 'openai', model: '' }
};

export default function ModelSettings() {
  const [open, setOpen] = useState(false);
  const [roles, setRoles] = useState(EMPTY_ROLES);
  const [catalog, setCatalog] = useState({});
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const dialogRef = useRef(null);

  const load = async () => {
    setMessage('');
    try {
      const response = await fetch('/api/model-config');
      const data = await response.json();
      if (response.status === 404) {
        throw new Error(agentText.staleServer);
      }
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      setRoles(data.roles);
      setCatalog(data.catalog || {});
    } catch (error) {
      setMessage(`Không tải được cấu hình: ${error.message}`);
    }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (open) dialogRef.current?.focus();
  }, [open]);

  const updateRole = (role, field, value) => {
    setRoles((current) => ({
      ...current,
      [role]: {
        ...current[role],
        [field]: value,
        ...(field === 'provider' ? {
          model: catalog[value]?.[0] || '',
          base_url: value === 'local' ? 'http://127.0.0.1:11434/v1' : ''
        } : {})
      }
    }));
  };

  const save = async () => {
    setSaving(true);
    setMessage('');
    try {
      const response = await fetch('/api/model-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roles })
      });
      const data = await response.json();
      if (response.status === 404) {
        throw new Error(agentText.staleServer);
      }
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
      setRoles(data.roles);
      setMessage('Đã lưu. Model mới sẽ được dùng từ yêu cầu tiếp theo.');
    } catch (error) {
      setMessage(`Không lưu được cấu hình: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <button type="button" className="settings-trigger" onClick={() => setOpen(true)} aria-label="Cấu hình model AI" title="Cấu hình model AI">⚙</button>
      {open && (
        <div className="settings-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
          <section className="settings-panel" role="dialog" aria-modal="true" aria-labelledby="model-settings-title" tabIndex={-1} ref={dialogRef}>
            <div className="settings-head">
              <div><span className="settings-kicker">AI runtime</span><h2 id="model-settings-title">Cấu hình model</h2></div>
              <button type="button" className="settings-close" onClick={() => setOpen(false)} aria-label="Đóng">×</button>
            </div>

            {['chat', 'work'].map((role) => (
              <fieldset className="model-role" key={role}>
                <legend>{role === 'chat' ? 'Hội thoại' : 'Thực thi tác vụ'}</legend>
                <div className="provider-field">
                  <span className="provider-label">Provider</span>
                  <div className="provider-options" role="radiogroup" aria-label={`Provider cho ${role}`}>
                    {Object.keys(catalog).map((provider) => (
                      <button
                        type="button"
                        role="radio"
                        aria-checked={roles[role]?.provider === provider}
                        className={roles[role]?.provider === provider ? 'selected' : ''}
                        key={provider}
                        onClick={() => updateRole(role, 'provider', provider)}
                      >
                        {provider}
                      </button>
                    ))}
                  </div>
                </div>
                <label>Model
                  <input value={roles[role]?.model || ''} list={`models-${role}`} onChange={(event) => updateRole(role, 'model', event.target.value)} spellCheck="false" />
                  <datalist id={`models-${role}`}>
                    {(catalog[roles[role]?.provider] || []).map((model) => <option key={model} value={model} />)}
                  </datalist>
                </label>
                {roles[role]?.provider === 'local' && (
                  <label>Local endpoint
                    <input value={roles[role]?.base_url || ''} onChange={(event) => updateRole(role, 'base_url', event.target.value)} placeholder="http://127.0.0.1:11434/v1" spellCheck="false" />
                  </label>
                )}
                <span className={`model-readiness ${roles[role]?.ready ? 'ready' : ''}`}>
                  {roles[role]?.provider === 'mock' ? 'Mock offline — không gọi mạng' : roles[role]?.provider === 'local' ? 'Model chạy trên máy này' : roles[role]?.ready ? 'Đã có API key' : 'Chưa có API key'}
                </span>
              </fieldset>
            ))}

            {message && <p className="settings-message" aria-live="polite">{message}</p>}
            <div className="settings-actions">
              <button type="button" className="settings-cancel" onClick={() => setOpen(false)}>Hủy</button>
              <button type="button" className="settings-save" onClick={save} disabled={saving}>{saving ? 'Đang lưu…' : 'Lưu cấu hình'}</button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
