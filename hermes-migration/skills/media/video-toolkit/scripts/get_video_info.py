#!/usr/bin/env python3
"""Lấy duration / resolution / fps / codec của video bằng ffprobe. In JSON."""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _ffbin import ffbin


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_path", help="Đường dẫn tệp video")
    args = ap.parse_args()

    if not os.path.exists(args.input_path):
        print(json.dumps({"success": False, "error": f"Không tìm thấy tệp: {args.input_path}"}, ensure_ascii=False))
        return 1
    ffprobe = ffbin("ffprobe")
    if not ffprobe:
        print(json.dumps({"success": False, "error": "Không tìm thấy ffprobe (PATH hoặc F:\\Project\\Javis\\Tool)."}, ensure_ascii=False))
        return 1

    cmd = [ffprobe, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", args.input_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(json.dumps({"success": False, "error": proc.stderr.strip() or "ffprobe lỗi"}, ensure_ascii=False))
        return 1

    data = json.loads(proc.stdout or "{}")
    vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    duration = float(data.get("format", {}).get("duration", 0) or 0)

    fps = None
    try:
        n, d = vs.get("r_frame_rate", "0/1").split("/")
        fps = round(float(n) / float(d), 2) if float(d) else None
    except Exception:
        pass

    print(json.dumps({
        "success": True,
        "result": {
            "duration_sec": round(duration, 2),
            "resolution": f"{vs.get('width')}x{vs.get('height')}" if vs.get("width") else None,
            "fps": fps,
            "codec": vs.get("codec_name"),
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
