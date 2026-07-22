"""SkillAgent — bộ điều phối chính.

  handle_message(text) -> model CHAT: phân loại trò chuyện / tác vụ; nếu tác vụ thì lập KẾ HOẠCH.
  execute_task(task)   -> model WORK: (tách bước nếu tác vụ ghép) → tìm/sinh skill → KIỂM THỬ
                          → chạy → TỰ PHỤC HỒI (cài thư viện/công cụ thiếu, tự điền tham số,
                          hỏi lại nếu bí) → báo kết quả.
"""
from __future__ import annotations
import json
import os
import re
import time
from pathlib import Path

from . import SKILLS_DIR, planner
from . import autoinstall
from . import tools as tools_mod
from .config import Config
from .generator import generate, fix, validate, GeneratorError
from .llm import LLM, extract_json
from .identity import AGENT_NAME
from .memory import Memory
from .registry import Registry
from .runner import run_skill

_CLASSIFY_SYS = (
    "QUY TAC PHAN LOAI UU TIEN: chi chon task khi nguoi dung dang ra lenh de agent THUC HIEN mot hanh dong cu the. "
    "Neu co nghi ngo, chon chat va hoi lai mot cau ngan; khong tu y lap ke hoach hay sinh skill.\n"
    "- task: co dong tu menh lenh ro rang + ket qua/hanh dong can lam, vi du: 'mo Chrome', 'liet ke file trong thu muc', "
    "'doi ten anh A thanh B', 'tai video nay', 'tao bao cao PDF'. Cac yeu cau thao tac may tinh, file, trinh duyet, du lieu, "
    "tao/chuyen doi noi dung deu la task neu nguoi dung muon BAN thuc hien ngay.\n"
    "- chat: chao hoi, tranh luan, y kien, hoi thong tin, nho giai thich, so sanh, huong dan, de xuat, hoac hoi kha nang. "
    "Cac cau nhu 'Chrome co lam duoc gi?', 'lam sao de mo Chrome?', 'ban nghi gi ve X?', 'hay giai thich...', "
    "'co model nao mien phi?' la chat, KHONG phai task.\n"
    "- remember: chi khi nguoi dung noi ro muon luu/ghi nho mot thong tin cho cac lan sau.\n"
    "Vi du phan biet: 'Mo google.com' -> task; 'Huong dan toi mo google.com' -> chat; "
    "'Toi muon xu ly video, nen bat dau the nao?' -> chat; 'Trich am thanh tu video X.mp4' -> task.\n"
    "Voi chat, tra loi truc tiep, ngan gon va KHONG de xuat ke hoach thao tac tru khi nguoi dung yeu cau.\n\n"
    f"Bạn là {AGENT_NAME}, trợ lý AI tự sinh kỹ năng. Bạn CÓ BỘ NHỚ DÀI HẠN lưu trên đĩa — "
    "TUYỆT ĐỐI KHÔNG nói rằng bạn không thể ghi nhớ. Với mỗi tin nhắn, phân loại:\n"
    '- "remember": người dùng muốn bạn GHI NHỚ một thông tin lâu dài (đường dẫn, sở thích, quy ước...).\n'
    '- "task": yêu cầu thao tác với tệp/ảnh/video/âm thanh/dữ liệu, tải, chuyển đổi, tạo ra thứ gì đó...\n'
    '- "chat": trò chuyện, chào hỏi, hỏi đáp thông tin.\n'
    'Trả về DUY NHẤT JSON: {"type": "chat" | "task" | "remember", '
    '"reply": "<nếu chat: câu trả lời tiếng Việt, thân thiện, ngắn gọn>", '
    '"task": "<nếu task: mô tả tác vụ ngắn gọn>", '
    '"fact": "<nếu remember: điều cần nhớ, viết thành MỘT câu đầy đủ tự chứa — thay đại từ '
    "'này/đó' bằng thông tin cụ thể lấy từ hội thoại gần đây>\"}"
)

_PLAN_SYS = (
    "Bạn lập kế hoạch thực thi cho một tác vụ của agent tự sinh kỹ năng. "
    "Chia thành các bước NHỎ, mỗi bước MỘT việc đơn nhất mà một skill nhỏ làm được "
    "(việc lớn thì 5-8 bước, việc đơn giản thì 1-2 bước). Tiếng Việt, ngắn gọn. "
    'Trả DUY NHẤT JSON: {"steps": ["bước 1", "bước 2", ...]}'
)

_DECOMPOSE_SYS = (
    "Bạn tách một yêu cầu thành các BƯỚC ĐƠN GIẢN, tuần tự. NGUYÊN TẮC QUAN TRỌNG: "
    "một việc lớn PHẢI chia thành nhiều việc nhỏ — mỗi bước là MỘT việc đơn nhất mà một skill "
    "nhỏ có thể làm; KHÔNG cố giải quyết cả khối việc lớn trong 1 bước/1 skill. "
    "Ví dụ 'tạo biên bản cuộc họp từ video' phải tách thành: "
    '["Tách âm thanh từ video ra file wav", "Chuyển âm thanh thành văn bản (phụ đề/transcript)", '
    '"Đọc và phân tích văn bản transcript", "Tổng hợp nội dung thành biên bản cuộc họp", '
    '"Xuất biên bản ra file PDF"]. '
    "Chỉ trả đúng 1 bước khi yêu cầu THẬT SỰ là một thao tác đơn (vd: liệt kê file, đổi tên tệp). "
    'Trả DUY NHẤT JSON: {"steps": ["bước 1", "bước 2", ...]}'
)

_VIDEO_EXT = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v", ".wmv")
_AUDIO_EXT = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus")
_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff")

# công cụ hệ thống hay gặp + id cài trên Windows (winget)
_SYS_TOOLS = ("ffmpeg", "ffprobe", "yt-dlp", "youtube-dl", "tesseract", "pandoc", "magick", "git")
_NOTFOUND = ("not found", "no such file", "not recognized", "command not found",
             "winerror 2", "errno 2", "not installed")
_WINGET_ID = {
    "ffmpeg": "Gyan.FFmpeg", "ffprobe": "Gyan.FFmpeg", "yt-dlp": "yt-dlp.yt-dlp",
    "tesseract": "UB-Mannheim.TesseractOCR", "pandoc": "JohnMacFarlane.Pandoc",
    "magick": "ImageMagick.ImageMagick", "git": "Git.Git",
}


def _summarize(result: dict, limit: int = 400) -> str:
    val = result.get("result", result.get("error", ""))
    if not isinstance(val, str):
        val = json.dumps(val, ensure_ascii=False)
    return val if len(val) <= limit else val[:limit] + "…"


def _is_output(name: str) -> bool:
    n = (name or "").lower()
    return any(w in n for w in ("output", "out_", "_out", "save", "dest", "target", "ket_qua", "ketqua"))


def _missing_package(error: str):
    """Nhận diện THƯ VIỆN PYTHON còn thiếu (contract 'pip install X' hoặc ImportError).

    Đã map tên module -> tên gói pip (vd cv2 -> opencv-python). Xem core/autoinstall.py.
    """
    return autoinstall.missing_package(error)


def _looks_notfound(error: str) -> bool:
    low = (error or "").lower()
    return any(s in low for s in _NOTFOUND)


def _missing_tool(error: str):
    """Nhận diện CÔNG CỤ HỆ THỐNG còn thiếu (vd ffmpeg) từ thông báo lỗi."""
    if not error or not _looks_notfound(error):
        return None
    low = error.lower()
    for t in _SYS_TOOLS:
        if t in low:
            return t
    return None


def _guess_exe_from_params(error: str, params: dict):
    """Lỗi not-found KHÔNG nêu tên file (vd WinError 2) → đoán executable từ tham số lệnh."""
    if not _looks_notfound(error):
        return None
    import shutil
    for k, v in (params or {}).items():
        if not isinstance(v, str) or not v.strip():
            continue
        if not any(w in k.lower() for w in ("command", "cmd", "args", "lenh")):
            continue
        head = os.path.basename(v.strip().split()[0]).lower()
        if head.endswith(".exe"):
            head = head[:-4]
        if re.match(r"^[a-z0-9_+.-]{2,}$", head) and not shutil.which(head):
            return head
    return None


class _CtxLLM:
    """Proxy bọc LLM trong lúc chạy task: TỰ CHÈN bối cảnh toàn cục (mục tiêu gốc +
    diễn biến các bước/lỗi đến giờ) vào MỌI request, để model luôn có cái nhìn toàn cảnh
    thay vì chỉ thấy một lát cắt hẹp. Context lớn của DeepSeek/Claude/GPT chứa thoải mái."""

    def __init__(self, llm, get_block):
        self._llm = llm
        self._get = get_block

    @property
    def config(self):
        return self._llm.config

    def _inject(self, messages):
        blk = self._get()
        if not blk:
            return messages
        return ([{"role": "system",
                  "content": "=== BỐI CẢNH TOÀN CỤC (tự động đính kèm) ===\n" + blk}]
                + list(messages))

    def complete(self, messages, **kw):
        return self._llm.complete(self._inject(messages), **kw)

    def complete_json(self, messages, **kw):
        return self._llm.complete_json(self._inject(messages), **kw)


class SkillAgent:
    CTX_BUDGET = 12000  # số ký tự log diễn biến tối đa đính kèm mỗi request
    MAX_FIX = 0       # 0 = sửa skill mới TỚI KHI ĐƯỢC; chỉ dừng khi lỗi lặp y hệt (hết tiến triển)
    FIX_STALL = 2     # số lần sửa liên tiếp mà lỗi không đổi thì dừng
    MAX_RECOVER = 4   # số vòng tự phục hồi khi skill chạy lỗi

    def __init__(self, config: Config | None = None, memory: Memory | None = None,
                 session: str = "default"):
        self.config = config or Config.load()
        self.llm = LLM(self.config)
        self.registry = Registry().load()
        self.memory = (memory or Memory(session=session)).load()

    # ============ TOOL kiểu Hermes ============
    def tool_schemas(self) -> list[dict]:
        self.registry.load()
        return tools_mod.registry_to_schemas(self.registry)

    def tools_prompt(self) -> str:
        return tools_mod.hermes_system_prompt(self.tool_schemas())

    # ============ MODEL CHAT ============
    def handle_message(self, text: str) -> dict:
        sys_content = _CLASSIFY_SYS
        ctx = self.memory.context_block(text)
        if ctx:
            sys_content = _CLASSIFY_SYS + "\n\n--- BỐI CẢNH ĐÃ GHI NHỚ ---\n" + ctx

        self.memory.add_turn("user", text)

        try:
            data = self.llm.complete_json(
                [{"role": "system", "content": sys_content},
                 {"role": "user", "content": text}],
                role="chat", purpose="classify", temperature=0.2, max_tokens=400)
        except Exception as e:
            return {"mode": "chat", "reply": f"(Lỗi model chat: {e})"}

        data = data or {}
        if data.get("type") == "remember":
            fact = (data.get("fact") or text).strip()
            self.memory.remember(fact, kind="preference")
            reply = f"Đã ghi nhớ: {fact}"
            self.memory.add_turn("assistant", reply)
            return {"mode": "chat", "reply": reply, "remembered": True}

        if data.get("type") == "task":
            task = data.get("task") or text
            steps = self._plan(task)
            path = planner.render_plan_html(task, steps)
            self.memory.add_turn("assistant", f"(kế hoạch cho tác vụ: {task})")
            return {"mode": "plan", "task": task, "steps": steps,
                    "plan_file": path.name, "plan_url": f"/plans/{path.name}"}

        reply = data.get("reply") or f"Mình nghe đây, bạn cần {AGENT_NAME} giúp gì?"
        self.memory.add_turn("assistant", reply)
        return {"mode": "chat", "reply": reply}

    def _plan(self, task: str) -> list[str]:
        try:
            data = self.llm.complete_json(
                [{"role": "system", "content": _PLAN_SYS},
                 {"role": "user", "content": f"Tác vụ: {task}"}],
                role="chat", purpose="plan", temperature=0.3, max_tokens=500)
            steps = (data or {}).get("steps")
            if isinstance(steps, list) and steps:
                return [str(s) for s in steps]
        except Exception:
            pass
        return [
            f"Phân tích yêu cầu: {task}",
            "Tách thành các bước nếu là tác vụ ghép",
            "Với mỗi bước: tìm/sinh skill, kiểm thử, tự điền tham số, chạy — tự phục hồi nếu lỗi",
            "Tổng hợp kết quả rồi báo cáo",
        ]

    # ============ MODEL WORK: điều phối ============
    MAX_ROUNDS = 0   # 0 = KHÔNG giới hạn vòng "chạy → nghiệm thu → lập kế hoạch lại"
    MAX_STALL = 3    # nhưng dừng nếu N vòng liên tiếp không có tiến triển mới

    def execute_task(self, task: str, log=None, steps=None) -> dict:
        logs: list[str] = []

        def _log(msg: str):
            logs.append(msg)
            if log:
                log(msg)

        _log("=" * 60)
        _log(f"[TASK] {task}")
        _log("=" * 60)

        # bọc LLM: mọi request trong task này đều được đính kèm bối cảnh toàn cục
        llm_orig = self.llm
        if not isinstance(self.llm, _CtxLLM):
            self.llm = _CtxLLM(llm_orig, lambda: self._ctx_block(task, logs))
        try:
            return self._execute_rounds(task, steps, _log, logs)
        finally:
            self.llm = llm_orig

    def _ctx_block(self, task: str, logs: list) -> str:
        body = "\n".join(logs)
        if len(body) > self.CTX_BUDGET:
            body = "…(cắt bớt phần đầu)\n" + body[-self.CTX_BUDGET:]
        try:
            mem = self.memory.context_block(task, k_facts=5, n_history=0)
        except Exception:
            mem = ""
        return (f"MỤC TIÊU GỐC của người dùng: {task}\n"
                + (mem + "\n" if mem else "")
                + f"DIỄN BIẾN ĐẾN GIỜ (log thực thi, mới nhất ở cuối):\n{body}")

    def _execute_rounds(self, task, steps, _log, logs) -> dict:
        feedback = ""
        res: dict = {}
        rnd = 0
        stall = 0
        last_sig = None
        while True:
            rnd += 1
            if self.MAX_ROUNDS and rnd > self.MAX_ROUNDS:
                _log(f"[✗] Chạm giới hạn {self.MAX_ROUNDS} vòng.")
                break

            attempt = task if not feedback else (
                f"{task}\n(Lần thử trước CHƯA ĐẠT, rút kinh nghiệm: {feedback})")
            if rnd > 1:
                _log("=" * 60)
                _log(f"[VÒNG {rnd}] Lập kế hoạch lại và thử cách khác...")

            plan_steps = [str(s).strip() for s in (steps or []) if str(s).strip()]
            if rnd == 1 and len(plan_steps) > 1:
                # vòng đầu: thực thi ĐÚNG các bước trong kế hoạch người dùng đã duyệt
                subtasks = plan_steps
                _log(f"[i] Thực thi theo {len(subtasks)} bước của kế hoạch đã duyệt.")
            else:
                subtasks = self._decompose(attempt, _log)
            if len(subtasks) <= 1:
                res = self._run_single(attempt, _log, logs)
            else:
                res = self._run_pipeline(attempt, subtasks, _log, logs)

            if res.get("needs_input"):          # cần hỏi người dùng → dừng chờ
                return res

            verdict = self._goal_check(task, res, _log)
            if verdict.get("achieved"):
                return res
            feedback = (verdict.get("feedback") or str(res.get("error") or "")
                        or "kết quả chưa đạt mục tiêu")[:300]
            _log(f"[~] MỤC TIÊU CHƯA ĐẠT: {feedback[:150]}")

            # phát hiện GIẬM CHÂN TẠI CHỖ: skill + kết quả + lỗi y hệt vòng trước
            # (KHÔNG so feedback — LLM nghiệm thu mỗi lần diễn đạt lại một kiểu)
            sig = (res.get("skill"), str(res.get("result"))[:200],
                   str(res.get("error"))[:200])
            if sig == last_sig:
                stall += 1
                if stall >= self.MAX_STALL - 1:
                    _log(f"[✗] Dừng: {self.MAX_STALL} vòng liên tiếp không có tiến triển mới.")
                    break
            else:
                stall = 0
            last_sig = sig

        res["success"] = False
        res.setdefault("error", f"Chưa hoàn thành mục tiêu sau {rnd} vòng: {feedback}")
        return res

    def _step_check(self, step: str, res: dict, _log) -> dict:
        """Kiểm tra kết quả một BƯỚC: skill vừa chạy có thực sự làm đúng việc của bước không.

        Đọc cả mô tả skill để phát hiện dùng nhầm skill (vd bước 'trích âm thanh' mà chạy list_files).
        """
        name = res.get("skill") or ""
        entry = self.registry.get(name)
        desc = (entry["meta"].get("description", "") if entry else "")
        out = res.get("result")
        if not isinstance(out, str):
            out = json.dumps(out, ensure_ascii=False, default=str)
        sys_p = ("Bạn kiểm tra MỘT BƯỚC trong pipeline của agent. Cho biết skill vừa chạy có "
                 "THỰC SỰ thực hiện đúng việc của bước không — hay nó làm việc KHÁC (vd bước yêu "
                 "cầu trích xuất âm thanh nhưng skill chỉ liệt kê file). "
                 'Trả DUY NHẤT JSON: {"achieved": true|false, "reason": "<nếu sai: skill này làm gì, còn thiếu gì>"}')
        user_p = (f"Bước cần làm: {step}\n"
                  f"Skill đã chạy: {name} — mô tả: {desc}\n"
                  f"Kết quả trả về: {out[:600]}")
        try:
            data = self.llm.complete_json(
                [{"role": "system", "content": sys_p},
                 {"role": "user", "content": user_p}], role="work", purpose="verify")
            if isinstance(data, dict) and "achieved" in data:
                return {"achieved": bool(data["achieved"]),
                        "feedback": str(data.get("reason", ""))}
        except Exception as e:
            _log(f"[!] Lỗi verify bước: {e} → tạm chấp nhận kết quả bước.")
        return {"achieved": True}

    def _goal_check(self, task: str, res: dict, _log) -> dict:
        """Đối chiếu KẾT QUẢ với MỤC TIÊU. Trả {"achieved": bool, "feedback": str}."""
        if not res.get("success"):
            return {"achieved": False, "feedback": str(res.get("error", ""))[:300]}
        if not self._llm_ready():
            _log("[i] Không có LLM để nghiệm thu → tạm chấp nhận kết quả.")
            return {"achieved": True}
        summary = _summarize(res if isinstance(res.get("result"), str) else
                             {"result": json.dumps(res.get("result"), ensure_ascii=False, default=str)}, 600)
        done = res.get("done") or []
        steps_txt = "\n".join(f"- B{d.get('step')}: {d.get('task')} → "
                              f"{'OK' if d.get('success') else 'LỖI'}" for d in done)
        sys_p = ("Bạn KIỂM TRA nghiệm thu: kết quả bên dưới đã HOÀN THÀNH mục tiêu chưa? "
                 "Khắt khe nhưng công bằng: nếu sản phẩm đầu ra người dùng cần đã được tạo đúng "
                 "thì đạt; nếu mới xong bước trung gian hoặc kết quả rỗng/vô nghĩa thì chưa đạt. "
                 'Trả DUY NHẤT JSON: {"achieved": true|false, '
                 '"reason": "<nếu chưa đạt: còn thiếu gì và nên làm gì tiếp>"}')
        user_p = (f"Mục tiêu: {task}\n"
                  + (f"Các bước đã chạy:\n{steps_txt}\n" if steps_txt else "")
                  + f"Kết quả cuối: {summary}")
        try:
            data = self.llm.complete_json(
                [{"role": "system", "content": sys_p},
                 {"role": "user", "content": user_p}], role="work", purpose="verify")
            if isinstance(data, dict) and "achieved" in data:
                ok = bool(data["achieved"])
                if ok:
                    _log("[✓] Nghiệm thu: mục tiêu đã hoàn thành.")
                else:
                    _log(f"[~] Nghiệm thu: CHƯA ĐẠT — {str(data.get('reason', ''))[:150]}")
                return {"achieved": ok, "feedback": str(data.get("reason", ""))}
            _log("[!] Nghiệm thu không kết luận được → coi như CHƯA đạt.")
            return {"achieved": False, "feedback": "bộ nghiệm thu không kết luận được"}
        except Exception as e:
            # KHÔNG im lặng chấp nhận: lỗi nghiệm thu = chưa đạt (stall-detector sẽ chặn lặp vô ích)
            _log(f"[!] Lỗi khi nghiệm thu: {e} → coi như CHƯA đạt.")
            return {"achieved": False, "feedback": f"không nghiệm thu được: {e}"}

    # ---------- tách tác vụ ghép thành nhiều bước ----------
    def _decompose(self, task, _log) -> list[str]:
        # LUÔN hỏi LLM (nếu có): việc lớn phải được chia thành nhiều bước nhỏ,
        # kể cả khi câu lệnh không có từ nối ("tạo biên bản từ video" vẫn là việc ghép).
        if not self._llm_ready():
            return [task]
        try:
            data = self.llm.complete_json(
                [{"role": "system", "content": _DECOMPOSE_SYS},
                 {"role": "user", "content": f"Yêu cầu: {task}"}],
                role="work", purpose="decompose", temperature=0.2, max_tokens=500)
            steps = (data or {}).get("steps")
            if isinstance(steps, list):
                steps = [str(s).strip() for s in steps if str(s).strip()]
                if len(steps) >= 2:
                    _log(f"[i] Tách tác vụ thành {len(steps)} bước.")
                    return steps
        except Exception:
            pass
        return [task]

    # ---------- chạy pipeline nhiều bước ----------
    def _run_pipeline(self, task, subtasks, _log, logs) -> dict:
        _log(f"[i] Chạy pipeline {len(subtasks)} bước.")
        done = []
        prev_ctx = ""
        for i, st in enumerate(subtasks, 1):
            _log("-" * 60)
            _log(f"[BƯỚC {i}/{len(subtasks)}] {st}")
            res = self._run_single(st, _log, logs, context=prev_ctx)

            # VERIFY TỪNG BƯỚC: chạy "thành công" chưa đủ — kết quả phải ĐÚNG VIỆC của bước
            if res.get("success") and self._llm_ready():
                chk = self._step_check(st, res, _log)
                if not chk.get("achieved"):
                    why = str(chk.get("feedback", ""))[:200]
                    _log(f"[~] Bước {i} chạy xong nhưng SAI VIỆC ({why}) → bỏ skill cũ, sinh skill mới cho bước này...")
                    res = self._run_single(f"{st}\n(Chú ý: {why})", _log, logs,
                                           context=prev_ctx, force_new=True)
                    if res.get("success"):
                        chk = self._step_check(st, res, _log)
                        if not chk.get("achieved"):
                            res = {**res, "success": False,
                                   "error": f"Kết quả bước {i} vẫn không đúng việc: {chk.get('feedback', '')}"}

            out = res.get("result") or res.get("error") or ""
            if not isinstance(out, str):
                out = json.dumps(out, ensure_ascii=False)
            prev_ctx = f"(Kết quả bước trước — dùng tên tệp/giá trị THẬT từ đây, không bịa: {out[:500]})"
            done.append({"step": i, "task": st, "skill": res.get("skill"),
                         "success": res.get("success"), "result": res.get("result"),
                         "error": res.get("error")})
            if res.get("needs_input"):
                res.update({"pipeline": True, "pipeline_step": i,
                            "steps_total": len(subtasks), "done": done})
                return res
            if not res.get("success"):
                _log(f"[✗] Pipeline dừng ở bước {i}/{len(subtasks)}.")
                return {"success": False, "pipeline": True, "pipeline_step": i,
                        "steps_total": len(subtasks), "skill": res.get("skill"),
                        "params": res.get("params"), "result": None,
                        "error": f"Dừng ở bước {i}: {res.get('error')}",
                        "done": done, "generated": False, "logs": logs}
        _log(f"[✓] Hoàn tất pipeline {len(subtasks)} bước.")
        last = done[-1] if done else {}
        summary = " | ".join(f"B{d['step']}: {d['skill']}" for d in done)
        return {"success": True, "pipeline": True, "steps_total": len(subtasks),
                "skill": last.get("skill"), "params": {},
                "result": f"Hoàn tất {len(subtasks)} bước — {summary}",
                "error": None, "done": done, "generated": False, "logs": logs}

    # ---------- chạy MỘT tác vụ đơn ----------
    def _run_single(self, task, _log, logs, context: str = "", force_new: bool = False) -> dict:
        """Lưới an toàn: bug nội bộ của Agent cũng chỉ làm bước này thất bại
        (để vòng phục hồi/lập kế hoạch lại xử lý tiếp), không giết cả task."""
        import traceback
        try:
            return self._run_single_inner(task, _log, logs, context, force_new)
        except Exception:
            tb = traceback.format_exc(limit=5).strip()
            _log(f"[✗] LỖI NỘI BỘ khi chạy bước: {tb.splitlines()[-1]}")
            return {"success": False, "skill": None, "generated": False, "params": {},
                    "result": None, "error": f"Lỗi nội bộ {AGENT_NAME}: {tb}", "logs": logs}

    def _run_single_inner(self, task, _log, logs, context: str = "", force_new: bool = False) -> dict:
        self.registry.load()
        _log(f"[i] Có {self.registry.count()} skill trong registry")

        # tìm skill theo TASK gốc; còn rút tham số thì kèm bối cảnh bước trước
        task_ctx = f"{task}\n{context}" if context else task

        if not force_new:
            name = self.registry.find(task, self.llm, role="work")
            if name:
                _log(f"[✓] Match skill: {name}")
                return self._run_existing(task_ctx, name, _log, logs)

            recalled = self._recall_skill(task)
            # gợi ý từ bộ nhớ CHỈ được dùng nếu skill đó thật sự liên quan tới việc hiện tại
            if recalled and not self._recall_relevant(task, recalled):
                _log(f"[i] Bộ nhớ gợi ý '{recalled}' nhưng KHÔNG liên quan bước này → bỏ qua, sinh skill mới.")
                recalled = None
            if recalled:
                _log(f"[i] Bộ nhớ gợi ý: tái dùng skill '{recalled}' (đã dùng cho việc tương tự)")
                return self._run_existing(task_ctx, recalled, _log, logs)

        _log("[!] Không có skill phù hợp → đang sinh skill mới...")
        try:
            gen = generate(task, self.llm, taken=self.registry.names(), role="work")
        except (GeneratorError, Exception) as e:
            _log(f"[✗] Sinh skill thất bại: {e}")
            return {"success": False, "error": str(e), "logs": logs,
                    "skill": None, "generated": False, "params": {}}
        name = gen["name"]
        _log(f"[+] Skill mới được sinh: skills/{gen['filename']}")

        ok, params, result = self._test_new_skill(task_ctx, name, _log)
        if not ok:
            self._remove_skill(name, _log)
            self.memory.remember(
                f"Skill sinh cho tác vụ \"{task}\" không đạt kiểm thử, đã gỡ bỏ.",
                kind="note", tags=[])
            return {"success": False, "skill": None, "generated": True,
                    "params": params or {}, "result": None,
                    "error": "Skill mới không vượt qua kiểm thử (đã gỡ bỏ).", "logs": logs}

        entry = self.registry.get(name)
        desc = entry["meta"].get("description", "") if entry else ""
        tags = list((entry["meta"].get("tags", []) if entry else [])) + [name]
        self.memory.remember(f"Skill '{name}': {desc}", kind="skill", tags=tags)

        if not result.get("success") and entry is not None:
            schema = self._param_schema(entry)
            result, params, asked = self._recover(task_ctx, name, entry, schema, params, result, _log, logs, True)
            if asked is not None:
                return asked
        return self._finish(task, name, True, params, result, _log, logs)

    # ---------- chạy skill đã có ----------
    def _run_existing(self, task, name, _log, logs) -> dict:
        entry = self.registry.get(name)
        if entry is None:
            result = {"success": False,
                      "error": self.registry.load_errors.get(f"{name}.py", "Skill không import được")}
            return self._finish(task, name, False, {}, result, _log, logs)

        schema = self._param_schema(entry)
        params = self.registry.extract_params(task, name, self.llm, role="work", schema=schema)
        params = self._self_fill(task, name, schema, params, "", use_llm=False)
        _log(f"[i] Params: {json.dumps(params, ensure_ascii=False)}")
        _log("[>] Đang chạy skill...")
        result = run_skill(entry, params)

        if not result.get("success"):
            result, params, asked = self._recover(task, name, entry, schema, params, result, _log, logs, False)
            if asked is not None:
                return asked
        return self._finish(task, name, False, params, result, _log, logs)

    # ---------- TỰ PHỤC HỒI ----------
    def _recover(self, task, name, entry, schema, params, result, _log, logs, generated):
        """Cài thư viện/công cụ thiếu, tự điền tham số, thử lại; thiếu param bắt buộc thì hỏi lại.

        Trả (result, params, asked). asked != None nghĩa là cần hỏi người dùng.
        """
        tried = set()
        for _ in range(self.MAX_RECOVER):
            err = str(result.get("error", ""))

            # 1) thiếu THƯ VIỆN python -> pip install
            pkg = _missing_package(err)
            if pkg and ("pip:" + pkg.lower()) not in tried:
                tried.add("pip:" + pkg.lower())
                _log(f"[~] Skill cần thư viện '{pkg}' → tự cài (pip install {pkg})...")
                if self._pip_install(pkg, _log):
                    _log("[>] Đã cài xong, thử lại...")
                    result = run_skill(entry, params)
                    if result.get("success"):
                        _log("[✓] Tự khắc phục thành công.")
                        break
                    continue
                _log(f"[!] Cài '{pkg}' không thành.")

            # 2) thiếu CÔNG CỤ hệ thống -> tìm cục bộ / winget/brew/apt
            # lỗi not-found không nêu tên (WinError 2) -> đoán từ params rồi từ code skill
            tool = _missing_tool(err)
            if not tool and _looks_notfound(err):
                tool = _guess_exe_from_params(err, params) or self._tool_from_code(entry)
                if tool:
                    _log(f"[~] Lỗi không nêu tên file thiếu → đoán là công cụ '{tool}'.")
            if tool and ("sys:" + tool.lower()) not in tried:
                tried.add("sys:" + tool.lower())
                _log(f"[~] Skill cần công cụ hệ thống '{tool}' → thử tự cài...")
                if self._install_system_tool(tool, _log):
                    _log("[>] Đã cài công cụ, thử lại...")
                    result = run_skill(entry, params)
                    if result.get("success"):
                        _log("[✓] Tự khắc phục thành công.")
                        break
                    continue
                _log(f"[!] Không tự cài được '{tool}' — cần cài thủ công ở mức hệ điều hành.")

            # 3) thiếu THAM SỐ -> tự điền / hỏi lại
            _log(f"[~] Skill lỗi → tự đọc lại skill & tìm cách khắc phục... ({err[:80]})")
            new_params = self._self_fill(task, name, schema, params, err, use_llm=True, _log=_log)
            missing = [k for k, s in schema.items()
                       if s.get("required") and not _is_output(k) and not new_params.get(k)]
            if missing:
                ask = self._ask_message(name, schema, missing)
                _log(f"[?] Thiếu thông tin bắt buộc: {', '.join(missing)} → hỏi lại người dùng.")
                asked = {"success": False, "skill": name, "generated": generated,
                         "params": new_params, "result": None, "error": ask,
                         "needs_input": missing, "ask": ask, "logs": logs}
                return result, new_params, asked

            if new_params != params:
                params = new_params
                _log(f"[>] Thử lại với: {json.dumps(params, ensure_ascii=False)}")
                result = run_skill(entry, params)
                if result.get("success"):
                    _log("[✓] Tự khắc phục thành công.")
                    break
                continue

            # 4) hết rule → nhờ LLM ĐỌC CODE + LỖI để chẩn đoán cách sửa
            # mọi lỗi đều được LLM xem (tối đa 3 lượt); LLM biết những gì đã thử để đổi hướng
            n_diag = sum(1 for t in tried if t.startswith("diag"))
            if self._llm_ready() and n_diag < 3:
                tried.add(f"diag{n_diag}")
                fixed, result, params, entry = self._apply_diagnosis(
                    task, name, entry, params, err, _log, tried)
                if fixed:
                    if result.get("success"):
                        _log("[✓] Tự khắc phục thành công (theo chẩn đoán).")
                        break
                    continue

            _log("[~] Không suy thêm được cách khắc phục → dừng.")
            break

        return result, params, None

    # ---------- chẩn đoán lỗi bằng LLM (đọc code + lỗi) ----------
    def _apply_diagnosis(self, task, name, entry, params, err, _log, tried=None):
        """Nhờ LLM đọc code skill + tham số + lỗi, chọn 1 cách sửa rồi áp dụng.

        Trả (đã_thử: bool, result, params, entry)."""
        diag = self._diagnose(task, name, entry, params, err, tried, _log) or {}
        act = diag.get("action") or ""
        if tried is not None and act:
            tried.add("act:" + act)  # để lượt chẩn đoán sau biết cách này đã thử
        _log(f"[~] Chẩn đoán: {act or '(không rõ)'} — {str(diag.get('reason', ''))[:120]}")

        if act == "install_package" and diag.get("package"):
            if self._pip_install(str(diag["package"]), _log):
                return True, run_skill(entry, params), params, entry
        elif act == "install_tool" and diag.get("tool"):
            if self._install_system_tool(str(diag["tool"]), _log):
                return True, run_skill(entry, params), params, entry
        elif act == "params" and isinstance(diag.get("params"), dict) and diag["params"]:
            params = {**params, **diag["params"]}
            _log(f"[>] Thử lại với tham số chẩn đoán: {json.dumps(params, ensure_ascii=False)}")
            return True, run_skill(entry, params), params, entry
        elif act == "fix_code":
            new_entry = self._try_fix_code(task, name, entry, err, _log)
            if new_entry:
                return True, run_skill(new_entry, params), params, new_entry
        elif act in ("new_skill", "write_code"):
            # LLM quyết định VIẾT CODE MỚI thay vì sửa skill cũ
            try:
                gen = generate(task, self.llm, taken=self.registry.names(), role="work")
                self.registry.load()
                e = self.registry.get(gen["name"])
                if e:
                    schema = self._param_schema(e)
                    p = self.registry.extract_params(task, gen["name"], self.llm,
                                                     role="work", schema=schema)
                    p = self._self_fill(task, gen["name"], schema, p, "", use_llm=False)
                    _log(f"[+] Viết skill mới '{gen['name']}' theo chẩn đoán, chạy thử...")
                    return True, run_skill(e, p), p, e
            except Exception as e:
                _log(f"[!] Viết skill mới không thành: {e}")
        return False, {"success": False, "error": err}, params, entry

    def _diagnose(self, task, name, entry, params, error, tried=None, _log=None) -> dict:
        _log = _log or (lambda m: None)
        try:
            code = Path(entry["path"]).read_text(encoding="utf-8")[:6000]
        except Exception:
            code = ""
        sys_p = (
            "Bạn là bộ CHẨN ĐOÁN lỗi runtime cho skill Python của agent. Đọc code, tham số và "
            "thông báo lỗi, rồi chọn MỘT cách khắc phục khả thi nhất. Trả DUY NHẤT JSON: "
            '{"action": "install_package" | "install_tool" | "params" | "fix_code" | "new_skill" | "stop", '
            '"package": "<tên gói pip nếu install_package>", '
            '"tool": "<tên lệnh hệ thống nếu install_tool, vd ffmpeg>", '
            '"params": {"<tham số mới nếu action=params>": "..."}, '
            '"reason": "<giải thích ngắn>"}. '
            "Gợi ý: lỗi 'WinError 2 / cannot find the file' khi code gọi subprocess thường là "
            "THIẾU CÔNG CỤ hệ thống → install_tool. "
            "Chọn fix_code nếu lỗi nằm trong code skill (sẽ được sửa tự động); "
            "chọn new_skill nếu skill hiện tại sai hướng tiếp cận và nên VIẾT CODE MỚI từ đầu; "
            "chỉ chọn stop khi thực sự không còn cách nào.")
        user_p = (f"Yêu cầu: {task}\nSkill: {name}\n"
                  f"Code:\n```python\n{code}\n```\n"
                  f"Tham số: {json.dumps(params, ensure_ascii=False)}\nLỗi: {error}\n"
                  f"Đã thử (đừng lặp lại cách đã thất bại): {sorted(tried or [])}")
        try:
            raw = self.llm.complete(
                [{"role": "system", "content": sys_p},
                 {"role": "user", "content": user_p}], role="work", purpose="diagnose")
        except Exception as e:
            # KHÔNG nuốt lỗi: cho người dùng thấy LLM có được gọi hay không
            _log(f"[!] GỌI LLM CHẨN ĐOÁN THẤT BẠI: {e}")
            return {}
        data = extract_json(raw)
        if not isinstance(data, dict):
            _log(f"[!] LLM chẩn đoán trả lời KHÔNG PHẢI JSON: {str(raw)[:150]!r}")
            return {}
        return data

    def _try_fix_code(self, task, name, entry, err, _log):
        path = Path(entry["path"])
        try:
            code = path.read_text(encoding="utf-8")
        except Exception as e:
            _log(f"[!] Không đọc được code skill: {e}")
            return None
        try:
            fixed = fix(task, code, str(err), self.llm, role="work")
            path.write_text(fixed + "\n", encoding="utf-8")
            self.registry.load()
            e = self.registry.get(name)
            if e:
                _log(f"[~] Đã sửa code skill '{name}' theo chẩn đoán, thử lại...")
                return e
            # bản sửa KHÔNG nạp được -> khôi phục bản gốc, không phá skill đang có
            path.write_text(code, encoding="utf-8")
            self.registry.load()
            _log(f"[!] Bản sửa của '{name}' không nạp được → đã KHÔI PHỤC code gốc.")
        except Exception as e:
            try:
                path.write_text(code, encoding="utf-8")
                self.registry.load()
            except Exception:
                pass
            _log(f"[!] Sửa code không thành ({e}) → đã khôi phục code gốc.")
        return None

    def _tool_from_code(self, entry):
        """Quét code skill tìm công cụ hệ thống quen thuộc chưa có trên PATH."""
        import shutil
        try:
            code = Path(entry["path"]).read_text(encoding="utf-8")
        except Exception:
            return None
        for t in _SYS_TOOLS:
            if t in code and not shutil.which(t):
                return t
        return None

    def _pip_install(self, pkg, _log) -> bool:
        return autoinstall.pip_install(pkg, log=_log)

    def _find_local_tool(self, tool) -> str | None:
        """Tìm executable CỤC BỘ: PATH → ký ức (fact chứa đường dẫn) → thư mục tool/tools/bin."""
        import shutil
        exe = shutil.which(tool)
        if exe:
            return exe
        names = (f"{tool}.exe", f"{tool}.bat", f"{tool}.cmd", tool)
        # 1) ký ức: fact có nhắc tới tool kèm một đường dẫn
        try:
            for f in self.memory.recall(tool, k=8):
                for m in re.findall(r"[A-Za-z]:[\\/][^\s\"'<>|,;]+|(?:\.{0,2}/)?[\w./\\-]+[\\/][\w.-]+", f.get("text", "")):
                    p = Path(m.rstrip(".,)"))
                    if p.is_file() and p.stem.lower() == tool.lower():
                        return str(p)
                    if p.is_dir():
                        for n in names:
                            if (p / n).is_file():
                                return str(p / n)
        except Exception:
            pass
        # 2) quét thư mục tool/tools/bin cạnh dự án và cwd (sâu tối đa 3 cấp)
        roots = {Path.cwd(), Path(__file__).resolve().parent.parent}
        for root in roots:
            for sub in ("tool", "tools", "bin", "Tool", "Tools"):
                d = root / sub
                if not d.is_dir():
                    continue
                for n in names:
                    for hit in d.rglob(n):
                        if hit.is_file() and len(hit.relative_to(d).parts) <= 3:
                            return str(hit)
        return None

    def _install_system_tool(self, tool, _log) -> bool:
        import platform
        import shutil
        import subprocess
        # ưu tiên bản CÓ SẴN trong máy (thư mục tool/, ký ức...) trước khi cài mới
        exe = self._find_local_tool(tool)
        if exe:
            d = os.path.dirname(os.path.abspath(exe))
            if d not in os.environ.get("PATH", ""):
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            _log(f"[✓] Tìm thấy '{tool}' tại: {exe} → đã thêm vào PATH.")
            self.memory.remember(f"Công cụ {tool} nằm tại {exe}.", kind="note", tags=[tool])
            return True
        sysname = platform.system().lower()
        if "windows" in sysname:
            cmds = [["winget", "install", "-e", "--id", _WINGET_ID.get(tool, tool),
                     "--accept-source-agreements", "--accept-package-agreements"],
                    ["choco", "install", tool, "-y"]]
        elif "darwin" in sysname:
            cmds = [["brew", "install", tool]]
        else:
            cmds = [["apt-get", "install", "-y", tool],
                    ["sudo", "apt-get", "install", "-y", tool]]
        for c in cmds:
            if not shutil.which(c[0]):
                continue
            _log(f"[>] Thử: {' '.join(c)}")
            try:
                subprocess.run(c, capture_output=True, text=True, timeout=600)
            except Exception as e:
                _log(f"[!] {c[0]} lỗi: {e}")
            if shutil.which(tool):
                return True
        return bool(shutil.which(tool))

    # ---------- đọc lại schema (chuẩn hoá cả meta cũ) ----------
    def _param_schema(self, entry) -> dict:
        from .registry import normalize_schema
        meta = entry["meta"]
        schema = meta.get("params")
        if isinstance(schema, dict) and schema:
            return normalize_schema(schema)
        alt = meta.get("parameters")
        out = {}
        if isinstance(alt, dict):
            for k, v in alt.items():
                desc = v if isinstance(v, str) else (v.get("description", "") if isinstance(v, dict) else "")
                out[k] = {"type": "str", "description": desc, "required": not _is_output(k)}
        return out

    # ---------- tự điền tham số ----------
    def _self_fill(self, task, name, schema, params, error, use_llm=False, _log=None) -> dict:
        params = dict(params or {})
        for k in schema:
            if not params.get(k) and _is_output(k):
                params[k] = self._default_output(k)
        missing = [k for k, s in schema.items()
                   if s.get("required") and not _is_output(k) and not params.get(k)]
        if missing:
            params.update(self._scan_files(missing))
        if use_llm:
            still = [k for k, s in schema.items()
                     if s.get("required") and not _is_output(k) and not params.get(k)]
            if still and self._llm_ready():
                for k, v in (self._llm_fill(task, name, schema, params, error, _log) or {}).items():
                    if k in schema and v not in (None, "", []):
                        params[k] = v
        return params

    def _default_output(self, key: str) -> str:
        kl = key.lower()
        ext = ".txt"
        if any(w in kl for w in ("video", "mp4")):
            ext = ".mp4"
        elif any(w in kl for w in ("audio", "wav", "mp3")):
            ext = ".wav"
        elif any(w in kl for w in ("image", "img", "anh", "photo", "png")):
            ext = ".png"
        elif "json" in kl:
            ext = ".json"
        return f"{key}_{time.strftime('%H%M%S')}{ext}"

    def _scan_files(self, missing) -> dict:
        out = {}
        try:
            files = [f for f in os.listdir(".") if os.path.isfile(f)]
        except Exception:
            return out
        for k in missing:
            kl = k.lower()
            pool = files
            if "video" in kl:
                pool = [f for f in files if f.lower().endswith(_VIDEO_EXT)]
            elif "audio" in kl or "am_thanh" in kl:
                pool = [f for f in files if f.lower().endswith(_AUDIO_EXT)]
            elif any(w in kl for w in ("image", "img", "anh", "photo")):
                pool = [f for f in files if f.lower().endswith(_IMAGE_EXT)]
            if len(pool) == 1:
                out[k] = pool[0]
        return out

    def _llm_fill(self, task, name, schema, params, error, _log=None) -> dict:
        _log = _log or (lambda m: None)
        try:
            files = [f for f in os.listdir(".") if os.path.isfile(f)][:50]
        except Exception:
            files = []
        sys_p = ("Bạn giúp điền tham số để chạy một skill. Dựa vào yêu cầu, mô tả tham số, "
                 "danh sách tệp trong thư mục, ký ức đã lưu và lỗi trước đó, suy ra giá trị hợp lý. "
                 "CHỈ trả JSON gồm các tham số bạn CHẮC CHẮN; không bịa đường dẫn.")
        try:
            mem_ctx = self.memory.context_block(task, k_facts=5, n_history=0)
        except Exception:
            mem_ctx = ""
        user_p = (f"Yêu cầu: {task}\nSkill: {name}\n"
                  f"Schema: {json.dumps(schema, ensure_ascii=False)}\n"
                  f"Tham số hiện có: {json.dumps(params, ensure_ascii=False)}\n"
                  f"Tệp trong thư mục: {files}\n"
                  + (f"{mem_ctx}\n" if mem_ctx else "")
                  + f"Lỗi trước: {error}\n\nTrả JSON tham số.")
        try:
            data = self.llm.complete_json(
                [{"role": "system", "content": sys_p},
                 {"role": "user", "content": user_p}], role="work", purpose="extract")
            if data is None:
                _log("[!] LLM điền tham số trả lời không parse được JSON.")
            return data or {}
        except Exception as e:
            _log(f"[!] GỌI LLM ĐIỀN THAM SỐ THẤT BẠI: {e}")
            return {}

    def _ask_message(self, name, schema, missing) -> str:
        parts = []
        for k in missing:
            d = (schema.get(k, {}) or {}).get("description") or k
            parts.append(f"{k} ({d})")
        return (f"Mình cần thêm thông tin để chạy '{name}': " + "; ".join(parts)
                + ". Bạn cung cấp giúp nhé (ví dụ gửi kèm đường dẫn tệp).")

    def _llm_ready(self) -> bool:
        try:
            rc = self.config.resolve("work")
            return rc.ready and not rc.is_mock
        except Exception:
            return False

    # ---------- kiểm thử skill VỪA SINH ----------
    def _test_new_skill(self, task, name, _log):
        path = SKILLS_DIR / f"{name}.py"
        params, result, err = {}, {}, ""
        attempt = 0
        last_err, stall = None, 0

        while True:
            self.registry.load()
            entry = self.registry.get(name)
            if entry is None:
                ok_v, err_v = validate(path)
                err = err_v or self.registry.load_errors.get(f"{name}.py", "Không nạp được skill.")
            else:
                schema = self._param_schema(entry)
                params = self.registry.extract_params(task, name, self.llm, role="work", schema=schema)
                params = self._self_fill(task, name, schema, params, "", use_llm=False)
                _log(f"[i] Params (kiểm thử): {json.dumps(params, ensure_ascii=False)}")
                _log("[>] Kiểm thử skill mới (smoke test)...")
                result = run_skill(entry, params)
                if result.get("success"):
                    _log(f"[✓] Kiểm thử ĐẠT: {_summarize(result)}")
                    return True, params, result
                if not result.get("_crashed"):
                    _log("[i] Skill chạy được, chỉ lỗi do dữ liệu/đầu vào (không phải lỗi code) → nhận skill.")
                    return True, params, result
                err = result.get("error", "")

            # sửa TỚI KHI ĐƯỢC — chỉ dừng khi hết tiến triển (lỗi lặp y hệt) hoặc chạm trần (nếu đặt)
            if self.MAX_FIX and attempt >= self.MAX_FIX:
                _log(f"[✗] Vẫn lỗi code sau {self.MAX_FIX} lần sửa: {str(err)[:160]}")
                break
            e_sig = str(err)[-200:]  # so ĐUÔI traceback (nơi chứa thông điệp lỗi thật)
            if e_sig == last_err:
                stall += 1
                if stall >= self.FIX_STALL:
                    _log(f"[✗] Lỗi không đổi sau {stall + 1} lần sửa liên tiếp → dừng (hết tiến triển).")
                    break
            else:
                stall = 0
            last_err = e_sig

            attempt += 1
            _log(f"[~] Lỗi code → auto-fix lần {attempt}... ({str(err)[:120]})")
            try:
                code = path.read_text(encoding="utf-8")
                fixed = fix(task, code, str(err), self.llm, role="work")
                path.write_text(fixed + "\n", encoding="utf-8")
            except Exception as e:
                _log(f"[~] Auto-fix không thành: {e}")
                break

        return False, params, result

    def _remove_skill(self, name, _log):
        try:
            p = SKILLS_DIR / f"{name}.py"
            if p.exists():
                p.unlink()
                _log(f"[✗] Đã gỡ skill hỏng: skills/{name}.py")
        except Exception as e:
            _log(f"[!] Không gỡ được skill hỏng: {e}")
        self.registry.load()

    def _recall_relevant(self, task, name) -> bool:
        """Skill do bộ nhớ gợi ý phải có mô tả/tags trùng đủ với việc hiện tại mới được dùng."""
        from .registry import tokens
        entry = self.registry.get(name)
        if not entry:
            return False
        m = entry["meta"]
        tt = tokens(task)
        st = tokens(name) | tokens(" ".join(m.get("tags", []))) | tokens(m.get("description", ""))
        return bool(tt) and len(tt & st) / max(1, len(tt)) >= 0.2

    def _recall_skill(self, task) -> str | None:
        try:
            for f in self.memory.recall(task, k=6):
                if f.get("kind") in ("skill", "task"):
                    for tag in f.get("tags", []):
                        if self.registry.get(tag):
                            return tag
        except Exception:
            pass
        return None

    def _finish(self, task, name, generated, params, result, _log, logs) -> dict:
        success = bool(result.get("success"))
        if success:
            _log(f"[✓] Thành công: {_summarize(result)}")
        else:
            _log(f"[✗] Thất bại: {_summarize(result)}")

        verb = "sinh mới" if generated else "tái dùng"
        status = "thành công" if success else "thất bại"
        self.memory.remember(
            f"Tác vụ \"{task}\" → dùng skill '{name}' ({verb}), kết quả: {status}.",
            kind="task", tags=[name] + list((params or {}).keys()))

        return {
            "success": success,
            "skill": name,
            "generated": generated,
            "params": params,
            "result": result.get("result"),
            "error": result.get("error"),
            "logs": logs,
        }
