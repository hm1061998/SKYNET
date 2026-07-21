SKILL_META = {
    "name": "speech_to_srt_whisper",
    "description": "Chuyển file âm thanh (WAV) thành phụ đề SRT sử dụng OpenAI Whisper offline. Hỗ trợ nhiều ngôn ngữ.",
    "parameters": {
        "audio_path": "Đường dẫn tới file âm thanh (.wav)",
        "language": "Ngôn ngữ của file (ví dụ 'vi', 'en'). Mặc định 'vi'.",
        "output_srt": "Đường dẫn file SRT xuất ra. Nếu null, tự tạo cùng thư mục với tên file gốc."
    },
    "tags": ["audio", "speech-to-text", "srt", "whisper"]
}

def run(**kwargs) -> dict:
    import os
    import warnings

    # Lấy tham số
    audio_path = kwargs.get("audio_path")
    if not audio_path or not os.path.isfile(audio_path):
        return {"success": False, "error": f"File âm thanh không tồn tại: {audio_path}"}

    language = kwargs.get("language", "vi")
    if not language:
        language = "vi"

    output_srt = kwargs.get("output_srt")
    if not output_srt:
        base = os.path.splitext(audio_path)[0]
        output_srt = base + ".srt"

    # Lazy import whisper
    try:
        import whisper
    except ImportError:
        return {"success": False, "error": "Thiếu thư viện 'openai-whisper'. Vui lòng cài: pip install openai-whisper"}

    # Tắt cảnh báo không cần thiết
    warnings.filterwarnings("ignore")

    try:
        # Load model (có thể chọn tiny/base/small/medium/large)
        model = whisper.load_model("medium")  # Cân bằng tốc độ và chất lượng
    except Exception as e:
        return {"success": False, "error": f"Không thể load model Whisper: {str(e)}"}

    try:
        # Transcribe
        result = model.transcribe(audio_path, language=language, verbose=False)
    except Exception as e:
        return {"success": False, "error": f"Lỗi khi chuyển đổi giọng nói: {str(e)}"}

    # Tạo file SRT
    segments = result.get("segments", [])
    if not segments:
        return {"success": False, "error": "Không tìm thấy phân đoạn nào."}

    try:
        with open(output_srt, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, start=1):
                start = seg["start"]
                end = seg["end"]
                text = seg["text"].strip()
                # Định dạng thời gian SRT: HH:MM:SS,mmm
                start_str = format_timestamp(start)
                end_str = format_timestamp(end)
                f.write(f"{i}\n{start_str} --> {end_str}\n{text}\n\n")
    except Exception as e:
        return {"success": False, "error": f"Không thể ghi file SRT: {str(e)}"}

    return {
        "success": True,
        "result": {
            "srt_path": output_srt,
            "segment_count": len(segments)
        }
    }

def format_timestamp(seconds: float) -> str:
    """Đổi giây thành SRT timestamp HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
