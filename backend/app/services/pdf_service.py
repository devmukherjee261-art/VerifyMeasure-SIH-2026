import io
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

from app.services.qr_service import build_verification_url


def generate_qr_image_bytes(data: str) -> io.BytesIO:
    """Generates a high-quality QR code image as BytesIO."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)
    return img_byte_arr


def generate_certificate_pdf(cert) -> bytes:
    """
    Generates a professional Legal Metrology Verification Certificate PDF.
    
    Accepts a Certificate model instance or object with certificate attributes.
    Returns bytes of the generated PDF document.
    """
    buffer = io.BytesIO()
    
    # 0.5 inch margins for a crisp, authoritative layout
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette
    PRIMARY = colors.HexColor("#1e3a8a")     # Deep Government Navy
    SECONDARY = colors.HexColor("#0f766e")   # Deep Metrology Teal
    ACCENT = colors.HexColor("#b45309")      # Gold / Bronze
    DARK_NEUTRAL = colors.HexColor("#1e293b")
    LIGHT_BG = colors.HexColor("#f8fafc")
    BORDER_COLOR = colors.HexColor("#cbd5e1")
    SUCCESS_COLOR = colors.HexColor("#15803d")
    
    # Custom Typography Styles
    style_gov_header = ParagraphStyle(
        "GovHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        alignment=TA_CENTER,
        textColor=PRIMARY,
        textTransform="uppercase"
    )
    
    style_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=DARK_NEUTRAL
    )
    
    style_act_subtitle = ParagraphStyle(
        "ActSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569")
    )
    
    style_cert_num = ParagraphStyle(
        "CertNumStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=PRIMARY
    )
    
    style_label = ParagraphStyle(
        "LabelStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=DARK_NEUTRAL
    )
    
    style_value = ParagraphStyle(
        "ValueStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=DARK_NEUTRAL
    )
    
    style_value_bold = ParagraphStyle(
        "ValueBoldStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=DARK_NEUTRAL
    )
    
    style_pass = ParagraphStyle(
        "PassBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
        textColor=SUCCESS_COLOR
    )
    
    style_footer = ParagraphStyle(
        "FooterNote",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748b")
    )

    story = []
    
    # 1. Header Banner
    story.append(Paragraph("DIRECTORATE OF LEGAL METROLOGY", style_gov_header))
    story.append(Paragraph("GOVERNMENT OF INDIA / STATE VERIFICATION SERVICE", style_gov_header))
    story.append(Spacer(1, 4))
    story.append(Paragraph("CERTIFICATE OF VERIFICATION OF WEIGHING AND MEASURING INSTRUMENT", style_title))
    story.append(Paragraph("[Issued under Section 24 of The Legal Metrology Act, 2009 and The Legal Metrology (General) Rules, 2011]", style_act_subtitle))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceBefore=2, spaceAfter=8))
    
    # 2. Certificate Number & Issue Banner
    # QR must always point at the deployed public verification page, so build it
    # from configuration rather than falling back to a hardcoded domain.
    qr_data = cert.qr_code_url or build_verification_url(cert.qr_token)
    qr_bytes = generate_qr_image_bytes(qr_data)
    qr_img = Image(qr_bytes, width=1.15 * inch, height=1.15 * inch)
    
    issued_date_str = cert.verification_date.strftime("%d-%b-%Y") if hasattr(cert.verification_date, "strftime") else str(cert.verification_date)
    valid_from_str = cert.valid_from.strftime("%d-%b-%Y") if hasattr(cert.valid_from, "strftime") else str(cert.valid_from)
    valid_until_str = cert.valid_until.strftime("%d-%b-%Y") if hasattr(cert.valid_until, "strftime") else str(cert.valid_until)
    
    meta_info_left = [
        [Paragraph("Certificate Number:", style_label), Paragraph(f"<b>{cert.certificate_number}</b>", style_cert_num)],
        [Paragraph("Security Verification Token:", style_label), Paragraph(f"<font face='Courier'>{cert.qr_token[:16]}...</font>", style_value)],
        [Paragraph("Issuing Authority:", style_label), Paragraph(cert.issuing_authority, style_value_bold)],
        [Paragraph("Verification Status:", style_label), Paragraph(f"<font color='#15803d'><b>{cert.status.upper()} (LEGAL)</b></font>", style_value)]
    ]
    meta_table_left = Table(meta_info_left, colWidths=[150, 240])
    meta_table_left.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    
    qr_block = [
        [qr_img],
        [Paragraph("<font size='7' color='#475569'>Scan to Verify Authenticity</font>", ParagraphStyle("QRCaption", alignment=TA_CENTER))]
    ]
    qr_table = Table(qr_block, colWidths=[100])
    qr_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    
    top_banner_table = Table([[meta_table_left, qr_table]], colWidths=[420, 120])
    top_banner_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("BOX", (0, 0), (-1, -1), 1, BORDER_COLOR),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(top_banner_table)
    story.append(Spacer(1, 10))
    
    # 3. Instrument Identification Details
    story.append(Paragraph("<font color='#1e3a8a'><b>1. INSTRUMENT IDENTIFICATION SPECIFICATIONS</b></font>", style_label))
    story.append(Spacer(1, 3))
    
    inst_data = [
        [
            Paragraph("Instrument ID:", style_label),
            Paragraph(cert.instrument_identifier, style_value_bold),
            Paragraph("Instrument Category / Type:", style_label),
            Paragraph(cert.instrument_type, style_value)
        ],
        [
            Paragraph("Manufacturer:", style_label),
            Paragraph(cert.manufacturer, style_value),
            Paragraph("Model Number:", style_label),
            Paragraph(cert.model_number, style_value)
        ],
        [
            Paragraph("Serial Number:", style_label),
            Paragraph(cert.serial_number, style_value_bold),
            Paragraph("Rated Capacity / Range:", style_label),
            Paragraph(cert.capacity, style_value)
        ],
        [
            Paragraph("Instrument Owner:", style_label),
            Paragraph(cert.owner_name, style_value_bold),
            Paragraph("Installed Location:", style_label),
            Paragraph(cert.location, style_value)
        ]
    ]
    inst_table = Table(inst_data, colWidths=[110, 160, 130, 140])
    inst_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.75, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(inst_table)
    story.append(Spacer(1, 10))
    
    # 4. Technical Inspection & Verification Observations
    story.append(Paragraph("<font color='#1e3a8a'><b>2. STATUTORY INSPECTION & METROLOGICAL OBSERVATIONS</b></font>", style_label))
    story.append(Spacer(1, 3))
    
    insp_data = [
        [
            Paragraph("Reference Standard Value", style_label),
            Paragraph("Measured / Observed Value", style_label),
            Paragraph("Absolute Error", style_label),
            Paragraph("Inspection Result", style_label)
        ],
        [
            Paragraph(f"{cert.standard_value:.4f}".rstrip("0").rstrip("."), style_value),
            Paragraph(f"{cert.measured_value:.4f}".rstrip("0").rstrip("."), style_value),
            Paragraph(f"{cert.error:.4f}".rstrip("0").rstrip("."), style_value_bold),
            Paragraph(f"<b><font color='#15803d'>{cert.result.upper()} (CONFORMS)</font></b>", style_pass)
        ]
    ]
    insp_table = Table(insp_data, colWidths=[135, 135, 135, 135])
    insp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
        ("BOX", (0, 0), (-1, -1), 0.75, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(insp_table)
    story.append(Spacer(1, 10))
    
    # 5. Periodicity & Statutory Validity Period (Rule-based)
    story.append(Paragraph("<font color='#1e3a8a'><b>3. RULE-BASED VALIDITY & NEXT RE-VERIFICATION SCHEDULE</b></font>", style_label))
    story.append(Spacer(1, 3))
    
    validity_data = [
        [
            Paragraph("Verification Date:", style_label),
            Paragraph(issued_date_str, style_value),
            Paragraph("Statutory Periodicity:", style_label),
            Paragraph(f"<b>{cert.validity_months} Months</b> (Legal Metrology Rules)", style_value)
        ],
        [
            Paragraph("Valid From:", style_label),
            Paragraph(valid_from_str, style_value),
            Paragraph("Valid Until (Due Date):", style_label),
            Paragraph(f"<font color='#047857'><b>{valid_until_str}</b></font>", style_value_bold)
        ]
    ]
    validity_table = Table(validity_data, colWidths=[110, 160, 130, 140])
    validity_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.75, BORDER_COLOR),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(validity_table)
    
    if cert.remarks:
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Inspector Remarks:</b> {cert.remarks}", style_act_subtitle))
        
    story.append(Spacer(1, 14))
    
    # 6. Attestation, Seal and Signatures
    sign_block = [
        [
            Paragraph("<b>Verified By:</b>", style_label),
            Paragraph("<b>Approved & Counter-Signed:</b>", style_label)
        ],
        [
            Paragraph("<br/><br/>_______________________________<br/><b>Legal Metrology Officer (LMO)</b><br/>Inspectorate Division", style_value),
            Paragraph(f"<br/><br/>_______________________________<br/><b>Controller of Legal Metrology</b><br/>{cert.issuing_authority}", style_value)
        ]
    ]
    sign_table = Table(sign_block, colWidths=[270, 270])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(sign_table)
    story.append(Spacer(1, 10))
    
    # 7. Statutory Footer
    story.append(HRFlowable(width="100%", thickness=0.75, color=BORDER_COLOR, spaceBefore=4, spaceAfter=6))
    story.append(Paragraph(
        "<b>LEGAL NOTICE:</b> This verification certificate is an official statutory document issued in accordance with "
        "The Legal Metrology Act, 2009. The instrument described herein must be presented for re-verification before the expiry "
        f"of validity on <b>{valid_until_str}</b>. Possession or use of unverified weights or measures is an offence under Section 30. "
        f"Authenticity can be verified at: {qr_data}",
        style_footer
    ))
    
    # Build PDF
    doc.build(story)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
