#!/usr/bin/env python3
"""Phát hiện ranh giới cảnh trong video bằng PySceneDetect. In JSON."""
import argparse
import json
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_path", help="Đường dẫn tệp video")
    ap.add_argument("--threshold", type=float, default=27.0, help="Ngưỡng phát hiện (mặc định 27.0)")
    args = ap.parse_args()

    if not os.path.exists(args.input_path):
        print(json.dumps({"success": False, "error": f"Không tìm thấy tệp: {args.input_path}"}, ensure_ascii=False))
        return 1
    try:
        from scenedetect import ContentDetector, detect
    except ImportError:
        print(json.dumps({"success": False,
                          "error": "Chưa cài PySceneDetect. Chạy: pip install scenedetect opencv-python"},
                         ensure_ascii=False))
        return 1

    scene_list = detect(args.input_path, ContentDetector(threshold=args.threshold))
    scenes = [{"scene": i + 1, "start": s.get_timecode(), "end": e.get_timecode()}
              for i, (s, e) in enumerate(scene_list)]
    print(json.dumps({"success": True, "result": {"num_scenes": len(scenes), "scenes": scenes}},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
