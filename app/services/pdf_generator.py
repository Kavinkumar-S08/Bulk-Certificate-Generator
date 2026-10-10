import os
from pathlib import Path
from uuid import uuid4

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


OUTPUT_DIR = Path("/app/generated_certificates")


def generate_certificate_pdf(
    certificate_id: int,
    recipient_name: str,
    event_name: str,
) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    final_path = OUTPUT_DIR / f"certificate_{certificate_id}.pdf"
    temp_path = OUTPUT_DIR / f".{certificate_id}_{uuid4().hex}.tmp"

    page_width, page_height = landscape(A4)

    try:
        pdf = canvas.Canvas(
            str(temp_path),
            pagesize=(page_width, page_height),
        )

        pdf.setFillColor(colors.HexColor("#FAF8F0"))
        pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

        pdf.setStrokeColor(colors.HexColor("#B08D57"))
        pdf.setLineWidth(3)
        pdf.rect(
            0.35 * inch,
            0.35 * inch,
            page_width - 0.7 * inch,
            page_height - 0.7 * inch,
        )

        pdf.setFillColor(colors.HexColor("#17365D"))
        pdf.setFont("Helvetica-Bold", 30)
        pdf.drawCentredString(
            page_width / 2,
            page_height - 1.35 * inch,
            "CERTIFICATE OF PARTICIPATION",
        )

        pdf.setFillColor(colors.HexColor("#333333"))
        pdf.setFont("Helvetica", 16)
        pdf.drawCentredString(
            page_width / 2,
            page_height - 2.1 * inch,
            "This certificate is proudly presented to",
        )

        pdf.setFillColor(colors.HexColor("#17365D"))
        pdf.setFont("Helvetica-Bold", 26)
        pdf.drawCentredString(
            page_width / 2,
            page_height - 2.9 * inch,
            recipient_name,
        )

        pdf.setFillColor(colors.HexColor("#333333"))
        pdf.setFont("Helvetica", 15)
        pdf.drawCentredString(
            page_width / 2,
            page_height - 3.6 * inch,
            f"For participating in {event_name}",
        )

        pdf.setStrokeColor(colors.HexColor("#B08D57"))
        pdf.setLineWidth(1)
        pdf.line(
            page_width / 2 - 1.1 * inch,
            1.15 * inch,
            page_width / 2 + 1.1 * inch,
            1.15 * inch,
        )

        pdf.setFont("Helvetica", 10)
        pdf.drawCentredString(
            page_width / 2,
            0.85 * inch,
            f"Certificate ID: {certificate_id}",
        )

        pdf.save()

        # Publish only after ReportLab finishes the PDF.
        os.replace(temp_path, final_path)

        return str(final_path)

    finally:
        # Clean up an unfinished temporary file if generation fails.
        if temp_path.exists():
            temp_path.unlink()