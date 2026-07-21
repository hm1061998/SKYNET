```python
SKILL_META = {
    "name": "video_meeting_minutes_pdf",
    "description": "Generates a meeting minutes PDF from a video recording. Extracts audio, transcribes using Whisper (or Google Speech Recognition as fallback), and creates a structured PDF.",
    "parameters": {
        "video_path": "Path to the input meeting video file.",
        "output_pdf_path": "Path to save the output PDF. If not provided, defaults to same folder with .pdf extension."
    }
}

def run(**kwargs) -> dict:
    import os
    import subprocess

    video_path = kwargs.get("video_path")
    output_pdf_path = kwargs.get("output_pdf_path")

    if not video_path:
        return {"success": False, "error": "Video path not provided."}

    if not os.path.exists(video_path):
        return {"success": False, "error": f"Video file does not exist: {video_path}"}

    # Derive default output PDF path if not given
    if not output_pdf_path:
        base, _ = os.path.splitext(video_path)
        output_pdf_path = base + ".pdf"

    # 1. Extract audio from video
    audio_path = "temp_audio.wav"
    ffmpeg_cmd
