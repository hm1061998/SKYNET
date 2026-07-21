"""Skill builtin: liệt kê file & thư mục trong một đường dẫn.

Cho phép Agent "đọc thư mục và lấy danh sách file" — có thể lọc theo mẫu (glob)
và tuỳ chọn duyệt đệ quy các thư mục con. Chỉ dùng thư viện chuẩn.
"""

SKILL_META = {
    "name": "list_files",
    "description": ("Liệt kê danh sách file và thư mục trong một đường dẫn. "
                    "Hỗ trợ lọc theo mẫu (vd *.py) và duyệt đệ quy thư mục con."),
    "tags": ["list", "files", "file", "folder", "directory", "thu-muc", "thumuc",
             "liet-ke", "danh-sach", "ls", "dir", "doc-thu-muc", "list_files"],
    "params": {
        "path": {"type": "str", "description": "Đường dẫn thư mục cần liệt kê",
                 "required": False, "default": "."},
        "pattern": {"type": "str", "description": "Mẫu lọc kiểu glob, vd '*.py' hoặc '*'",
                    "required": False, "default": "*"},
        "recursive": {"type": "bool", "description": "Duyệt cả thư mục con hay không",
                      "required": False, "default": False},
        "limit": {"type": "int", "description": "Số mục tối đa trả về",
                  "required": False, "default": 500},
    },
}


def run(**kwargs) -> dict:
    from pathlib import Path

    path = str(kwargs.get("path") or ".").strip().strip('"').strip("'")
    pattern = str(kwargs.get("pattern") or "*")
    recursive = bool(kwargs.get("recursive", False))
    try:
        limit = int(kwargs.get("limit", 500))
    except (TypeError, ValueError):
        limit = 500

    base = Path(path).expanduser()
    if not base.exists():
        return {"success": False, "error": f"Không tìm thấy đường dẫn: {base}"}
    if not base.is_dir():
        return {"success": False, "error": f"Đây không phải thư mục: {base}"}

    try:
        it = base.rglob(pattern) if recursive else base.glob(pattern)
    except Exception as e:
        return {"success": False, "error": f"Mẫu lọc không hợp lệ '{pattern}': {e}"}

    dirs, files = [], []
    for p in it:
        try:
            rel = str(p.relative_to(base))
        except Exception:
            rel = p.name
        if p.is_dir():
            dirs.append(rel + "/")
        else:
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            files.append({"name": rel, "size": size})
        if len(dirs) + len(files) >= limit:
            break

    dirs.sort()
    files.sort(key=lambda x: x["name"])

    # chuỗi tóm tắt dễ đọc (agent sẽ đọc phần này)
    lines = [f"Thư mục: {base}  ({len(dirs)} thư mục, {len(files)} file)"]
    for d in dirs:
        lines.append(f"  [DIR] {d}")
    for f in files:
        lines.append(f"  {f['name']}  ({_human(f['size'])})")
    summary = "\n".join(lines)

    return {
        "success": True,
        "result": summary,
        "data": {"path": str(base), "dirs": dirs, "files": files,
                 "count": len(dirs) + len(files)},
    }


def _human(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"
