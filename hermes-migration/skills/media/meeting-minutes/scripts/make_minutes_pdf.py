#!/usr/bin/env python3
"""Chuyển biên bản Markdown đơn giản thành PDF (hỗ trợ tiếng Việt). In JSON.

Cần: pip install reportlab
Hỗ trợ: # / ## heading, - bullet, đoạn văn thường, **đậm** (bỏ dấu sao).
"""
import argparse
import json
import os
import re
import sys


def _find_font() -> str | None:
    candidates = [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    return next((p for p in candidates if os.path.exists(p)), None)


def _find_bold(regular: str) -> str | None:
    mapping = {
        "segoeui.ttf": "segoeuib.ttf", "arial.ttf": "arialbd.ttf",
        "tahoma.ttf": "tahomabd.ttf", "DejaVuSans.ttf": "DejaVuSans-Bold.ttf",
    }
    base = os.path.basename(regular)
    if base in mapping:
        cand = os.path.join(os.path.dirname(regular), mapping[base])
        if os.path.exists(cand):
            return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_md", help="File biên bản .md/.txt")
    ap.add_argument("-o", "--output", help="File PDF đầu ra (mặc định: cùng tên .pdf)")
    args = ap.parse_args()

    if not os.path.exists(args.input_md):
        print(json.dumps({"success": False, "error": f"Không tìm thấy tệp: {args.input_md}"}, ensure_ascii=False))
        return 1
    try:
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        print(json.dumps({"success": False, "error": "Thiếu reportlab. Chạy: pip install reportlab"}, ensure_ascii=False))
        return 1

    font_path = _find_font()
    if not font_path:
        print(json.dumps({"success": False, "error": "Không tìm thấy font Unicode (Segoe UI/Arial/DejaVu)."}, ensure_ascii=False))
        return 1
    pdfmetrics.registerFont(TTFont("VNFont", font_path))
    bold_path = _find_bold(font_path)
    bold_name = "VNFont"
    if bold_path:
        pdfmetrics.registerFont(TTFont("VNFontB", bold_path))
        bold_name = "VNFontB"

    st_title = ParagraphStyle("t", fontName=bold_name, fontSize=17, leading=22,
                              alignment=TA_CENTER, spaceAfter=10)
    st_h2 = ParagraphStyle("h2", fontName=bold_name, fontSize=13, leading=17,
                           spaceBefore=10, spaceAfter=4)
    st_body = ParagraphStyle("b", fontName="VNFont", fontSize=11, leading=15.5, spaceAfter=3)
    st_bullet = ParagraphStyle("bl", parent=st_body, leftIndent=8 * mm, bulletIndent=3 * mm)

    def esc(s: str) -> str:
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return re.sub(r"\*\*(.+?)\*\*", rf'<font name="{bold_name}">\1</font>', s)

    with open(args.input_md, encoding="utf-8") as f:
        lines = f.read().splitlines()

    story = []
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            story.append(Spacer(1, 3))
        elif line.startswith("# "):
            story.append(Paragraph(esc(line[2:].strip()), st_title))
        elif line.startswith("## "):
            story.append(Paragraph(esc(line[3:].strip()), st_h2))
        elif re.match(r"^\s*[-*•]\s+", line):
            item = re.sub(r"^\s*[-*•]\s+", "", line)
            story.append(Paragraph(esc(item), st_bullet, bulletText="•"))
        else:
            story.append(Paragraph(esc(line.strip()), st_body))

    out = args.output or os.path.splitext(args.input_md)[0] + ".pdf"
    SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                      topMargin=18 * mm, bottomMargin=18 * mm).build(story)
    print(json.dumps({"success": True,
                      "result": {"output": out,
                                 "size_kb": round(os.path.getsize(out) / 1024, 1)}},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
