# Ghi chú di trú từ Agent → Hermes Agent

Ở lần chạy Hermes đầu tiên, dán câu này vào chat:

> Đọc file F:\Project\Agent\hermes-migration\MIGRATION-NOTES.md và lưu các fact quan trọng vào memory (mục "Facts cần nhớ").

## Facts cần nhớ

- ffmpeg/ffprobe nằm tại `F:\Project\Agent\Tool\` (không có trên PATH). Video họp nằm trong `F:\Project\Agent\Uploads\`.
- Quy trình chính của người dùng: video ghi hình cuộc họp → biên bản cuộc họp tiếng Việt → xuất PDF lưu cùng thư mục video. Dùng skill `meeting-minutes`.
- Bài học từ Agent cũ: Google Web Speech API thất bại liên tục với video họp dài ("Bad Request") — luôn dùng OpenAI Whisper API (skill có sẵn script).
- Người dùng tên JCK, nói tiếng Việt, thích trả lời ngắn gọn, deliverable dạng PDF.
- Dự án Agent cũ (agent tự viết) vẫn ở `F:\Project\Agent\` làm lưu trữ — không sửa/xoá.

## Lịch sử

- Agent là agent tự sinh skill do người dùng tự viết (Python, 2 model chat/work qua DeepSeek).
- Di trú sang Hermes Agent (Nous Research) tháng 7/2026. Provider: DeepSeek (key cũ), OPENAI_API_KEY dùng cho Whisper.
- Skills đã port: `video-toolkit` (info/tách audio/detect scenes), `meeting-minutes` (quy trình biên bản họp PDF).
- Skills KHÔNG port vì Hermes có sẵn tool tương đương: list_files, run_command (→ tool `terminal`), parse_api_response 1+2, select_first_video, latest_video (→ agent tự làm bằng terminal).
