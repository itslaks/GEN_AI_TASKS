import {
  consumeStream,
  convertToModelMessages,
  streamText,
  UIMessage,
  tool,
  stepCountIs,
} from 'ai'
import { createOpenAI } from '@ai-sdk/openai'
import { createGroq } from '@ai-sdk/groq'
import { z } from 'zod'

export const maxDuration = 60

const openaiProvider = createOpenAI({ apiKey: process.env.OPENAI_API_KEY })
const groqProvider = createGroq({ apiKey: process.env.GROQ_API_KEY })

function getModel() {
  if (process.env.OPENAI_API_KEY?.startsWith('sk-')) {
    return openaiProvider('gpt-4o')
  }
  if (process.env.GROQ_API_KEY) {
    return groqProvider('llama-3.1-8b-instant')
  }
  throw new Error('No AI provider configured. Set OPENAI_API_KEY or GROQ_API_KEY in .env.local')
}

const SYSTEM_PROMPT = `You are VedaKrishi AI — an expert agricultural assistant for Indian farmers combining Vedic wisdom with modern science.

EXPERTISE: Crop management (rice, wheat, cotton, pulses, vegetables, spices), pest/disease control, soil health, irrigation, monsoon planning, government schemes (PM-KISAN, PMFBY, KCC), MSP/market prices, organic farming, image analysis.

LANGUAGE RULES:
- Respond in the SAME LANGUAGE the user writes in.
- Supported: English (en), Hindi (hi), Tamil (ta), Telugu (te), Kannada (kn), Malayalam (ml), Bengali (bn), Marathi (mr), Gujarati (gu), Punjabi (pa), Odia (or), Assamese (as), German (de), French (fr), Spanish (es).
- IMPORTANT: When a user mentions their LOCATION (state, district, country), ALWAYS provide the response in BOTH English AND the regional language of that location. Mapping:
  * Tamil Nadu/Pondicherry -> Tamil | Andhra Pradesh/Telangana -> Telugu | Karnataka -> Kannada
  * Kerala -> Malayalam | West Bengal/Bangladesh -> Bengali | Maharashtra -> Marathi
  * Gujarat -> Gujarati | Punjab/Haryana -> Punjabi | Odisha -> Odia | Assam/Northeast -> Assamese
  * Rajasthan/UP/MP/Bihar/Jharkhand/Delhi/Uttarakhand/HP -> Hindi
  * Germany/Austria/Switzerland -> German | France/Belgium -> French | Spain/Mexico/Latin America -> Spanish
  * All other Indian states -> Hindi as default
  Format bilingual: [English content]\n\n---\n\n[Regional content]

RESPONSE STYLE:
- Concise, practical, actionable advice with bullet points and numbered steps
- Include timings, costs (INR), safety warnings, emojis: 🌾🌱💧☀️🐛🧪
- Suggest local KVK centre for region-specific advice
- Always mention safety gear for pesticides

TOOLS: Use tools for weather, crop schedules, government schemes, pest problems, market prices, soil questions.

FUTURE: Live video field analysis coming soon!`

const tools = {
  getWeatherInfo: tool({
    description: 'Get weather data for farming decisions. Call when farmer asks about weather, rain, temperature, spray timing, or planting conditions.',
    inputSchema: z.object({
      location: z.string().describe('District or city name'),
      state: z.string().describe('Indian state name'),
    }),
    async *execute({ location, state }) {
      yield { state: 'loading' as const, message: 'Fetching weather data...' }
      const conditions = ['Clear', 'Partly Cloudy', 'Cloudy', 'Light Rain', 'Heavy Rain']
      const condition = conditions[Math.floor(Math.random() * conditions.length)]
      const temp = Math.floor(Math.random() * 15) + 25
      const humidity = Math.floor(Math.random() * 40) + 50
      const rainfall = Math.floor(Math.random() * 100)
      yield {
        state: 'ready' as const,
        location: `${location}, ${state}`,
        temperature: temp,
        humidity,
        condition,
        rainfall_probability: rainfall,
        wind_speed: Math.floor(Math.random() * 20) + 5,
        farming_advisory: condition.includes('Rain')
          ? 'Good for sowing. Avoid pesticide spraying. Ensure drainage.'
          : 'Ensure irrigation. Good conditions for field work.',
        forecast_3day: `Day 1: ${temp}C | Day 2: ${temp + 2}C | Day 3: ${temp - 1}C`,
      }
    },
  }),

  getCropCalendar: tool({
    description: 'Get crop calendar. Call when farmer asks about planting time, growing stages, or harvest planning.',
    inputSchema: z.object({
      crop: z.string().describe('Crop name'),
      season: z.string().describe('Season: Kharif, Rabi, or Zaid'),
      region: z.string().optional().describe('State or region'),
    }),
    async *execute({ crop, season, region }) {
      yield { state: 'loading' as const, message: 'Loading crop calendar...' }
      const sowingMap: Record<string, string> = { Kharif: 'June-July', Rabi: 'Oct-Nov', Zaid: 'Mar-Apr' }
      const harvestMap: Record<string, string> = { Kharif: 'Oct-Nov', Rabi: 'Mar-Apr', Zaid: 'Jun-Jul' }
      yield {
        state: 'ready' as const,
        crop, season, region: region || 'Pan India',
        sowing_period: sowingMap[season] || 'June-July',
        harvesting_period: harvestMap[season] || 'Oct-Nov',
        growing_duration: '90-120 days',
        activities: [
          { phase: 'Land Prep', timing: 'Week 1-2', task: 'Ploughing, levelling, soil testing' },
          { phase: 'Sowing', timing: 'Week 3-4', task: 'Seed treatment and sowing at recommended spacing' },
          { phase: 'Vegetative', timing: 'Week 5-8', task: 'Irrigation, weeding, first fertiliser dose' },
          { phase: 'Flowering', timing: 'Week 9-12', task: 'Pest monitoring, second fertiliser dose' },
          { phase: 'Harvest', timing: 'Week 14-16', task: 'Harvest at optimal moisture, proper storage' },
        ],
        tips: `For ${crop} in ${season}: treat seeds before sowing, maintain spacing, monitor weather during flowering.`,
      }
    },
  }),

  getSchemeInfo: tool({
    description: 'Get government scheme details. Call when farmer asks about PM-KISAN, crop insurance, KCC, subsidies, or government agricultural support.',
    inputSchema: z.object({
      schemeName: z.string().describe('Scheme name: PM-KISAN, PMFBY, KCC, soil health card, subsidy'),
    }),
    async *execute({ schemeName }) {
      yield { state: 'loading' as const, message: 'Fetching scheme details...' }
      const key = schemeName.toLowerCase().replace(/[\s\-_]/g, '').replace(/[^a-z]/g, '')
      const schemes: Record<string, {
        name: string; benefit: string; eligibility: string;
        howToApply: string; documents: string; helpline: string
      }> = {
        pmkisan: {
          name: 'PM-KISAN Samman Nidhi',
          benefit: 'Rs.6,000/year in 3 instalments of Rs.2,000',
          eligibility: 'All landholding farmer families',
          howToApply: 'Online at pmkisan.gov.in or nearest CSC centre',
          documents: 'Aadhaar, Bank account, Land records',
          helpline: '155261 / 011-24300606',
        },
        pmfby: {
          name: 'PM Fasal Bima Yojana (Crop Insurance)',
          benefit: 'Insurance at 2% (Kharif), 1.5% (Rabi), 5% (Commercial)',
          eligibility: 'All farmers growing notified crops',
          howToApply: 'Bank, CSC, or pmfby.gov.in before sowing deadline',
          documents: 'Aadhaar, Bank, Land records, Sowing certificate',
          helpline: '1800-180-1551',
        },
        kcc: {
          name: 'Kisan Credit Card',
          benefit: 'Credit up to Rs.3 lakh at 4% interest p.a.',
          eligibility: 'All farmers, sharecroppers, tenant farmers, SHGs',
          howToApply: 'Any bank branch or PM-KISAN portal',
          documents: 'Aadhaar, PAN, Land records, Passport photo',
          helpline: 'Nearest bank branch',
        },
        soilhealth: {
          name: 'Soil Health Card Scheme',
          benefit: 'Free soil testing and fertiliser recommendations every 2 years',
          eligibility: 'All farmers across India',
          howToApply: 'Nearest KVK, Agriculture Office, or soilhealth.dac.gov.in',
          documents: 'Aadhaar, Land details',
          helpline: '1800-180-1551',
        },
      }
      const matchedKey = Object.keys(schemes).find(k => key.includes(k) || k.includes(key.slice(0, 5)))
      const scheme = schemes[matchedKey || 'pmkisan']
      yield { state: 'ready' as const, ...scheme }
    },
  }),

  getPestSolution: tool({
    description: 'Identify pest/disease and get control measures. Call when farmer reports crop problems, yellowing, spots, wilting, holes, or unusual growth.',
    inputSchema: z.object({
      crop: z.string().describe('Affected crop name'),
      symptoms: z.string().describe('Visible symptoms: yellowing, spots, wilting, holes, stunted growth, etc.'),
    }),
    async *execute({ crop, symptoms }) {
      yield { state: 'loading' as const, message: 'Analysing symptoms...' }
      yield {
        state: 'ready' as const,
        crop, symptoms_reported: symptoms,
        possible_issue: `Likely fungal infection or pest attack in ${crop} based on described symptoms`,
        severity: 'Moderate',
        organic_solution: 'Neem oil (5ml/L water), Trichoderma viride, or garlic-chilli extract spray',
        chemical_solution: 'Mancozeb or Carbendazim (fungal); consult local KVK for exact dose',
        prevention: 'Proper spacing, good drainage, crop rotation, use resistant varieties',
        safety_note: 'Wear gloves, mask and goggles. Keep children and animals away during spraying.',
        when_to_apply: 'Early morning or evening. Never during rain or wind.',
        cost_estimate: 'Neem oil: Rs.200-400/L | Chemical fungicide: Rs.300-600/kg',
      }
    },
  }),

  getMarketPrice: tool({
    description: 'Get MSP and market/mandi prices. Call when farmer asks about selling price, MSP, mandi rates, or best time to sell.',
    inputSchema: z.object({
      crop: z.string().describe('Crop or produce name'),
      marketState: z.string().optional().describe('State for local mandi prices'),
    }),
    async *execute({ crop, marketState }) {
      yield { state: 'loading' as const, message: 'Fetching market prices...' }
      const baseMSP = Math.floor(Math.random() * 3000) + 1500
      const marketPrice = baseMSP + Math.floor(Math.random() * 800) - 200
      yield {
        state: 'ready' as const,
        crop,
        market_state: marketState || 'India Average',
        msp: `Rs.${baseMSP}/quintal`,
        market_price: `Rs.${marketPrice}/quintal`,
        price_trend: marketPrice > baseMSP ? 'Above MSP' : 'Below MSP',
        best_time_to_sell: '2-3 weeks after harvest when market supply stabilises',
        storage_tip: 'Dry, ventilated area. Moisture-proof containers. Regular pest checks.',
        nearby_mandis: 'Check enam.gov.in for live prices at nearest e-NAM mandi',
      }
    },
  }),

  getSoilRecommendation: tool({
    description: 'Get soil health and fertiliser recommendations. Call when farmer asks about fertilisers, soil improvement, nutrient deficiency, or soil type.',
    inputSchema: z.object({
      soilType: z.string().describe('Soil type: clay, sandy, loamy, black cotton, red laterite, alluvial'),
      crop: z.string().describe('Crop to be grown'),
      issue: z.string().optional().describe('Specific problem: salinity, acidity, waterlogging, low fertility'),
    }),
    async *execute({ soilType, crop, issue }) {
      yield { state: 'loading' as const, message: 'Analysing soil needs...' }
      yield {
        state: 'ready' as const,
        soil_type: soilType, crop, issue: issue || 'General improvement',
        nitrogen: `${Math.floor(Math.random() * 40) + 80} kg/ha`,
        phosphorus: `${Math.floor(Math.random() * 20) + 40} kg/ha`,
        potassium: `${Math.floor(Math.random() * 20) + 30} kg/ha`,
        ph_recommendation: '6.0-7.5 (optimal for most crops)',
        organic_matter: '5-10 tonnes FYM or compost per hectare',
        organic_option: 'Vermicompost (2-3 t/ha) + Jeevamrit (200L/acre/month)',
        chemical_option: 'Urea + DAP + MOP per soil test report',
        green_manure: 'Grow dhaincha or sun hemp before main crop',
        improvement_tip: `For ${soilType} soil with ${crop}: improve organic matter and ensure proper drainage`,
      }
    },
  }),
}

// Pre-written greetings per language — returned instantly without AI call
const INIT_GREETINGS: Record<string, string> = {
  en: "Hello! I'm VedaKrishi AI - your intelligent farming companion. I can help with crop selection, pest control, weather, government schemes, market prices, and more. What can I help you with today?",
  hi: "Namaste! Main VedaKrishi AI hoon - aapka krishi sahayak. Fasal, keet niyantran, mausam, sarkari yojanaen, bazar bhav - sab mein madad kar sakta hoon. Aaj kya jaanna chahte hain?",
  ta: "Vanakkam! Naan VedaKrishi AI - ungal vivasaya uthaiyalar. Payir, poocci, vaanikkai, arasaangat tiTTangkaL, sandai vilaikaL parri udavuven. Inru enna udhavi vendum?",
  te: "Namaskaram! Nenu VedaKrishi AI - mee vyavasaya sahayakudu. Pantalu, keeta niyantrana, vataavarana, praabhutva pathakalu, market dharalu anni vishayalalo sahayam chestanu. Nedu meeku emi kaavali?",
  kn: "Namaskara! Naanu VedaKrishi AI - nimma krushi sahayaka. Bele, keeta niyantrana, havamana, sarkari yojane, marukatte belegalalli sahaaya maaduttene. Indu yaava sahaaya beku?",
  ml: "Namaskaram! Njaan VedaKrishi AI - ningalude krishi sahaayi. Vila, keetaniyantrana, kaalavastsha, sarkkaar padhdditikal, vilakale enival vishayangalil sahaayikkum. Innu enthu chodyam?",
  bn: "Namaskar! Ami VedaKrishi AI - aapnar krishii sahayak. Fashal, keetapatanga, aabahawa, sarkari prokalpa o bazaar mulye sahaaya korte paari. Aaj kii janate chaahan?",
  mr: "Namaskar! Mi VedaKrishi AI - tumcha sheti sahayak. Pik, keed, havaman, sarkari yojana ani baazarabhav yaansaathi madad karto. Aaj kay janun ghyaayache aahe?",
  gu: "Namaskar! Hoon VedaKrishi AI - taamaaro krishi sahayak. Paak, jaakhat, havamaan, sarkaari yojanao ane bazar kinmato vishe madad karee shakoon. Aaj shu jaanvu chhe?",
  pa: "Sat Sri Akal! Main VedaKrishi AI haan - tuhada kheti saathi. Fasal, keede, mausam, sarkari yojnaan te bazar bhav baare madad kar sakda haan. Aaj ki puchna hai?",
  de: "Hallo! Ich bin VedaKrishi AI - Ihr landwirtschaftlicher Assistent. Ich helfe bei Kulturen, Schaedlingsbekaempfung, Wetter und Foerderprogrammen. Wie kann ich Ihnen helfen?",
  fr: "Bonjour! Je suis VedaKrishi AI - votre assistant agricole. Je vous aide avec les cultures, les ravageurs, la meteo et les subventions. Comment puis-je vous aider?",
  es: "Hola! Soy VedaKrishi AI - su asistente agricola inteligente. Puedo ayudar con cultivos, plagas, clima y programas de apoyo. En que le puedo ayudar hoy?",
}

export async function POST(req: Request) {
  try {
    // Parse raw body — we check for initLang before touching UIMessage types
    const body = await req.json() as {
      messages?: UIMessage[]
      language?: string
      initLang?: string
    }
    const { messages = [], language = 'en', initLang } = body

    // ── INIT: Return greeting instantly, zero tokens ──────────────────────────
    if (initLang) {
      const greeting = INIT_GREETINGS[initLang] ?? INIT_GREETINGS.en
      const escaped = greeting
        .replace(/\\/g, '\\\\')
        .replace(/"/g, '\\"')
        .replace(/\r?\n/g, '\\n')

      const streamBody = [
        `0:"${escaped}"`,
        `e:{"finishReason":"stop","usage":{"promptTokens":0,"completionTokens":0},"isContinued":false}`,
        `d:{"finishReason":"stop","usage":{"promptTokens":0,"completionTokens":0}}`,
        '',
      ].join('\n')

      return new Response(streamBody, {
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'X-Vercel-AI-Data-Stream': 'v1',
        },
      })
    }

    // ── NORMAL CHAT ────────────────────────────────────────────────────────────
    const languageContext = language !== 'en'
      ? `\n\nUSER LANGUAGE: ${language}. Respond in this language unless a location triggers bilingual response.`
      : ''

    const model = getModel()

    const result = streamText({
      model,
      system: SYSTEM_PROMPT + languageContext,
      messages: await convertToModelMessages(messages),
      tools,
      stopWhen: stepCountIs(5),
      abortSignal: req.signal,
    })

    return result.toUIMessageStreamResponse({
      originalMessages: messages,
      onFinish: async ({ isAborted }) => { if (isAborted) return },
      consumeSseStream: consumeStream,
    })
  } catch (error: any) {
    console.error('Chat API error:', error)
    return new Response(
      JSON.stringify({ error: error.message || 'AI service unavailable' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    )
  }
}
