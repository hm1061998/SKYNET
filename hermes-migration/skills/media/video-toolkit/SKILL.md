---
name: video-toolkit
description: Xử lý video bằng ffmpeg/ffprobe — lấy thông tin video (duration, resolution, fps), tách âm thanh, phát hiện cảnh (scene detection). Di trú từ Javis Agent.
version: 1.0.0
author: JCK (migrated from Javis Agent)
license: MIT
metadata:
  hermes:
    tags: [Video, Media, FFmpeg]
    related_skills: [meeting-minutes]
    config:
      - key: javis.ffmpeg_dir
        description: "Thư mục chứa ffmpeg.exe/ffprobe.exe nếu không có trên PATH"
        default: "F:\\Project\\Javis\\Tool"
        prompt: "Đường dẫn thư mục ffmpeg"
---

# Video Toolkit

Bộ công cụ xử lý video di trú từ Javis Agent. Tất cả script tự tìm ffmpeg/ffprobe trên PATH, nếu không có sẽ dùng thư mục cấu hình `javis.ffmpeg_dir` (mặc định `F:\Project\Javis\Tool`).

## When to Use

Khi người dùng yêu cầu: lấy thông tin video (thời lượng, độ phân giải, fps, codec), tách âm thanh khỏi video, phát hiện/cắt cảnh trong video, hoặc bất kỳ thao tác ffmpeg nào.

## Quick Reference

| Việc | Lệnh |
| --- | --- |
| Thông tin video | `python ${HERMES_SKILL_DIR}/scripts/get_video_info.py "<video>"` |
| Tách âm thanh (WAV 16kHz mono) | `python ${HERMES_SKILL_DIR}/scripts/extract_audio.py "<video>" -o "<out.wav>"` |
| Tách âm thanh (MP3 nhỏ gọn) | `python ${HERMES_SKILL_DIR}/scripts/extract_audio.py "<video>" -o "<out.mp3>" --mp3` |
| Phát hiện cảnh | `python ${HERMES_SKILL_DIR}/scripts/detect_scenes.py "<video>" --threshold 27` |

Mọi script in JSON ra stdout: `{"success": true/false, ...}`.

## Procedure

1. Nếu người dùng nói "video mới nhất trong Uploads", tìm file video mới nhất bằng terminal (PowerShell: `Get-ChildItem 'F:\Project\Javis\Uploads' -Include *.mp4,*.mkv,*.avi,*.mov -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1`).
2. Chạy script tương ứng ở Quick Reference với đường dẫn tuyệt đối (luôn đặt trong dấu ngoặc kép — tên file có thể chứa khoảng trắng và ký tự đặc biệt).
3. Đọc JSON kết quả và báo lại bằng tiếng Việt.

## Pitfalls

- Tên video của người dùng thường chứa khoảng trắng, dấu `[]` và `&` — luôn quote đường dẫn.
- `detect_scenes.py` cần `pip install scenedetect opencv-python` (script sẽ báo nếu thiếu).
- Video họp có thể rất dài (>1h) — tách âm thanh MP3 trước khi transcribe để file nhỏ.

## Verification

Kiểm tra JSON trả về có `"success": true` và file đầu ra tồn tại (`Test-Path`).
