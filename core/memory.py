"""Bộ nhớ cho Agent — hai tầng, lưu trên đĩa (không cần thư viện ngoài).

  • NGẮN HẠN (working):  lịch sử hội thoại của phiên hiện tại — ai nói gì, theo thứ tự.
  • DÀI HẠN (facts):     những điều đáng nhớ (sở thích, thông tin, kết quả task đã làm),
                          lưu bền trong memory/facts.jsonl và gọi lại theo độ liên quan.

Thiết kế theo tinh thần "agent có trí nhớ": mỗi lượt chat được ghi lại, mỗi task xong
sinh ra một "fact"; trước khi gọi LLM, agent nạp phần ký ức LIÊN QUAN vào system prompt.

Contract (dict) đồng nhất với phần còn lại của Agent. Không phụ thuộc thư viện ngoài.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path
from .identity import AGENT_NAME

from . import MEMORY_DIR

_WORD = re.compile(r"[^\W_]+", re.UNICODE)


# ---------------- tiện ích văn bản (tách dấu để khớp tiếng Việt không dấu) ----------------
def _strip_accent(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def _tokens(text: str) -> set[str]:
    base = {w.lower() for w in _WORD.findall(text or "")}
    return base | {_strip_accent(w) for w in base}


def _now() -> float:
    return time.time()


def _stamp(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


class Memory:
    """Trí nhớ của agent. Một instance = một 'não' dùng chung cho các phiên.

    Tham số:
        session:        tên phiên (mặc định 'default') — tách lịch sử theo phiên.
        max_working:    số lượt hội thoại giữ trong RAM cho ngữ cảnh gần.
        persist_chat:   có ghi lịch sử hội thoại xuống đĩa hay không.
    """

    def __init__(self, root: Path | None = None, session: str = "default",
                 max_working: int = 20, persist_chat: bool = True):
        self.root = Path(root or MEMORY_DIR)
        self.session = session
        self.max_working = max_working
        self.persist_chat = persist_chat

        self.facts_path = self.root / "facts.jsonl"
        self.chat_path = self.root / f"chat_{session}.jsonl"

        self._working: list[dict] = []   # [{role, content, ts}]
        self._facts: list[dict] = []      # [{id, text, kind, tags, ts}]
        self._loaded = False

    # ================= nạp / lưu =================
    def load(self) -> "Memory":
        self.root.mkdir(exist_ok=True)
        self._facts = _read_jsonl(self.facts_path)
        # nạp lại vài lượt hội thoại gần nhất của phiên vào working set
        if self.persist_chat:
            turns = _read_jsonl(self.chat_path)
            self._working = turns[-self.max_working:]
        self._loaded = True
        return self

    def _ensure(self):
        if not self._loaded:
            self.load()

    # ================= NGẮN HẠN: hội thoại =================
    def add_turn(self, role: str, content: str) -> None:
        """Ghi một lượt hội thoại (role = 'user' | 'assistant' | 'system')."""
        self._ensure()
        turn = {"role": role, "content": content, "ts": _now()}
        self._working.append(turn)
        if len(self._working) > self.max_working:
            self._working = self._working[-self.max_working:]
        if self.persist_chat:
            _append_jsonl(self.chat_path, turn)

    def history(self, limit: int | None = None) -> list[dict]:
        """Trả các lượt gần nhất dưới dạng [{role, content}] để đưa vào messages."""
        self._ensure()
        turns = self._working if limit is None else self._working[-limit:]
        return [{"role": t["role"], "content": t["content"]} for t in turns]

    def clear_session(self) -> None:
        """Xoá lịch sử hội thoại của phiên hiện tại (giữ nguyên facts dài hạn)."""
        self._working = []
        if self.chat_path.exists():
            self.chat_path.unlink()

    # ================= DÀI HẠN: facts =================
    def remember(self, text: str, kind: str = "note", tags=None) -> dict:
        """Lưu một điều đáng nhớ. kind: 'note' | 'preference' | 'task' | 'skill' ...

        Chống trùng: nếu đã có fact gần như y hệt thì cập nhật thời gian thay vì thêm mới.
        """
        self._ensure()
        text = (text or "").strip()
        if not text:
            return {}
        norm = _strip_accent(text.lower())
        for f in self._facts:
            if _strip_accent(f["text"].lower()) == norm:
                f["ts"] = _now()
                _rewrite_jsonl(self.facts_path, self._facts)
                return f
        fact = {
            "id": f"m{int(_now()*1000)}",
            "text": text,
            "kind": kind,
            "tags": list(tags or []),
            "ts": _now(),
        }
        self._facts.append(fact)
        _append_jsonl(self.facts_path, fact)
        return fact

    def forget(self, fact_id: str) -> bool:
        self._ensure()
        n = len(self._facts)
        self._facts = [f for f in self._facts if f.get("id") != fact_id]
        if len(self._facts) != n:
            _rewrite_jsonl(self.facts_path, self._facts)
            return True
        return False

    def all_facts(self) -> list[dict]:
        self._ensure()
        return list(self._facts)

    def recall(self, query: str, k: int = 5) -> list[dict]:
        """Trả tối đa k fact liên quan nhất tới `query` (chấm điểm lexical + ưu tiên mới)."""
        self._ensure()
        qt = _tokens(query)
        if not self._facts:
            return []
        scored = []
        newest = max((f["ts"] for f in self._facts), default=_now())
        oldest = min((f["ts"] for f in self._facts), default=newest)
        span = max(1.0, newest - oldest)
        for f in self._facts:
            ft = _tokens(f["text"]) | _tokens(" ".join(f.get("tags", [])))
            overlap = len(qt & ft) / max(1, len(qt)) if qt else 0.0
            recency = (f["ts"] - oldest) / span      # 0..1, mới hơn = cao hơn
            score = overlap + 0.15 * recency
            if overlap > 0 or not qt:
                scored.append((score, f))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:k]]

    # ================= ngữ cảnh cho prompt =================
    def context_block(self, query: str = "", k_facts: int = 5,
                      n_history: int = 6) -> str:
        """Dựng một khối text 'ký ức' để chèn vào system prompt.

        Gồm: các fact liên quan (nếu có query) + tóm tắt vài lượt hội thoại gần đây.
        Trả chuỗi rỗng nếu không có gì đáng đưa vào.
        """
        self._ensure()
        parts: list[str] = []

        facts = self.recall(query, k=k_facts) if query else self._facts[-k_facts:]
        if facts:
            lines = [f"- [{f['kind']}] {f['text']}" for f in facts]
            parts.append("KÝ ỨC LIÊN QUAN:\n" + "\n".join(lines))

        hist = self.history(limit=n_history)
        # bỏ lượt cuối nếu nó chính là câu user hiện tại (tránh lặp)
        convo = [h for h in hist if h["role"] in ("user", "assistant")]
        if convo:
            lines = [f"{'Bạn' if h['role']=='user' else AGENT_NAME}: {h['content']}" for h in convo]
            parts.append("HỘI THOẠI GẦN ĐÂY:\n" + "\n".join(lines))

        return "\n\n".join(parts)


# ---------------- I/O JSONL an toàn ----------------
def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue  # bỏ dòng hỏng, không làm sập
    return out


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _rewrite_jsonl(path: Path, objs: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for o in objs:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
