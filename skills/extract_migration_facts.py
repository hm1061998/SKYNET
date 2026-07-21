SKILL_META = {
    "name": "extract_migration_facts",
    "version": "1.0",
    "description": "Phân tích văn bản MIGRATION-NOTES.md, trích xuất các fact quan trọng được liệt kê dưới dạng gạch đầu dòng trong mục 'Facts cần nhớ'.",
    "params": {
        "text": "string: nội dung văn bản cần phân tích"
    }
}

def run(**kwargs) -> dict:
    import re

    text = kwargs.get("text", "")
    if not text:
        return {"success": False, "error": "Thiếu tham số 'text'."}

    # Tìm phần sau "## Facts cần nhớ"
    match = re.search(r'##\s*Facts cần nhớ\s*\n(.*?)(?=\n#|$)', text, re.DOTALL)
    if not match:
        # Thử tìm alternate "## Facts cần nhớ" có thể viết hoa/thường
        match = re.search(r'##\s*[Ff]acts\s*[cầCầ]n\s*[nN]hớ\s*\n(.*?)(?=\n#|$)', text, re.DOTALL)
        if not match:
            return {"success": True, "result": []}  # Không có mục Facts, trả về rỗng

    facts_block = match.group(1).strip()
    # Tách dòng
    lines = facts_block.splitlines()
    facts = []
    for line in lines:
        stripped = line.strip()
        # Bắt đầu bằng dấu gạch đầu dòng: "- " hoặc "* "
        if re.match(r'[-*]\s+', stripped):
            # Bỏ dấu gạch và khoảng trắng
            fact = re.sub(r'^[-*]\s+', '', stripped).strip()
            if fact:
                facts.append(fact)
    return {"success": True, "result": facts}
