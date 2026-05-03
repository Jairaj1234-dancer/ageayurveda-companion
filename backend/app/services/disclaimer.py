import json
import os
import re

from app.core.logging import logger

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

EMERGENCY_KEYWORDS = [
    "chest pain", "heart attack", "stroke", "bleeding heavily", "unconscious",
    "seizure", "difficulty breathing", "severe allergic", "anaphylaxis",
    "poisoning", "suicidal", "self-harm", "overdose",
    "सीने में दर्द", "दिल का दौरा", "बेहोश", "खून बह रहा",
]

HEALTH_KEYWORDS = [
    "disease", "treatment", "cure", "medicine", "symptom", "diagnosis",
    "pain", "ache", "disorder", "infection", "fever", "diabetes",
    "blood pressure", "cholesterol", "cancer", "tumor", "surgery",
    "pregnant", "pregnancy", "breastfeeding",
    "बीमारी", "इलाज", "दवा", "दर्द", "बुखार", "मधुमेह",
]

SERIOUS_CONDITIONS = [
    "cancer", "tumor", "heart disease", "cardiac", "stroke",
    "kidney failure", "liver failure", "hiv", "aids",
    "epilepsy", "schizophrenia", "bipolar",
]

DISCLAIMERS = {
    "en": {
        "general": "This information is for educational purposes only and is based on classical Ayurvedic texts. It is not a substitute for professional medical advice. Please consult a qualified Ayurvedic practitioner or healthcare provider before starting any treatment.",
        "emergency": "This sounds like a medical emergency. Please call emergency services (112) or visit the nearest hospital immediately. Your safety is the priority.",
        "serious": "This is a serious medical condition that requires professional medical attention. While Ayurveda offers supportive care, please consult a qualified doctor for proper diagnosis and treatment. Do not delay seeking medical help.",
    },
    "hi": {
        "general": "यह जानकारी केवल शैक्षिक उद्देश्यों के लिए है और शास्त्रीय आयुर्वेदिक ग्रंथों पर आधारित है। यह पेशेवर चिकित्सा सलाह का विकल्प नहीं है। कोई भी उपचार शुरू करने से पहले किसी योग्य आयुर्वेदिक चिकित्सक या स्वास्थ्य सेवा प्रदाता से परामर्श करें।",
        "emergency": "यह एक चिकित्सा आपातकाल जैसा लगता है। कृपया तुरंत आपातकालीन सेवाओं (112) को कॉल करें या निकटतम अस्पताल जाएं। आपकी सुरक्षा प्राथमिकता है।",
        "serious": "यह एक गंभीर चिकित्सा स्थिति है जिसमें पेशेवर चिकित्सा ध्यान की आवश्यकता है। जबकि आयुर्वेद सहायक देखभाल प्रदान करता है, कृपया उचित निदान और उपचार के लिए किसी योग्य डॉक्टर से परामर्श करें।",
    },
}


def check_emergency(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in EMERGENCY_KEYWORDS)


def check_health_topic(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in HEALTH_KEYWORDS)


def check_serious_condition(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in SERIOUS_CONDITIONS)


def get_disclaimer(text: str, language: str = "en") -> str | None:
    lang = language if language in DISCLAIMERS else "en"

    if check_emergency(text):
        return DISCLAIMERS[lang]["emergency"]
    if check_serious_condition(text):
        return DISCLAIMERS[lang]["serious"]
    if check_health_topic(text):
        return DISCLAIMERS[lang]["general"]
    return None
