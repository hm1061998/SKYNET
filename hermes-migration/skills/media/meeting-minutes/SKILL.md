---
name: meeting-minutes
description: Tạo biên bản cuộc họp (PDF) từ video ghi hình cuộc họp — tách âm thanh, transcribe bằng OpenAI Whisper API, tóm tắt thành biên bản tiếng Việt và xuất PDF. Di trú từ Javis Agent.
version: 1.0.0
author: JCK (migrated from Javis Agent)
license: MIT
metadata:
  hermes:
    tags: [Video, Meeting, Transcription, PDF]
    related_skills: [video-toolkit]
    config:
      - key: javis.uploads_dir
        description: "Thư mục chứa video cuộc họp"
        default: "F:\\Project\\Javis\\Uploads"
        prompt: "Thư mục chứa video họp"
required_environment_variables:
  - name: OPENAI_API_KEY
    prompt: "OpenAI API key (dùng cho Whisper transcription)"
    help: "Lấy tại https://platform.openai.com/api-keys"
    required_for: "Chuyển giọng nói thành văn bản"
---

# Meeting Minutes — Biên bản cuộc họp từ video

Quy trình chuẩn: video họp → tách âm thanh MP3 → transcribe (Whisper API, tự chia chunk) → **bạn (agent) tự tóm tắt** transcript thành biên bản → xuất PDF.

QUAN TRỌNG (bài học từ Javis cũ): KHÔNG dùng Google Web Speech API cho video dài — từng thất bại liên tục ("Bad Request"). Whisper API ổn định hơn nhiều.

## When to Use

Người dùng yêu cầu: "tạo biên bản cuộc họp từ video", "tóm tắt video họp", "meeting minutes", "xuất PDF biên bản".

## Procedure

1. **Tìm video**: nếu không chỉ rõ, lấy video mới nhất trong thư mục cấu hình `javis.uploads_dir` (PowerShell: `Get-ChildItem '<uploads_dir>' -Include *.mp4,*.mkv,*.mov -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1`). Luôn quote đường dẫn (tên file hay có `[]`, `&`, khoảng trắng).
2. **Tách âm thanh MP3** (nhỏ gọn cho Whisper):
   `python ${HERMES_SKILL_DIR}/../video-toolkit/scripts/extract_audio.py "<video>" -o "<video-dir>/audio_tmp.mp3" --mp3`
3. **Transcribe**:
   `python ${HERMES_SKILL_DIR}/scripts/transcribe_whisper.py "<audio_tmp.mp3>" -o "<video-dir>/transcript.txt" --language vi`
   Script tự chia file >20MB thành các đoạn 10 phút rồi ghép transcript.
4. **Tự soạn biên bản**: đọc transcript.txt rồi TỰ tóm tắt (không gọi script nào) thành biên bản tiếng Việt có cấu trúc:
   `# Biên bản cuộc họp`, ngày giờ (lấy từ tên file nếu có, vd `...-20260709_022704UTC-...`), `## Người tham gia` (nếu suy ra được), `## Nội dung chính` (gạch đầu dòng), `## Quyết định`, `## Việc cần làm (Action items)` — ai làm gì, hạn khi nào. Lưu thành `<video-dir>/bien_ban.md`.
5. **Xuất PDF**:
   `python ${HERMES_SKILL_DIR}/scripts/make_minutes_pdf.py "<bien_ban.md>" -o "<video-dir>/Bien_ban_cuoc_hop.pdf"`
6. **Dọn dẹp**: xoá `audio_tmp.mp3`. Báo cho người dùng đường dẫn PDF + tóm tắt 3-5 dòng.

## Quick Reference

| Bước | Lệnh |
| --- | --- |
| Transcribe | `python ${HERMES_SKILL_DIR}/scripts/transcribe_whisper.py "<audio>" -o transcript.txt --language vi` |
| PDF | `python ${HERMES_SKILL_DIR}/scripts/make_minutes_pdf.py "<minutes.md>" -o "<out.pdf>"` |

## Pitfalls

- `make_minutes_pdf.py` cần `pip install reportlab` (script báo nếu thiếu). Font tiếng Việt tự lấy từ `C:\Windows\Fonts` (Segoe UI/Arial) hoặc DejaVu trên Linux.
- Video 170MB ~1h họp → audio MP3 64kbps ≈ 28MB → script tự chia 2 chunk. Đừng transcribe WAV (quá lớn).
- Transcript hội thoại có thể lẫn tiếng Anh (thuật ngữ IT) — giữ nguyên thuật ngữ khi tóm tắt.
- KHÔNG bịa tên người tham gia hay action item không có trong transcript.

## Verification

PDF tồn tại và >5KB (`Test-Path` + kích thước), mở được (không lỗi font). Biên bản phải khớp nội dung transcript.
