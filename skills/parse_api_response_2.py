SKILL_META = {
    "name": "parse_api_response_2",
    "description": "Parse JSON response from an API call, either from a file or a string."
}

def run(**kwargs) -> dict:
    import json

    json_file = kwargs.get("json_file", "")
    json_string = kwargs.get("json_string", "")

    if json_file:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"success": True, "result": data}
        except FileNotFoundError:
            return {"success": False, "error": f"File not found: {json_file}"}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON in file: {str(e)}"}
    elif json_string:
        try:
            data = json.loads(json_string)
            return {"success": True, "result": data}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON string: {str(e)}"}
    else:
        return {"success": False, "error": "No input provided. Please specify 'json_file' or 'json_string'."}
