import os
import re
import math
from collections import Counter

SKILL_META = {
    "name": "summarize_to_meeting_minutes",
    "description": "Tóm tắt văn bản (từ transcript/SRT) thành biên bản cuộc họp dạng text, sử dụng thuật toán extractive TextRank đơn giản.",
    "params": [
        {"name": "input_text_file", "type": "str", "required": True, "description": "Đường dẫn file văn bản hoặc SRT đầu vào"},
        {"name": "output_summary_file", "type": "str", "required": False, "description": "Đường dẫn file lưu biên bản, mặc định lưu cùng thư mục với input"},
        {"name": "language", "type": "str", "required": False, "default": "vi", "description": "Ngôn ngữ văn bản: vi hoặc en"},
        {"name": "max_sentences", "type": "int", "required": False, "default": 10, "description": "Số câu tối đa trong phần tóm tắt"}
    ]
}

# Không cần lazy imports vì chỉ dùng stdlib
# Nếu có thư viện nặng (ví dụ nltk) sẽ được import trong run()

def looks_like_srt(text: str) -> bool:
    """Kiểm tra xem văn bản có dạng SRT không (có số thứ tự và timestamp)"""
    lines = text.strip().split('\n')
    for line in lines:
        if re.match(r'\d+', line.strip()) and '-->' in text:
            return True
    return False

def extract_text_from_srt(srt_text: str) -> str:
    """Trích xuất phần văn bản thuần túy từ nội dung SRT"""
    # Xóa số thứ tự và timestamp, chỉ giữ lại phần text
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    texts = []
    for block in blocks:
        lines = block.strip().split('\n')
        # Block SRT thường có 2-3 dòng: số thứ tự, timestamp, text (có thể nhiều dòng)
        if len(lines) >= 2 and re.match(r'\d+', lines[0].strip()) and '-->' in lines[1]:
            # Bắt đầu từ dòng thứ 2 (index 1) trở đi là text (trừ dòng timestamp)
            # Nhưng cần lấy từ dòng thứ 2 trở đi, bỏ qua dòng timestamp
            # Vì dòng timestamp là dòng thứ 2 (index 1), text là từ dòng thứ 3 (index 2)
            text_lines = lines[2:]  # từ dòng thứ 3 trở đi
            if text_lines:
                texts.append(' '.join(text_lines))
        else:
            # Có thể block không đúng chuẩn, lấy toàn bộ trừ dòng đầu
            if len(lines) > 1:
                texts.append(' '.join(lines[1:]))
    return ' '.join(texts).strip()

def split_sentences(text: str, lang: str) -> list:
    """Tách văn bản thành danh sách các câu"""
    # Đơn giản: tách theo dấu câu kết thúc câu: .!?
    # Cải thiện: không tách sau các chữ viết tắt, số thập phân
    if lang == 'vi':
        # Tiếng Việt thường dùng dấu ., !, ? để kết thúc câu
        return re.split(r'(?<=[.!?])\s+', text)
    else:
        # Ngôn ngữ khác cũng tương tự
        return re.split(r'(?<=[.!?])\s+', text)

def tokenize(sentence: str, lang: str) -> list:
    """Tách từ đơn giản, loại bỏ dấu câu, chuyển thường"""
    # Tách theo khoảng trắng và loại bỏ ký tự không phải chữ cái/số
    tokens = re.findall(r'[a-zA-Z0-9_À-ỹ]+', sentence.lower())
    return tokens

def get_stop_words(lang: str) -> set:
    """Trả về tập stop words cho ngôn ngữ"""
    stopwords_vi = {
        'và', 'của', 'là', 'có', 'được', 'trong', 'với', 'một', 'những', 'các',
        'cho', 'để', 'khi', 'tại', 'vào', 'ra', 'cũng', 'đã', 'đang', 'sẽ',
        'thì', 'mà', 'này', 'kia', 'đó', 'ấy', 'nên', 'vì', 'hay', 'hoặc',
        'rằng', 'thế', 'nào', 'sao', 'ai', 'gì', 'nếu', 'như', 'tuy', 'nhưng'
    }
    stopwords_en = {
        'the', 'is', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'to', 'for',
        'with', 'this', 'that', 'it', 'as', 'at', 'by', 'from', 'are', 'was',
        'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'can', 'shall',
        'but', 'not', 'no', 'so', 'if', 'then', 'than', 'too', 'very', 'just',
        'about', 'also', 'such', 'all', 'its', 'how', 'which', 'who', 'whom',
        'what', 'when', 'where', 'why'
    }
    if lang == 'vi':
        return stopwords_vi
    else:
        return stopwords_en

def cosine_similarity(vec1, vec2):
    """Tính cosine similarity giữa hai vector từ điển (từ -> tần suất)"""
    intersection = set(vec1.keys()) & set(vec2.keys())
    if not intersection:
        return 0.0
    dot_product = sum(vec1[word] * vec2[word] for word in intersection)
    norm1 = math.sqrt(sum(val**2 for val in vec1.values()))
    norm2 = math.sqrt(sum(val**2 for val in vec2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)

def build_sentence_vectors(tokenized_sentences):
    """Xây dựng vector tần suất từ cho mỗi câu"""
    vectors = []
    for tokens in tokenized_sentences:
        vec = Counter(tokens)
        vectors.append(vec)
    return vectors

def textrank(tokenized_sentences, damping=0.85, max_iter=100, tolerance=1e-4):
    """Tính điểm TextRank cho các câu"""
    n = len(tokenized_sentences)
    if n == 0:
        return []
    if n == 1:
        return [1.0]

    # Xây dựng ma trận tương đồng
    vectors = build_sentence_vectors(tokenized_sentences)
    similarity_matrix = [[0.0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                sim = cosine_similarity(vectors[i], vectors[j])
                if sim > 0:
                    similarity_matrix[i][j] = sim

    # Chuẩn hóa ma trận theo hàng (row normalization) để thành xác suất chuyển tiếp
    for i in range(n):
        row_sum = sum(similarity_matrix[i])
        if row_sum > 0:
            for j in range(n):
                similarity_matrix[i][j] /= row_sum

    # Khởi tạo rank
    ranks = [1.0 / n] * n

    # Lặp
    for _ in range(max_iter):
        new_ranks = [0.0] * n
        for i in range(n):
            # Phần teleport
            new_ranks[i] = (1 - damping) / n
            # Phần từ các câu khác
            for j in range(n):
                if j != i and similarity_matrix[j][i] > 0:
                    new_ranks[i] += damping * similarity_matrix[j][i] * ranks[j]
        # Kiểm tra hội tụ
        diff = sum(abs(new_ranks[i] - ranks[i]) for i in range(n))
        ranks = new_ranks
        if diff < tolerance:
            break

    return ranks

def run(**kwargs) -> dict:
    try:
        input_file = kwargs.get("input_text_file")
        if not input_file:
            return {"success": False, "error": "Thiếu tham số 'input_text_file'"}
        if not os.path.exists(input_file):
            return {"success": False, "error": f"File không tồn tại: {input_file}"}

        output_file = kwargs.get("output_summary_file")
        if not output_file:
            base = os.path.splitext(input_file)[0]
            output_file = base + "_meeting_summary.txt"

        language = kwargs.get("language", "vi").lower()
        max_sentences = int(kwargs.get("max_sentences", 10))

        # Đọc nội dung file
        with open(input_file, "r", encoding="utf-8") as f:
            raw_text = f.read()

        # Nếu là file SRT, trích xuất chỉ phần text
        if looks_like_srt(raw_text):
            clean_text = extract_text_from_srt(raw_text)
        else:
            clean_text = raw_text

        if not clean_text.strip():
            return {"success": False, "error": "Không có nội dung văn bản sau khi xử lý"}

        # Tách câu
        sentences = split_sentences(clean_text, language)
        if not sentences:
            sentences = [clean_text.strip()]

        # Lọc câu rỗng
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return {"success": False, "error": "Không có câu nào để tóm tắt"}

        original_sentences = sentences[:]  # giữ lại để sắp xếp theo thứ tự

        # Tiền xử lý: tách từ, loại stop words
        stop_words = get_stop_words(language)
        tokenized_sentences = []
        for sent in sentences:
            tokens = tokenize(sent, language)
            tokens = [t for t in tokens if t not in stop_words and len(t) > 1]
            tokenized_sentences.append(tokens)

        # Tính điểm
        ranks = textrank(tokenized_sentences)

        # Chọn top câu theo rank
        ranked_indices = sorted(range(len(ranks)), key=lambda i: ranks[i], reverse=True)
        selected_indices = sorted(ranked_indices[:max_sentences])  # sắp xếp lại theo thứ tự xuất hiện

        summary_sentences = [original_sentences[i] for i in selected_indices]

        # Tạo biên bản họp
        minutes_header = "--- BIÊN BẢN CUỘC HỌP ---\n\n"
        minutes_body = " ".join(summary_sentences)
        full_minutes = minutes_header + minutes_body + "\n"

        # Ghi ra file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(full_minutes)

        return {
            "success": True,
            "summary_text": full_minutes,
            "output_file": output_file,
            "selected_sentences": len(selected_indices),
            "total_sentences": len(sentences)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
