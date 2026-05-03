import re

from app.core.logging import logger

# Common Hindi Ayurvedic terms -> English mapping for search
HINDI_TERM_MAP = {
    "वात": "vata",
    "पित्त": "pitta",
    "कफ": "kapha",
    "दोष": "dosha",
    "प्रकृति": "prakriti",
    "आयुर्वेद": "ayurveda",
    "पाचन": "digestion",
    "रोग प्रतिरोधक": "immunity",
    "नींद": "sleep",
    "त्वचा": "skin",
    "बाल": "hair",
    "जोड़": "joints",
    "सूजन": "inflammation",
    "पेट": "stomach",
    "कब्ज": "constipation",
    "अम्लपित्त": "acidity",
    "शरीर": "body",
    "स्वास्थ्य": "health",
    "औषधि": "medicine",
    "जड़ी बूटी": "herbs",
    "रसायन": "rasayana",
    "पंचकर्म": "panchakarma",
    "अभ्यंग": "abhyanga",
    "शिरोधारा": "shirodhara",
    "त्रिफला": "triphala",
    "अश्वगंधा": "ashwagandha",
    "हल्दी": "turmeric",
    "गिलोय": "giloy",
    "तुलसी": "tulsi",
    "ब्राह्मी": "brahmi",
    "शतावरी": "shatavari",
    "अर्जुन": "arjuna",
    "आमला": "amla",
    "मधु": "honey",
    "घी": "ghee",
}

# Transliterated Hindi terms
TRANSLITERATED_MAP = {
    "vaat": "vata",
    "pitt": "pitta",
    "kaph": "kapha",
    "dosh": "dosha",
    "prakriti": "prakriti",
    "pachan": "digestion",
    "neend": "sleep",
    "twacha": "skin",
    "baal": "hair",
    "jod": "joints",
    "pet": "stomach",
    "kabz": "constipation",
    "amlapitta": "acidity",
    "aushadhi": "medicine",
    "jadi buti": "herbs",
}

# Devanagari Unicode range: \u0900-\u097F
_DEVANAGARI_RE = re.compile(r'[\u0900-\u097F]')


def detect_language(text: str) -> str:
    """Detect language based on presence of Devanagari script. Returns 'hi' or 'en'."""
    if _DEVANAGARI_RE.search(text):
        return "hi"
    return "en"


def translate_hindi_terms(text: str) -> str:
    """Replace Hindi terms with English equivalents for search."""
    result = text
    for hindi, english in HINDI_TERM_MAP.items():
        if hindi in result:
            result = result.replace(hindi, english)
    for transliterated, english in TRANSLITERATED_MAP.items():
        if transliterated.lower() in result.lower():
            result = result + f" {english}"
    return result
