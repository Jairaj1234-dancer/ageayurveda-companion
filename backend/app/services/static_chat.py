"""
Rule-based chatbot that works without any LLM API.
Handles: greetings, dosha info, prakriti guidance, product matching,
common Ayurvedic topics, and guided product finder flow.
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

_products: list[dict] = []
_mappings: dict = {}


def _load_data():
    global _products, _mappings
    if not _products:
        with open(DATA_DIR / "products.json") as f:
            _products = json.load(f)
        with open(DATA_DIR / "product_mappings.json") as f:
            _mappings = json.load(f)


# ---------------------------------------------------------------------------
# Dosha knowledge base
# ---------------------------------------------------------------------------

DOSHA_INFO = {
    "vata": {
        "title": "Vata Dosha (Air + Space)",
        "traits": "Creative, quick-thinking, energetic when balanced. Thin frame, dry skin, cold hands/feet. Prone to anxiety, insomnia, constipation, and joint pain when imbalanced.",
        "diet_dos": """**Foods:** Khichdi, soups, stews, porridges, warm milk with nutmeg. Cooked rice, wheat, oats. Sweet potato, carrot, beetroot, asparagus, zucchini (always cooked). Bananas, mangoes, avocado, dates, figs, stewed apples. Ghee, sesame oil, olive oil generously.
**Tastes:** Sweet, Sour, Salty — they ground and nourish Vata.
**Spices:** Ginger, cumin, cinnamon, cardamom, fennel, asafoetida (hing), black pepper (moderate).
**Habits:** Eat at regular times, never skip meals. Sip warm water or ginger tea all day. Warm milk with turmeric or nutmeg before bed.""",
        "diet_donts": """Raw salads, cold smoothies, dried foods, popcorn, crackers, corn, carbonated drinks, excess caffeine, ice-cold water. Bitter and astringent tastes in excess. Light fasting is NOT recommended — Vata needs consistent nourishment.""",
        "lifestyle_dos": """Regular daily routine (Dinacharya) is essential. Daily warm sesame oil self-massage (Abhyanga). Gentle yoga — forward bends, hip openers, Shavasana. Nadi Shodhana (alternate nostril breathing). Bed by 10 PM, 7-8 hours sleep. Stay warm and layered.""",
        "lifestyle_donts": """Cold wind and prolonged cold exposure. Excess travel and over-stimulation. Irregular sleep schedule. Skipping meals or fasting. Loud noise, excessive screen time, and chaotic environments.""",
        "herbs": "Ashwagandha (stress/sleep), Brahmi (calm mind), Jatamansi (sleep), Tagara (relaxation).",
    },
    "pitta": {
        "title": "Pitta Dosha (Fire + Water)",
        "traits": "Sharp intellect, strong digestion, natural leaders when balanced. Medium build, warm body, oily skin. Prone to acidity, inflammation, skin rashes, and irritability when imbalanced.",
        "diet_dos": """**Foods:** Basmati rice, wheat, barley, oats. Cucumber, leafy greens, broccoli, cauliflower, celery, zucchini. Sweet grapes, melons, pomegranate, coconut, pears, sweet apples. Coconut oil, ghee, sunflower oil. Fresh paneer, milk (boiled and cooled).
**Tastes:** Sweet, Bitter, Astringent — they cool and calm Pitta fire.
**Spices:** Coriander, fennel, cardamom, turmeric (moderate), fresh mint, saffron, dill.
**Habits:** Largest meal at lunch when Agni peaks. Light dinner. Coconut water, aloe vera juice, mint tea are excellent Pitta coolers. Room-temperature water with meals.""",
        "diet_donts": """Hot, spicy, sour, fermented foods — chili, vinegar, pickles, sour yogurt. Excess tomatoes, garlic, raw onions, citrus. Deep-fried food, excess salt, alcohol, coffee. Eating when angry or stressed. Ice-cold drinks with meals.""",
        "lifestyle_dos": """Moderate exercise — swimming, cycling, nature walks. Sheetali pranayama (cooling breath). Moonlight walks and time near water. Daily coconut oil massage. Channel intensity into creative outlets. Practice forgiveness and letting go.""",
        "lifestyle_donts": """Overheating and midday sun (10am–2pm). Overly competitive or aggressive exercise. Working through meals. Suppressing emotions — especially anger. Skipping lunch (Pitta's sharp Agni becomes acidic).""",
        "herbs": "Yashtimadhu (cooling/throat), Amla (Vitamin C), Brahmi (calm mind), Haridra (anti-inflammatory).",
    },
    "kapha": {
        "title": "Kapha Dosha (Earth + Water)",
        "traits": "Steady, compassionate, strong endurance when balanced. Larger frame, smooth skin, thick hair. Prone to weight gain, congestion, lethargy, and attachment when imbalanced.",
        "diet_dos": """**Foods:** Barley, millet, buckwheat, corn, rye. Leafy greens, radish, cabbage, broccoli, bell peppers, sprouts, mushrooms. Apples, pears, pomegranate, berries, dried figs. Honey (raw, never cooked) in warm water. Legumes — mung dal, red lentils, chickpeas.
**Tastes:** Pungent, Bitter, Astringent — they stimulate and lighten Kapha.
**Spices:** Black pepper, dry ginger, turmeric, mustard seeds, fenugreek, cloves, cayenne, cinnamon, garlic.
**Habits:** Eat only 2 meals/day if possible — skip or lighten breakfast. Ginger tea with black pepper and honey is ideal. Periodic light fasting (1 day/week) benefits Kapha.""",
        "diet_donts": """Heavy, sweet, oily, cold foods — cheese, ice cream, fried food, excess sweets. Cold milk, yogurt, cream (if dairy, use warm goat milk). Bananas, dates, coconut. Excess wheat, rice, sugar. Snacking between meals. Napping after meals.""",
        "lifestyle_dos": """Wake before 6 AM. Vigorous daily exercise — running, HIIT, Surya Namaskar, power yoga. Dry brushing (Garshana) before bath. Kapalabhati pranayama for energy. Seek variety, travel, and new experiences. Declutter your space regularly.""",
        "lifestyle_donts": """Sleeping past 6 AM — Kapha time worsens lethargy. Daytime napping. Sedentary habits and excessive sitting. Oversleeping (more than 7-8 hours). Staying in the same routine without variety. Hoarding possessions.""",
        "herbs": "Haridra (metabolism/inflammation), Tulsi (respiratory), Giloy (immunity), Ashwagandha (energy).",
    },
}

# ---------------------------------------------------------------------------
# Topic responses (keyword -> response)
# ---------------------------------------------------------------------------

TOPIC_RESPONSES = {
    "digestion": {
        "keywords": ["digestion", "digestive", "stomach", "constipation", "bloating", "gas", "acidity", "heartburn", "gut", "bowel", "appetite"],
        "response": """**Digestive Health in Ayurveda**

Ayurveda considers digestion (*Agni*) the foundation of health. The Charaka Samhita states: "A person whose Agni is balanced has good health, longevity, and vitality."

**Key principles:**
- **Eat according to your Agni** — don't overeat or undereat
- **Warm, cooked foods** are easier to digest than raw/cold
- **Eat your largest meal at noon** when digestive fire is strongest
- **Avoid drinking cold water** with meals — sip warm water instead
- **Ginger before meals** stimulates Agni

**Age Ayurveda recommends:**
- *Acid Relief* — natural relief from hyperacidity and heartburn
- *Bowel Kare* — 4-herb blend for digestive wellness and regularity
- *Chyawanprash Avaleha* — traditional Rasayana that supports overall digestive health

Would you like to take the **Prakriti Quiz** to get personalized digestive recommendations?""",
    },
    "immunity": {
        "keywords": ["immunity", "immune", "cold", "cough", "flu", "fever", "infection", "respiratory"],
        "response": """**Building Immunity (Vyadhikshamatva) with Ayurveda**

Ayurveda's approach to immunity focuses on strengthening *Ojas* — the vital essence that protects against disease.

**Daily immunity practices:**
- **Chyawanprash** — 1 spoon daily, the most revered Rasayana
- **Tulsi tea** — 3-5 leaves boiled in water each morning
- **Turmeric milk** (Golden Milk) — before bed
- **Seasonal cleansing** (Ritucharya) — adjust diet with seasons
- **Adequate sleep** — immunity drops with sleep deprivation

**Age Ayurveda recommends:**
- *Immuno Plus* — combination of 7 herbs to build immunity
- *Chyawanprash Avaleha* — pristine formulation with fresh amla and 40+ herbs
- *Chyawan Cap* — the goodness of Chyawanprash in a convenient capsule
- *Immunity Kit* — complete immunity solution bundle

Take the **Prakriti Quiz** to discover which immunity herbs suit your constitution best!""",
    },
    "sleep": {
        "keywords": ["sleep", "insomnia", "can't sleep", "restless", "sleeping"],
        "response": """**Ayurvedic Approach to Better Sleep (Nidra)**

The Charaka Samhita lists proper sleep as one of the three pillars of health (Traya Upastambha), alongside food and celibacy.

**Ayurvedic sleep tips:**
- **Warm milk with nutmeg** — a pinch of nutmeg in warm milk before bed
- **Abhyanga (self-massage)** — warm sesame oil on feet and scalp
- **No screens 1 hour before bed** — read or practice Yoga Nidra instead
- **Dinner before 7 PM** — light, easy-to-digest food
- **Consistent bedtime** — ideally before 10 PM (Kapha time)
- **Brahmi or Shankhpushpi** before bed calms the mind

**Age Ayurveda recommends:**
- *Natural Sleep Aid* — Ashwagandha, Brahmi, Jatamansi & Tagara for restful sleep
- *Ashwagandha* — reduces cortisol, promotes deep sleep and stress relief

Sleep problems are often a Vata imbalance. Take the **Prakriti Quiz** to confirm!""",
    },
    "skin": {
        "keywords": ["skin", "acne", "glow", "complexion", "pigmentation", "wrinkle", "aging", "face", "beauty"],
        "response": """**Ayurvedic Skin Care (Tvak Chikitsa)**

In Ayurveda, skin health is a reflection of internal health — particularly Rakta Dhatu (blood tissue) and Pitta dosha.

**Skin care by dosha:**
- **Vata skin** (dry, thin) → Nourish with ghee, sesame oil, warm oils
- **Pitta skin** (sensitive, rashes) → Cool with Aloe Vera, sandalwood, turmeric
- **Kapha skin** (oily, thick) → Purify with turmeric, dry masks, light oils

**Daily Ayurvedic skin ritual:**
1. Cleanse with chickpea flour (Ubtan)
2. Tone with rosewater
3. Moisturize with dosha-appropriate oil
4. Internal: blood-purifying herbs

**Age Ayurveda recommends:**
- *Haridra* — high-potency turmeric for inflammation and skin health
- *Chyawanprash Avaleha* — antioxidant-rich Rasayana for rejuvenation
- *Nutrijam* — delicious immunity and nutrition boost

What's your skin type? Take the **Prakriti Quiz** to find out!""",
    },
    "stress": {
        "keywords": ["stress", "anxiety", "tension", "worry", "nervous", "panic", "overwhelm", "mental"],
        "response": """**Managing Stress with Ayurveda**

Ayurveda views stress as primarily a Vata imbalance — the restless mind (Manas) becomes agitated when Vata rises.

**Ayurvedic stress management:**
- **Abhyanga** — daily warm oil self-massage grounds Vata
- **Nasya** — nasal oil for clarity and calm
- **Pranayama** — Nadi Shodhana (alternate nostril breathing)
- **Ashwagandha** — the premier adaptogenic herb
- **Warm, nourishing diet** — avoid caffeine, raw/cold foods
- **Routine** — Vata thrives on consistency

**Age Ayurveda recommends:**
- *Ashwagandha* — clinically proven adaptogen for stress relief
- *ADHD Ease* — Brahmi, Tagar, Jyotishmati blend for focus and calm
- *Natural Sleep Aid* — if stress is disrupting your sleep

Long-term stress needs a personalized approach. Take the **Prakriti Quiz** to understand your constitution!""",
    },
    "hair": {
        "keywords": ["hair", "hair loss", "hair fall", "balding", "grey", "gray", "dandruff", "scalp"],
        "response": """**Ayurvedic Hair Care (Kesha Chikitsa)**

Hair health in Ayurveda is connected to bone tissue (Asthi Dhatu) and is strongly influenced by Pitta dosha.

**Ayurvedic hair care tips:**
- **Weekly oil massage** — Bhringraj or coconut oil, leave overnight
- **Iron and calcium** — hair is a byproduct of bone tissue
- **Avoid excess heat** — hot water, blow dryers aggravate Pitta
- **Amla internally** — strengthens hair from within
- **Reduce stress** — Vata-type stress causes hair fall

**Age Ayurveda recommends:**
- *Grow and Glow Hair Oil* — Bhringraj, Amla & Brahmi for hair growth and strength
- *Ashwagandha* — if stress-related hair fall

Take the **Prakriti Quiz** to understand your hair type and get personalized advice!""",
    },
    "weight": {
        "keywords": ["weight", "obesity", "fat", "lose weight", "slim", "overweight", "metabolism", "sugar", "diabetes", "blood sugar"],
        "response": """**Ayurvedic Weight & Metabolism Management**

Excess weight is typically a Kapha imbalance with weakened Agni (digestive fire) and accumulation of Ama (toxins).

**Ayurvedic approach:**
- **Boost Agni** — ginger tea before meals
- **Eat light dinner** before sunset, no snacking after
- **Hot water sipping** throughout the day dissolves Ama
- **Vigorous morning exercise** — Surya Namaskar, brisk walking
- **Honey** (uncooked) with warm water — scrapes Kapha
- **Avoid daytime sleeping** — increases Kapha

**Age Ayurveda recommends:**
- *Sugar Formula* — 11-herb blend to help control blood sugar levels
- *Bowel Kare* — supports detoxification and digestive wellness
- *Haridra* — turmeric for metabolism and anti-inflammatory support

Take the **Prakriti Quiz** — Kapha types need different strategies than Vata types!""",
    },
    "joint": {
        "keywords": ["joint", "arthritis", "pain", "knee", "back pain", "muscle", "stiffness"],
        "response": """**Joint Health in Ayurveda (Sandhi Chikitsa)**

Joint pain is predominantly a Vata disorder. When Vata accumulates in joints, it causes pain, cracking, and stiffness.

**Ayurvedic joint care:**
- **Warm oil massage** (Abhyanga) with Mahanarayan oil
- **Anti-inflammatory spices** — turmeric, ginger in daily cooking
- **Castor oil** — 1 tsp with warm milk at bedtime for Vata
- **Avoid cold, dry foods** and exposure to cold wind
- **Gentle yoga** — Cat-Cow, gentle twists, Pawanmuktasana

**Age Ayurveda recommends:**
- *Haridra* — potent turmeric capsules for inflammation and joint health
- *Nitya Naturals Balm* — Ayurvedic pain relief balm for muscles and joints
- *Ashwagandha* — strength and stress support

Take the **Prakriti Quiz** to confirm if Vata is your primary imbalance!""",
    },
    "women": {
        "keywords": ["women", "period", "menstrual", "pcos", "hormonal", "pregnancy", "menopause", "lactation", "fertility"],
        "response": """**Women's Health in Ayurveda (Stri Roga)**

Ayurveda has an entire branch dedicated to women's health. Key herbs like Shatavari and Ashwagandha are revered for their rejuvenating power for women at all life stages.

**Key recommendations:**
- **Ashwagandha** — energy, strength, and hormonal balance
- **Warm, nourishing diet** during menstruation
- **Avoid cold foods/drinks** during periods
- **Gentle yoga** and rest during the first 2 days
- **Turmeric (Haridra)** for menstrual comfort

**Age Ayurveda recommends:**
- *Ashwagandha* — energy, stress support, and vitality
- *Haridra* — anti-inflammatory support and skin health
- *Chyawanprash Avaleha* — daily nourishment and Rasayana
- *Immuno Plus* — overall wellness with 7 powerful herbs

**Important:** For pregnancy, PCOS, or serious hormonal concerns, please consult a qualified Ayurvedic practitioner alongside your doctor.

Take the **Prakriti Quiz** for personalized recommendations!""",
    },
    "respiratory": {
        "keywords": ["breathing", "sinus", "nasal", "congestion", "throat", "voice", "lungs"],
        "response": """**Respiratory Health in Ayurveda (Pranavaha Srotas)**

Ayurveda emphasizes keeping the respiratory channels clear through proper diet, breathing exercises, and herbal support.

**Ayurvedic respiratory care:**
- **Nasya** — nasal oil application for sinus health
- **Steam inhalation** with eucalyptus or tulsi
- **Pranayama** — Kapalabhati and Bhastrika for lung strength
- **Warm fluids** — ginger-tulsi tea throughout the day
- **Avoid cold, damp environments** and dairy excess

**Age Ayurveda recommends:**
- *Yastimadhu* — licorice root for throat, stomach, and respiratory health
- *Nasja Oil* — Ayurvedic nasal oil for sinus and breathing
- *Immuno Plus* — 7-herb blend supporting respiratory health

Take the **Prakriti Quiz** for a personalized respiratory wellness plan!""",
    },
    "focus": {
        "keywords": ["focus", "concentration", "memory", "brain", "adhd", "attention", "cognitive", "mental clarity"],
        "response": """**Brain Health & Focus in Ayurveda (Medhya Rasayana)**

Ayurveda has a specific category of herbs called *Medhya Rasayanas* — brain tonics that enhance intellect, memory, and concentration.

**Ayurvedic brain health tips:**
- **Brahmi** — the premier Medhya herb for memory and focus
- **Meditation** — even 10 minutes daily strengthens concentration
- **Nasya** — nasal oil application clears mental fog
- **Adequate sleep** — the brain consolidates memory during sleep
- **Sattvic diet** — fresh, wholesome foods support mental clarity

**Age Ayurveda recommends:**
- *ADHD Ease* — Brahmi, Tagar, Jyotishmati, Shankhpushpi & Vacha for focus and clarity
- *Natural Sleep Aid* — quality sleep is essential for cognitive health
- *Nasja Oil* — nasal oil for mental clarity

Take the **Prakriti Quiz** to understand how your dosha affects your mental patterns!""",
    },
    "diet_rules": {
        "keywords": ["diet", "eating rules", "food rules", "agni", "how to eat", "eating habits", "meal timing"],
        "response": """**Ayurvedic Rules of Eating (Ahara Vidhi)**

The Charaka Samhita prescribes specific rules for *how* to eat — not just *what*. Following these enhances Agni and prevents Ama (toxins).

**Meal timing (Dinacharya):**
- **Breakfast (7-8 AM)** — light, warm; Kapha time, so keep it simple
- **Lunch (12-1 PM)** — your LARGEST meal; Pitta time = peak Agni
- **Dinner (6-7 PM)** — light, easy to digest; finish 2-3 hours before sleep
- Allow 4-6 hours between meals; no snacking unless genuinely hungry

**How to eat:**
- Always sit down — never eat standing or walking
- Eat in silence or with pleasant company; no screens
- Chew thoroughly — food should be nearly liquid before swallowing
- Fill stomach 1/3 food, 1/3 water, 1/3 empty (for digestion)
- Never eat when angry, anxious, or rushing — emotions weaken Agni

**The 4 types of Agni (digestive fire):**
- **Sama Agni** (balanced) — steady appetite, good energy, regular stools
- **Vishama Agni** (Vata) — irregular appetite, gas, bloating, constipation
- **Tikshna Agni** (Pitta) — sharp hunger, acidity, irritable if meals delayed
- **Manda Agni** (Kapha) — dull appetite, heaviness, slow metabolism

**Water rules:**
- Sip warm water during meals — never ice-cold
- Avoid large amounts 30 min before meals (weakens Agni)
- Wait 30-45 min after meals before drinking
- Morning warm water on empty stomach (Ushapan) is excellent

**After eating:**
- Sit quietly for 5-10 minutes
- Gentle 100-step walk (Shatapavali) — NOT vigorous exercise
- No sleeping for at least 2 hours after meals
- Chew fennel seeds or a thin ginger slice for digestive support

Take the **Prakriti Quiz** to discover your Agni type and get personalized diet guidance!""",
    },
    "food_combinations": {
        "keywords": ["food combination", "viruddha", "incompatible", "mix", "combine", "together", "milk and fruit", "wrong food"],
        "response": """**Incompatible Food Combinations (Viruddha Ahara)**

The Charaka Samhita describes 18 types of food incompatibility. Eating wrong combinations weakens Agni and creates Ama (toxins), leading to skin problems, digestive issues, and chronic disease.

**Top combinations to AVOID:**

🚫 **Milk + sour fruits** (oranges, pineapple, berries)
→ Milk curdles in the stomach; creates toxins and skin disorders

🚫 **Milk + banana**
→ Extremely heavy; creates congestion, dulls Agni

🚫 **Milk + fish or meat**
→ Potency clash (Veerya Viruddha); causes blood toxicity, skin diseases

🚫 **Milk + melons**
→ Different digestion rates cause fermentation, bloating

🚫 **Honey heated or cooked**
→ Creates toxic compounds; classically described as producing poison (visha)

🚫 **Honey + ghee in equal quantities**
→ Slow-acting toxin (Matra Viruddha — dose incompatibility)

🚫 **Curd/yogurt at night**
→ Increases Kapha, blocks channels, aggravates skin conditions

🚫 **Curd + fruit**
→ Sour + sweet ferments; impairs digestion

🚫 **Cold drinks with meals**
→ Extinguishes Agni directly; promotes Ama

🚫 **Radish + milk**
→ Causes skin eruptions and digestive disturbance

**Signs of Ama (toxin) buildup:**
- White/yellow coating on tongue in the morning
- Bad breath, body odor
- Heaviness and lethargy after meals
- Brain fog, poor concentration
- Sticky, irregular stools
- Frequent colds, congestion

**Ama-clearing protocol:**
- Kitchari mono-diet (rice + mung dal + spices) for 3-7 days
- CCF Tea (Cumin-Coriander-Fennel) throughout the day
- Digestive spices: ginger, cumin, fennel, turmeric, asafoetida""",
    },
    "seasonal_diet": {
        "keywords": ["seasonal", "ritucharya", "season", "summer diet", "winter diet", "monsoon", "spring"],
        "response": """**Seasonal Eating (Ritucharya) — Ayurvedic Seasonal Regimen**

Charaka Samhita (Sutrasthana Ch. 6) prescribes adjusting diet every 2 months to stay in harmony with nature's cycles.

**🌸 Vasanta (Spring: Mar-May) — Kapha season**
- Eat light, dry, bitter, pungent foods — barley, honey, mung dal, bitter greens
- Avoid heavy, oily, sweet foods; no daytime sleeping
- Best time for Kapha-reducing practices and fasting

**☀️ Grishma (Summer: May-Jul) — Pitta season**
- Eat sweet, light, cooling, liquid foods — rice, milk, ghee, coconut water, sweet fruits
- Favor coriander, fennel, mint; avoid pungent, sour, salty
- Reduce exercise intensity; stay hydrated

**🌧️ Varsha (Monsoon: Jul-Sep) — Vata aggravation**
- Eat warm, light, slightly oily, sour foods — old grains, soups, ginger water, ghee
- Always boil water; avoid raw salads and street food
- Agni is weakest — eat only freshly cooked food

**🍂 Sharad (Autumn: Sep-Nov) — Pitta pacification**
- Eat sweet, bitter, cooling foods — rice, green gram, amla, ghee, candy sugar
- Avoid excess fat, oil, curd; this is the season for Pitta cleansing
- Drink water cooled after boiling; traditionally, water exposed to moonlight

**❄️ Hemanta (Early Winter: Nov-Jan) — Agni is strong**
- Eat heavy, nourishing, sweet, sour, salty foods — wheat, milk, sesame, jaggery
- Generous ghee, warm soups, root vegetables; Agni can handle rich meals
- Avoid fasting, light/dry foods

**🧊 Shishira (Late Winter: Jan-Mar) — Agni peaks**
- Similar to Hemanta — favor heavy, warm, unctuous foods
- Urad dal, new rice, sesame oil, warm milk, sweet preparations
- Avoid cold, dry, bitter, astringent foods

**Golden rule:** *Eat with the seasons, not against them. Your Agni naturally adjusts every 2 months.*""",
    },
    "fasting": {
        "keywords": ["fast", "fasting", "detox", "cleanse", "upvas", "ekadashi", "langhana"],
        "response": """**Fasting in Ayurveda (Langhana)**

*"Langhanam param aushadham"* — "Fasting is the supreme medicine" (Charaka Samhita)

Ayurveda uses fasting therapeutically, but the approach differs by dosha:

**Kapha — benefits MOST from fasting**
- Frequency: once a week is ideal
- Type: dry fast or complete food fast for 24 hours; liquid fast with ginger tea and honey water also works
- Why: stimulates Kapha's sluggish Agni, reduces heaviness, clears congestion

**Pitta — moderate, careful fasting**
- Frequency: once or twice a month
- Type: liquid fast only — vegetable broth, coconut water, cooling herbal teas
- Duration: 10-12 hours max; never dry fast
- Why: Pitta's sharp Agni becomes hyperacidic without food

**Vata — fasting is generally NOT recommended**
- Frequency: once a month at most, and only when feeling heavy
- Type: warm liquid fast only — ginger-lemon water, light vegetable broth
- Duration: skip one meal, never a full day
- Why: prolonged fasting aggravates Vata, causing anxiety, insomnia, and weakness

**Universal fasting rules:**
- Break fast gently: warm water → thin soup → kitchari → normal food
- Ekadashi (11th lunar day) fasting is traditional for all doshas
- Fast only when Ama is present or digestion is sluggish — not as weight loss
- Stay warm and rest during fasting
- Avoid intense exercise while fasting

**Age Ayurveda recommends for cleansing support:**
- *Bowel Kare* — gentle detoxification and digestive support
- *Chyawanprash Avaleha* — Rasayana nourishment post-fast""",
    },
}

# ---------------------------------------------------------------------------
# Product finder by dosha
# ---------------------------------------------------------------------------

DOSHA_PRODUCT_RECS = {
    "vata": {
        "intro": "Based on **Vata** constitution, here are your top recommendations:",
        "slugs": ["ashwagandha", "natural-sleep-aid", "bowel-kare", "nitya-naturals-balm", "nasja-oil"],
    },
    "pitta": {
        "intro": "Based on **Pitta** constitution, here are your top recommendations:",
        "slugs": ["acid-relief", "yastimadhu", "grow-and-glow-hair-oil", "adhd-ease", "natural-sleep-aid"],
    },
    "kapha": {
        "intro": "Based on **Kapha** constitution, here are your top recommendations:",
        "slugs": ["immuno-plus", "haridra", "sugar-formula", "nasja-oil", "ashwagandha"],
    },
}

# ---------------------------------------------------------------------------
# Main response function
# ---------------------------------------------------------------------------

def get_static_response(message: str, language: str = "en") -> dict:
    """
    Return a rule-based response with optional product recommendations.
    Returns: {"content": str, "products": list[dict], "citations": [], "model": "static-rules"}
    """
    _load_data()
    msg = message.lower().strip()

    # 1. Dosha-specific queries
    for dosha_key, info in DOSHA_INFO.items():
        patterns = [dosha_key]
        if dosha_key == "vata":
            patterns += ["vaat"]
        elif dosha_key == "pitta":
            patterns += ["piit"]
        elif dosha_key == "kapha":
            patterns += ["kaph", "sleshma"]

        if any(p in msg for p in patterns):
            # Check if asking for products/recommendations
            wants_products = any(w in msg for w in ["product", "recommend", "buy", "suggest", "which"])

            if wants_products:
                return _dosha_product_response(dosha_key, language)

            content = f"**{info['title']}**\n\n"
            content += f"**Characteristics:** {info['traits']}\n\n"
            content += f"**Diet — Do's:**\n{info['diet_dos']}\n\n"
            content += f"**Diet — Don'ts:**\n{info['diet_donts']}\n\n"
            content += f"**Lifestyle — Do's:**\n{info['lifestyle_dos']}\n\n"
            content += f"**Lifestyle — Don'ts:**\n{info['lifestyle_donts']}\n\n"
            content += f"**Key herbs:** {info['herbs']}\n\n"
            content += "Would you like **product recommendations** for your dosha, or take the **Prakriti Quiz** to confirm your constitution?"

            return {"content": content, "products": [], "citations": [], "model": "static-rules"}

    # 2. Prakriti / dosha quiz intent
    if any(w in msg for w in ["prakriti", "prakruti", "constitution", "dosha quiz", "my dosha", "find my", "know my body"]):
        content = """**Discover Your Prakriti (Body Constitution)**

In Ayurveda, every person has a unique combination of three doshas:
- **Vata** (Air + Space) — governs movement, creativity, flexibility
- **Pitta** (Fire + Water) — governs digestion, metabolism, intellect
- **Kapha** (Earth + Water) — governs structure, stability, immunity

Knowing your Prakriti helps you choose the right:
✅ Diet and foods
✅ Exercise and lifestyle
✅ Herbs and supplements
✅ Daily routine (Dinacharya)

**Click the "Prakriti Quiz" button** below to take our 25-question assessment and get personalized product recommendations!

Or tell me your known dosha (Vata/Pitta/Kapha) and I'll recommend products right away."""
        return {"content": content, "products": [], "citations": [], "model": "static-rules"}

    # 3. Topic-based responses (no product cards — only after Prakriti quiz)
    for topic_key, topic in TOPIC_RESPONSES.items():
        if any(kw in msg for kw in topic["keywords"]):
            return {"content": topic["response"], "products": [], "citations": [], "model": "static-rules"}

    # 4. Product-specific queries
    for product in _products:
        name_lower = product["name"].lower()
        slug = product["slug"]
        ingredients_lower = [i.lower() for i in product.get("ingredients", [])]

        if name_lower in msg or slug.replace("-", " ") in msg or any(ing in msg for ing in ingredients_lower if len(ing) > 3):
            content = f"**{product['name']}**\n\n"
            content += f"{product['description']}\n\n"
            content += f"**Category:** {product['category']}\n"
            content += f"**Key ingredients:** {', '.join(product.get('ingredients', []))}\n"
            content += f"**Benefits:** {', '.join(product.get('benefits', []))}\n"
            content += f"**Suitable for:** {', '.join(d.capitalize() for d in product.get('doshas', []))} doshas\n\n"
            if product.get("dosha_balance"):
                content += f"**Dosha balance:** {product['dosha_balance']}\n\n"
            content += f"[View on Age Ayurveda →]({product['shopify_url']})\n\n"
            content += "Would you like recommendations for other products based on your dosha?"

            prod_out = [{
                "id": product["id"],
                "name": product["name"],
                "slug": product["slug"],
                "price": product["price"],
                "image_url": product.get("image_url", ""),
                "shopify_url": product.get("shopify_url", ""),
                "dosha_balance": product.get("dosha_balance", ""),
                "score": 10.0,
            }]
            return {"content": content, "products": prod_out, "citations": [], "model": "static-rules"}

    # 5. General help / product finder
    if any(w in msg for w in ["product", "buy", "recommend", "what should", "help me", "suggest", "shop"]):
        content = """**I can help you find the right Ayurvedic products!**

Tell me about:
- **Your concern** — digestion, sleep, stress, skin, hair, joints, weight, immunity
- **Your dosha** — Vata, Pitta, or Kapha (if you know it)
- **A specific product** — Ashwagandha, Chyawanprash, Haridra, etc.

Or take the **Prakriti Quiz** for personalized recommendations based on your unique constitution!

**Our popular categories:**
🌿 Digestive Health — Acid Relief, Bowel Kare
💪 Immunity — Immuno Plus, Chyawanprash, Chyawan Cap, Immunity Kit
😴 Sleep & Stress — Natural Sleep Aid, Ashwagandha, ADHD Ease
🩹 Pain Relief — Haridra, Nitya Naturals Balm
🌬️ Respiratory — Yastimadhu, Nasja Oil
💇 Hair Care — Grow and Glow Hair Oil"""
        return {"content": content, "products": [], "citations": [], "model": "static-rules"}

    # 6. What is Ayurveda
    if any(w in msg for w in ["what is ayurveda", "about ayurveda"]):
        content = """**Ayurveda — The Science of Life**

Ayurveda (आयुर्वेद) is a 5,000-year-old holistic healing system from India. The word means "Knowledge of Life" (Ayus = life, Veda = knowledge).

**Core principles:**
- **Three Doshas** — Vata, Pitta, Kapha govern all bodily functions
- **Prakriti** — Each person has a unique constitutional type
- **Agni** — Digestive fire is the foundation of health
- **Ojas** — Vital energy that provides immunity and vitality
- **Dinacharya** — Daily routine aligned with nature's rhythms

**Classical texts:**
- *Charaka Samhita* — Internal medicine
- *Sushruta Samhita* — Surgery and procedures
- *Ashtanga Hridaya* — Comprehensive compendium

Would you like to discover your dosha? Take the **Prakriti Quiz**!"""
        return {"content": content, "products": [], "citations": [], "model": "static-rules"}

    # 7. Default fallback
    content = """I'm your **Ayurveda Guide** — I can help you with:

🔬 **Prakriti Quiz** — Discover your dosha constitution
🌿 **Product Finder** — Get matched with the right herbs
📚 **Ayurvedic Topics** — Digestion, immunity, sleep, stress, skin, hair, joints, weight, women's health

**Try asking me:**
- "What is my dosha?"
- "I have digestion problems"
- "Recommend products for sleep"
- "Tell me about Vata dosha"
- "What is Ashwagandha good for?"

Or click one of the **quick action buttons** below!"""
    return {"content": content, "products": [], "citations": [], "model": "static-rules"}


def _dosha_product_response(dosha: str, language: str = "en") -> dict:
    """Return product recommendations for a specific dosha."""
    _load_data()
    rec = DOSHA_PRODUCT_RECS.get(dosha, DOSHA_PRODUCT_RECS["vata"])
    info = DOSHA_INFO[dosha]

    products_out = []
    content = f"**{info['title']} — Product Recommendations**\n\n{rec['intro']}\n\n"

    for slug in rec["slugs"]:
        product = next((p for p in _products if p["slug"] == slug), None)
        if product:
            balance = product.get("dosha_balance", "")
            content += f"- **{product['name']}** — {product['description'][:80]}...\n"
            if balance:
                content += f"  *Dosha balance: {balance}*\n"
            products_out.append({
                "id": product["id"],
                "name": product["name"],
                "slug": product["slug"],
                "price": product["price"],
                "image_url": product.get("image_url", ""),
                "shopify_url": product.get("shopify_url", ""),
                "dosha_balance": balance,
                "score": 8.0,
            })

    content += f"\n**Diet tip:** {info['diet_dos'][:120]}...\n\n"
    content += "Take the **Prakriti Quiz** for a full personalized plan!"

    return {"content": content, "products": products_out[:3], "citations": [], "model": "static-rules"}


def _get_products_for_topic(topic_key: str) -> list[dict]:
    """Get relevant products for a topic using the mappings."""
    _load_data()
    topic_keywords = TOPIC_RESPONSES.get(topic_key, {}).get("keywords", [])
    scored = []

    for slug, mapping in _mappings.items():
        score = 0
        for concept in mapping.get("concepts", []):
            if concept in topic_keywords or topic_key in concept:
                score += 3
        for condition in mapping.get("conditions", []):
            if any(kw in condition for kw in topic_keywords):
                score += 5
        if score > 0:
            product = next((p for p in _products if p["slug"] == slug), None)
            if product:
                scored.append((score, product))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "id": p["id"],
            "name": p["name"],
            "slug": p["slug"],
            "price": p["price"],
            "image_url": p.get("image_url", ""),
            "shopify_url": p.get("shopify_url", ""),
            "score": float(s),
        }
        for s, p in scored[:2]
    ]
