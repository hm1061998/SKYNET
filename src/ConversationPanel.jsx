import { useEffect, useRef, useState } from "react";

const logClass = (line) =>
  line.startsWith("[✓]")
    ? "lg-ok"
    : line.startsWith("[✗]")
      ? "lg-no"
      : line.startsWith("[!]")
        ? "lg-warn"
        : line.startsWith("[+]")
          ? "lg-add"
          : line.startsWith("[>]")
            ? "lg-run"
            : line.startsWith("[~]")
              ? "lg-fix"
              : line.startsWith("[TASK]")
                ? "lg-task"
                : "lg-dim";

function PlanCard({ plan, onApprove, onReject }) {
  const locked = plan.status !== "pending";
  return (
    <div className="row bot">
      <div className="card">
        <div className="tag">
          Kế hoạch — {plan.status === "pending" ? "chờ duyệt" : plan.status}
        </div>
        <h3>{plan.task}</h3>
        <ul className="steps">
          {plan.steps.map((step, index) => (
            <li key={`${index}-${step}`}>
              <span className="n">{index + 1}</span>
              <span className="t">{step}</span>
            </li>
          ))}
        </ul>
        <div className="acts">
          <button
            className="btn ok"
            disabled={locked}
            onClick={() => onApprove(plan)}
          >
            ✅ Đồng ý
          </button>
          <button
            className="btn no"
            disabled={locked}
            onClick={() => onReject(plan)}
          >
            ✕ Từ chối
          </button>
          {plan.planUrl && (
            <a
              className="open"
              href={plan.planUrl}
              target="_blank"
              rel="noreferrer"
            >
              Mở ↗
            </a>
          )}
        </div>
        {plan.logs?.length > 0 && (
          <pre className="logs">
            {plan.logs.map((line, index) => (
              <span className={logClass(line)} key={`${index}-${line}`}>
                {line}
                {"\n"}
              </span>
            ))}
          </pre>
        )}
      </div>
    </div>
  );
}

export default function ConversationPanel({ controller, onInputActivity }) {
  const [input, setInput] = useState("");
  const transcriptRef = useRef(null);
  useEffect(() => {
    onInputActivity?.(Boolean(input.trim()));
    return () => onInputActivity?.(false);
  }, [input, onInputActivity]);
  useEffect(() => {
    const el = transcriptRef.current;
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 140)
      el.scrollTop = el.scrollHeight;
  }, [controller.messages]);
  const submit = () => {
    if (!input.trim()) return;
    controller.send(input);
    setInput("");
  };
  return (
    <>
      <aside
        className="transcript"
        ref={transcriptRef}
        aria-live="polite"
        onWheel={(event) => event.stopPropagation()}
      >
        {controller.messages.map((message) =>
          message.type === "plan" ? (
            <PlanCard
              key={message.id}
              plan={message}
              onApprove={controller.approvePlan}
              onReject={controller.rejectPlan}
            />
          ) : (
            <div className={`row ${message.author}`} key={message.id}>
              <div className="bubble">{message.text}</div>
            </div>
          ),
        )}
        {controller.busy && controller.status === "thinking" && (
          <div className="row bot">
            <div className="bubble">…</div>
          </div>
        )}
      </aside>
      <div className="wakehint" style={{ opacity: controller.hint ? 1 : 0 }}>
        {controller.hint}
      </div>
      <div className="composer">
        <button
          type="button"
          className={`icon ${controller.micOn ? "on" : ""} ${controller.micArmed ? "rec" : ""}`}
          onClick={controller.toggleMic}
          title="Bật nghe rảnh tay"
          aria-label="Bật nghe rảnh tay"
        >
          🎙️
        </button>
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              submit();
            }
          }}
          autoComplete="off"
          aria-label="Tin nhắn"
        />
        <button
          type="button"
          className={`icon ${controller.ttsOn ? "on" : ""}`}
          onClick={controller.toggleTts}
          title="Đọc bằng giọng nói"
          aria-label="Bật hoặc tắt đọc bằng giọng nói"
        >
          🔊
        </button>
        <button
          type="button"
          className="icon send"
          onClick={submit}
          disabled={controller.busy}
          title="Gửi"
          aria-label="Gửi tin nhắn"
        >
          ➤
        </button>
      </div>
    </>
  );
}
