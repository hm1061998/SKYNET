import os

SKILL_META = {
    "name": "latest_video",
    "description": "Find the most recently modified video file in a given directory (default 'Uploads').",
    "parameters": {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Path to the directory to scan for video files (default: 'Uploads')"
            }
        },
        "required": []
    }
}

def run(**kwargs) -> dict:
    """
    Returns the full path of the most recently modified video file in the specified directory.
    Accepts keyword argument:
        directory: str (optional) - directory to scan, defaults to 'Uploads'.
    Returns:
        dict with success status and result (file path) or error message.
    """
    directory = kwargs.get("directory", "Uploads")
    
    # Validate directory existence
    if not os.path.isdir(directory):
        return {"success": False, "error": f"Directory '{directory}' not found."}
    
    # Common video extensions
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg', '.3gp'}
    
    video_files = []
    for entry in os.listdir(directory):
        full_path = os.path.join(directory, entry)
        if os.path.isfile(full_path):
            ext = os.path.splitext(entry)[1].lower()
            if ext in video_extensions:
                video_files.append(full_path)
    
    if not video_files:
        return {"success": False, "error": "No video files found in the directory."}
    
    # Find the file with the latest modification time
    latest_file = max(video_files, key=os.path.getmtime)
    
    return {"success": True, "result": latest_file}
