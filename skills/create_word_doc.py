SKILL_META = {
    "name": "create_word_doc",
    "description": "Tạo một tệp Microsoft Word (.docx) với tiêu đề cho trước và lưu vào thư mục Documents của người dùng.",
    "parameters": {
        "title": "Tiêu đề nội dung bên trong file Word.",
        "filename": "Tên tệp tin (bao gồm phần mở rộng .docx)."
    }
}

def run(**kwargs) -> dict:
    import os
    from pathlib import Path

    # Lấy tham số
    title = kwargs.get("title", "kiểm tra skill")
    filename = kwargs.get("filename", "kiem_tra_skill.docx")

    # Đảm bảo filename có đuôi .docx
    if not filename.lower().endswith(".docx"):
        filename += ".docx"

    try:
        # Lazy import thư viện python-docx
        try:
            from docx import Document
        except ImportError:
            return {
                "success": False, 
                "error": "Thiếu thư viện hỗ trợ Word. Vui lòng cài đặt bằng lệnh: pip install python-docx"
            }

        # Xác định đường dẫn thư mục Documents
        # os.path.expanduser("~") sẽ trỏ đến thư mục người dùng (C:\Users\Name hoặc /home/name)
        documents_path = os.path.join(os.path.expanduser("~"), "Documents")
        
        # Kiểm tra nếu thư mục Documents không tồn tại (một số hệ thống Linux/Server)
        if not os.path.exists(documents_path):
            # Nếu không có Documents, lưu ở thư mục hiện tại
            save_path = os.path.abspath(filename)
        else:
            save_path = os.path.join(documents_path, filename)

        # Tạo nội dung file Word
        doc = Document()
        doc.add_heading(title, level=0)
        
        # Lưu file
        doc.save(save_path)

        return {
            "success": True,
            "result": {
                "message": f"Đã tạo file Word thành công.",
                "file_path": save_path,
                "title": title
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi khi tạo file Word: {str(e)}"
        }
