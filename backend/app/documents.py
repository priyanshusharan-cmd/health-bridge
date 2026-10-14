import io
import re
import time
from datetime import date as calendar_date
from PIL import Image
import pdfplumber
import pytesseract

MAX_BYTES = 10 * 1024 * 1024

def get_installed_ocr_languages() -> set[str]:
    try:
        langs = pytesseract.get_languages()
        return set(langs)
    except Exception:
        return {'eng'}

def validate_ocr_language(lang_code: str | None) -> str:
    """Validate and map ISO language code (en, hi, kn) to Tesseract language code (eng, hin, kan)."""
    if not lang_code or lang_code == 'en':
        return 'eng'
    mapping = {'hi': 'hin', 'kn': 'kan', 'eng': 'eng', 'hin': 'hin', 'kan': 'kan'}
    if lang_code not in mapping:
        raise ValueError(f"OCR is only supported for English, Hindi, and Kannada. '{lang_code}' is not supported.")
    tess_code = mapping[lang_code]
    installed = get_installed_ocr_languages()
    if tess_code not in installed and tess_code != 'eng':
        raise ValueError(f"Tesseract OCR language pack '{tess_code}' is not installed in this environment.")
    return tess_code

def read_document_detailed(data: bytes, filename: str, lang: str | None = None) -> tuple[str, str, dict]:
    """Extract text from document while preserving page boundaries, extraction provenance, and warnings."""
    suffix = filename.lower().rsplit('.', 1)[-1]
    tess_lang = validate_ocr_language(lang)
    start_time = time.monotonic()
    deadline = start_time + 120  # Total 120s processing deadline for multi-page jobs

    if suffix == 'txt':
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError('UTF-8 encoding required for plain text files.') from exc
        meta = {
            'method': 'direct_text',
            'ocr_lang': None,
            'policy_version': '1.0',
            'warnings': [],
            'pages': [{'page_number': 1, 'method': 'direct_text', 'length': len(text), 'has_warning': False}]
        }
        return text, 'text/plain', meta

    if suffix == 'pdf' and data.startswith(b'%PDF'):
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > 20:
                raise ValueError('Please upload a PDF with 20 pages or fewer.')
            pages_info = []
            text_chunks = []
            warnings = []
            for idx, page in enumerate(pdf.pages, 1):
                if time.monotonic() > deadline:
                    warnings.append(f"Processing deadline exceeded at page {idx}; remaining pages were omitted.")
                    break
                page_text = page.extract_text() or ''
                method = 'direct_text'
                page_warning = None
                if not page_text.strip():
                    try:
                        page_text = pytesseract.image_to_string(page.to_image(resolution=120).original, lang=tess_lang, timeout=20)
                        method = 'tesseract_ocr'
                    except Exception as ocr_err:
                        page_warning = f"Page {idx} OCR failed: {ocr_err}"
                        warnings.append(page_warning)
                        page_text = ''
                pages_info.append({
                    'page_number': idx,
                    'method': method,
                    'length': len(page_text),
                    'has_warning': bool(page_warning),
                    'warning': page_warning
                })
                if page_text:
                    text_chunks.append(f"--- Page {idx} ---\n{page_text}")

            full_text = '\n\n'.join(text_chunks)
            primary_method = 'mixed_pdf' if any(p['method'] == 'tesseract_ocr' for p in pages_info) else 'direct_text'
            meta = {
                'method': primary_method,
                'ocr_lang': tess_lang if primary_method != 'direct_text' else None,
                'policy_version': '1.0',
                'warnings': warnings,
                'pages': pages_info
            }
            return full_text, 'application/pdf', meta

    if suffix in ('png', 'jpg', 'jpeg'):
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ('PNG', 'JPEG') or image.width * image.height > 20_000_000:
                raise ValueError('Use a PNG or JPEG image under 20 megapixels.')
            media = 'image/png' if image.format == 'PNG' else 'image/jpeg'
            text = str(pytesseract.image_to_string(image, lang=tess_lang, timeout=30))
            meta = {
                'method': 'tesseract_ocr',
                'ocr_lang': tess_lang,
                'policy_version': '1.0',
                'warnings': [],
                'pages': [{'page_number': 1, 'method': 'tesseract_ocr', 'length': len(text), 'has_warning': False}]
            }
            return text, media, meta

    raise ValueError('Supported files: PDF, PNG, JPG and UTF-8 TXT.')

def read_document(data: bytes, filename: str) -> tuple[str, str]:
    text, media, _ = read_document_detailed(data, filename)
    return text, media

def metadata(text: str) -> dict:
    kinds = [('lab report', 'Lab report'), ('referral', 'Referral'), ('discharge', 'Discharge summary'), ('prescription', 'Prescription'), ('visit note', 'Visit note')]
    kind = next((label for term, label in kinds if term in text.lower()), 'Other')
    date = re.search(r'^Date:\s*(\d{4}-\d{2}-\d{2})', text, re.M)
    provider = re.search(r'^Provider:\s*(.+)', text, re.M)
    parsed_date = None
    if date:
        try:
            parsed_date = calendar_date.fromisoformat(date.group(1)).isoformat()
        except ValueError:
            pass
    return {'kind': kind, 'date': parsed_date, 'provider': provider.group(1)[:160] if provider else 'Not provided'}
