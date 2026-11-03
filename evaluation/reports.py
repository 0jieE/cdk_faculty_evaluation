"""PDF reports built with ReportLab (pure Python: no GTK/Pango install needed on Windows)."""
from io import BytesIO

from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from xml.sax.saxutils import escape

from .services import GRADES, full_name

SCHOOL = "Colegio de Kidapawan"
SEAL = colors.HexColor("#5E2EA3")
SEAL_TINT = colors.HexColor("#F1EBF9")
INK = colors.HexColor("#251C35")
MUTED = colors.HexColor("#6B6478")
RULE = colors.HexColor("#DDD8E6")

BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)
SMALL = ParagraphStyle("small", parent=BASE, fontSize=8.5, leading=11, textColor=MUTED)
H1 = ParagraphStyle("h1", parent=BASE, fontName="Helvetica-Bold", fontSize=16, leading=20)
H2 = ParagraphStyle("h2", parent=BASE, fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=SEAL,
                    spaceBefore=12, spaceAfter=6)
CELL = ParagraphStyle("cell", parent=BASE, fontSize=8.5, leading=11)
CELL_R = ParagraphStyle("cellr", parent=CELL, alignment=TA_RIGHT)
FIGURE = ParagraphStyle("figure", parent=BASE, fontName="Helvetica-Bold", fontSize=18, leading=22)


def _fmt(value, places=2):
    return "–" if value is None else f"{value:.{places}f}"


def _p(text, style=CELL):
    return Paragraph(escape(str(text)), style)


def _table(rows, widths, numeric_cols=(), header=True):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
    ]
    if header:
        style += [("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
                  ("TEXTCOLOR", (0, 0), (-1, 0), SEAL),
                  ("LINEBELOW", (0, 0), (-1, 0), 0.8, SEAL)]
    for col in numeric_cols:
        style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    table.setStyle(TableStyle(style))
    return table


def _header(title, subtitle):
    logo_path = finders.find("img/cdk_logo.jpg")
    logo = Image(logo_path, width=18 * mm, height=18 * mm) if logo_path else ""
    text = [Paragraph(SCHOOL, SMALL), Paragraph(escape(title), H1), Paragraph(escape(subtitle), SMALL)]
    t = Table([[logo, text]], colWidths=[22 * mm, None])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return [t, Spacer(0, 4), _rule()]


def _rule():
    t = Table([[""]], colWidths=["100%"], rowHeights=[1])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1.2, SEAL)]))
    return t


def _facts(pairs):
    rows = [[_p(k, SMALL), _p(v, BASE)] for k, v in pairs]
    t = Table(rows, colWidths=[32 * mm, None])
    t.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _figures(items):
    """A row of headline numbers: [(label, value)]."""
    cells = [[Paragraph(escape(value), FIGURE), Paragraph(escape(label), SMALL)] for label, value in items]
    t = Table([cells], colWidths=[None] * len(items))
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SEAL_TINT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    return t


def _legend():
    text = "Descriptive equivalents: " + "; ".join(
        f"{label} ({code}) {minimum}{'–100' if code == 'O' else '+'}" for minimum, code, label in GRADES)
    return Paragraph(escape(text) + ". Ratings combine 90% of the inventory score and the rapid appraisal score.",
                     SMALL)


def _statement_table(title, statements, scale_max, note):
    if not statements:
        return []
    rows = [["#", "Statement", "Average", "Responses"]]
    rows += [[s.number, _p(s.text + ("" if s.is_positive else "  (reversed)")), _fmt(s.average), s.responses]
             for s in statements]
    return [KeepTogether([Paragraph(escape(title), H2), Paragraph(escape(note), SMALL), Spacer(0, 3),
                          _table(rows, [8 * mm, None, 18 * mm, 18 * mm], numeric_cols=(2, 3))])]


def _comments(comments):
    flow = [Paragraph("Comments", H2)]
    if not comments:
        return flow + [Paragraph("No comments were written.", SMALL)]
    for author, text in comments:
        label = f"<b>{escape(author)}</b> — " if author else ""
        flow.append(Paragraph(label + escape(text).replace("\n", "<br/>"), BASE))
        flow.append(Spacer(0, 4))
    return flow


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 10 * mm,
                      f"{SCHOOL} faculty evaluation, generated {timezone.localtime():%B %d, %Y %I:%M %p}")
    canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _build(story, title):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=title, author=SCHOOL,
                            leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=18 * mm)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def class_report_pdf(result, *, show_names):
    fc = result.faculty_class
    code, label = result.grade
    story = _header("Class evaluation report", f"{fc.semester.school_year}, {fc.semester.get_semester_display()}")
    story += [Spacer(0, 8), _facts([
        ("Instructor", full_name(fc.faculty.user)),
        ("Subject", f"{fc.subject.subject_code} — {fc.subject.description}"),
        ("Class", f"{fc.program.short_name} {fc.year_level.year_level}{fc.section.section}"),
        ("Responses", f"{result.evaluators} of {result.enrolled} enrolled students"
                      + (f" ({result.response_rate}%)" if result.response_rate is not None else "")),
    ]), Spacer(0, 8), _figures([
        ("Average rating" + (f" ({label})" if label else ""), _fmt(result.avg_rating)),
        ("Average inventory score", _fmt(result.avg_is)),
        ("Average rapid appraisal", _fmt(result.avg_ra)),
    ]), Spacer(0, 4), _legend()]

    story += _statement_table("Inventory statements", result.is_statements, 5,
                              "Average per statement on a 1–5 scale. Negatively worded statements are reversed, "
                              "so a higher number is always better.")
    story += _statement_table("Rapid appraisal", result.ras_statements, 10, "Average on a 6–10 scale.")

    story.append(Paragraph("Student evaluations", H2))
    rows = [["Student", "Inventory", "Rapid appraisal", "Rating", "Submitted"]]
    for s in result.submissions:
        name = full_name(s.student.user, middle=False) if show_names else "Anonymous"
        rows.append([_p(name), s.isscore_total, s.rasscore_total, _fmt(s.rating),
                     timezone.localtime(s.submitted_at).strftime("%b %d, %Y")])
    if len(rows) == 1:
        story.append(Paragraph("No evaluations submitted yet.", SMALL))
    else:
        story.append(_table(rows, [None, 22 * mm, 28 * mm, 18 * mm, 26 * mm], numeric_cols=(1, 2, 3)))

    story += _comments(result.comments)
    return _build(story, f"{fc.subject.subject_code} evaluation report")


def faculty_summary_pdf(summary):
    faculty, semester = summary.faculty, summary.semester
    code, label = summary.grade
    story = _header("Faculty evaluation summary", f"{semester.school_year}, {semester.get_semester_display()}")
    story += [Spacer(0, 8), _facts([
        ("Instructor", full_name(faculty.user)),
        ("Department", str(faculty.department)),
        ("Responses", f"{summary.evaluators} of {summary.enrolled} enrolled students"
                      + (f" ({summary.response_rate}%)" if summary.response_rate is not None else "")),
    ]), Spacer(0, 8), _figures([
        ("Overall rating" + (f" ({label})" if label else ""), _fmt(summary.avg_rating)),
        ("Average inventory score", _fmt(summary.avg_is)),
        ("Average rapid appraisal", _fmt(summary.avg_ra)),
    ]), Spacer(0, 4), _legend(), Paragraph("Classes", H2)]

    rows = [["Subject", "Class", "Responses", "Inventory", "Rapid appr.", "Rating"]]
    for r in summary.classes:
        fc = r.faculty_class
        rows.append([_p(f"{fc.subject.subject_code} — {fc.subject.description}"),
                     f"{fc.program.short_name} {fc.year_level.year_level}{fc.section.section}",
                     f"{r.evaluators}/{r.enrolled}", _fmt(r.avg_is), _fmt(r.avg_ra), _fmt(r.avg_rating)])
    rows.append([_p("Weighted average", ParagraphStyle("b", parent=CELL, fontName="Helvetica-Bold")), "",
                 f"{summary.evaluators}/{summary.enrolled}", _fmt(summary.avg_is), _fmt(summary.avg_ra),
                 _fmt(summary.avg_rating)])
    table = _table(rows, [None, 26 * mm, 20 * mm, 18 * mm, 20 * mm, 16 * mm], numeric_cols=(2, 3, 4, 5))
    table.setStyle(TableStyle([("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 8.5),
                               ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK)]))
    story.append(table)

    comments = [c for r in summary.classes for c in r.comments]
    story += _comments(comments)
    return _build(story, f"{full_name(faculty.user, middle=False)} evaluation summary")
