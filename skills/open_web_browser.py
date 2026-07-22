SKILL_META = {
    "name": "open_web_browser",
    "description": "Mở trình duyệt web mặc định của hệ thống với một URL cụ thể.",
    "parameters": {
        "url": {
            "type": "string",
            "description": "Địa chỉ URL cần mở (ví dụ: https://google.com). Nếu để trống sẽ mở trang mặc định.",
            "required": False
        }
    }
}

def run(**kwargs) -> dict:
    """
    Thực hiện mở trình duyệt web.
    """
    import webbrowser
    
    url = kwargs.get("url", "https://www.google.com")
    
    # Đảm bảo URL có scheme nếu người dùng quên
    if url and not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    try:
        # webbrowser.open trả về True nếu trình duyệt được khởi chạy thành công
        success = webbrowser.open(url)
        
        if success:
            return {
                "success": True,
                "result": f"Đã mở trình duyệt tại địa chỉ: {url}"
            }
        else:
            return {
                "success": False,
                "error": "Không thể khởi chạy trình duyệt web mặc định."
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi khi mở trình duyệt: {str(e)}"
        }
