#!/usr/bin/env python3
"""Tách âm thanh khỏi video bằng ffmpeg. Mặc định WAV 16kHz mono; --mp3 cho file nhỏ. In JSON."""
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
    ap.add_argument("-o", "--output", help="Đường dẫn file âm thanh đầu ra (mặc định: cùng tên .wav/.mp3)")
    ap.add_argument("--mp3", action="store_true", help="Xuất MP3 64kbps mono (nhỏ, hợp để transcribe)")
    args = ap.parse_args()

    if not os.path.exists(args.input_path):
        print(json.dumps({"success": False, "error": f"Không tìm thấy tệp: {args.input_path}"}, ensure_ascii=False))
        return 1
    ffmpeg = ffbin("ffmpeg")
    if not ffmpeg:
        print(json.dumps({"success": False, "error": "Không tìm thấy ffmpeg (PATH hoặc F:\\Project\\Agent\\Tool)."}, ensure_ascii=False))
        return 1

    ext = ".mp3" if args.mp3 else ".wav"
    out = args.output or os.path.splitext(args.input_path)[0] + ext
    if args.mp3 or out.lower().endswith(".mp3"):
        codec = ["-acodec", "libmp3lame", "-b:a", "64k", "-ar", "16000", "-ac", "1"]
    else:
        codec = ["-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1"]

    proc = subprocess.run([ffmpeg, "-i", args.input_path, "-vn", *codec, "-y", out],
                          capture_output=True, text=True)
    if proc.returncode != 0 or not os.path.exists(out):
        print(json.dumps({"success": False, "error": (proc.stderr or "ffmpeg lỗi").strip()[-800:]}, ensure_ascii=False))
        return 1

    print(json.dumps({
        "success": True,
        "result": {"output": out, "size_mb": round(os.path.getsize(out) / 1048576, 2)},
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
