"""마크다운 리포트를 PDF로 변환한다.

Streamlit Cloud(Linux)에는 한글 폰트가 없으므로, 리포지토리에 함께 커밋된
TTF 폰트 파일(fonts/NanumGothic-*.ttf)을 reportlab에 직접 등록해서 쓴다 —
OS에 설치된 폰트(맑은 고딕 등)에 의존하지 않는다.

HTML→PDF 변환 라이브러리(xhtml2pdf)는 Windows에서 커스텀 @font-face 폰트를
로드할 때 임시파일을 닫자마자 다시 열려고 시도하다 PermissionError가 나는
버그가 있어(POSIX 방식 임시파일 처리를 가정한 코드로 보임) 쓰지 않는다.
대신 reportlab의 Platypus(SimpleDocTemplate)로 마크다운 구조(제목·표·목록 등)를
직접 그린다 — reportlab에 폰트를 등록해 바로 쓰는 방식은 실제로 한글이
정상 렌더링되는 것을 확인했다.
"""
import os
import re
from io import BytesIO

import markdown
from bs4 import BeautifulSoup, NavigableString
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE_DIR, "fonts")
FONT_NAME = "NanumGothic"
FONT_NAME_BOLD = "NanumGothic-Bold"

INK = colors.HexColor("#0f172a")
MUTED_INK = colors.HexColor("#52514e")
GRID = colors.HexColor("#cbd5e1")
HEADER_BG = colors.HexColor("#f1f5f9")
LINK_BLUE = colors.HexColor("#2563eb")

PAGE_MARGIN = 20 * mm

_font_registered = False


def _ensure_font_registered():
    global _font_registered
    if _font_registered:
        return
    registerFont(TTFont(FONT_NAME, os.path.join(FONT_DIR, "NanumGothic-Regular.ttf")))
    registerFont(TTFont(FONT_NAME_BOLD, os.path.join(FONT_DIR, "NanumGothic-Bold.ttf")))
    _font_registered = True


def _get_styles():
    return {
        "h1": ParagraphStyle("h1", fontName=FONT_NAME_BOLD, fontSize=19, leading=24, spaceAfter=8, textColor=INK),
        "h2": ParagraphStyle("h2", fontName=FONT_NAME_BOLD, fontSize=14, leading=18, spaceBefore=16, spaceAfter=6, textColor=INK),
        "h3": ParagraphStyle("h3", fontName=FONT_NAME_BOLD, fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=4, textColor=INK),
        "h4": ParagraphStyle("h4", fontName=FONT_NAME_BOLD, fontSize=10.5, leading=14, spaceBefore=8, spaceAfter=4, textColor=INK),
        "body": ParagraphStyle("body", fontName=FONT_NAME, fontSize=9.5, leading=14.5, spaceAfter=5, textColor=INK),
        "li": ParagraphStyle("li", fontName=FONT_NAME, fontSize=9.5, leading=14.5, spaceAfter=3, leftIndent=12, textColor=INK),
        "quote": ParagraphStyle("quote", fontName=FONT_NAME, fontSize=9.5, leading=14.5, textColor=MUTED_INK, leftIndent=14, spaceAfter=6),
        "code": ParagraphStyle("code", fontName="Courier", fontSize=8, leading=11, backColor=HEADER_BG, spaceAfter=6),
        "table_header": ParagraphStyle("table_header", fontName=FONT_NAME_BOLD, fontSize=8.5, leading=11.5, textColor=INK),
        "table_cell": ParagraphStyle("table_cell", fontName=FONT_NAME, fontSize=8.5, leading=11.5, textColor=INK),
    }


def _strip_frontmatter(markdown_text):
    """맨 앞 '---\\n...\\n---' YAML 프론트매터 블록은 PDF에는 필요 없어 제거한다."""
    return re.sub(r"^---\n.*?\n---\n", "", markdown_text, count=1, flags=re.DOTALL)


def _escape(text):
    return text.replace("&", "&amp;")


def _inline_to_reportlab_markup(node):
    """BeautifulSoup 인라인 요소(strong/em/code/a/br 등)를 reportlab Paragraph의
    미니 XML 마크업으로 바꾼다."""
    if isinstance(node, NavigableString):
        return _escape(str(node))

    name = getattr(node, "name", None)
    inner = "".join(_inline_to_reportlab_markup(c) for c in node.children)

    if name in ("strong", "b"):
        return f'<font name="{FONT_NAME_BOLD}">{inner}</font>'
    if name in ("em", "i"):
        return f"<u>{inner}</u>"
    if name == "code":
        return f'<font face="Courier" size="8.5">{inner}</font>'
    if name == "a":
        return f'<font color="#2563eb"><u>{inner}</u></font>'
    if name == "br":
        return "<br/>"
    return inner


def _render_table(table_tag, styles, available_width):
    rows = []
    n_cols = 0
    for tr in table_tag.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        n_cols = max(n_cols, len(cells))
        row = []
        for cell in cells:
            style = styles["table_header"] if cell.name == "th" else styles["table_cell"]
            row.append(Paragraph(_inline_to_reportlab_markup(cell), style))
        rows.append(row)
    if not rows or n_cols == 0:
        return []

    col_width = available_width / n_cols
    table = Table(rows, colWidths=[col_width] * n_cols, hAlign="LEFT", repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, GRID),
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [table]


def _render_block(el, styles, available_width):
    name = getattr(el, "name", None)
    if name is None:
        return []

    if name in ("h1", "h2", "h3", "h4"):
        return [Paragraph(_inline_to_reportlab_markup(el), styles[name])]
    if name == "p":
        return [Paragraph(_inline_to_reportlab_markup(el), styles["body"])]
    if name == "hr":
        return [Spacer(1, 4), HRFlowable(width="100%", color=GRID, thickness=0.8), Spacer(1, 10)]
    if name in ("ul", "ol"):
        ordered = name == "ol"
        out = []
        for i, li in enumerate(el.find_all("li", recursive=False), start=1):
            prefix = f"{i}. " if ordered else "• "
            out.append(Paragraph(prefix + _inline_to_reportlab_markup(li), styles["li"]))
        out.append(Spacer(1, 4))
        return out
    if name == "table":
        return _render_table(el, styles, available_width) + [Spacer(1, 8)]
    if name == "blockquote":
        return [Paragraph(_inline_to_reportlab_markup(el), styles["quote"])]
    if name == "pre":
        code_text = _escape(el.get_text()).replace("\n", "<br/>")
        return [Paragraph(code_text, styles["code"])]

    # 위에서 다루지 않는 래퍼 태그는 자식으로 내려가 계속 처리한다.
    out = []
    for child in getattr(el, "children", []):
        out.extend(_render_block(child, styles, available_width))
    return out


def build_report_pdf(markdown_text: str) -> bytes:
    """리포트 마크다운 전체를 PDF 바이트로 변환해 반환한다."""
    _ensure_font_registered()

    body_md = _strip_frontmatter(markdown_text)
    html_body = markdown.markdown(body_md, extensions=["tables", "fenced_code", "nl2br"])
    soup = BeautifulSoup(html_body, "html.parser")

    styles = _get_styles()
    available_width = A4[0] - 2 * PAGE_MARGIN

    flowables = []
    for el in soup.contents:
        flowables.extend(_render_block(el, styles, available_width))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="고객서비스 만족도개선 리포트",
    )
    doc.build(flowables)
    return buffer.getvalue()
