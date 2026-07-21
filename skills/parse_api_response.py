SKILL_META = {
    "name": "parse_api_response",
    "description": "Parse JSON string from API response and return structured data",
    "parameters": {
        "json_string": {
            "type": "string",
            "description": "JSON string to parse"
        }
    }
}

def run(**kwargs) -> dict:
    try:
        import json
        
        json_string = kwargs.get("json_string", "")
        if not json_string:
            return {"success": False, "error": "No JSON string provided"}
        
        data = json.loads(json_string)
        return {"success": True, "result": data}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
