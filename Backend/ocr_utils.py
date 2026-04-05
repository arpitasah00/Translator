# ocr_utils.py
from PIL import Image
import pytesseract

# Agar Windows pe ho toh Tesseract ka path specify karna
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

TESSERACT_LANGUAGE_MAP = {
    "en": "eng",
    "es": "spa",
    "ar": "ara",
    "hi": "hin",
    "or": "ori",
    "bn": "ben",
    "fr": "fra",
    "de": "deu",
    "it": "ita",
    "pt": "por",
    "zh": "chi_sim",
    "ja": "jpn",
    "ko": "kor",
    "ru": "rus",
    "tr": "tur",
    "nl": "nld",
    "ta": "tam",
    "te": "tel",
    "kn": "kan",
}


def looks_like_garbled_ocr(text: str) -> bool:
    sample = (text or "").strip()
    if not sample:
        return True

    visible_chars = [ch for ch in sample if not ch.isspace()]
    if not visible_chars:
        return True

    punctuation_like = sum(
        1 for ch in visible_chars if not ch.isalnum() and ch not in ".,!?;:'\"()-"
    )
    digit_count = sum(1 for ch in visible_chars if ch.isdigit())
    return (
        len(sample) < 8
        or punctuation_like / max(1, len(visible_chars)) > 0.28
        or digit_count / max(1, len(visible_chars)) > 0.2
    )


def ocr_from_file(image_path: str, lang: str = "eng+hin") -> str:
    """
    Read text from image using Tesseract OCR.
    lang: default 'eng+hin' (English + Hindi)
    """
    try:
        img = Image.open(image_path)
        img = img.convert("L")
        text = pytesseract.image_to_string(img, lang=lang)
        return text.strip()
    except Exception as e:
        return f"OCR Error: {e}"


def get_tesseract_lang_for_code(language_code: str | None) -> str:
    code = (language_code or "").strip().lower()
    if code in {"", "auto", "auto-detect", "detect language"}:
        return "eng+hin+ori+ben+tam+tel+kan"

    mapped = TESSERACT_LANGUAGE_MAP.get(code)
    if mapped:
        return f"{mapped}+eng"
    return "eng"
    
