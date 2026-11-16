"""CSV and PDF export of any report."""
import csv
import io
from decimal import Decimal
from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.utils import timezone

from .reports import period_text, report_sections


def _filename(ctx, ext):
    return f"pesawise-{ctx['kind']}-{ctx['start']:%Y%m%d}-{ctx['end']:%Y%m%d}.{ext}"


def _csv_safe(value):
    """Stop 'CSV injection': a text cell starting with = + - @ would run as a formula in Excel."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def report_csv_response(ctx, user):
    buffer = io.StringIO()
    w = csv.writer(buffer)
    w.writerow(["PesaWise", ctx["kind_label"]])
    w.writerow(["Student", user.get_full_name() or user.username])
    w.writerow(["Period", period_text(ctx)])
    w.writerow(["Generated", timezone.localtime().strftime("%d %B %Y %H:%M")])
    w.writerow(["Currency", "KES"])
    for title, header, rows in report_sections(ctx):
        w.writerow([])
        w.writerow([title])
        w.writerow(header)
        for row in rows:
            w.writerow([_csv_safe(c) if not isinstance(c, Decimal) else f"{c:.2f}" for c in row])
    # utf-8-sig adds a byte-order mark so Excel opens the file with the correct characters
    response = HttpResponse(buffer.getvalue().encode("utf-8-sig"), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{_filename(ctx, "csv")}"'
    return response


def report_pdf_response(ctx, user):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    GREEN, INK = colors.HexColor("#0f6b4f"), colors.HexColor("#0b2e24")
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=INK, alignment=0, fontSize=20)
    h2 = ParagraphStyle("h2", parent=styles["Heading3"], textColor=GREEN, spaceBefore=10)
    cell = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=8.5, leading=10.5)
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=9, textColor=colors.HexColor("#5d6f66"))

    def fmt(v):
        if isinstance(v, Decimal):
            return f"KSh {v:,.2f}"
        return Paragraph(escape(str(v)), cell)          # escape(): user text can never break the PDF markup

    story = [Paragraph("Pesa<font color='#f2b705'>Wise</font>", h1),
             Paragraph(f"<b>{escape(ctx['kind_label'])}</b>: {escape(period_text(ctx))}", styles["BodyText"]),
             Paragraph(f"Student: {escape(user.get_full_name() or user.username)} · Generated "
                       f"{timezone.localtime():%d %B %Y %H:%M} · Currency: KES", small), Spacer(1, 6)]
    for title, header, rows in report_sections(ctx):
        story.append(Paragraph(escape(title), h2))
        if not rows:
            story.append(Paragraph("Nothing recorded in this period.", small))
            continue
        data = [[Paragraph(f"<b>{escape(h)}</b>", cell) for h in header]] + [[fmt(c) for c in r] for r in rows]
        t = Table(data, repeatRows=1, hAlign="LEFT")
        money_cols = [i for i, c in enumerate(rows[0]) if isinstance(c, Decimal)]
        style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4ebe6")), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                 ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dde5df")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7faf8")])]
        style += [("ALIGN", (i, 1), (i, -1), "RIGHT") for i in money_cols]
        t.setStyle(TableStyle(style))
        story.append(t)
    story += [Spacer(1, 12), Paragraph("PesaWise is a budgeting aid, not professional financial advice.", small)]

    buffer = io.BytesIO()

    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.grey)
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}"); canvas.restoreState()

    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
                      title=f"PesaWise {ctx['kind_label']}").build(story, onFirstPage=footer, onLaterPages=footer)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{_filename(ctx, "pdf")}"'
    return response