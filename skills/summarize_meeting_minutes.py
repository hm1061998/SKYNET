SKILL_META = {
    "name": "summarize_meeting_minutes",
    "description": "Tóm tắt nội dung văn bản (transcript, SRT) thành biên bản cuộc họp, xuất ra file hoặc trả về văn bản.",
    "params": {
        "input_text_file": "đường dẫn file văn bản chứa transcript cuộc họp (có thể là SRT hoặc plain text)",
        "output_text_file": "đường dẫn file lưu biên bản (tùy chọn, nếu không có chỉ trả về nội dung)",
        "num_sentences": "số câu tóm tắt muốn trích xuất (mặc định 20)"
    },
    "dependencies": []
}

import re
import os
from datetime import datetime

def clean_srt_text(text):
    """Loại bỏ số thứ tự và mốc thời gian khỏi nội dung SRT, giữ lại lời thoại."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if '-->' in line:
            continue
        if re.match(r'\d{2}:\d{2}:\d{2}[.,]\d{3}', line):
            continue
        cleaned.append(line)
    return ' '.join(cleaned)

def split_sentences(text):
    """Tách văn bản thành các câu dựa trên dấu câu."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def simple_summarize(text, num_sentences=20):
    """Tóm tắt văn bản bằng phương pháp trích xuất câu dựa trên TF và từ khóa."""
    sentences = split_sentences(text)
    if not sentences:
        return ""
    if len(sentences) <= num_sentences:
        return text  # trả về toàn bộ nếu ít câu

    keywords = ['quyết định', 'hành động', 'cần', 'phải', 'sẽ', 'kế hoạch', 'nhiệm vụ',
                'vấn đề', 'giải pháp', 'đề xuất', 'thống nhất', 'kết luận', 'yêu cầu',
                'deadline', 'hạn', 'hoàn thành', 'báo cáo', 'phân công', 'phụ trách']

    word_freq = {}
    for sentence in sentences:
        words = re.findall(r'\w+', sentence.lower())
        for w in words:
            word_freq[w] = word_freq.get(w, 0) + 1

    def score(sentence):
        words = re.findall(r'\w+', sentence.lower())
        if not words:
            return 0
        tf_sum = sum(word_freq.get(w, 0) for w in words) / len(words)
        kw_score = sum(0.5 for kw in keywords if kw in sentence.lower())
        len_score = min(len(words) / 20.0, 1.0)
        return tf_sum + kw_score + len_score

    scored = [(score(s), s) for s in sentences]
    scored.sort(reverse=True)
    top_sentences = sorted([s for _, s in scored[:num_sentences]], key=lambda s: sentences.index(s))
    return ' '.join(top_sentences)

def run(**kwargs) -> dict:
    try:
        input_file = kwargs.get('input_text_file')
        if not input_file:
            return {"success": False, "error": "Thiếu tham số 'input_text_file'"}
        if not os.path.exists(input_file):
            return {"success": False, "error": f"File không tồn tại: {input_file}"}

        num_sentences = int(kwargs.get('num_sentences', 20))
        output_file = kwargs.get('output_text_file')

        with open(input_file, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        # Làm sạch nếu là SRT
        if '-->' in raw_text:
            clean_text = clean_srt_text(raw_text)
        else:
            clean_text = raw_text

        # Tóm tắt
        summarized = simple_summarize(clean_text, num_sentences)
        if not summarized:
            summarized = clean_text  # fallback to full text if summarization returns empty

        # Tạo biên bản
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        minutes_template = (
            "BIÊN BẢN CUỘC HỌP\n"
            f"Ngày tạo: {now}\n"
            "----------------------------------------\n"
            f"{summarized}\n"
            "----------------------------------------\n"
            "Ghi chú: Đây là biên bản được tạo tự động từ transcript cuộc họp.\n"
        )

        result = {"success": True, "result": minutes_template}

        if output_file:
            os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(minutes_template)
            result["output_file"] = output_file

        return result

    except Exception as e:
        return {"success": False, "error": str(e)}
