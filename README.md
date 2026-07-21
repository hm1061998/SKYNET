# Skill Agent — AI Agent tự sinh kỹ năng

Tên hiển thị và từ khóa đánh thức của Agent được cấu hình tập trung trong
`agent.config.json`. Đổi `name` tại đây sẽ cập nhật giao diện, tiêu đề trình
duyệt, gợi ý giọng nói và console server.

Nếu tên tiếng Anh bị TTS đọc sai, đặt `speechName` thành phiên âm tiếng Việt
(ví dụ `SKYNET` dùng `X-kai-nét`). Giá trị này chỉ áp dụng khi phát giọng nói;
giao diện và nội dung văn bản vẫn giữ nguyên `name`.

## Kiến trúc

```
User: "cắt video từ 1:23 đến 2:45"
          │
          ▼
   ┌─────────────┐
   │  Agent Loop  │
   └──────┬──────┘
          │
    ┌─────▼──────┐    có     ┌──────────┐
    │ Tìm skill  │─────────→│ Rút      │──→ Chạy skill
    │ trong      │           │ params   │
    │ registry   │           └──────────┘
    └─────┬──────┘
          │ không có
    ┌─────▼──────┐
    │ Gọi LLM   │──→ Sinh file .py ──→ Lưu vào skills/
    │ sinh skill │                          │
    └────────────┘                    Chạy skill vừa sinh
                                          │
                                    Lỗi? → Auto-fix 1 lần
```

## Hai model: trò chuyện (nhanh) + làm việc (thinking)

Trên dashboard, mỗi tin nhắn đi qua 2 giai đoạn:

```
Bạn gõ/nói
   │
   ▼
[Model CHAT — nhanh]  → trò chuyện / hỏi đáp  → trả lời ngay
   │ (nếu là tác vụ)
   ▼
Lập KẾ HOẠCH → render file HTML → hiện kèm nút ✅ Đồng ý / ✖ Từ chối
   │ (bạn bấm Đồng ý)
   ▼
[Model WORK — thinking]  → tìm/sinh skill → chạy → auto-fix → báo kết quả (đọc bằng giọng nói)
```

Chọn model cho từng vai trò trong `config.json` → `roles`:

```json
"roles": {
  "chat": { "provider": "gemini",   "model": "gemini-2.0-flash" },
  "work": { "provider": "deepseek", "model": "deepseek-reasoner" }
}
```

`chat` và `work` có thể dùng provider khác nhau. File HTML kế hoạch được lưu trong thư mục `plans/`.

## Cài đặt

```bash
pip install anthropic --break-system-packages
# hoặc
pip install google-generativeai --break-system-packages
```

## Cấu hình API key (config.json)

Mở `config.json`, chọn `provider` và dán API key vào provider tương ứng:

```json
{
  "provider": "gemini",
  "anthropic": { "api_key": "sk-ant-...", "model": "claude-sonnet-4-5" },
  "gemini":    { "api_key": "AIza...",    "model": "gemini-2.0-flash" },
  "openai":    { "api_key": "sk-...",     "model": "gpt-4o-mini" },
  "deepseek":  { "api_key": "sk-...",     "model": "deepseek-chat",
                 "base_url": "https://api.deepseek.com" }
}
```

Hỗ trợ 4 provider: **anthropic, gemini, openai, deepseek**. Chỉ cần điền key cho
provider bạn dùng. Nếu để `api_key` trống, agent sẽ tự đọc từ biến môi trường
(`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`).
SDK tương ứng được tự cài khi cần.

## Chạy

```bash
# Cách 1: dùng config.json (khuyến nghị) — không cần export gì

# Cách 2: dùng biến môi trường
export ANTHROPIC_API_KEY="sk-..."
# hoặc dùng Gemini:
export GEMINI_API_KEY="..."
export SKILL_AGENT_PROVIDER="gemini"

# Interactive mode
python agent.py

# One-shot
python agent.py "cắt video input.mp4 từ 00:01:23 đến 00:02:45"
python agent.py "resize ảnh photo.jpg về 800x600"
python agent.py "trộn 2 file audio voice.wav và bgm.mp3"
```

## Ví dụ hoạt động

```
> resize ảnh photo.jpg về 800x600

============================================================
[TASK] resize ảnh photo.jpg về 800x600
============================================================
[i] Có 2 skill trong registry
[!] Không có skill phù hợp → đang sinh skill mới...
[+] Skill mới được sinh: skills/resize_image.py
[i] Params: {"input_path": "photo.jpg", "width": 800, "height": 600}
[>] Đang chạy skill...
[✓] Thành công: Đã resize photo.jpg → photo_resized.jpg (800x600)

> resize ảnh banner.png về 1920x1080

[i] Có 3 skill trong registry
[✓] Match skill: resize_image          ← dùng lại skill đã sinh!
```

## Skill có sẵn

| Skill | Mô tả |
|-------|--------|
| `get_video_info` | Lấy duration, resolution, fps bằng ffprobe |
| `detect_scenes` | Phát hiện scene boundaries bằng PySceneDetect |

## Tự thêm skill

Tạo file `.py` trong `skills/` theo format:

```python
SKILL_META = {
    "name": "my_skill",
    "description": "Mô tả skill",
    "tags": ["tag1", "tag2"],
    "params": {
        "input_path": {"type": "str", "description": "...", "required": True},
    }
}

def run(**kwargs) -> dict:
    # logic
    return {"success": True, "result": "..."}
```

## Dashboard (giao diện web + giọng nói)

```bash
python server.py     # mở http://127.0.0.1:8765
```

- Gõ **hoặc bấm 🎙️ để nói**. Model *chat* phân loại: trò chuyện hay tác vụ.
- Nếu là tác vụ → hiện **KẾ HOẠCH** kèm nút ✅ Đồng ý / ✖ Từ chối (file HTML lưu trong `plans/`).
- Bấm **Đồng ý** → model *work* tìm/sinh skill → chạy → auto-fix → **đọc kết quả bằng giọng nói**.

Dashboard chỉ dùng thư viện chuẩn của Python — không cần Flask.

## Chạy thử offline (không cần API key)

Đặt `"provider": "mock"` trong `config.json` (hoặc `export SKILL_AGENT_PROVIDER=mock`), rồi:

```bash
python selftest.py   # kiểm tra cả luồng: chat, kế hoạch, tự sinh + chạy + tái dùng skill
```

## Bộ nhớ (memory)

Agent có bộ nhớ hai tầng, lưu trên đĩa trong thư mục `memory/` — không cần thư viện ngoài:

- **Ngắn hạn (hội thoại):** mỗi lượt chat được ghi lại theo phiên (`memory/chat_<session>.jsonl`).
  Trước khi gọi model, agent nạp vài lượt gần nhất vào ngữ cảnh.
- **Dài hạn (facts):** những điều đáng nhớ — sở thích, thông tin, và kết quả mỗi tác vụ đã chạy —
  lưu bền trong `memory/facts.jsonl`. Trước khi trả lời, agent gọi lại (`recall`) các fact
  **liên quan nhất** tới câu hỏi (chấm điểm theo từ khoá + ưu tiên fact mới) rồi chèn vào system prompt.

```python
from core.memory import Memory
m = Memory(session="me").load()
m.remember("Mình thích xuất ảnh ở 800x600", kind="preference", tags=["resize"])
m.recall("resize ảnh")        # -> các fact liên quan
m.context_block("resize ảnh") # -> khối ký ức + hội thoại để nhét vào prompt
```

`SkillAgent` tự động: ghi mỗi lượt chat, và sau mỗi tác vụ lưu lại "đã dùng skill nào, kết quả ra sao".

## Tool kiểu Hermes (function-calling)

Mỗi skill (`SKILL_META`) được "dịch" sang **JSON Schema chuẩn** giống Hermes / OpenAI function-calling,
để Agent nói cùng ngôn ngữ tool với các model fine-tune theo Hermes:

```python
agent.tool_schemas()   # [{"type":"function","function":{"name","description","parameters"}}, ...]
agent.tools_prompt()   # system prompt liệt kê mọi tool trong <tools>...</tools>
```

Model gọi tool bằng cú pháp Hermes, và Agent parse lại được:

```
<tool_call>{"name": "resize_image", "arguments": {"input_path": "a.jpg", "width": 800}}</tool_call>
```

```python
from core.tools import parse_tool_calls
parse_tool_calls(output)  # -> [{"name": "resize_image", "arguments": {...}}]
```

Cơ chế registry + tự sinh skill vẫn giữ nguyên; đây chỉ là lớp chuẩn hoá định dạng tool bên trên.

## Vòng đời một skill (sinh → kiểm thử → nhớ → tái dùng)

Khi gặp tác vụ chưa có skill, Agent KHÔNG chạy mù. Quy trình:

1. **Tìm lại trước khi sinh.** Khớp registry (lexical/LLM). Nếu không khớp, **hỏi bộ nhớ** (`_recall_skill`) xem đã từng dùng skill nào cho việc tương tự — memory tham gia chọn skill.
2. **Sinh skill mới** (nếu vẫn không có) — file `.py` kèm `SKILL_META` có **mô tả ngắn**.
3. **Kiểm thử trước khi nhận** (`_test_new_skill`): compile + smoke test bằng tham số rút được.
   - Lỗi **code** (cú pháp/import/exception) → auto-fix tối đa `MAX_FIX` lần (mặc định 2).
   - Lỗi **dữ liệu/đầu vào** (skill tự trả `success=False`, không ném exception) → coi như code ổn, **nhận** skill.
   - Vẫn lỗi code sau khi hết lượt sửa → **gỡ bỏ** skill hỏng (không để rác trong registry).
4. **Ghi nhớ để tái dùng.** Skill đạt được lưu vào `memory` dạng fact `kind='skill'` (tên + mô tả + tags); mỗi tác vụ lưu fact `kind='task'` (đã dùng skill nào, kết quả ra sao). Lần sau gặp việc tương tự, skill được khớp lại qua registry hoặc gợi ý qua bộ nhớ.

Phân biệt "lỗi code" và "lỗi dữ liệu" dựa vào cờ `_crashed` do `runner.run_skill` gắn khi skill ném exception. Kiểm thử tĩnh nằm ở `generator.validate()`.

## Tự phục hồi khi chạy lỗi

Khi một skill chạy **thất bại**, Agent không bỏ cuộc ngay mà tự khắc phục (`_recover`, tối đa `MAX_RECOVER` vòng):

1. **Thiếu thư viện Python** (skill trả `"pip install X"` hoặc `No module named 'X'`) → tự chạy `pip install X --break-system-packages` rồi thử lại. Cài được nhiều gói nối tiếp, mỗi gói thử một lần.
2. **Thiếu công cụ hệ thống** (vd `ffmpeg`, `ffprobe`, `tesseract`, `yt-dlp`...) → tự cài qua trình quản lý gói của HĐH: `winget`/`choco` (Windows), `brew` (macOS), `apt-get` (Linux) rồi thử lại.
3. **Đọc lại yêu cầu tham số** — `_param_schema` lấy schema, chuẩn hoá cả skill kiểu cũ (dùng `parameters` thay `params`).
4. **Tự điền tham số** (`_self_fill`): đặt tên mặc định cho tham số đầu ra; **quét thư mục làm việc** tìm tệp khớp loại (video/audio/ảnh); nhờ **LLM suy luận** từ yêu cầu + danh sách tệp + lỗi trước.
5. **Hỏi lại người dùng** nếu vẫn thiếu tham số **bắt buộc**: trả `needs_input` + `ask`; dashboard hiện câu hỏi và đọc to để bạn bổ sung.

Ví dụ "tạo biên bản cuộc họp từ video" mà quên đính kèm đường dẫn: nếu trong thư mục có đúng một tệp video, Agent tự dùng; thiếu `ffmpeg` thì tự cài; nếu vẫn bí thì hỏi lại đúng thứ còn thiếu.

## Tác vụ đa bước (pipeline)

Với yêu cầu **ghép nhiều thao tác** (vd "chia nhỏ video, tách phụ đề, rồi tạo biên bản"), `execute_task` gọi `_decompose` (dùng model WORK) để tách thành các bước tuần tự, rồi `_run_pipeline` chạy **từng bước một** qua đúng cơ chế tìm/sinh/kiểm thử/tự phục hồi ở trên. Bước sau có thể dùng tệp do bước trước tạo ra (nhờ `_self_fill` quét thư mục). Pipeline **dừng và báo rõ** nếu một bước thất bại, hoặc **hỏi lại** nếu một bước thiếu thông tin. Tác vụ đơn giản (một thao tác) chạy thẳng như cũ.

## Dev auto-reload (server)

`server.py` tự **nạp lại code** khi `core/*.py` thay đổi (so `mtime` mỗi request) — sửa code xong chỉ cần thao tác lại trên dashboard, khỏi tắt/mở lại server. Nếu `config.json` hoặc skill đang sửa dở gây lỗi, server **giữ nguyên bản đang chạy** và thử lại ở lần đổi kế tiếp. Tắt tính năng: đặt biến môi trường `AGENT_NO_RELOAD=1`.

## Cấu trúc dự án

```
agent.py      # CLI (tương tác + one-shot)
server.py     # Dashboard web + API (/api/message, /api/approve)
selftest.py   # kiểm thử offline bằng provider mock
config.json   # provider + roles + API key
core/         # llm · registry · generator · runner · planner · orchestrator · memory · tools · config
skills/       # skill .py (có sẵn + do agent tự sinh)
plans/        # kế hoạch HTML
memory/       # bộ nhớ: facts.jsonl (dài hạn) + chat_<session>.jsonl (hội thoại)
dashboard/    # giao diện web (chat + giọng nói)
```
"# AI Agent"
