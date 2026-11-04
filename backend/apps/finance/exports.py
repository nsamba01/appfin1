from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _fmt(amount: Decimal | None) -> str:
    return f"{(amount or Decimal('0.00')):,.2f}".replace(",", " ")


def build_operations_workbook(operations, totals, currency: str, company: str) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Opérations"

    header_fill = PatternFill("solid", fgColor="1D4ED8")
    header_font = Font(color="FFFFFF", bold=True)

    ws["A1"] = f"{company} — Journal des opérations financières"
    ws["A1"].font = Font(size=14, bold=True, color="0F172A")
    ws["A2"] = f"Devise : {currency}  |  Généré le {datetime.now():%d/%m/%Y %H:%M}"
    ws["A2"].font = Font(size=9, color="475569")

    headers = ["Date", "Libellé", "Type", "Montant", "Référence", "Observation", "Créé par"]
    ws.append([])
    ws.append(headers)
    header_row = ws.max_row
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for op in operations:
        ws.append(
            [
                op.date.strftime("%d/%m/%Y"),
                op.label,
                op.get_operation_type_display(),
                float(op.amount),
                op.reference,
                op.observation,
                op.created_by.username if op.created_by else "",
            ]
        )

    ws.append([])
    ws.append(["", "Total des entrées", "", float(totals.total_entries)])
    ws.append(["", "Total des sorties", "", float(totals.total_exits)])
    ws.append(["", "Solde financier", "", float(totals.balance)])
    for row in ws.iter_rows(min_row=ws.max_row - 2, max_row=ws.max_row, min_col=2, max_col=4):
        row[0].font = Font(bold=True)
        row[2].font = Font(bold=True)
        row[2].number_format = "#,##0.00"
    ws.cell(row=ws.max_row, column=4).font = Font(bold=True, color="047857")

    for idx, op in enumerate(operations, start=header_row + 1):
        ws.cell(row=idx, column=4).number_format = "#,##0.00"

    widths = [12, 40, 10, 15, 20, 40, 16]
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    return wb


def build_operations_pdf(operations, totals, currency: str, company: str):
    """Returns a BytesIO containing a professional landscape PDF statement."""
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Journal des opérations financières",
        author=company,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleFx", parent=styles["Title"], fontSize=16, textColor=colors.HexColor("#0F172A")
    )
    normal = ParagraphStyle(
        "NormalFx", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#334155")
    )
    story = [
        Paragraph(f"{company} — Journal des opérations financières", title_style),
        Paragraph(
            f"Devise : {currency} &nbsp;|&nbsp; Généré le {datetime.now():%d/%m/%Y %H:%M} "
            f"&nbsp;|&nbsp; {len(operations)} opération(s)",
            normal,
        ),
        Spacer(1, 6 * mm),
    ]

    data = [["Date", "Libellé", "Type", "Montant", "Référence", "Observation"]]
    for op in operations:
        data.append(
            [
                op.date.strftime("%d/%m/%Y"),
                Paragraph(op.label[:80], normal),
                op.get_operation_type_display(),
                _fmt(op.amount),
                op.reference or "—",
                Paragraph((op.observation or "—")[:90], normal),
            ]
        )

    table = Table(
        data, colWidths=[22 * mm, 75 * mm, 18 * mm, 30 * mm, 34 * mm, 72 * mm], repeatRows=1
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, -1), 7.5),
                ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TEXTCOLOR", (2, 1), (2, -1), colors.HexColor("#0F172A")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 8 * mm))

    summary = Table(
        [
            ["Total des entrées", "Total des sorties", "Solde financier"],
            [
                f"{_fmt(totals.total_entries)} {currency}",
                f"{_fmt(totals.total_exits)} {currency}",
                f"{_fmt(totals.balance)} {currency}",
            ],
        ],
        colWidths=[60 * mm, 60 * mm, 60 * mm],
    )
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("TEXTCOLOR", (2, 1), (2, 1), colors.HexColor("#047857")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary)
    doc.build(story)
    buffer.seek(0)
    return buffer
