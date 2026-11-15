"""Build the complete two-page report.pdf from saved baseline/follow-up summaries.

Layout and content live in complete_report.py; shared helpers remain here for the supplementary report.
No API calls are made.
"""
import json
from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PROJECT = Path(__file__).resolve().parents[1]
FONTS = Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DV", str(FONTS / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", str(FONTS / "DejaVuSans-Bold.ttf")))
INK, MUTED, LINE, HEAD = colors.HexColor("#0b0b0b"), colors.HexColor("#52514e"), colors.HexColor("#d9d8d2"), colors.HexColor("#efeee9")

base = ParagraphStyle("b", fontName="DV", fontSize=8.0, leading=10.2, textColor=INK, alignment=TA_LEFT, spaceAfter=2.4)
H1 = ParagraphStyle("h1", parent=base, fontName="DVB", fontSize=13, leading=16, spaceAfter=1)
SUB = ParagraphStyle("sub", parent=base, textColor=MUTED, fontSize=7.5, spaceAfter=5)
H2 = ParagraphStyle("h2", parent=base, fontName="DVB", fontSize=9.3, leading=12, spaceBefore=4, spaceAfter=2)
CELL = ParagraphStyle("c", parent=base, fontSize=7.3, leading=9.1, spaceAfter=0)
CAP = ParagraphStyle("cap", parent=base, fontSize=6.9, leading=8.5, textColor=MUTED)


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def P(t, s=base):
    return Paragraph(t, s)


def table(rows, widths):
    t = Table([[P(c, CELL) for c in r] for r in rows], colWidths=widths, hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), HEAD), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5), ("LEFTPADDING", (0, 0), (-1, -1), 3),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    return t


def img(name, w):
    from PIL import Image as PI
    path = PROJECT / "results" / "charts" / name
    iw, ih = PI.open(path).size
    return Image(str(path), width=w, height=w * ih / iw)


def pair(a, b, W):
    return Table([[img(a, W * 0.5 - 2 * mm), img(b, W * 0.5 - 2 * mm)]], colWidths=[W * 0.5, W * 0.5],
                 style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)])


def main():
    from complete_report import build
    build()


if __name__ == "__main__":
    main()
