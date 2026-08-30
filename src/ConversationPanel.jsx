import { useEffect, useRef, useState } from "react";
import { AGENT_NAME } from "./agentConfig.js";

const QUICK_PROMPTS = [
  "Bạn có thể làm gì?",
  "Liệt kê các file trong thư mục",
  "Giúp tôi lập kế hoạch công việc",
];
const STATUS_TEXT = {
  idle: "Sẵn sàng hỗ trợ",
  listening: "Đang nghe bạn",
  thinking: "Đang phân tích",
  speaking: "Đang trả lời",
  working: "Đang thực thi tác vụ",
};
const PLAN_STATUS = {
  pending: "Chờ bạn duyệt",
  running: "Đang thực thi",
  done: "Đã hoàn thành",
  error: "Có lỗi",
  rejected: "Đã từ chối",
};
const logClass = (line) =>
  line.startsWith("[✓]") ? "lg-ok" : line.startsWith("[✗]") ? "lg-no"
    : line.startsWith("[!]") ? "lg-warn" : line.startsWith("[+]") ? "lg-add"
      : line.startsWith("[>]") ? "lg-run" : line.startsWith("[~]") ? "lg-fix"
        : line.startsWith("[TASK]") ? "lg-task" : "lg-dim";
const formatTime = (value) =>
  new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" })
    .format(value ? new Date(value) : new Date());

function PlanCard({ plan, onApprove, onReject }) {
  const locked = plan.status !== "pending";
  const running = plan.status === "running";
  return (
    <article className={`plan-card plan-${plan.status}`}>
      <div className="plan-head">
        <div><span className="message-author">Kế hoạch tác vụ</span><h3>{plan.task}</h3></div>
        <span className={`plan-status status-${plan.status}`}>
          {running && <span className="mini-spinner" aria-hidden="true" />}
          {PLAN_STATUS[plan.status] || plan.status}
        </span>
      </div>
      <ol className="steps">
        {plan.steps.map((step, index) => (
          <li key={`${index}-${step}`}><span className="n">{index + 1}</span><span className="t">{step}</span></li>
        ))}
      </ol>
      <div className="acts">
        <button className="btn ok" disabled={locked} onClick={() => onApprove(plan)}>Thực thi kế hoạch</button>
        <button className="btn no" disabled={locked} onClick={() => onReject(plan)}>Từ chối</button>
        {plan.planUrl && <a className="open" href={plan.planUrl} target="_blank" rel="noreferrer">Xem chi tiết ↗</a>}
      </div>
      {plan.logs?.length > 0 && (
        <details className="execution-log" open={running}>
          <summary>Nhật ký thực thi <span>{plan.logs.length}</span></summary>
          <pre className="logs">
            {plan.logs.map((line, index) => <span className={logClass(line)} key={`${index}-${line}`}>{line}{"\n"}</span>)}
          </pre>
        </details>
      )}
    </article>
  );
}

function TextMessage({ message }) {
  const error = /^(Lỗi|❌)/i.test(message.text);
  const success = /^✅/.test(message.text);
  return (
    <div className={`row ${message.author}`}>
      <div className={`message-wrap ${error ? "is-error" : ""} ${success ? "is-success" : ""}`}>
        <div className="message-meta">
          <span className="message-author">{message.author === "me" ? "Bạn" : AGENT_NAME}</span>
          <time dateTime={message.createdAt}>{formatTime(message.createdAt)}</time>
        </div>
        <div className="bubble">{message.text}</div>
      </div>
    </div>
  );
}

export default function ConversationPanel({ controller }) {
  const [input, setInput] = useState("");
  const [atBottom, setAtBottom] = useState(true);
  const transcriptRef = useRef(null);
  const inputRef = useRef(null);
  const scrollToBottom = (behavior = "smooth") => {
    const el = transcriptRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior });
  };
  useEffect(() => { if (atBottom) scrollToBottom("smooth"); }, [controller.messages, controller.busy, atBottom]);
  useEffect(() => {
    const field = inputRef.current;
    if (!field) return;
    field.style.height = "0px";
    field.style.height = `${Math.min(field.scrollHeight, 112)}px`;
  }, [input]);
  const submit = (value = input) => {
    if (!value.trim() || controller.busy) return;
    controller.send(value); setInput(""); inputRef.current?.focus();
  };

  return (
    <section className="conversation-shell" aria-label="Trò chuyện với Agent">
      <div className="conversation-head">
        <div><span className="conversation-kicker">Agent workspace</span><strong>Hội thoại</strong></div>
        <div className={`agent-presence presence-${controller.status}`}><span aria-hidden="true" />{STATUS_TEXT[controller.status] || STATUS_TEXT.idle}</div>
      </div>
      <div className="transcript" ref={transcriptRef} aria-live="polite"
        onWheel={(event) => event.stopPropagation()}
        onScroll={(event) => { const el = event.currentTarget; setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80); }}>
        {controller.messages.length === 0 && (
          <div className="conversation-empty">
            <div className="empty-orb" aria-hidden="true">✦</div>
            <h2>Tôi có thể giúp gì cho bạn?</h2>
            <p>Hỏi đáp, xử lý tệp hoặc giao một tác vụ để Agent tự lập kế hoạch và thực thi.</p>
            <div className="quick-prompts" aria-label="Gợi ý câu hỏi">
              {QUICK_PROMPTS.map((prompt) => <button type="button" key={prompt} onClick={() => setInput(prompt)}>{prompt}<span>↗</span></button>)}
            </div>
          </div>
        )}
        {controller.messages.map((message) => message.type === "plan" ? (
          <div className="row bot" key={message.id}><PlanCard plan={message} onApprove={controller.approvePlan} onReject={controller.rejectPlan} /></div>
        ) : <TextMessage key={message.id} message={message} />)}
        {controller.busy && controller.status === "thinking" && (
          <div className="row bot thinking-row" role="status"><div className="message-wrap">
            <div className="message-meta"><span className="message-author">{AGENT_NAME}</span></div>
            <div className="bubble typing-indicator" aria-label="Agent đang suy nghĩ"><i /><i /><i /></div>
          </div></div>
        )}
      </div>
      {!atBottom && <button className="scroll-latest" type="button" onClick={() => scrollToBottom()}>Tin nhắn mới ↓</button>}
      <div className="interaction-dock">
        <div className={`wakehint ${controller.hint ? "visible" : ""}`} role="status">{controller.hint}</div>
        <div className={`composer ${controller.busy ? "is-busy" : ""}`}>
          <button type="button" className={`icon ${controller.micOn ? "on" : ""} ${controller.micArmed ? "rec" : ""}`}
            onClick={controller.toggleMic} title="Bật nghe tiếng Việt" aria-label="Bật hoặc tắt microphone"><span aria-hidden="true">🎙</span></button>
          <div className="input-wrap">
            <textarea ref={inputRef} value={input} onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }}
              rows={1} autoComplete="off" placeholder={controller.busy ? "Agent đang xử lý…" : "Nhắn tin cho Agent…"} aria-label="Tin nhắn" />
            <span className="input-hint">Enter để gửi · Shift+Enter xuống dòng</span>
          </div>
          <button type="button" className={`icon ${controller.ttsOn ? "on" : ""}`} onClick={controller.toggleTts}
            title={controller.ttsOn ? "Tắt đọc tiếng Việt" : "Bật đọc tiếng Việt"} aria-label="Bật hoặc tắt đọc bằng giọng nói">
            <span aria-hidden="true">{controller.ttsOn ? "🔊" : "🔇"}</span></button>
          <button type="button" className="icon send" onClick={() => submit()} disabled={controller.busy || !input.trim()}
            title="Gửi tin nhắn" aria-label="Gửi tin nhắn"><span aria-hidden="true">↑</span></button>
        </div>
      </div>
    </section>
  );
}
