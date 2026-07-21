import { useCallback, useEffect, useRef, useState } from 'react';
import { createVoiceEngine } from './voiceEngine.js';
import { AGENT_VISUAL_EVENT } from './agentConfig.js';

const visual = (detail) => window.dispatchEvent(new CustomEvent(AGENT_VISUAL_EVENT, { detail }));
const api = async (path, body) => {
  const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
};
const brief = (value) => { const text = typeof value === 'string' ? value : JSON.stringify(value ?? ''); return text.length > 420 ? `${text.slice(0, 420)}…` : text; };

export function useAgentController() {
  const [messages, setMessages] = useState([]);
  const [status, setStatusValue] = useState('idle');
  const [busy, setBusy] = useState(false);
  const [ttsOn, setTtsOn] = useState(true);
  const [micOn, setMicOn] = useState(false);
  const [micArmed, setMicArmed] = useState(false);
  const [hint, setHint] = useState('');
  const voiceRef = useRef(null);
  const sendRef = useRef(null);

  const setStatus = useCallback((next) => { setStatusValue(next); visual({ type: 'state', state: next }); }, []);
  const addText = useCallback((text, author = 'bot') => setMessages((current) => [...current, { id: crypto.randomUUID(), type: 'text', author, text }]), []);
  const speak = useCallback((text) => {
    if (!ttsOn) { setTimeout(() => { setBusy(false); setStatus('idle'); }, 900); return; }
    setStatus('speaking');
    voiceRef.current?.speak(text, () => { setBusy(false); setStatus('idle'); });
  }, [ttsOn, setStatus]);

  const finishTask = useCallback((result, planId, task) => {
    if (result?.needs_input?.length) {
      visual({ type: 'flash', color: [255, 200, 90] }); visual({ type: 'task', task, status: 'pending' });
      const ask = result.ask || 'Mình cần thêm thông tin để tiếp tục.'; addText(`❓ ${ask}`); speak(ask); return;
    }
    const good = Boolean(result?.success);
    visual({ type: 'flash', color: good ? [80, 246, 150] : [255, 90, 90] });
    visual({ type: 'task', task, status: good ? 'done' : 'error' });
    const summary = good ? `✅ ${result.skill}${result.generated ? ' (mới sinh)' : ''}: ${brief(result.result)}` : `❌ Thất bại: ${brief(result?.error)}`;
    addText(summary); speak(good ? `Xong. ${brief(result.result)}` : 'Tác vụ thất bại.');
    setMessages((current) => current.map((item) => item.id === planId ? { ...item, status: good ? 'done' : 'error' } : item));
  }, [addText, speak]);

  const approvePlan = useCallback(async (plan) => {
    setBusy(true); setStatus('working'); visual({ type: 'task', task: plan.task, status: 'running' });
    setMessages((current) => current.map((item) => item.id === plan.id ? { ...item, status: 'running' } : item));
    try {
      const start = await api('/api/approve', { task: plan.task, steps: plan.steps });
      if (!start.job) { setMessages((current) => current.map((item) => item.id === plan.id ? { ...item, logs: start.logs || [] } : item)); finishTask(start, plan.id, plan.task); return; }
      let from = 0, misses = 0;
      while (true) {
        try {
          const response = await fetch(`/api/job?id=${encodeURIComponent(start.job)}&from=${from}`);
          const job = await response.json();
          misses = 0;
          if (job.logs?.length) { from = job.total; setMessages((current) => current.map((item) => item.id === plan.id ? { ...item, logs: [...(item.logs || []), ...job.logs] } : item)); }
          if (job.status === 'done') { finishTask(job.result, plan.id, plan.task); break; }
        } catch (_) { if (++misses > 30) throw new Error('Mất kết nối tới job'); }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    } catch (error) { finishTask({ success: false, error: error.message }, plan.id, plan.task); }
  }, [finishTask, setStatus]);

  const rejectPlan = useCallback(async (plan) => {
    await api('/api/reject', { task: plan.task }).catch(() => {});
    visual({ type: 'task', task: plan.task, status: 'error' });
    setMessages((current) => current.map((item) => item.id === plan.id ? { ...item, status: 'rejected' } : item));
    setBusy(false); setStatus('idle');
  }, [setStatus]);

  const send = useCallback(async (raw) => {
    const text = raw.trim();
    if (!text || busy) return;
    addText(text, 'me'); setBusy(true); setStatus('thinking');
    try {
      const data = await api('/api/message', { text });
      if (data.mode === 'plan') {
        const plan = { id: crypto.randomUUID(), type: 'plan', task: data.task, steps: data.steps || [], planUrl: data.plan_url, status: 'pending', logs: [] };
        setMessages((current) => [...current, plan]); visual({ type: 'task', task: data.task, status: 'pending' }); setBusy(false); setStatus('idle');
      } else {
        const reply = data.reply || '…'; addText(reply); speak(reply);
      }
    } catch (error) { addText(`Lỗi kết nối: ${error.message}`); setBusy(false); setStatus('idle'); }
  }, [addText, busy, setStatus, speak]);
  sendRef.current = send;

  useEffect(() => {
    voiceRef.current = createVoiceEngine({ onCommand: (text) => sendRef.current?.(text), onHint: setHint, onListeningChange: (on, armed) => { setMicOn(on); setMicArmed(armed); }, onError: addText });
    fetch('/api/health').then((response) => response.json()).then((data) => { if (Array.isArray(data.skills)) visual({ type: 'skills', skills: data.skills }); }).catch(() => {});
    return () => voiceRef.current?.destroy();
  }, [addText]);

  const toggleTts = () => { setTtsOn((current) => { if (current) { voiceRef.current?.stopSpeaking(); setBusy(false); setStatus('idle'); } return !current; }); };
  return { messages, status, busy, ttsOn, micOn, micArmed, hint, send, approvePlan, rejectPlan, toggleTts, toggleMic: () => voiceRef.current?.toggleListening() };
}
