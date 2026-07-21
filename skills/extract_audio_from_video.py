SKILL_META = {
    "name": "extract_audio_from_video",
    "description": "Trích xuất âm thanh từ file video bằng ffmpeg, xuất ra file WAV 16kHz mono.",
    "input_schema": {
        "video_path": {"type": "string", "desc": "Đường dẫn đến file video đầu vào"},
        "audio_output_path": {"type": "string", "desc": "Đường dẫn file âm thanh đầu ra (nếu không có, tự tạo)", "optional": True}
    },
    "output_schema": {
        "audio_path": {"type": "string", "desc": "Đường dẫn file âm thanh đã trích xuất"}
    }
}

def run(**kwargs) -> dict:
    import os
    import subprocess
    import shutil

    video_path = kwargs.get("video_path")
    if not video_path:
        return {"success": False, "error": "Thiếu tham số video_path"}

    if not os.path.exists(video_path):
        return {"success": False, "error": f"File video không tồn tại: {video_path}"}

    # Xác định đường dẫn đầu ra
    audio_output_path = kwargs.get("audio_output_path")
    if not audio_output_path:
        base, _ = os.path.splitext(video_path)
        audio_output_path = base + "_audio.wav"

    # Kiểm tra ffmpeg
    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        return {"success": False, "error": "ffmpeg không được tìm thấy. Vui lòng cài đặt ffmpeg và thêm vào PATH."}

    # Lệnh ffmpeg: không re-encode video, lấy audio PCM 16kHz mono
    cmd = [
        ffmpeg_exe,
        "-i", video_path,
        "-vn",                  # bỏ luồng video
        "-acodec", "pcm_s16le", # PCM 16-bit little-endian
        "-ar", "16000",         # sample rate 16kHz (thường dùng cho nhận dạng giọng nói)
        "-ac", "1",             # mono
        "-y",                   # ghi đè nếu file đích tồn tại
        audio_output_path
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            return {"success": False, "error": f"ffmpeg lỗi (mã {proc.returncode}): {proc.stderr.strip()}"}
    except Exception as e:
        return {"success": False, "error": f"Lỗi khi chạy ffmpeg: {str(e)}"}

    if not os.path.exists(audio_output_path):
        return {"success": False, "error": "Không tìm thấy file âm thanh đầu ra sau khi trích xuất"}

    return {"success": True, "result": {"audio_path": audio_output_path}}
