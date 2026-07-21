"""Registry kỹ năng: nạp các file skill trong skills/, tìm skill khớp yêu cầu,
và rút tham số (params) từ câu lệnh người dùng.

Contract của một skill (file .py trong skills/):

    SKILL_META = {
        "name": "...", "description": "...", "tags": [...],
        "params": { "input_path": {"type": "str", "required": True, ...}, ... }
    }
    def run(**kwargs) -> dict:   # trả {"success": bool, "result"/"error": ...}
        ...
"""
from __future__ import annotations
import importlib.util
import re
import unicodedata

from . import SKILLS_DIR
from . import autoinstall

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
MATCH_THRESHOLD = 0.25


def normalize_schema(schema) -> dict:
    """Chuẩn hóa params schema về dạng {name: {type, description, required}}.

    Skill do LLM sinh hay khai tắt {"video_path": "đường dẫn video"} (value là chuỗi)
    — không chuẩn hóa thì code rút tham số sẽ crash khi gọi .get() trên chuỗi.
    """
    out = {}
    if not isinstance(schema, dict):
        return out
    for k, v in schema.items():
        if isinstance(v, dict):
            out[k] = v
        elif isinstance(v, str):
            out[k] = {"type": "str", "description": v, "required": True}
        else:
            out[k] = {"type": "str", "description": str(v), "required": False}
    return out


# ---------------- tiện ích văn bản ----------------
def _strip_accent(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def tokens(text: str) -> set[str]:
    text = text or ""
    base = {w.lower() for w in _WORD.findall(text)}
    return base | {_strip_accent(w) for w in base}


# ---------------- registry ----------------
class Registry:
    def __init__(self, skills_dir=SKILLS_DIR):
        self.skills_dir = skills_dir
        self.skills: dict[str, dict] = {}
        self.load_errors: dict[str, str] = {}

    def load(self) -> "Registry":
        self.skills = {}
        self.load_errors = {}
        if not self.skills_dir.exists():
            return self
        for path in sorted(self.skills_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            self._load_file(path)
        return self

    def _load_file(self, path, _retry=True):
        import linecache
        import types
        try:
            # exec trực tiếp từ SOURCE (không qua import loader) để tránh bytecode cache:
            # vòng auto-fix ghi code mới cùng kích thước/cùng giây mtime sẽ bị Python
            # chạy lại bản cũ nếu dùng loader chuẩn.
            src = path.read_text(encoding="utf-8")
            linecache.checkcache(str(path))
            mod = types.ModuleType(f"skill_{path.stem}")
            mod.__file__ = str(path)
            exec(compile(src, str(path), "exec"), mod.__dict__)
            meta = getattr(mod, "SKILL_META", None)
            run = getattr(mod, "run", None)
            if not isinstance(meta, dict) or not callable(run):
                return
            name = meta.get("name") or path.stem
            self.skills[name] = {"meta": meta, "run": run, "path": path, "module": mod}
        except ImportError as e:
            # thiếu thư viện ở import-time -> tự cài rồi nạp lại (1 lần)
            pkg = autoinstall.missing_package(str(e))
            if _retry and pkg:
                print(f"[registry] {path.name} thiếu '{pkg}' → tự cài...")
                if autoinstall.pip_install(pkg, log=print):
                    return self._load_file(path, _retry=False)
            self.load_errors[path.name] = str(e)
            print(f"[registry] Bỏ qua {path.name}: {e}")
        except Exception as e:  # skill lỗi không được làm sập cả registry
            self.load_errors[path.name] = str(e)
            print(f"[registry] Bỏ qua {path.name}: {e}")

    # ---- thông tin ----
    def count(self) -> int:
        return len(self.skills)

    def names(self) -> list[str]:
        return list(self.skills)

    def get(self, name) -> dict | None:
        return self.skills.get(name)

    def catalog(self) -> str:
        """Mô tả ngắn danh sách skill cho LLM đọc."""
        lines = []
        for n, e in self.skills.items():
            m = e["meta"]
            ps = ", ".join(m.get("params", {}).keys())
            lines.append(f"- {n}: {m.get('description','')} | params: {ps or '(none)'}")
        return "\n".join(lines) if lines else "(registry trống)"

    # ---- tìm skill ----
    def _lexical(self, task: str):
        tt = tokens(task)
        if not tt:
            return None, 0.0
        best, best_score = None, 0.0
        for name, e in self.skills.items():
            m = e["meta"]
            st = tokens(name) | tokens(" ".join(m.get("tags", []))) | tokens(m.get("description", ""))
            overlap = len(tt & st)
            score = overlap / max(1, len(tt))
            # thưởng nếu tag xuất hiện nguyên vẹn trong yêu cầu
            if any(t in tt for t in tokens(" ".join(m.get("tags", [])))):
                score += 0.05
            if score > best_score:
                best, best_score = name, score
        return best, best_score

    def find(self, task: str, llm=None, role: str = "work") -> str | None:
        """Trả tên skill khớp, hoặc None nếu cần sinh mới."""
        best, score = self._lexical(task)
        # Nếu có LLM thật -> để LLM chọn (đúng tinh thần README).
        if llm is not None and self._llm_ready(llm, role) and self.skills:
            picked = self._llm_select(task, llm, role)
            if picked == "__NONE__":
                return None
            if picked in self.skills:
                return picked
            # LLM không chắc -> quay về lexical
        return best if score >= MATCH_THRESHOLD else None

    def _llm_ready(self, llm, role) -> bool:
        try:
            rc = llm.config.resolve(role)
            return rc.ready and not rc.is_mock
        except Exception:
            return False

    def _llm_select(self, task, llm, role) -> str:
        sys_p = ("Bạn là bộ định tuyến skill. Chỉ chọn skill THỰC SỰ phù hợp để thực thi "
                 "yêu cầu. Nếu không có skill nào phù hợp, trả về null.")
        user_p = (f"Yêu cầu: {task}\n\nDanh sách skill:\n{self.catalog()}\n\n"
                  'Trả JSON: {"skill": "<tên skill hoặc null>"}')
        try:
            data = llm.complete_json(
                [{"role": "system", "content": sys_p},
                 {"role": "user", "content": user_p}], role=role, purpose="select")
            val = (data or {}).get("skill")
            return val if val else "__NONE__"
        except Exception as e:
            print(f"[registry] LLM chọn skill LỖI ({e}) → dùng so khớp từ khóa.")
            return "__lexical__"

    # ---- rút tham số ----
    def extract_params(self, task: str, name: str, llm=None, role: str = "work",
                       schema: dict | None = None) -> dict:
        entry = self.skills.get(name)
        if not entry:
            return {}
        if schema is None:
            schema = entry["meta"].get("params", {}) or {}
        schema = normalize_schema(schema)
        if not schema:
            return {}
        if llm is not None and self._llm_ready(llm, role):
            try:
                return self._coerce(self._llm_extract(task, name, schema, llm, role), schema)
            except Exception as e:
                print(f"[registry] LLM rút tham số LỖI ({e}) → dùng heuristic (kém chính xác).")
        return self._coerce(_naive_extract(task, schema), schema)

    def _llm_extract(self, task, name, schema, llm, role) -> dict:
        import json
        sys_p = "Bạn rút tham số cho skill từ câu lệnh người dùng. Chỉ trả JSON các tham số."
        user_p = (f"Câu lệnh: {task}\nSkill: {name}\n"
                  f"Schema params: {json.dumps(schema, ensure_ascii=False)}\n\n"
                  "Trả JSON object chỉ gồm các tham số có giá trị (đúng kiểu).")
        data = llm.complete_json(
            [{"role": "system", "content": sys_p},
             {"role": "user", "content": user_p}], role=role, purpose="extract")
        return data or {}

    @staticmethod
    def _coerce(params: dict, schema: dict) -> dict:
        out = {}
        for k, v in (params or {}).items():
            spec = schema.get(k, {})
            t = spec.get("type", "str")
            try:
                if t == "int":
                    out[k] = int(v)
                elif t in ("float", "number"):
                    out[k] = float(v)
                elif t == "bool":
                    out[k] = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "có")
                else:
                    out[k] = v
            except Exception:
                out[k] = v
        # điền default cho param bắt buộc còn thiếu (nếu schema có default)
        for k, spec in schema.items():
            if k not in out and "default" in spec:
                out[k] = spec["default"]
        return out


# ---------------- rút tham số kiểu heuristic (không cần LLM) ----------------
def _naive_extract(task: str, schema: dict) -> dict:
    out = {}
    numbers = re.findall(r"\d+(?:\.\d+)?", task)
    wh = re.search(r"(\d+)\s*[x×]\s*(\d+)", task)
    files = re.findall(r"[^\s\"']+\.\w{2,5}", task)
    used_files = 0
    used_nums = 0

    for name, spec in schema.items():
        t = spec.get("type", "str")
        lname = name.lower()
        if name == "width" and wh:
            out[name] = int(wh.group(1)); continue
        if name == "height" and wh:
            out[name] = int(wh.group(2)); continue
        if t == "str" and ("path" in lname or "file" in lname or "input" in lname or "output" in lname):
            if used_files < len(files):
                out[name] = files[used_files]; used_files += 1; continue
        if t in ("int", "float", "number"):
            # bỏ qua các số đã dùng cho WxH
            pool = [n for n in numbers if not (wh and n in (wh.group(1), wh.group(2)))]
            if used_nums < len(pool):
                val = pool[used_nums]; used_nums += 1
                out[name] = int(val) if t == "int" else float(val); continue
        if t == "str" and ("text" in lname or "content" in lname or "query" in lname or "prompt" in lname):
            out[name] = task; continue
    return out
