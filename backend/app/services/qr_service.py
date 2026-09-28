import io
import qrcode
from app.core.config import settings


def generate_qr_code_png(data: str, box_size: int = 8, border: int = 2) -> bytes:
    """
    Generates a high-quality, crisp QR code PNG image as bytes.
    Uses Medium Error Correction for reliability on low-resolution cameras.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()
    buffer.close()
    return png_bytes


def build_verification_url(qr_token: str) -> str:
    """Constructs the canonical public verification URL.

    Resolves against PUBLIC_VERIFICATION_URL (falling back to FRONTEND_URL) so
    certificates printed in production always carry the deployed domain.
    """
    return f"{settings.verification_base_url()}/verify.html?token={qr_token}"


def mask_stakeholder_name(name: str) -> str:
    """
    Masks stakeholder/owner name for public display to protect PII.
    Example: 'Ramesh Trading Corp' -> 'R***h T***g C**p'
             'Anil Kumar' -> 'A**l K***r'
    """
    if not name:
        return "Registered Stakeholder"
        
    words = name.strip().split()
    masked_words = []
    
    for word in words:
        if len(word) <= 2:
            masked_words.append(word[0] + "*")
        elif len(word) == 3:
            masked_words.append(word[0] + "*" + word[-1])
        else:
            masked_count = len(word) - 2
            masked_words.append(word[0] + ("*" * min(masked_count, 3)) + word[-1])
            
    return " ".join(masked_words)
