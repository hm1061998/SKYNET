"""Tự sinh skill mới bằng LLM khi registry không có skill phù hợp, và auto-fix 1 lần khi lỗi."""
from __future__ import annotations
import ast
import re

from . import SKILLS_DIR
from .llm import extract_json

_SYSTEM = """Bạn là bộ SINH SKILL cho một AI agent (Skill Agent). Nhiệm vụ: viết MỘT file Python \
độc lập thực hiện đúng yêu cầu của người dùng.

QUY TẮC BẮT BUỘC:
1. File phải có biến `SKILL_META` (dict) và hàm `def run(**kwargs) -> dict`.
2. `run` trả về dict: thành công -> {"success": True, "result": <giá trị>}; \
lỗi -> {"success": False, "error": "<mô tả>"}.
3. TẤT CẢ import của thư viện ngoài phải đặt BÊN TRONG hàm run (lazy import). \
Nếu thiếu thư viện, bắt ImportError và trả {"success": False, "error": "pip install <tên>"}.
4. KHÔNG dùng input(); không hỏi lại; đọc mọi thứ từ kwargs.
5. Kiểm tra tệp đầu vào tồn tại trước khi xử lý; trả lỗi rõ ràng nếu thiếu.
6. Ưu tiên stdlib; xử lý media qua subprocess gọi ffmpeg; xử lý ảnh qua Pillow (PIL).
7. Đặt "name" là định danh hợp lệ (a-z, 0-9, _), ngắn gọn, mô tả đúng chức năng.
8. MỘT SKILL CHỈ LÀM MỘT VIỆC NHỎ (single responsibility). Nếu yêu cầu gộp nhiều công đoạn \
(vd: video → biên bản PDF), CHỈ viết skill cho công đoạn đang được yêu cầu — các công đoạn khác \
đã/sẽ có skill riêng do agent điều phối theo pipeline.

ĐỊNH DẠNG TRẢ VỀ (đúng y như vậy):
===PARAMS===
{ ...JSON tham số phù hợp cho yêu cầu hiện tại... }
===CODE===
```python
SKILL_META = { ... }

def run(**kwargs) -> dict:
    ...
```"""

_FIX_SYSTEM = """Bạn sửa lỗi một skill Python. Giữ nguyên contract (SKILL_META + \
run(**kwargs) -> dict, lazy import trong run). Trả về DUY NHẤT code đã sửa trong khối ```python```."""


class GeneratorError(RuntimeError):
    pass


def validate_generated_source(code: str) -> None:
    """Reject generated module-level execution before the source reaches Registry.exec."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise GeneratorError(f"Generated skill has invalid syntax: {exc}") from exc
    meta_found = False
    run_found = False
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.decorator_list:
                raise GeneratorError("Generated skill functions may not use decorators")
            definition_expressions = tuple(node.args.defaults) + tuple(
                item for item in node.args.kw_defaults if item is not None)
            definition_expressions += tuple(item for item in (
                node.returns, *(arg.annotation for arg in node.args.args),
                *(arg.annotation for arg in node.args.kwonlyargs)) if item is not None)
            if any(any(isinstance(child, ast.Call) for child in ast.walk(item))
                   for item in definition_expressions):
                raise GeneratorError("Generated skill definitions may not execute calls at module load")
            run_found = run_found or node.name == "run"
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if not all(isinstance(target, ast.Name) for target in targets):
                raise GeneratorError("Generated skill module assignments require simple names")
            value = node.value
            try:
                literal = ast.literal_eval(value) if value is not None else None
            except (ValueError, TypeError) as exc:
                raise GeneratorError("Generated skill module assignments must be literals") from exc
            if any(isinstance(target, ast.Name) and target.id == "SKILL_META" for target in targets):
                if not isinstance(literal, dict):
                    raise GeneratorError("Generated SKILL_META must be a literal dictionary")
                meta_found = True
            continue
        raise GeneratorError(
            f"Generated skill contains forbidden module-level statement: {type(node).__name__}")
    if not meta_found or not run_found:
        raise GeneratorError("Generated skill requires literal SKILL_META and run function")


def _sanitize(name: str) -> str:
    name = re.sub(r"[^a-z0-9_]+", "_", (name or "").lower()).strip("_")
    if not name:
        name = "skill"
    if name[0].isdigit():
        name = "s_" + name
    return name


def _unique(name: str, taken: set[str]) -> str:
    base, i = name, 2
    while name in taken or (SKILLS_DIR / f"{name}.py").exists():
        name = f"{base}_{i}"
        i += 1
    return name


def _parse_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    code = m.group(1) if m else text
    if "===CODE===" in code:
        code = code.split("===CODE===", 1)[1]
    return code.strip()


def _parse_params(text: str) -> dict:
    if "===PARAMS===" in text and "===CODE===" in text:
        block = text.split("===PARAMS===", 1)[1].split("===CODE===", 1)[0]
        return extract_json(block) or {}
    return {}


def _name_from_code(code: str) -> str | None:
    m = re.search(r'["\']name["\']\s*:\s*["\']([^"\']+)["\']', code)
    return m.group(1) if m else None


def generate(task: str, llm, taken=None, role: str = "work", attempts: int = 3) -> dict:
    """Sinh skill mới cho `task`. Trả {name, filename, path, code, params}.

    Thử lại tối đa `attempts` lần khi model trả sai định dạng (kèm feedback để model tự sửa).
    """
    taken = set(taken or [])
    raw, code, feedback, last_raw = "", "", "", None
    for _ in range(max(1, attempts)):
        user = f"Yêu cầu: {task}"
        if feedback:
            user += ("\n\nLần trả lời trước KHÔNG HỢP LỆ: " + feedback +
                     ". Trả đúng định dạng ===PARAMS===/===CODE=== với SKILL_META (dict) "
                     "và def run(**kwargs), toàn bộ code trong khối ```python```.")
        raw = llm.complete(
            [{"role": "system", "content": _SYSTEM},
             {"role": "user", "content": user}],
            role=role, purpose="generate", temperature=0.2, max_tokens=4096)
        code = _parse_code(raw)
        if "def run" in code and "SKILL_META" in code:
            break
        if last_raw is not None and raw.strip() == last_raw.strip():
            break  # model trả y hệt → thử thêm cũng vô ích
        last_raw = raw
        feedback = "thiếu SKILL_META hoặc def run"
    if "def run" not in code or "SKILL_META" not in code:
        raise GeneratorError(
            "LLM không sinh đúng contract (thiếu SKILL_META/run) sau "
            f"{attempts} lần. Model trả (đầu): {str(raw)[:200]!r}")

    name = _sanitize(_name_from_code(code) or task.split()[0])
    name = _unique(name, taken)
    # đồng bộ tên trong SKILL_META với tên file
    code = re.sub(r'(["\']name["\']\s*:\s*["\'])[^"\']+(["\'])',
                  lambda m: m.group(1) + name + m.group(2), code, count=1)

    validate_generated_source(code)

    path = SKILLS_DIR / f"{name}.py"
    path.write_text(code + "\n", encoding="utf-8")

    return {"name": name, "filename": path.name, "path": path,
            "code": code, "params": _parse_params(raw)}


def fix(task: str, code: str, error: str, llm, role: str = "work") -> str:
    """Sửa skill lỗi 1 lần. Trả code đã sửa."""
    raw = llm.complete(
        [{"role": "system", "content": _FIX_SYSTEM},
         {"role": "user", "content": (f"Yêu cầu gốc: {task}\n\nCode hiện tại:\n```python\n{code}\n```"
                                       f"\n\nLỗi khi chạy:\n{error}\n\nSửa lại và trả code hoàn chỉnh.")}],
        role=role, purpose="fix", temperature=0.2, max_tokens=4096)
    fixed = _parse_code(raw)
    if "def run" not in fixed:
        raise GeneratorError(f"Bản sửa không hợp lệ. Model trả (đầu): {str(raw)[:200]!r}")
    validate_generated_source(fixed)
    return fixed


def validate(path) -> tuple[bool, str]:
    """Kiểm thử TĨNH một file skill trước khi nhận: cú pháp + đúng contract.

    Trả (True, "") nếu hợp lệ; (False, "<lý do>") nếu không. KHÔNG chạy run().
    """
    import importlib.util
    import py_compile
    from pathlib import Path

    p = Path(path)
    if p.suffix != ".py":
        p = SKILLS_DIR / f"{p.name}.py"
    path = p
    # 1) cú pháp
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as e:
        return False, f"Lỗi cú pháp: {getattr(e, 'msg', e)}"
    except Exception as e:
        return False, f"Lỗi biên dịch: {e}"

    # 2) import + kiểm tra contract
    try:
        spec = importlib.util.spec_from_file_location(f"validate_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        return False, f"Lỗi khi import skill: {e}"

    meta = getattr(mod, "SKILL_META", None)
    run_fn = getattr(mod, "run", None)
    if not isinstance(meta, dict):
        return False, "Thiếu SKILL_META (phải là dict)."
    if not meta.get("name"):
        return False, "SKILL_META thiếu khoá 'name'."
    if not meta.get("description"):
        return False, "SKILL_META thiếu 'description' (mô tả ngắn)."
    if not isinstance(meta.get("params", {}), dict):
        return False, "SKILL_META['params'] phải là dict."
    if not callable(run_fn):
        return False, "Thiếu hàm run(**kwargs)."
    return True, ""
