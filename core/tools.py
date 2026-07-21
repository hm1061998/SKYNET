"""Chuẩn hoá skill của Agent sang định dạng TOOL kiểu Hermes / OpenAI function-calling.

Ý tưởng: registry của Agent đã có `SKILL_META` (name + description + params). Ở đây ta
'dịch' nó sang JSON Schema chuẩn để:

  • đưa cho model dưới dạng danh sách <tools> (giống Hermes),
  • cho model gọi tool bằng cú pháp <tool_call>{"name":..., "arguments":{...}}</tool_call>,
  • parse lại tool_call đó thành (name, arguments) để agent thực thi.

Nhờ vậy Agent nói cùng 'ngôn ngữ tool' với các model được fine-tune theo Hermes, đồng thời
vẫn giữ nguyên cơ chế registry + tự sinh skill sẵn có.
"""
from __future__ import annotations
from .identity import AGENT_NAME

import json
import re

# JSON Schema type tương ứng với "type" trong SKILL_META params
_TYPE_MAP = {
    "str": "string", "string": "string", "text": "string",
    "int": "integer", "integer": "integer",
    "float": "number", "number": "number",
    "bool": "boolean", "boolean": "boolean",
    "list": "array", "array": "array",
    "dict": "object", "object": "object",
}


def to_openai_schema(meta: dict) -> dict:
    """SKILL_META -> tool schema kiểu OpenAI/Hermes: {"type":"function","function":{...}}."""
    props: dict[str, dict] = {}
    required: list[str] = []
    for pname, spec in (meta.get("params", {}) or {}).items():
        spec = spec or {}
        jtype = _TYPE_MAP.get(str(spec.get("type", "str")).lower(), "string")
        p = {"type": jtype}
        if spec.get("description"):
            p["description"] = spec["description"]
        if "default" in spec:
            p["default"] = spec["default"]
        if "enum" in spec:
            p["enum"] = spec["enum"]
        props[pname] = p
        if spec.get("required"):
            required.append(pname)
    return {
        "type": "function",
        "function": {
            "name": meta.get("name", ""),
            "description": meta.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        },
    }


def registry_to_schemas(registry) -> list[dict]:
    """Trả danh sách tool schema cho mọi skill hiện có trong registry."""
    out = []
    for _name, entry in registry.skills.items():
        out.append(to_openai_schema(entry["meta"]))
    return out


# Hệ thống prompt kiểu Hermes: liệt kê tool trong <tools>, yêu cầu gọi bằng <tool_call>.
_HERMES_SYS = """Bạn là {agent_name} — trợ lý gọi công cụ (function calling). Bạn có các công cụ sau, \
mô tả bằng JSON Schema trong cặp thẻ <tools></tools>:

<tools>
{tools}
</tools>

Khi cần dùng công cụ, trả về MỘT lời gọi cho mỗi công cụ, đặt trong cặp thẻ \
<tool_call></tool_call>, với nội dung là JSON đúng dạng:
<tool_call>{{"name": "<tên công cụ>", "arguments": {{<tham số>}}}}</tool_call>

Nếu không cần công cụ nào, cứ trả lời bằng lời tự nhiên (tiếng Việt). Không bịa tên công cụ \
ngoài danh sách trên."""


def hermes_system_prompt(schemas: list[dict]) -> str:
    """Dựng system prompt kiểu Hermes từ danh sách tool schema."""
    tools = "\n".join(json.dumps(s, ensure_ascii=False) for s in schemas)
    return _HERMES_SYS.format(agent_name=AGENT_NAME, tools=tools)


_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.S)


def parse_tool_calls(text: str) -> list[dict]:
    """Rút mọi lời gọi công cụ từ output của model.

    Ưu tiên cú pháp Hermes <tool_call>{...}</tool_call>. Nếu không có thẻ, thử coi cả
    chuỗi là một JSON {"name":..., "arguments":...}. Trả list [{"name","arguments"}].
    """
    calls: list[dict] = []
    blocks = _TOOL_CALL_RE.findall(text or "")
    if blocks:
        for b in blocks:
            obj = _loads(b)
            if isinstance(obj, dict) and obj.get("name"):
                calls.append(_normalize(obj))
        return calls

    obj = _loads(text or "")
    if isinstance(obj, dict) and obj.get("name"):
        calls.append(_normalize(obj))
    return calls


def _normalize(obj: dict) -> dict:
    args = obj.get("arguments", obj.get("parameters", {}))
    if isinstance(args, str):
        args = _loads(args) or {}
    return {"name": obj["name"], "arguments": args if isinstance(args, dict) else {}}


def _loads(s: str):
    s = (s or "").strip()
    try:
        return json.loads(s)
    except Exception:
        # tìm khối {...} cân bằng đầu tiên
        start = s.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(s)):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i + 1])
                    except Exception:
                        return None
        return None
