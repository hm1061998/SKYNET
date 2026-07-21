# Javis → Hermes Agent

Javis (agent tự viết) được thay bằng [Hermes Agent](https://hermes-agent.nousresearch.com/docs/) — agent mã nguồn mở của Nous Research, cùng ý tưởng "tự sinh skill + memory" nhưng hoàn thiện hơn: 60+ tool sẵn, memory tự quản, cron, voice mode, chạy được qua Telegram/Discord, desktop app. Code Javis cũ giữ nguyên tại `F:\Project\Javis` làm lưu trữ.

## Cài đặt (1 lần)

Mở PowerShell, chạy:

```powershell
powershell -ExecutionPolicy Bypass -File F:\Project\Javis\hermes-migration\Cai-Hermes.ps1
```

Script sẽ: cài Hermes (installer chính thức) → copy 2 skill đã di trú → tạo `config.yaml` (DeepSeek làm model chính, như Javis) → ghi `DEEPSEEK_API_KEY` + `OPENAI_API_KEY` từ `config.json` cũ vào `%USERPROFILE%\.hermes\.env`.

Nếu sau khi cài báo "hermes chưa có trong PATH": mở lại PowerShell rồi chạy script lần nữa.

## Chạy

Double-click `F:\Project\Javis\Chay-Hermes.bat` (thay cho `Chay-Javis.bat` cũ), hoặc gõ `hermes` trong terminal.

Lần đầu tiên, dán vào chat:

> Đọc file F:\Project\Javis\hermes-migration\MIGRATION-NOTES.md và lưu các fact quan trọng vào memory

## Javis cũ → Hermes: cái gì đi đâu

| Javis | Hermes |
| --- | --- |
| `skills/get_video_info.py`, `detect_scenes.py`, tách audio | skill **video-toolkit** (`~/.hermes/skills/media/video-toolkit`) |
| `video_meeting_summary.py` (hỏng, chưa chạy được) | skill **meeting-minutes** — viết lại hoàn chỉnh: ffmpeg → Whisper API → biên bản → PDF |
| `extract_audio_transcribe.py` (Google Speech, hay lỗi) | thay bằng OpenAI Whisper API trong meeting-minutes |
| `list_files`, `run_command` | tool `terminal` có sẵn của Hermes |
| `parse_api_response(_2)`, `select_first_video`, `latest_video` | agent tự làm — không cần skill |
| `config.json` roles chat/work | `config.yaml`: model chính `deepseek-v4-pro`, nén hội thoại bằng `deepseek-chat` |
| `memory/facts.jsonl` | MEMORY.md của Hermes (seed qua MIGRATION-NOTES.md; log tác vụ cũ là nhiễu, không port) |
| Dashboard `javis-core.html` + giọng nói | Hermes CLI / desktop app / web dashboard, voice mode có sẵn |
| Kế hoạch HTML + nút Đồng ý | cơ chế approval có sẵn (`skills.write_approval`, duyệt lệnh) |

## Thử ngay

- "Tạo biên bản cuộc họp từ video mới nhất trong Uploads" — quy trình từng thất bại nhiều lần trên Javis, giờ là skill hoàn chỉnh.
- "Video trong Uploads dài bao nhiêu, độ phân giải bao nhiêu?"
- "Sáng nào 8h cũng tóm tắt tin AI cho tôi" — cron có sẵn.

## Lưu ý bảo mật

`config.json` cũ chứa API key dạng plaintext và đã từng commit vào git — nên thu hồi (revoke) key OpenAI/DeepSeek cũ và phát hành key mới, rồi cập nhật bằng:

```
hermes config set DEEPSEEK_API_KEY <key-moi>
hermes config set OPENAI_API_KEY <key-moi>
```

## Gỡ / quay lại Javis

Hermes nằm gọn trong `%USERPROFILE%\.hermes`. Javis cũ không bị đụng tới — `Chay-Javis.bat` vẫn chạy như trước.
