import os
import tempfile
import subprocess
import shutil
import wave

SKILL_META = {
    "name": "extract_audio_transcribe",
    "description": "Trích xuất âm thanh từ video và chuyển đổi thành văn bản bằng nhận dạng giọng nói (qua Google Speech Recognition).",
    "params": {
        "video_path": "Đường dẫn đến file video đầu vào (bắt buộc).",
        "language": "Mã ngôn ngữ cho nhận dạng (mặc định 'vi-VN').",
        "output_text_file": "Đường dẫn file text để lưu kết quả (tùy chọn). Nếu có, lưu vào file và trả về nội dung."
    },
    "required": ["video_path"]
}

def run(**kwargs) -> dict:
    video_path = kwargs.get("video_path")
    if not video_path or not os.path.exists(video_path):
        return {"success": False, "error": "File video không tồn tại hoặc không được cung cấp."}

    language = kwargs.get("language", "vi-VN")
    output_text_file = kwargs.get("output_text_file", None)
    chunk_duration = 55  # mỗi chunk dài tối đa 55 giây để tránh giới hạn của Google (thường khoảng 60s)

    tmp_dir = tempfile.mkdtemp()
    audio_path = os.path.join(tmp_dir, "extracted_audio.wav")

    try:
        if not shutil.which("ffmpeg"):
            return {"success": False, "error": "Cần cài đặt ffmpeg để trích xuất âm thanh."}

        # Trích xuất âm thanh dạng mono 16kHz PCM
        ffmpeg_cmd = [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            "-y", audio_path
        ]
        proc = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return {"success": False, "error": f"Lỗi ffmpeg: {proc.stderr.strip()}"}

        # Lazy import speech_recognition
        try:
            import speech_recognition as sr
        except ImportError:
            return {"success": False, "error": "Thiếu thư viện SpeechRecognition. Cài đặt: pip install SpeechRecognition"}

        recognizer = sr.Recognizer()
        text = _transcribe_with_chunking(audio_path, recognizer, language, chunk_duration)

        if text is None:
            return {"success": False, "error": "Không thể nhận dạng nội dung giọng nói sau khi chunk."}

        # Lưu ra file nếu được yêu cầu
        if output_text_file:
            with open(output_text_file, "w", encoding="utf-8") as f:
                f.write(text)

        return {
            "success": True,
            "text": text,
            "output_file": output_text_file if output_text_file else None
        }

    except Exception as e:
        return {"success": False, "error": f"Lỗi không xác định: {str(e)}"}

    finally:
        # Dọn dẹp thư mục tạm
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _transcribe_with_chunking(audio_path, recognizer, language, chunk_duration):
    """
    Nhận dạng giọng nói, tự động chia thành các chunk nếu file quá dài.
    """
    import speech_recognition as sr

    with wave.open(audio_path, 'rb') as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        duration = n_frames / framerate

        if duration <= chunk_duration:
            # Không cần chunk, nhận dạng toàn bộ
            with sr.AudioFile(audio_path) as source:
                audio_data = recognizer.record(source)
            try:
                return recognizer.recognize_google(audio_data, language=language)
            except sr.UnknownValueError:
                return None
            except sr.RequestError as e:
                raise e

        # Chunking
        chunk_samples = int(chunk_duration * framerate)
        full_text = []
        offset = 0
        while offset < n_frames:
            remaining = n_frames - offset
            read_frames = min(chunk_samples, remaining)
            wf.setpos(offset)
            raw_data = wf.readframes(read_frames)
            offset += read_frames

            # Tạo AudioData từ raw_data
            audio_data = sr.AudioData(raw_data, framerate, sample_width)
            try:
                chunk_text = recognizer.recognize_google(audio_data, language=language)
                full_text.append(chunk_text)
            except sr.UnknownValueError:
                # Bỏ qua chunk không nhận dạng được
                continue
            except sr.RequestError as e:
                # Nếu lỗi mạng hoặc giới hạn rate, ta dừng và báo lỗi
                raise e

        if not full_text:
            return None
        return " ".join(full_text)
