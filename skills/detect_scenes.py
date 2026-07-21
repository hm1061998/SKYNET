SKILL_META = {
    "name": "detect_scenes",
    "description": "Phát hiện ranh giới cảnh (scene boundaries) trong video bằng PySceneDetect",
    "tags": ["video", "scene", "pyscenedetect", "detect", "boundary", "cut"],
    "params": {
        "input_path": {"type": "str", "description": "Đường dẫn tệp video", "required": True},
        "threshold": {"type": "float", "description": "Ngưỡng phát hiện (mặc định 27.0)",
                      "required": False, "default": 27.0},
    },
}


def run(**kwargs) -> dict:
    import os

    path = kwargs.get("input_path")
    if not path or not os.path.exists(path):
        return {"success": False, "error": f"Không tìm thấy tệp video: {path}"}

    try:
        from scenedetect import ContentDetector, detect
    except ImportError:
        return {"success": False,
                "error": "Chưa cài PySceneDetect. Chạy: pip install scenedetect"}

    threshold = float(kwargs.get("threshold", 27.0))
    scene_list = detect(path, ContentDetector(threshold=threshold))
    scenes = [
        {"scene": i + 1, "start": s.get_timecode(), "end": e.get_timecode()}
        for i, (s, e) in enumerate(scene_list)
    ]
    return {
        "success": True,
        "result": {"num_scenes": len(scenes), "scenes": scenes},
    }
