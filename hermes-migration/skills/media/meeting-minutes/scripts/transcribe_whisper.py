#!/usr/bin/env python3
"""Transcribe âm thanh bằng OpenAI Whisper API (stdlib-only, tự chia chunk file lớn). In JSON.

Cần biến môi trường OPENAI_API_KEY.
File >20MB được chia thành đoạn 10 phút (cần ffmpeg) rồi ghép transcript.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid

MAX_BYTES = 20 * 1024 * 1024  # ngưỡng an toàn dưới limit 25MB của API
API_URL = "https://api.openai.com/v1/audio/transcriptions"

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "video-toolkit", "scripts"))
try:
    from _ffbin import ffbin
except ImportError:  # chạy độc lập không có video-toolkit
    def ffbin(name):
        return shutil.which(name)


def _fail(msg: str) -> int:
    print(json.dumps({"success": False, "error": msg}, ensure_ascii=False))
    return 1


def _multipart(fields: dict, file_field: str, file_path: str) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    lines: list[bytes] = []
    for k, v in fields.items():
        lines += [f"--{boundary}".encode(),
                  f'Content-Disposition: form-data; name="{k}"'.encode(),
                  b"", str(v).encode("utf-8")]
    fname = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        data = f.read()
    lines += [f"--{boundary}".encode(),
              f'Content-Disposition: form-data; name="{file_field}"; filename="{fname}"'.encode(),
              b"Content-Type: application/octet-stream", b"", data,
              f"--{boundary}--".encode(), b""]
    return b"\r\n".join(lines), boundary


def _transcribe_one(path: str, api_key: str, language: str) -> str:
    body, boundary = _multipart({"model": "whisper-1", "language": language,
                                 "response_format": "text"}, "file", path)
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    })
    with urllib.request.urlopen(req, timeout=600) as resp:
        return resp.read().decode("utf-8").strip()


def _split_audio(path: str, tmp_dir: str, seg_seconds: int = 600) -> list[str]:
    ffmpeg = ffbin("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("File >20MB cần ffmpeg để chia nhỏ nhưng không tìm thấy ffmpeg.")
    pattern = os.path.join(tmp_dir, "chunk_%03d.mp3")
    proc = subprocess.run(
        [ffmpeg, "-i", path, "-f", "segment", "-segment_time", str(seg_seconds),
         "-acodec", "libmp3lame", "-b:a", "64k", "-ar", "16000", "-ac", "1", "-y", pattern],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg chia file lỗi: " + (proc.stderr or "")[-400:])
    chunks = sorted(os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir)
                    if f.startswith("chunk_") and f.endswith(".mp3"))
    if not chunks:
        raise RuntimeError("Không tạo được chunk nào.")
    return chunks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_path", help="File âm thanh (mp3/wav/m4a...)")
    ap.add_argument("-o", "--output", help="File .txt lưu transcript")
    ap.add_argument("--language", default="vi", help="Mã ngôn ngữ ISO-639-1 (mặc định vi)")
    args = ap.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _fail("Thiếu biến môi trường OPENAI_API_KEY.")
    if not os.path.exists(args.input_path):
        return _fail(f"Không tìm thấy tệp: {args.input_path}")

    tmp_dir = tempfile.mkdtemp(prefix="whisper_")
    try:
        size = os.path.getsize(args.input_path)
        files = ([args.input_path] if size <= MAX_BYTES
                 else _split_audio(args.input_path, tmp_dir))
        parts = []
        for i, f in enumerate(files, 1):
            print(f"[transcribe] đoạn {i}/{len(files)} ...", file=sys.stderr)
            parts.append(_transcribe_one(f, api_key, args.language))
        text = "\n".join(p for p in parts if p)
        if not text:
            return _fail("Whisper không trả về nội dung nào.")
        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(text)
        print(json.dumps({"success": True,
                          "result": {"chars": len(text), "chunks": len(files),
                                     "output": args.output,
                                     "preview": text[:300]}}, ensure_ascii=False))
        return 0
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:400]
        except Exception:
            pass
        return _fail(f"Whisper API HTTP {e.code}: {detail}")
    except Exception as e:
        return _fail(str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
