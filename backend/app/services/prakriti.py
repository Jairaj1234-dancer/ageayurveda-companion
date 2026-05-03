import json
import os

from app.core.logging import logger

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

CONSTITUTION_DESCRIPTIONS = {
    "vata": {
        "en": "You have a Vata-dominant constitution. Vata types tend to be creative, quick-thinking, and energetic but may experience anxiety, dryness, and irregular digestion when imbalanced.",
        "hi": "आपकी प्रकृति वात प्रधान है। वात प्रकृति के लोग रचनात्मक, तेज़ बुद्धि और ऊर्जावान होते हैं, लेकिन असंतुलित होने पर चिंता, सूखापन और अनियमित पाचन का अनुभव कर सकते हैं।",
    },
    "pitta": {
        "en": "You have a Pitta-dominant constitution. Pitta types are typically focused, determined, and sharp-minded but may experience inflammation, acidity, and irritability when imbalanced.",
        "hi": "आपकी प्रकृति पित्त प्रधान है। पित्त प्रकृति के लोग आमतौर पर केंद्रित, दृढ़ और तेज़ बुद्धि वाले होते हैं, लेकिन असंतुलित होने पर सूजन, अम्लता और चिड़चिड़ापन का अनुभव कर सकते हैं।",
    },
    "kapha": {
        "en": "You have a Kapha-dominant constitution. Kapha types are calm, steady, and nurturing but may experience lethargy, weight gain, and congestion when imbalanced.",
        "hi": "आपकी प्रकृति कफ प्रधान है। कफ प्रकृति के लोग शांत, स्थिर और पोषणकारी होते हैं, लेकिन असंतुलित होने पर आलस्य, वज़न बढ़ना और कंजेशन का अनुभव कर सकते हैं।",
    },
    "vata-pitta": {
        "en": "You have a Vata-Pitta dual constitution. You combine the creativity and energy of Vata with the focus and intensity of Pitta. Balance both elements through grounding and cooling practices.",
        "hi": "आपकी प्रकृति वात-पित्त द्विदोषज है। आप वात की रचनात्मकता और ऊर्जा को पित्त के फोकस और तीव्रता के साथ जोड़ते हैं।",
    },
    "pitta-kapha": {
        "en": "You have a Pitta-Kapha dual constitution. You combine the determination of Pitta with the steadiness of Kapha. Maintain balance through moderation and regular exercise.",
        "hi": "आपकी प्रकृति पित्त-कफ द्विदोषज है। आप पित्त के दृढ़ संकल्प को कफ की स्थिरता के साथ जोड़ते हैं।",
    },
    "vata-kapha": {
        "en": "You have a Vata-Kapha dual constitution. You combine Vata's creativity with Kapha's endurance. Warmth, stimulation, and routine help keep both doshas balanced.",
        "hi": "आपकी प्रकृति वात-कफ द्विदोषज है। आप वात की रचनात्मकता को कफ की सहनशक्ति के साथ जोड़ते हैं।",
    },
    "tridosha": {
        "en": "You have a rare Tridoshic (Sama Prakriti) constitution with all three doshas in near-equal balance. This is considered ideal in Ayurveda. Maintain this balance through seasonal routines.",
        "hi": "आपकी प्रकृति दुर्लभ त्रिदोषज (सम प्रकृति) है जिसमें तीनों दोष लगभग समान हैं। आयुर्वेद में इसे आदर्श माना जाता है।",
    },
}

DIET_RECOMMENDATIONS = {
    "vata": ["Warm, cooked foods", "Healthy fats (ghee, sesame oil)", "Sweet, sour, salty tastes", "Regular meal times", "Avoid raw, cold, dry foods"],
    "pitta": ["Cooling foods", "Sweet, bitter, astringent tastes", "Fresh fruits and vegetables", "Avoid spicy, sour, fermented foods", "Coconut oil and ghee"],
    "kapha": ["Light, warm, dry foods", "Pungent, bitter, astringent tastes", "Plenty of spices", "Avoid heavy, oily, sweet foods", "Honey in warm water"],
}

LIFESTYLE_RECOMMENDATIONS = {
    "vata": ["Regular daily routine", "Warm oil massage (Abhyanga)", "Gentle yoga and meditation", "Early bedtime", "Avoid excessive travel"],
    "pitta": ["Moderate exercise", "Cooling activities", "Moon bathing", "Avoid midday sun", "Creative outlets"],
    "kapha": ["Vigorous daily exercise", "Wake up early", "Dry brushing", "Avoid daytime sleeping", "Stimulating activities"],
}


def load_questions() -> list[dict]:
    path = os.path.join(DATA_DIR, "prakriti_questions.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def score_prakriti(answers: dict[str, str]) -> dict:
    """Score Prakriti based on answers. Returns constitution and scores."""
    scores = {"vata": 0, "pitta": 0, "kapha": 0}

    for question_id, dosha in answers.items():
        if dosha in scores:
            scores[dosha] += 1

    total = sum(scores.values()) or 1
    percentages = {d: (s / total) * 100 for d, s in scores.items()}

    sorted_doshas = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = sorted_doshas[0]
    second = sorted_doshas[1]

    # Dual dosha if top two within 15%
    if percentages[top[0]] - percentages[second[0]] <= 15:
        # Check if all three are close (tridosha)
        third = sorted_doshas[2]
        if percentages[second[0]] - percentages[third[0]] <= 10:
            constitution = "tridosha"
        else:
            pair = sorted([top[0], second[0]])
            constitution = f"{pair[0]}-{pair[1]}"
    else:
        constitution = top[0]

    return {
        "constitution": constitution,
        "scores": scores,
        "percentages": percentages,
    }


def get_recommendations(constitution: str) -> dict:
    """Get diet, lifestyle, and product recommendations for a constitution."""
    primary_doshas = constitution.replace("tridosha", "vata-pitta-kapha").split("-")

    diet = []
    lifestyle = []
    for dosha in primary_doshas:
        diet.extend(DIET_RECOMMENDATIONS.get(dosha, []))
        lifestyle.extend(LIFESTYLE_RECOMMENDATIONS.get(dosha, []))

    # Deduplicate while preserving order
    diet = list(dict.fromkeys(diet))
    lifestyle = list(dict.fromkeys(lifestyle))

    return {
        "diet": diet[:8],
        "lifestyle": lifestyle[:6],
        "description": CONSTITUTION_DESCRIPTIONS.get(constitution, CONSTITUTION_DESCRIPTIONS.get(primary_doshas[0], {})),
    }
