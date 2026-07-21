SKILL_META = {
    "name": "select_first_video",
    "description": "Chọn video đầu tiên từ danh sách file để xử lý",
    "version": "1.0.0",
    "parameters": {
        "files": {
            "type": "list",
            "description": "Danh sách đường dẫn file video (strings)",
            "required": True
        }
    }
}

def run(**kwargs) -> dict:
    files = kwargs.get("files")
    if not files or not isinstance(files, list) or len(files) == 0:
        return {"success": False, "error": "Danh sách file trống hoặc không hợp lệ"}
    first_file = files[0]
    return {"success": True, "result": first_file}
