SKILL_META = {
    "name": "extract_audio_from_video_2",
    "description": "Trích xuất luồng âm thanh từ file video sử dụng ffmpeg.",
    "version": "1.0.0"
}

def run(**kwargs) -> dict:
    import os
    import subprocess

    input_path = kwargs.get("input_path")
    output_path = kwargs.get("output_path")

    if not input_path or not output_path:
        return {"success": False, "error": "Thiếu tham số input_path hoặc output_path"}

    if not os.path.exists(input_path):
        return {"success": False, "error": f"File không tồn tại: {input_path}"}

    try:
        # Kiểm tra ffmpeg
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        
        # Thực hiện trích xuất âm thanh
        # -i: input, -vn: bỏ video, -acodec copy: giữ nguyên codec hoặc chuyển đổi
        cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {"success": False, "error": f"Lỗi ffmpeg: {result.stderr}"}
            
        return {"success": True, "result": f"Đã trích xuất âm thanh thành công tại: {output_path}"}

    except FileNotFoundError:
        return {"success": False, "error": "Chưa cài đặt ffmpeg trên hệ thống. Vui lòng cài đặt ffmpeg."}
    except Exception as e:
        return {"success": False, "error": str(e)}
