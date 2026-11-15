"""Consolidated two-page assessment: results/failures, then improvement plan and limits. Offline only."""
import json,os
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak,KeepTogether
from build_report import PROJECT,pct

INK=colors.HexColor('#182637');MUTED=colors.HexColor('#536174');BLUE=colors.HexColor('#164e78')
LINE=colors.HexColor('#d5dfe8');TINT=colors.HexColor('#eef4f8')
BODY=ParagraphStyle('ReportBody',fontName='DV',fontSize=9.0,leading=11.5,textColor=INK,spaceAfter=4)
TITLE=ParagraphStyle('ReportTitle',parent=BODY,fontName='DVB',fontSize=16,leading=19,spaceAfter=3)
SUB=ParagraphStyle('ReportSubtitle',parent=BODY,fontSize=8,leading=10,textColor=MUTED,spaceAfter=7)
HEAD=ParagraphStyle('ReportHeading',parent=BODY,fontName='DVB',fontSize=10.4,leading=13,textColor=BLUE,spaceBefore=7,spaceAfter=4,keepWithNext=True)
CELL=ParagraphStyle('ReportCell',parent=BODY,fontSize=8.45,leading=10.7,spaceAfter=0)
SMALL=ParagraphStyle('ReportSmall',parent=BODY,fontSize=8.15,leading=10.3,textColor=MUTED,spaceAfter=4)

def para(text,style=BODY):return Paragraph(text,style)
def table(rows,widths):
    t=Table([[para(str(value),CELL) for value in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),TINT),('TEXTCOLOR',(0,0),(-1,0),BLUE),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,LINE),('LINEBELOW',(0,1),(-1,-1),.35,LINE),
        ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
        ('TOPPADDING',(0,0),(-1,-1),3.2),('BOTTOMPADDING',(0,0),(-1,-1),3.2)]))
    return t
def load(name):return json.loads((PROJECT/name).read_text(encoding='utf8'))
def footer(canvas,doc):
    canvas.saveState();width,height=A4
    canvas.setStrokeColor(LINE);canvas.line(13*mm,11*mm,width-13*mm,11*mm)
    canvas.setFillColor(MUTED);canvas.setFont('DV',7.3)
    canvas.drawString(13*mm,7*mm,'GNANI SPEECH EVALUATION  |  Results, failure analysis and recommendations')
    canvas.drawRightString(width-13*mm,7*mm,f'{doc.page} / 2');canvas.restoreState()

def build():
    from submission_report import build
    build()
