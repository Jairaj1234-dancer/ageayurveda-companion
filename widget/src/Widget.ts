import { sendMessage, sendGroundedMessageStream } from "./api/client";
import { getSessionId, getConversationId, setConversationId } from "./utils/storage";
import widgetStyles from "./styles/widget.css?inline";

interface WidgetConfig {
  apiUrl?: string;
  position?: string;
  primaryColor?: string;
  accentColor?: string;
  /**
   * Use the LLM-grounded chat backend (`/chat/grounded/stream`) instead of
   * the rule-based engine. Streams tokens, surfaces classical-text citations,
   * and renders product cards mid-stream from the recommendation tool.
   *
   * Default: false (rule-based — zero API cost).
   * Set to true once `ANTHROPIC_API_KEY` is configured on the backend.
   */
  useGroundedChat?: boolean;
  /**
   * Restrict grounded retrieval to specific classical sources.
   * Example: ["Charaka Samhita"]. Omit for full corpus.
   */
  groundedSources?: string[];
}

interface MenuOption {
  label: string;
  icon: string;
  query?: string;
  children?: MenuOption[];
  action?: string;
}

// ---------------------------------------------------------------------------
// Prakriti questions (embedded — no API needed)
// ---------------------------------------------------------------------------
const QUIZ_QUESTIONS = [
  { id:1, q:"What is your body frame?", opts:[{l:"Thin, light, lean frame",d:"vata"},{l:"Medium, athletic build",d:"pitta"},{l:"Large, solid, heavy frame",d:"kapha"}]},
  { id:2, q:"How is your skin type?", opts:[{l:"Dry, rough, thin",d:"vata"},{l:"Warm, oily, sensitive, prone to rashes",d:"pitta"},{l:"Thick, smooth, moist, cool",d:"kapha"}]},
  { id:3, q:"What is your hair type?", opts:[{l:"Dry, brittle, frizzy",d:"vata"},{l:"Fine, thin, early greying",d:"pitta"},{l:"Thick, oily, wavy, lustrous",d:"kapha"}]},
  { id:4, q:"How are your eyes?", opts:[{l:"Small, dry, darting",d:"vata"},{l:"Sharp, bright, sensitive to light",d:"pitta"},{l:"Large, calm, beautiful",d:"kapha"}]},
  { id:5, q:"How is your body weight?", opts:[{l:"Difficulty gaining weight",d:"vata"},{l:"Moderate, can gain or lose easily",d:"pitta"},{l:"Gains weight easily, hard to lose",d:"kapha"}]},
  { id:6, q:"How is your appetite?", opts:[{l:"Irregular, sometimes forget to eat",d:"vata"},{l:"Strong, irritable if meal is missed",d:"pitta"},{l:"Steady but can skip meals easily",d:"kapha"}]},
  { id:7, q:"How is your digestion?", opts:[{l:"Irregular — gas, bloating, constipation",d:"vata"},{l:"Strong — acidity, heartburn if delayed",d:"pitta"},{l:"Slow — feel heavy after meals",d:"kapha"}]},
  { id:8, q:"How do you handle cold weather?", opts:[{l:"Dislike cold, hands/feet get cold easily",d:"vata"},{l:"Prefer cool weather, tolerate cold well",d:"pitta"},{l:"Can tolerate cold but dislike damp weather",d:"kapha"}]},
  { id:9, q:"How is your sweat?", opts:[{l:"Minimal perspiration",d:"vata"},{l:"Profuse, especially when hot/stressed",d:"pitta"},{l:"Moderate, steady perspiration",d:"kapha"}]},
  { id:10, q:"How is your sleep pattern?", opts:[{l:"Light, interrupted, difficulty falling asleep",d:"vata"},{l:"Moderate, sound, 6-7 hours sufficient",d:"pitta"},{l:"Deep, heavy, love to sleep long",d:"kapha"}]},
  { id:11, q:"How is your physical endurance?", opts:[{l:"Low — tire quickly, quick bursts of energy",d:"vata"},{l:"Moderate — good stamina, can overheat",d:"pitta"},{l:"High — steady energy, slow to start",d:"kapha"}]},
  { id:12, q:"How is your thirst?", opts:[{l:"Variable, sometimes forget to drink",d:"vata"},{l:"Strong, need lots of water",d:"pitta"},{l:"Low, can go long without water",d:"kapha"}]},
  { id:13, q:"How do you walk?", opts:[{l:"Quick, light steps",d:"vata"},{l:"Moderate, purposeful stride",d:"pitta"},{l:"Slow, steady, graceful",d:"kapha"}]},
  { id:14, q:"How is your voice?", opts:[{l:"Low, hoarse, sometimes cracking",d:"vata"},{l:"Sharp, clear, penetrating",d:"pitta"},{l:"Deep, pleasant, melodious",d:"kapha"}]},
  { id:15, q:"How are your joints?", opts:[{l:"Prominent, cracking joints",d:"vata"},{l:"Flexible, sometimes inflamed",d:"pitta"},{l:"Large, well-lubricated",d:"kapha"}]},
  { id:16, q:"How do you handle stress?", opts:[{l:"Become anxious, worried, fearful",d:"vata"},{l:"Become irritable, angry, critical",d:"pitta"},{l:"Become withdrawn, avoid the situation",d:"kapha"}]},
  { id:17, q:"How is your learning style?", opts:[{l:"Quick to learn, quick to forget",d:"vata"},{l:"Sharp, focused, good comprehension",d:"pitta"},{l:"Slow to learn, excellent long-term memory",d:"kapha"}]},
  { id:18, q:"What is your emotional nature?", opts:[{l:"Enthusiastic, creative, changeable moods",d:"vata"},{l:"Passionate, driven, intense",d:"pitta"},{l:"Calm, loving, content, steady",d:"kapha"}]},
  { id:19, q:"How do you make decisions?", opts:[{l:"Quickly, may change mind later",d:"vata"},{l:"Confidently, with analysis",d:"pitta"},{l:"Slowly, carefully, after much thought",d:"kapha"}]},
  { id:20, q:"How is your speech pattern?", opts:[{l:"Fast, talkative, may go off-topic",d:"vata"},{l:"Precise, argumentative, convincing",d:"pitta"},{l:"Slow, thoughtful, sweet",d:"kapha"}]},
  { id:21, q:"How do you spend money?", opts:[{l:"Spend quickly, impulsive buying",d:"vata"},{l:"Spend on quality and luxury items",d:"pitta"},{l:"Save well, spend cautiously",d:"kapha"}]},
  { id:22, q:"What type of dreams do you have?", opts:[{l:"Flying, running, fearful, active",d:"vata"},{l:"Fiery, colorful, conflict, adventurous",d:"pitta"},{l:"Water, calm, romantic, peaceful",d:"kapha"}]},
  { id:23, q:"How is your bowel movement?", opts:[{l:"Irregular, tends to constipation",d:"vata"},{l:"Regular, loose stools, burning",d:"pitta"},{l:"Regular, heavy, well-formed",d:"kapha"}]},
  { id:24, q:"What is your social nature?", opts:[{l:"Make friends easily, many acquaintances",d:"vata"},{l:"Selective, natural leader, competitive",d:"pitta"},{l:"Few close friends, loyal, nurturing",d:"kapha"}]},
  { id:25, q:"What food cravings do you have?", opts:[{l:"Crunchy, salty snacks, warm foods",d:"vata"},{l:"Cold drinks, spicy food, sweets",d:"pitta"},{l:"Sweet, creamy, rich comfort food",d:"kapha"}]},
];

// ---------------------------------------------------------------------------
// Dosha result data (embedded)
// ---------------------------------------------------------------------------
const DOSHA_DESC: Record<string,string> = {
  vata: "You have a <strong>Vata-dominant</strong> constitution. Vata types tend to be creative, quick-thinking, and energetic but may experience anxiety, dryness, and irregular digestion when imbalanced.",
  pitta: "You have a <strong>Pitta-dominant</strong> constitution. Pitta types are focused, determined, and sharp-minded but may experience inflammation, acidity, and irritability when imbalanced.",
  kapha: "You have a <strong>Kapha-dominant</strong> constitution. Kapha types are calm, steady, and nurturing but may experience lethargy, weight gain, and congestion when imbalanced.",
  "vata-pitta": "You have a <strong>Vata-Pitta</strong> dual constitution. You combine the creativity and energy of Vata with the focus and intensity of Pitta.",
  "pitta-kapha": "You have a <strong>Pitta-Kapha</strong> dual constitution. You combine the determination of Pitta with the steadiness of Kapha.",
  "vata-kapha": "You have a <strong>Vata-Kapha</strong> dual constitution. You combine Vata's creativity with Kapha's endurance.",
  tridosha: "You have a rare <strong>Tridoshic (Sama Prakriti)</strong> constitution with all three doshas in near-equal balance. This is considered ideal in Ayurveda.",
};

const DOSHA_DIET_DOS: Record<string,string[]> = {
  vata: [
    "Favor warm, cooked, moist foods — soups, stews, porridges, khichdi",
    "Use healthy fats generously — ghee, sesame oil, olive oil nourish Vata",
    "Favor sweet, sour & salty tastes — they ground and calm Vata",
    "Best grains: rice, wheat, oats (cooked), quinoa",
    "Best vegetables (cooked): sweet potato, carrot, beetroot, asparagus, zucchini",
    "Best fruits: bananas, mangoes, avocado, dates, figs, stewed apples",
    "Best spices: ginger, cumin, cinnamon, cardamom, fennel, asafoetida (hing)",
    "Include warm milk with nutmeg or turmeric before bed",
    "Eat at regular times — never skip meals, Vata needs routine",
    "Sip warm water or ginger tea throughout the day",
  ],
  pitta: [
    "Favor cooling, refreshing, mildly-spiced foods — think fresh, not fried",
    "Sweet, bitter & astringent tastes pacify Pitta — emphasize these",
    "Best grains: basmati rice, wheat, barley, oats",
    "Best vegetables: cucumber, leafy greens, broccoli, cauliflower, celery, zucchini",
    "Best fruits: sweet grapes, melons, pomegranate, coconut, pears, sweet apples",
    "Use cooling oils — coconut oil, ghee, sunflower oil",
    "Best spices: coriander, fennel, cardamom, turmeric, fresh mint, saffron",
    "Eat your largest meal at lunch when Agni is strongest — keep dinner light",
    "Drink room-temperature or cool water with meals",
    "Fresh coconut water, aloe vera juice & mint tea are excellent Pitta coolers",
  ],
  kapha: [
    "Favor light, warm, dry & well-spiced foods",
    "Pungent, bitter & astringent tastes stimulate Kapha — emphasize these",
    "Best grains: barley, millet, buckwheat, corn, rye",
    "Best vegetables: leafy greens, radish, cabbage, broccoli, bell peppers, sprouts",
    "Best fruits: apples, pears, pomegranate, berries, dried figs",
    "Best spices: black pepper, ginger, turmeric, mustard seeds, fenugreek, cloves, cayenne",
    "Honey (raw, uncooked) with warm water in the morning helps scrape Kapha",
    "Eat only 2 meals a day if possible — skip breakfast or keep it very light",
    "Ginger tea with black pepper and honey is the ideal Kapha beverage",
    "Periodic light fasting (1 day/week) is beneficial for Kapha constitutions",
  ],
};

const DOSHA_DIET_DONTS: Record<string,string[]> = {
  vata: [
    "Raw salads, cold smoothies, dried fruits, popcorn & carbonated drinks",
    "Excess caffeine and bitter/astringent foods in large amounts",
    "Dry crackers, corn, and cold cereals",
    "Ice-cold water or beverages with meals",
    "Light fasting — Vata needs consistent nourishment",
    "Eating on the go or while distracted",
  ],
  pitta: [
    "Hot, spicy, sour & fermented foods — chili, vinegar, pickles, sour yogurt",
    "Excess tomatoes, garlic, raw onions, citrus — they increase Pitta fire",
    "Deep-fried food, excess salt, alcohol, and coffee",
    "Eating when angry or stressed — emotions weaken Agni",
    "Ice-cold drinks with meals",
    "Mustard oil and sesame oil — too heating for Pitta",
  ],
  kapha: [
    "Heavy, sweet, oily, cold foods — cheese, ice cream, fried food, excess sugar",
    "Cold milk, yogurt, and cream — if dairy, use warm goat milk only",
    "Bananas, dates, coconut, and watermelon",
    "Excess wheat, rice, and refined sugar",
    "Snacking between meals — let Agni fully digest each meal",
    "Napping after meals — it increases Kapha congestion",
  ],
};

const DOSHA_LIFESTYLE_DOS: Record<string,string[]> = {
  vata: [
    "Follow a consistent daily routine (Dinacharya) — eat, sleep, wake at same times",
    "Daily warm sesame oil self-massage (Abhyanga) — deeply calming for Vata",
    "Gentle yoga: forward bends, hip openers, Balasana, Shavasana",
    "Practice Nadi Shodhana (alternate nostril breathing) for nervous system balance",
    "Go to bed by 10 PM — Vata needs 7-8 hours of quality sleep",
    "Stay warm — wear layers, keep head and ears covered",
  ],
  pitta: [
    "Moderate exercise — swimming, cycling, walking in nature",
    "Practice Sheetali pranayama (cooling breath) — curl tongue, inhale cool air",
    "Moonlight walks and time near water bodies cool Pitta naturally",
    "Daily coconut oil massage — cooling alternative to sesame oil",
    "Channel intensity into creative outlets — painting, music, writing",
    "Practice letting go — Pitta types hold onto anger; forgiveness is medicine",
  ],
  kapha: [
    "Wake before 6 AM — morning energy is essential for Kapha",
    "Vigorous daily exercise: running, HIIT, Surya Namaskar, power yoga",
    "Dry brushing (Garshana) before bath stimulates lymphatic drainage",
    "Seek variety, travel, and new experiences to counter stagnation",
    "Practice Kapalabhati (skull-shining breath) for energy and lung strength",
    "Declutter your space regularly — external order reflects internal lightness",
  ],
};

const DOSHA_LIFESTYLE_DONTS: Record<string,string[]> = {
  vata: [
    "Cold wind and prolonged cold exposure without layers",
    "Over-stimulation — excess screen time, loud noise, chaotic environments",
    "Excessive travel and constant change of routine",
    "Staying up past 10 PM — it aggravates Vata restlessness",
    "Skipping meals or fasting — Vata needs regular nourishment",
  ],
  pitta: [
    "Overheating and midday sun (10am–2pm) — Pitta time when fire peaks",
    "Overly competitive or aggressive exercise",
    "Working through meals or skipping lunch",
    "Suppressing emotions — especially anger (it builds internal heat)",
    "Hot baths, saunas, or steam rooms in excess",
  ],
  kapha: [
    "Sleeping past 6 AM — Kapha time worsens lethargy and heaviness",
    "Daytime napping — it increases congestion and dullness",
    "Sedentary habits and excessive sitting or couch time",
    "Oversleeping (more than 7-8 hours)",
    "Staying in the same routine without variety or stimulation",
  ],
};

const CDN = "https://cdn.shopify.com/s/files/1/0950/5715/0251/files";
const DOSHA_PRODUCTS: Record<string,{name:string,price:number,slug:string,img:string,balance:string}[]> = {
  vata: [
    {name:"Ashwagandha",price:479,slug:"ashwagandha",img:`${CDN}/DSC04420copy.jpg?v=1756121134`,balance:"Pacifies Vata by calming anxiety and promoting restful sleep; builds vitality and resilience against fatigue."},
    {name:"Natural Sleep Aid",price:899,slug:"natural-sleep-aid",img:`${CDN}/DSC_3045copy.jpg?v=1756120146`,balance:"Calms aggravated Vata — the primary cause of insomnia — while Brahmi and Jatamansi cool Pitta-driven anxiety."},
    {name:"Bowel Kare",price:467,slug:"bowel-kare",img:`${CDN}/DSC_3024copy.jpg?v=1756121074`,balance:"Eases Vata-type constipation and irregular digestion with Triphala's gentle detoxifying action."},
    {name:"Nitya Naturals Balm",price:239,slug:"nitya-naturals-balm",img:`${CDN}/DSC_3081.jpg?v=1756119981`,balance:"Warms and relieves Vata-type stiffness, joint pain, and muscle tension with Eucalyptus and Camphor."},
  ],
  pitta: [
    {name:"Acid Relief",price:479,slug:"acid-relief",img:`${CDN}/DSC_3084.jpg?v=1760359362`,balance:"Directly pacifies aggravated Pitta — the root cause of acidity — using cooling Avipattikar herbs and Amla."},
    {name:"Yastimadhu",price:439,slug:"yastimadhu",img:`${CDN}/DSC_3040copy.jpg?v=1756121004`,balance:"Soothes Pitta-driven irritation in throat and stomach with the cooling, demulcent properties of Licorice root."},
    {name:"Grow and Glow Hair Oil",price:399,slug:"grow-and-glow-hair-oil",img:`${CDN}/DSC_3032copy.jpg?v=1756121042`,balance:"Cools excess Pitta — the main cause of premature greying and hair fall — with Bhringraj and Amla."},
    {name:"ADHD Ease",price:960,slug:"adhd-ease",img:`${CDN}/DSC_3054copy.jpg?v=1756119810`,balance:"Cools Pitta-related mental agitation using Medhya herbs like Brahmi and Shankhpushpi for focused clarity."},
  ],
  kapha: [
    {name:"Immuno Plus",price:488,slug:"immuno-plus",img:`${CDN}/DSC_3109.jpg?v=1756121121`,balance:"Clears Kapha congestion with Kalmegh and Haldi while 7 herbs strengthen sluggish Kapha immunity."},
    {name:"Haridra",price:485,slug:"haridra",img:`${CDN}/DSC04429.jpg?v=1756121096`,balance:"Reduces Kapha-driven stiffness and swelling through Curcumin's potent anti-inflammatory and metabolism-boosting action."},
    {name:"Sugar Formula",price:719,slug:"sugar-formula",img:`${CDN}/DSC_3051.jpg?v=1756121056`,balance:"Addresses Kapha-type metabolic sluggishness — Karela and Gudmar support pancreatic function and blood sugar regulation."},
    {name:"Nasja Oil",price:279,slug:"nasja-oil",img:`${CDN}/DSC04407.jpg?v=1756121147`,balance:"Clears Kapha congestion in the sinuses through traditional Nasya therapy, restoring clear breathing and mental clarity."},
  ],
};

// ---------------------------------------------------------------------------
// Menu tree
// ---------------------------------------------------------------------------
const MENU_TREE: MenuOption[] = [
  {
    label: "Take Prakriti Quiz", icon: "📋", action: "prakriti",
  },
  {
    label: "Know Your Dosha", icon: "🧘",
    children: [
      { label: "What is Vata?", icon: "💨", query: "Tell me about Vata dosha" },
      { label: "What is Pitta?", icon: "🔥", query: "Tell me about Pitta dosha" },
      { label: "What is Kapha?", icon: "🌊", query: "Tell me about Kapha dosha" },
    ],
  },
  {
    label: "Health Concerns", icon: "🌿",
    children: [
      { label: "Digestion", icon: "🍽️", query: "I have digestion problems" },
      { label: "Immunity", icon: "🛡️", query: "How to build immunity" },
      { label: "Sleep", icon: "😴", query: "I have sleep problems" },
      { label: "Stress & Anxiety", icon: "🧠", query: "I am feeling stressed" },
      { label: "Skin & Beauty", icon: "✨", query: "I want better skin" },
      { label: "Hair Care", icon: "💇", query: "I have hair fall problems" },
      { label: "Weight Management", icon: "⚖️", query: "Help me with weight management" },
      { label: "Joint & Pain", icon: "🦴", query: "I have joint pain" },
      { label: "Focus & Memory", icon: "🎯", query: "I need help with focus and memory" },
      { label: "Respiratory Health", icon: "🌬️", query: "I have breathing problems" },
      { label: "Women's Health", icon: "🌸", query: "Tell me about women's health in Ayurveda" },
    ],
  },
  {
    label: "Product Finder", icon: "🛒",
    children: [
      { label: "Products for Vata", icon: "💨", query: "Recommend products for Vata dosha" },
      { label: "Products for Pitta", icon: "🔥", query: "Recommend products for Pitta dosha" },
      { label: "Products for Kapha", icon: "🌊", query: "Recommend products for Kapha dosha" },
      { label: "Ashwagandha", icon: "🌿", query: "What is Ashwagandha good for?" },
      { label: "Chyawanprash", icon: "🍯", query: "Tell me about Chyawanprash" },
      { label: "Haridra (Turmeric)", icon: "🌿", query: "Tell me about Haridra" },
      { label: "Browse All Products", icon: "📦", query: "Help me find a product" },
    ],
  },
  {
    label: "Diet & Nutrition", icon: "🥗",
    children: [
      { label: "Ayurvedic Eating Rules", icon: "📜", query: "What are the Ayurvedic rules of eating" },
      { label: "Foods to Never Combine", icon: "🚫", query: "What are incompatible food combinations in Ayurveda" },
      { label: "Seasonal Eating Guide", icon: "🍂", query: "Tell me about seasonal eating in Ayurveda" },
      { label: "Fasting Guidelines", icon: "⏳", query: "How should I fast according to Ayurveda" },
    ],
  },
  { label: "What is Ayurveda?", icon: "📚", query: "What is Ayurveda" },
];

const FOLLOWUPS: Record<string, MenuOption[]> = {
  dosha: [
    { label: "Products for this dosha", icon: "🛒", query: "Recommend products for {dosha} dosha" },
    { label: "Take Prakriti Quiz", icon: "📋", action: "prakriti" },
    { label: "Back to Main Menu", icon: "🏠", action: "home" },
  ],
  health: [
    { label: "Take Prakriti Quiz", icon: "📋", action: "prakriti" },
    { label: "Find Products", icon: "🛒", action: "menu:3" },
    { label: "Back to Main Menu", icon: "🏠", action: "home" },
  ],
  product: [
    { label: "Health Topics", icon: "🌿", action: "menu:2" },
    { label: "Take Prakriti Quiz", icon: "📋", action: "prakriti" },
    { label: "Back to Main Menu", icon: "🏠", action: "home" },
  ],
  default: [
    { label: "Take Prakriti Quiz", icon: "📋", action: "prakriti" },
    { label: "Health Concerns", icon: "🌿", action: "menu:2" },
    { label: "Back to Main Menu", icon: "🏠", action: "home" },
  ],
  prakritiResult: [
    { label: "View Products for My Dosha", icon: "🛒", query: "Recommend products for {dosha} dosha" },
    { label: "Health Concerns", icon: "🌿", action: "menu:2" },
    { label: "Back to Main Menu", icon: "🏠", action: "home" },
  ],
};

// ---------------------------------------------------------------------------
// Widget class
// ---------------------------------------------------------------------------
export class Widget {
  private config: WidgetConfig;
  private shadow!: ShadowRoot;
  private container!: HTMLElement;
  private isOpen = false;
  private isBusy = false;
  private sessionId: string;
  private conversationId: string | null;
  private activeStreamController: AbortController | null = null;

  // Quiz state
  private quizIndex = 0;
  private quizAnswers: Record<number, string> = {};

  constructor(config: WidgetConfig) {
    this.config = config;
    this.sessionId = getSessionId();
    this.conversationId = getConversationId();
  }

  mount(): void {
    const host = document.createElement("div");
    host.id = "ageayurveda-widget";
    this.shadow = host.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = widgetStyles;
    this.shadow.appendChild(style);

    this.container = document.createElement("div");
    this.shadow.appendChild(this.container);

    this.render();
    document.body.appendChild(host);
  }

  private render(): void {
    this.container.innerHTML = `
      ${this.renderBubble()}
      ${this.renderWindow()}
    `;
    this.attachBaseEvents();
    this.showMainMenu();
  }

  private renderBubble(): string {
    return `
      <button class="aay-bubble" aria-label="Open chat">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 3C6.5 3 2 6.58 2 11c0 2.34 1.19 4.44 3.07 5.88L4 21l4.45-2.12C9.58 19.28 10.76 19.5 12 19.5c5.5 0 10-3.58 10-8S17.5 3 12 3z"/>
        </svg>
      </button>
    `;
  }

  private renderWindow(): string {
    return `
      <div class="aay-window">
        <div class="aay-header">
          <div class="aay-header-info">
            <div class="aay-header-avatar">🌿</div>
            <div>
              <div class="aay-header-title">Ayurveda Guide</div>
              <div class="aay-header-subtitle">Classical Ayurvedic Wisdom</div>
            </div>
          </div>
          <div class="aay-header-actions">
            <button class="aay-header-btn aay-reset-btn" title="Start a new conversation" aria-label="New conversation">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
                <path d="M3 12a9 9 0 0 1 15-6.7L21 8"/>
                <path d="M21 3v5h-5"/>
                <path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>
                <path d="M3 21v-5h5"/>
              </svg>
            </button>
            <button class="aay-header-btn aay-close-btn" title="Close">✕</button>
          </div>
        </div>
        <div class="aay-messages" id="aay-messages">
          <div class="aay-message assistant">
            Namaste! 🙏 I'm your <strong>Ayurveda Guide</strong>. Choose a topic below to get started.
          </div>
        </div>
        <div class="aay-options" id="aay-options"></div>
        <div class="aay-input-area">
          <input
            type="text"
            class="aay-input"
            id="aay-input"
            placeholder="Ask anything about Ayurveda…"
            maxlength="1000"
            autocomplete="off"
            aria-label="Ask a question"
          />
          <button class="aay-send-btn" id="aay-send-btn" aria-label="Send message" title="Send">
            <svg class="aay-send-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="18" height="18">
              <path d="M22 2L11 13"/>
              <path d="M22 2l-7 20-4-9-9-4 20-7z"/>
            </svg>
            <svg class="aay-stop-icon" viewBox="0 0 24 24" fill="currentColor" width="14" height="14">
              <rect x="6" y="6" width="12" height="12" rx="1.5"/>
            </svg>
          </button>
        </div>
        <div class="aay-footer">Powered by Age Ayurveda</div>
      </div>
    `;
  }

  private attachBaseEvents(): void {
    this.shadow.querySelector(".aay-bubble")?.addEventListener("click", () => this.toggle());
    this.shadow.querySelector(".aay-close-btn")?.addEventListener("click", () => this.toggle());
    this.shadow.querySelector(".aay-reset-btn")?.addEventListener("click", () => this.resetConversation());
    this.attachInputEvents();
  }

  private attachInputEvents(): void {
    const input = this.shadow.querySelector("#aay-input") as HTMLInputElement | null;
    const sendBtn = this.shadow.querySelector("#aay-send-btn") as HTMLButtonElement | null;
    if (!input || !sendBtn) return;

    const submit = () => {
      const value = input.value.trim();
      if (!value || this.isBusy) return;
      input.value = "";
      this.handleFreeTextSubmit(value);
    };

    input.addEventListener("keydown", (e: KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submit();
      }
    });
    sendBtn.addEventListener("click", (e) => {
      e.preventDefault();
      // While streaming, the same button acts as a stop. AbortController
      // cancels the in-flight fetch; the stream handler finalises the
      // partial message.
      if (this.isBusy && this.activeStreamController) {
        this.activeStreamController.abort();
        return;
      }
      submit();
    });
  }

  /**
   * Reset the conversation: abort any in-flight stream, drop the local
   * conversation_id (so the next message starts fresh server-side), clear
   * the transcript, and re-show the main menu. Session id is preserved so
   * the same user keeps their chat history visible in admin tooling.
   */
  private resetConversation(): void {
    if (this.activeStreamController) {
      this.activeStreamController.abort();
      this.activeStreamController = null;
    }
    this.conversationId = null;
    setConversationId(null);
    this.setBusy(false);

    const m = this.shadow.querySelector("#aay-messages") as HTMLElement | null;
    if (m) {
      m.innerHTML = `
        <div class="aay-message assistant">
          New conversation started. 🌿 What would you like to explore?
        </div>
      `;
    }
    this.showMainMenu();
  }

  /**
   * User typed something into the input. Render their message in the
   * transcript, then route through sendQuery (which uses grounded if
   * enabled, rule-based otherwise). Free-text questions usually benefit
   * most from the grounded backend — that's the whole point of having
   * an open-ended input rather than a menu of canned queries.
   */
  private async handleFreeTextSubmit(text: string): Promise<void> {
    this.appendMsg("user", this.escapeHtml(text));
    await this.sendQuery(text);
  }

  private escapeHtml(text: string): string {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  private setInputDisabled(disabled: boolean): void {
    const input = this.shadow.querySelector("#aay-input") as HTMLInputElement | null;
    if (input) input.disabled = disabled;
    // The send button stays enabled while busy — it doubles as the stop
    // button, and the CSS swaps icons based on the input's disabled state.
  }

  private setBusy(busy: boolean): void {
    this.isBusy = busy;
    this.setInputDisabled(busy);
  }

  private toggle(): void {
    this.isOpen = !this.isOpen;
    const win = this.shadow.querySelector(".aay-window") as HTMLElement;
    const bubble = this.shadow.querySelector(".aay-bubble") as HTMLElement;
    if (win) win.classList.toggle("open", this.isOpen);
    if (bubble) bubble.style.display = this.isOpen ? "none" : "flex";
  }

  // -----------------------------------------------------------------------
  // Menu
  // -----------------------------------------------------------------------
  private showMainMenu(): void { this.renderOptions(MENU_TREE); }

  private renderOptions(options: MenuOption[]): void {
    const c = this.shadow.querySelector("#aay-options") as HTMLElement;
    if (!c) return;
    c.innerHTML = options.map((o, i) => `<button class="aay-option-btn" data-idx="${i}">${o.icon} ${o.label}</button>`).join("");
    c.querySelectorAll(".aay-option-btn").forEach((btn) => {
      btn.addEventListener("click", () => this.handleOption(options[parseInt((btn as HTMLElement).dataset.idx || "0", 10)]));
    });
  }

  private async handleOption(opt: MenuOption): Promise<void> {
    if (this.isBusy) return;
    if (opt.children) {
      this.appendMsg("user", `${opt.icon} ${opt.label}`);
      this.appendMsg("assistant", `Choose a topic under <strong>${opt.label}</strong>:`);
      this.renderOptions([...opt.children, { label: "← Back to Main Menu", icon: "", action: "home" }]);
      this.scroll();
      return;
    }
    if (opt.action) { this.handleAction(opt.action); return; }
    if (opt.query) { this.appendMsg("user", `${opt.icon} ${opt.label}`); await this.sendQuery(opt.query); }
  }

  private handleAction(action: string): void {
    if (action === "home") this.showMainMenu();
    else if (action === "prakriti") this.startQuiz();
    else if (action.startsWith("menu:")) {
      const m = MENU_TREE[parseInt(action.split(":")[1], 10)];
      if (m?.children) this.renderOptions([...m.children, { label: "← Back to Main Menu", icon: "", action: "home" }]);
    }
  }

  // -----------------------------------------------------------------------
  // API query — routes to grounded streaming or rule-based depending on config
  // -----------------------------------------------------------------------
  private async sendQuery(query: string): Promise<void> {
    if (this.config.useGroundedChat) {
      await this.sendGroundedQuery(query);
    } else {
      await this.sendRuleBasedQuery(query);
    }
  }

  private async sendRuleBasedQuery(query: string): Promise<void> {
    this.setBusy(true);
    this.renderOptions([]);
    this.showTyping();
    try {
      const result = await sendMessage({ message: query, session_id: this.sessionId, language: "en", conversation_id: this.conversationId || undefined });
      this.hideTyping();
      if (result.conversation_id) { this.conversationId = result.conversation_id; setConversationId(result.conversation_id); }
      this.appendMsg("assistant", this.fmt(result.message));
      if (result.products?.length) this.appendProducts(result.products);
      if (result.disclaimer) this.appendDisclaimer(result.disclaimer);
      this.showFollowups(query);
    } catch {
      this.hideTyping();
      this.appendMsg("assistant", "Sorry, something went wrong. Please try again.");
      this.showMainMenu();
    }
    this.setBusy(false);
  }

  /**
   * Streaming grounded chat. Tokens are appended to a single message bubble
   * as they arrive. The recommendation tool fires server-side and surfaces
   * product cards via a separate SSE event — those render *before* the final
   * text completes streaming, so the user sees a product appear and then the
   * model's prose explanation flow in around it.
   */
  private async sendGroundedQuery(query: string): Promise<void> {
    this.setBusy(true);
    this.renderOptions([]);
    this.showTyping();

    const renderedProductIds = new Set<string>();
    let messageEl: HTMLElement | null = null;
    let accumulated = "";
    let typingHidden = false;

    const ensureMessageEl = (): HTMLElement => {
      if (messageEl) return messageEl;
      if (!typingHidden) {
        this.hideTyping();
        typingHidden = true;
      }
      const m = this.shadow.querySelector("#aay-messages") as HTMLElement;
      const el = document.createElement("div");
      el.className = "aay-message assistant aay-streaming";
      el.innerHTML = "";
      m.appendChild(el);
      messageEl = el;
      this.scroll();
      return el;
    };

    const controller = new AbortController();
    this.activeStreamController = controller;

    try {
      await sendGroundedMessageStream(
        {
          message: query,
          session_id: this.sessionId,
          language: "en",
          conversation_id: this.conversationId || undefined,
          sources: this.config.groundedSources,
        },
        {
          onToken: (token: string) => {
            const el = ensureMessageEl();
            accumulated += token;
            el.innerHTML = this.fmt(accumulated) + '<span class="aay-cursor"></span>';
            this.scroll();
          },
          onToolUse: (data) => {
            if (!data?.products?.length) return;
            if (!typingHidden) {
              this.hideTyping();
              typingHidden = true;
            }
            for (const p of data.products) {
              if (renderedProductIds.has(p.id)) continue;
              renderedProductIds.add(p.id);
              this.appendProductCard(
                p.name,
                p.price,
                p.shopify_url || `https://ageayurveda.com/products/${p.slug}`,
                p.image_url,
                p.why || p.dosha_balance,
              );
            }
          },
          onDone: (data) => {
            if (!typingHidden) {
              this.hideTyping();
              typingHidden = true;
            }
            if (data.conversation_id) {
              this.conversationId = data.conversation_id;
              setConversationId(data.conversation_id);
            }

            const cleanedText = this.stripCitations(accumulated);
            const citationsHtml = this.renderCitationChips(data.citations);

            if (data.aborted) {
              // User-cancelled mid-stream. Keep the partial text, mark it,
              // skip follow-ups and disclaimer (the model never finished).
              if (messageEl) {
                messageEl.classList.remove("aay-streaming");
                messageEl.innerHTML =
                  (cleanedText ? this.fmt(cleanedText) : "<em>Stopped.</em>") +
                  '<div class="aay-stopped-notice">Response stopped.</div>';
              }
              this.showMainMenu();
              return;
            }

            const el = ensureMessageEl();
            el.classList.remove("aay-streaming");
            el.innerHTML = this.fmt(cleanedText) + citationsHtml;

            if (data.disclaimer) this.appendDisclaimer(data.disclaimer);
            this.showFollowups(query);
          },
          onError: (err) => {
            if (!typingHidden) {
              this.hideTyping();
              typingHidden = true;
            }
            if (messageEl) messageEl.classList.remove("aay-streaming");
            this.appendMsg(
              "assistant",
              `Sorry — ${err}. Falling back to the standard guide.`,
            );
            this.showMainMenu();
          },
        },
        controller.signal,
      );
    } catch (e) {
      if (!typingHidden) this.hideTyping();
      this.appendMsg("assistant", "Sorry, something went wrong. Please try again.");
      this.showMainMenu();
    } finally {
      if (this.activeStreamController === controller) {
        this.activeStreamController = null;
      }
    }

    this.setBusy(false);
  }

  /**
   * Replace inline `[Source, Section, Ch.X verse Y]` markers with nothing
   * (we render them as chips below). Done after the stream completes so we
   * preserve the live-typing feel during streaming.
   */
  private stripCitations(text: string): string {
    return text.replace(
      /\[([^\]]*?(?:Samhita|Hridaya|Sangraha|Nidana|Prakasha|Ratnavali|Ratna)[^\]]*?)\]/gi,
      "",
    ).replace(/\s+([.,;:])/g, "$1").replace(/  +/g, " ");
  }

  private renderCitationChips(citations: any[] | undefined): string {
    if (!citations || !citations.length) return "";
    const chips = citations
      .map((c) => {
        const parts = [c.source];
        if (c.chapter) parts.push(c.chapter);
        if (c.verse) parts.push(c.verse);
        const label = parts.filter(Boolean).join(", ");
        return `<span class="aay-citation-chip" title="${label}">📜 ${label}</span>`;
      })
      .join("");
    return `<div class="aay-citations">${chips}</div>`;
  }

  private showFollowups(query: string): void {
    const q = query.toLowerCase();
    let key = "default";
    if (q.includes("vata") || q.includes("pitta") || q.includes("kapha") || q.includes("dosha")) key = "dosha";
    else if (q.includes("product") || q.includes("recommend") || q.includes("ashwagandha") || q.includes("triphala") || q.includes("chyawanprash") || q.includes("find")) key = "product";
    else if (q.includes("digestion") || q.includes("sleep") || q.includes("immun") || q.includes("stress") || q.includes("skin") || q.includes("hair") || q.includes("weight") || q.includes("joint") || q.includes("women") || q.includes("focus") || q.includes("memory") || q.includes("breathing") || q.includes("respiratory") || q.includes("diet") || q.includes("eating") || q.includes("food") || q.includes("fast") || q.includes("season")) key = "health";

    let opts = FOLLOWUPS[key] || FOLLOWUPS["default"];
    if (key === "dosha") {
      let d = "Vata";
      if (q.includes("pitta")) d = "Pitta";
      else if (q.includes("kapha")) d = "Kapha";
      opts = opts.map((o) => ({ ...o, query: o.query?.replace("{dosha}", d) }));
    }
    this.renderOptions(opts);
  }

  // -----------------------------------------------------------------------
  // Prakriti Quiz (fully local)
  // -----------------------------------------------------------------------
  private startQuiz(): void {
    this.appendMsg("user", "📋 Take Prakriti Quiz");
    this.quizIndex = 0;
    this.quizAnswers = {};
    this.appendMsg("assistant",
      `<strong>Prakriti Assessment</strong> — ${QUIZ_QUESTIONS.length} questions<br><br>` +
      "Answer based on your <strong>natural, lifelong tendencies</strong> — not temporary states.<br><br>Let's begin!"
    );
    this.showQuizQuestion();
  }

  private showQuizQuestion(): void {
    const q = QUIZ_QUESTIONS[this.quizIndex];
    if (!q) return;

    const pct = Math.round((this.quizIndex / QUIZ_QUESTIONS.length) * 100);
    this.appendMsg("assistant",
      `<div class="aay-progress"><div class="aay-progress-fill" style="width:${pct}%"></div></div>` +
      `<strong>Question ${this.quizIndex + 1} of ${QUIZ_QUESTIONS.length}</strong><br>${q.q}`
    );

    const c = this.shadow.querySelector("#aay-options") as HTMLElement;
    if (!c) return;
    c.innerHTML = q.opts.map((o, i) => `<button class="aay-option-btn aay-quiz-opt" data-idx="${i}">${o.l}</button>`).join("");
    c.querySelectorAll(".aay-quiz-opt").forEach((btn) => {
      btn.addEventListener("click", () => {
        const i = parseInt((btn as HTMLElement).dataset.idx || "0", 10);
        this.appendMsg("user", q.opts[i].l);
        this.quizAnswers[q.id] = q.opts[i].d;
        this.quizIndex++;
        if (this.quizIndex < QUIZ_QUESTIONS.length) this.showQuizQuestion();
        else this.showQuizResult();
      });
    });
    this.scroll();
  }

  private showQuizResult(): void {
    this.renderOptions([]);

    // Score
    const scores = { vata: 0, pitta: 0, kapha: 0 };
    for (const d of Object.values(this.quizAnswers)) scores[d as keyof typeof scores]++;
    const total = scores.vata + scores.pitta + scores.kapha || 1;
    const pcts = { vata: (scores.vata / total) * 100, pitta: (scores.pitta / total) * 100, kapha: (scores.kapha / total) * 100 };

    const sorted = Object.entries(scores).sort((a, b) => b[1] - a[1]);
    const top = sorted[0], second = sorted[1], third = sorted[2];
    let constitution: string;
    if (pcts[top[0] as keyof typeof pcts] - pcts[second[0] as keyof typeof pcts] <= 15) {
      if (pcts[second[0] as keyof typeof pcts] - pcts[third[0] as keyof typeof pcts] <= 10) {
        constitution = "tridosha";
      } else {
        const pair = [top[0], second[0]].sort();
        constitution = `${pair[0]}-${pair[1]}`;
      }
    } else {
      constitution = top[0];
    }

    const vP = Math.round(pcts.vata), pP = Math.round(pcts.pitta), kP = Math.round(pcts.kapha);
    const primary = constitution.split("-")[0];

    let html = `<strong>Your Prakriti: ${constitution.charAt(0).toUpperCase() + constitution.slice(1)}</strong><br><br>`;
    html += `<div class="aay-dosha-bars">`;
    html += `<div class="aay-dosha-row"><span>Vata</span><div class="aay-bar"><div class="aay-bar-fill aay-vata" style="width:${vP}%"></div></div><span>${vP}%</span></div>`;
    html += `<div class="aay-dosha-row"><span>Pitta</span><div class="aay-bar"><div class="aay-bar-fill aay-pitta" style="width:${pP}%"></div></div><span>${pP}%</span></div>`;
    html += `<div class="aay-dosha-row"><span>Kapha</span><div class="aay-bar"><div class="aay-bar-fill aay-kapha" style="width:${kP}%"></div></div><span>${kP}%</span></div>`;
    html += `</div><br>`;

    html += (DOSHA_DESC[constitution] || DOSHA_DESC[primary] || "") + "<br><br>";

    const dietDos = DOSHA_DIET_DOS[primary] || [];
    const dietDonts = DOSHA_DIET_DONTS[primary] || [];
    if (dietDos.length) {
      html += `<strong>Diet — Do's:</strong><br>` + dietDos.map((d) => `✅ ${d}`).join("<br>") + "<br><br>";
    }
    if (dietDonts.length) {
      html += `<strong>Diet — Don'ts:</strong><br>` + dietDonts.map((d) => `🚫 ${d}`).join("<br>") + "<br><br>";
    }

    const lifeDos = DOSHA_LIFESTYLE_DOS[primary] || [];
    const lifeDonts = DOSHA_LIFESTYLE_DONTS[primary] || [];
    if (lifeDos.length) {
      html += `<strong>Lifestyle — Do's:</strong><br>` + lifeDos.map((l) => `✅ ${l}`).join("<br>") + "<br><br>";
    }
    if (lifeDonts.length) {
      html += `<strong>Lifestyle — Don'ts:</strong><br>` + lifeDonts.map((l) => `🚫 ${l}`).join("<br>") + "<br><br>";
    }

    const prods = DOSHA_PRODUCTS[primary] || [];
    if (prods.length) {
      html += `<strong>Recommended Products:</strong><br>` + prods.map((p) => `• <strong>${p.name}</strong>`).join("<br>");
    }

    this.appendMsg("assistant", html);

    // Product cards
    for (const p of prods) {
      this.appendProductCard(p.name, p.price, `https://ageayurveda.com/products/${p.slug}`, p.img, p.balance);
    }

    const dosha = primary.charAt(0).toUpperCase() + primary.slice(1);
    const followups = FOLLOWUPS["prakritiResult"].map((o) => ({ ...o, query: o.query?.replace("{dosha}", dosha) }));
    this.renderOptions(followups);
  }

  // -----------------------------------------------------------------------
  // DOM helpers
  // -----------------------------------------------------------------------
  private appendMsg(role: string, content: string): void {
    const m = this.shadow.querySelector("#aay-messages") as HTMLElement;
    if (!m) return;
    const el = document.createElement("div");
    el.className = `aay-message ${role}`;
    el.innerHTML = content;
    m.appendChild(el);
    this.scroll();
  }

  private appendProducts(products: any[]): void {
    for (const p of products) this.appendProductCard(p.name, p.price, p.shopify_url, p.image_url, p.dosha_balance);
  }

  private appendProductCard(name: string, price: number, url: string, imageUrl?: string, doshaBalance?: string): void {
    const m = this.shadow.querySelector("#aay-messages") as HTMLElement;
    if (!m) return;
    const card = document.createElement("div");
    card.className = "aay-product-card";
    const imgSrc = imageUrl && imageUrl.startsWith("http") ? imageUrl : "";
    card.innerHTML = `
      <a href="${url}" target="_blank" rel="noopener" class="aay-product-img-link">
        ${imgSrc
          ? `<img class="aay-product-img" src="${imgSrc}" alt="${name}" loading="lazy">`
          : `<div class="aay-product-img aay-product-img-placeholder">🌿</div>`}
      </a>
      <div class="aay-product-info">
        <a href="${url}" target="_blank" rel="noopener" class="aay-product-name-link">${name}</a>
        ${doshaBalance ? `<div class="aay-product-balance">${doshaBalance}</div>` : ""}
      </div>
      <a href="${url}" target="_blank" rel="noopener" class="aay-product-btn">Buy Now</a>
    `;
    m.appendChild(card);
    this.scroll();
  }

  private appendDisclaimer(text: string): void {
    const m = this.shadow.querySelector("#aay-messages") as HTMLElement;
    if (!m) return;
    const el = document.createElement("div");
    el.className = "aay-disclaimer";
    el.innerHTML = `⚠️ ${text}`;
    m.appendChild(el);
    this.scroll();
  }

  private showTyping(): void {
    const m = this.shadow.querySelector("#aay-messages") as HTMLElement;
    if (!m) return;
    const t = document.createElement("div");
    t.className = "aay-typing"; t.id = "aay-typing";
    t.innerHTML = `<div class="aay-typing-dot"></div><div class="aay-typing-dot"></div><div class="aay-typing-dot"></div>`;
    m.appendChild(t);
    this.scroll();
  }

  private hideTyping(): void { this.shadow.querySelector("#aay-typing")?.remove(); }

  private scroll(): void {
    const m = this.shadow.querySelector("#aay-messages") as HTMLElement;
    if (m) m.scrollTop = m.scrollHeight;
  }

  private fmt(text: string): string {
    return text
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/\n/g, "<br>");
  }

  destroy(): void { document.getElementById("ageayurveda-widget")?.remove(); }
}
