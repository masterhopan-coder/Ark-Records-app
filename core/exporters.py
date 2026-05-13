"""Excel / PDF 내보내기.

PDF는 ReportLab Platypus(SimpleDocTemplate + Paragraph + Table)을 사용해
임원 보고서 스타일의 깔끔한 레이아웃으로 생성한다.

한글 깨짐 방지
- CIDFont('HYSMyeongJo-Medium')를 등록해 한국어 글리프를 출력한다.
  (어도비 표준 CJK 폰트로 reportlab에 기본 포함됨, 별도 ttf 파일 불필요)
- 등록 실패 시에만 Helvetica로 폴백한다.
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """기록 DataFrame을 깔끔한 헤더 서식의 xlsx 바이트로 반환."""
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="records")
        workbook = writer.book
        worksheet = writer.sheets["records"]

        header_fmt = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#1F2A44",
                "font_color": "#FFFFFF",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )
        cell_fmt = workbook.add_format({"valign": "top", "text_wrap": True})

        # 헤더
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)

        # 열 너비
        widths = {
            "id": 6,
            "created_at": 20,
            "date": 12,
            "time": 10,
            "theme": 16,
            "content": 60,
            "category": 14,
            "tags": 18,
            "source": 8,
        }
        for col_num, col_name in enumerate(df.columns.values):
            worksheet.set_column(col_num, col_num, widths.get(col_name, 16), cell_fmt)

        # 첫 행 고정 + 자동 필터
        worksheet.freeze_panes(1, 0)
        if len(df) > 0:
            worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

    return out.getvalue()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def _register_korean_font() -> str:
    """한글 표시가 가능한 폰트 이름을 반환한다.

    1) reportlab 내장 CIDFont 'HYSMyeongJo-Medium' (한국어 명조) 등록 시도
    2) 실패 시 'STSong-Light'(중국어 명조 - 한국어 한자 일부 포함) 시도
    3) 둘 다 실패하면 'Helvetica' (영문만, 한글은 □로 깨질 수 있음)
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont

        pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
        return "HYSMyeongJo-Medium"
    except Exception:
        pass

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont

        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:
        pass

    return "Helvetica"


def to_pdf_bytes(df: pd.DataFrame, title: str = "방주의 기록 리포트") -> bytes:
    """ReportLab Platypus로 표 기반 PDF를 생성한다."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    font_name = _register_korean_font()

    out = io.BytesIO()
    doc = SimpleDocTemplate(
        out,
        pagesize=A4,
        title=title,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    # 한글 폰트가 적용된 스타일 시트
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title_K",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1F2A44"),
        spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        "Meta_K",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        textColor=colors.HexColor("#6B7280"),
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        "Body_K",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=13,
    )

    elements = []
    elements.append(Paragraph(title, title_style))
    elements.append(
        Paragraph(
            f"생성 일시: {datetime.now():%Y-%m-%d %H:%M}    ·    총 {len(df)}건",
            meta_style,
        )
    )

    if df.empty:
        elements.append(Paragraph("내보낼 기록이 없습니다.", body_style))
    else:
        # 표 데이터 구성: 표 안에 들어가는 모든 문자열도 Paragraph로 감싸야 자동 줄바꿈 동작
        header = ["일시", "주제", "내용", "분류", "태그"]
        data = [[Paragraph(f"<b>{h}</b>", body_style) for h in header]]

        for _, row in df.iterrows():
            data.append(
                [
                    Paragraph(str(row.get("created_at", "")), body_style),
                    Paragraph(str(row.get("theme", "")), body_style),
                    Paragraph(str(row.get("content", "")).replace("\n", "<br/>"), body_style),
                    Paragraph(str(row.get("category", "")), body_style),
                    Paragraph(str(row.get("tags", "")), body_style),
                ]
            )

        col_widths = [32 * mm, 22 * mm, 78 * mm, 22 * mm, 26 * mm]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2A44")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                    ("LEFTPADDING", (0, 1), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 1), (-1, -1), 5),
                    ("TOPPADDING", (0, 1), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 6 * mm))

    # 페이지 번호 푸터
    def _footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont(font_name, 8)
        canvas_obj.setFillColor(colors.HexColor("#6B7280"))
        canvas_obj.drawRightString(
            A4[0] - 15 * mm,
            10 * mm,
            f"방주의 기록  ·  Page {doc_obj.page}",
        )
        canvas_obj.restoreState()

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    return out.getvalue()
