"""Tìm ffmpeg/ffprobe: PATH trước, sau đó thư mục Tool của Javis."""
import os
import shutil

FALLBACK_DIRS = [
    os.environ.get("JAVIS_FFMPEG_DIR", ""),
    r"F:\Project\Javis\Tool",
]


def ffbin(name: str) -> str | None:
    """Trả về đường dẫn tới ffmpeg/ffprobe, hoặc None nếu không tìm thấy."""
    p = shutil.which(name)
    if p:
        return p
    exe = name + (".exe" if os.name == "nt" else "")
    for d in FALLBACK_DIRS:
        if d:
            cand = os.path.join(d, exe)
            if os.path.exists(cand):
                return cand
    return None
