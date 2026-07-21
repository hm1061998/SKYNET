"""Tự động cài package Python khi thiếu.

Dùng chung cho registry (lỗi import lúc nạp skill) và orchestrator (lỗi lúc chạy skill).
Tắt bằng biến môi trường JAVIS_NO_AUTO_INSTALL=1.
"""
from __future__ import annotations
import importlib
import os
import re
import subprocess
import sys

# Tên module import ≠ tên gói pip
IMPORT_TO_PIP = {
    "cv2": "opencv-python",
    "PIL": "pillow",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "skimage": "scikit-image",
    "dotenv": "python-dotenv",
    "fitz": "pymupdf",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "Crypto": "pycryptodome",
    "dateutil": "python-dateutil",
    "serial": "pyserial",
    "usb": "pyusb",
    "win32api": "pywin32",
    "win32com": "pywin32",
    "win32con": "pywin32",
    "win32gui": "pywin32",
    "wx": "wxpython",
    "cairo": "pycairo",
    "gi": "pygobject",
    "OpenSSL": "pyopenssl",
    "jwt": "pyjwt",
    "mpl_toolkits": "matplotlib",
    "speech_recognition": "SpeechRecognition",
    "youtube_dl": "youtube-dl",
    "yt_dlp": "yt-dlp",
    "moviepy": "moviepy",
    "scenedetect": "scenedetect",
    "whisper": "openai-whisper",
    "google.generativeai": "google-generativeai",
}

_VALID_PKG = re.compile(r"^[A-Za-z0-9_.\-\[\]=<>,!~ ]+$")


def enabled() -> bool:
    return os.environ.get("JAVIS_NO_AUTO_INSTALL", "").strip() not in ("1", "true", "yes")


def pip_name(module: str) -> str:
    """Đổi tên module import -> tên gói pip."""
    module = (module or "").strip()
    return IMPORT_TO_PIP.get(module) or IMPORT_TO_PIP.get(module.split(".")[0], module.split(".")[0])


def missing_package(error: str) -> str | None:
    """Rút tên GÓI PIP còn thiếu từ thông báo lỗi.

    Nhận diện: contract 'pip install X' của skill, hoặc ImportError/ModuleNotFoundError.
    """
    if not error:
        return None
    m = re.search(r"pip install\s+([A-Za-z0-9_.\-\[\]=<>]+)", error)
    if m:
        return m.group(1)
    m = re.search(r"No module named ['\"]([A-Za-z0-9_.]+)['\"]", str(error))
    if m:
        return pip_name(m.group(1))
    return None


def pip_install(pkg: str, log=None, timeout: int = 300) -> bool:
    """pip install một gói. Trả True nếu thành công."""
    _log = log or (lambda m: None)
    pkg = str(pkg).strip()
    if not _VALID_PKG.match(pkg):
        _log(f"[!] Tên gói không hợp lệ, bỏ qua: {pkg}")
        return False
    if not enabled():
        _log("[!] Auto-install đang tắt (JAVIS_NO_AUTO_INSTALL=1).")
        return False
    _log(f"[>] pip install {pkg} ...")
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
            capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0 and "--break-system-packages" in (r.stderr or ""):
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "--break-system-packages", "--quiet"],
                capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            _log(f"[!] pip lỗi: {(r.stderr or r.stdout or '').strip()[:200]}")
            return False
        # gói có thể vừa được cài vào user-site chưa có trong sys.path (lần cài đầu tiên)
        try:
            import site
            usp = site.getusersitepackages()
            if usp and os.path.isdir(usp) and usp not in sys.path:
                site.addsitedir(usp)
        except Exception:
            pass
        importlib.invalidate_caches()
        return True
    except Exception as e:
        _log(f"[!] Không chạy được pip: {e}")
        return False


def ensure_module(module: str, log=None) -> bool:
    """Đảm bảo import được `module`; nếu thiếu thì tự cài gói pip tương ứng."""
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        pass
    if not pip_install(pip_name(module), log=log):
        return False
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False
