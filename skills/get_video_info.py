SKILL_META = {
    "name": "get_video_info",
    "description": "Lấy thời lượng (duration), độ phân giải (resolution) và fps của video bằng ffprobe",
    "tags": ["video", "ffprobe", "info", "duration", "resolution", "fps", "metadata"],
    "params": {
        "input_path": {"type": "str", "description": "Đường dẫn tệp video", "required": True},
    },
}


def run(**kwargs) -> dict:
    import json
    import os
    import shutil
    import subprocess

    path = kwargs.get("input_path")
    if not path or not os.path.exists(path):
        return {"success": False, "error": f"Không tìm thấy tệp video: {path}"}
    if not shutil.which("ffprobe"):
        return {"success": False, "error": "Chưa cài ffprobe (thuộc bộ ffmpeg)."}

    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"success": False, "error": proc.stderr.strip() or "ffprobe lỗi"}

    data = json.loads(proc.stdout or "{}")
    vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    duration = float(data.get("format", {}).get("duration", 0) or 0)

    fps = None
    rate = vs.get("r_frame_rate", "0/1")
    try:
        n, d = rate.split("/")
        fps = round(float(n) / float(d), 2) if float(d) else None
    except Exception:
        pass

    resolution = f"{vs.get('width')}x{vs.get('height')}" if vs.get("width") else None
    return {
        "success": True,
        "result": {
            "duration_sec": round(duration, 2),
            "resolution": resolution,
            "fps": fps,
            "codec": vs.get("codec_name"),
        },
    }
