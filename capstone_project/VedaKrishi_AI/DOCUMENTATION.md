# VedaKrishi AI — Complete Project Documentation
## A to Z Technical & Functional Guide

---

## TABLE OF CONTENTS

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [Solution Architecture](#3-solution-architecture)
4. [Why VedaKrishi is Different](#4-why-vedakrishi-is-different)
5. [Tech Stack Deep Dive](#5-tech-stack-deep-dive)
6. [Feature Documentation](#6-feature-documentation)
7. [API Reference](#7-api-reference)
8. [Component Guide](#8-component-guide)
9. [AI Model Strategy](#9-ai-model-strategy)
10. [Token Efficiency Guide](#10-token-efficiency-guide)
11. [Deployment Guide](#11-deployment-guide)
12. [Troubleshooting](#12-troubleshooting)
13. [Roadmap](#13-roadmap)

---

## 1. PROJECT OVERVIEW

**VedaKrishi AI** is a full-stack Next.js web application that serves as an AI-powered agricultural assistant for Indian farmers. It combines:

- **Ancient Vedic agricultural wisdom** — traditional farming knowledge passed down for generations
- **Modern AI capabilities** — GPT-4o, Whisper, TTS, and Vision APIs
- **Multilingual accessibility** — 12 Indian regional languages with voice support
- **Rich visual data** — 6 types of infographic cards for data visualization

**Mission:** Bridge the agricultural knowledge gap in rural India by providing every farmer with instant, expert-level guidance — in their own language, available 24/7.

**Target Users:**
- Small & marginal farmers (< 2 hectares)
- Agricultural extension workers
- Farming cooperatives
- Agri-students and researchers

---

## 2. PROBLEM STATEMENT

### 2.1 The Agricultural Knowledge Gap

India is home to 140 million+ farming households. Despite being the backbone of the economy, Indian farmers face severe information asymmetry:

**Access Issues:**
- Krishi Vigyan Kendra (KVK) reaches only 5-10% of farmers annually
- Private agricultural consultants charge ₹500-2000 per visit
- Government advisory is slow, often arriving after the crop damage has occurred
- Internet agricultural content is predominantly in English

**Language Barrier:**
- 65% of farmers are comfortable ONLY in their regional language
- Agricultural advice in Tamil, Telugu, Kannada, Malayalam, Bengali etc. is extremely scarce
- Voice is the primary communication mode in rural areas, not text typing

**Information Silos:**
- Pest/disease identification requires physical expert visit or lab testing
- Government scheme awareness is low — crores of rupees go unclaimed yearly
- Market price information is opaque, leaving farmers vulnerable to middlemen
- Weather-based farming decisions require agricultural expertise most farmers lack

**Financial Impact:**
- 30-40% of crop losses in India are due to preventable pest/disease
- Farmers receive 40-60% less than fair market price due to information gaps
- Billions in government agricultural benefits remain unclaimed due to low awareness

### 2.2 Technology Solutions — The Gap

Existing solutions fail farmers because:

| Solution | Failure Mode |
|----------|-------------|
| Agricultural websites | English-only, not conversational |
| Government apps | Poor UX, no AI, not multilingual |
| WhatsApp groups | Unverified information, slow |
| SMS services | No images, very limited |
| Private consultants | Expensive, unavailable 24/7 |

---

## 3. SOLUTION ARCHITECTURE

### 3.1 System Flow

```
Farmer Input (Text/Voice/Image)
         │
         ▼
    Next.js Frontend
    ┌─────────────────────────────────────┐
    │  Chat UI + Language Selector        │
    │  Voice Recording (MediaRecorder)    │
    │  Image Upload (File API)            │
    └──────────┬──────────────────────────┘
               │
    ┌──────────▼──────────────────────────┐
    │       API Routes (Next.js)          │
    │                                     │
    │  /api/chat          ──► AI Streaming│
    │  /api/speech-to-text ──► Whisper    │
    │  /api/text-to-speech ──► TTS-1      │
    │  /api/analyze-image  ──► Vision     │
    └──────────┬──────────────────────────┘
               │
    ┌──────────▼──────────────────────────┐
    │         AI Layer                    │
    │                                     │
    │  Primary: OpenAI GPT-4o             │
    │  Fallback: Groq llama-3.1-8b-instant│
    │                                     │
    │  Tools: 6 agricultural tools        │
    │  System Prompt: Agriculture expert  │
    └──────────┬──────────────────────────┘
               │
    ┌──────────▼──────────────────────────┐
    │       Response to Farmer            │
    │                                     │
    │  Text: Streamed markdown response   │
    │  Tools: Infographic cards auto-shown│
    │  Voice: Optional TTS playback       │
    └─────────────────────────────────────┘
```

### 3.2 Streaming Architecture

The chat uses **Vercel AI SDK v5** with:
- `streamText` for real-time streaming responses
- `UIMessage` format for structured message state
- `DefaultChatTransport` for HTTP streaming
- `tool()` with async generator (`yield`) for tool execution states
- `stepCountIs(5)` to prevent infinite tool loops

---

## 4. WHY VEDAKRISHI IS DIFFERENT

### 4.1 Technical Differentiators

**1. True Multilingual AI (Not Just Translation)**
- AI responds in the SAME language the user types — no translation needed
- Voice input and output in regional languages via Whisper + TTS
- Language-aware UI — placeholders, greetings, labels all change per selected language

**2. Agricultural Tool Suite with Infographics**
- 6 purpose-built tools that trigger automatically based on conversation context
- Each tool produces a visual infographic card (not just text)
- Cards include: weather gauges, crop timelines, scheme details, pest comparison charts, price trends, NPK soil graphs

**3. Image Analysis for Crop Disease**
- GPT-4o Vision API analyzes photos directly
- Identifies diseases, pests, nutrient deficiencies from images
- Provides both organic AND chemical treatment paths
- Live video field analysis coming soon (WebRTC planned)

**4. Dual AI Model with Instant Fallback**
- OpenAI GPT-4o as primary (best accuracy)
- Groq llama-3.1-8b-instant as fallback (10x faster, cheaper)
- Automatic switch — zero user impact if primary fails

**5. Transparent Workflow UX**
- Shows processing steps: Understanding → Searching → Analyzing → Generating
- Tool-specific loading indicators
- Streaming response so farmers see answers building in real-time

### 4.2 Impact Differentiators

- **Free & accessible** — runs on any smartphone with internet
- **Voice-first design** — farmers who can't type can speak
- **Locally relevant** — traditional crop names, Vedic methods respected alongside modern science
- **Safety-conscious** — always warns about pesticide safety, encourages organic alternatives first
- **Government-aware** — automatically surfaces relevant welfare schemes

---

## 5. TECH STACK DEEP DIVE

### 5.1 Frontend

**Next.js 16 (App Router)**
- Server and client components
- API routes for backend logic
- File-based routing
- Built-in optimization (images, fonts, bundling)

**React 19**
- Latest concurrent features
- `useChat` hook from Vercel AI SDK
- `useState`, `useEffect`, `useRef`, `useCallback`

**Tailwind CSS v4**
- Utility-first styling
- Custom animations in `globals.css`
- Dark mode support
- Premium nature/earth color palette

**Lucide React**
- Consistent icon library
- Tree-shakeable imports

**react-markdown**
- Renders AI markdown responses as formatted HTML
- Custom component overrides for styling

### 5.2 Backend

**Next.js API Routes (App Router)**
- Edge-compatible route handlers
- `export const maxDuration = 60` for streaming support
- FormData parsing for file uploads

**Vercel AI SDK v5**
```typescript
import { streamText, tool, UIMessage, convertToModelMessages, stepCountIs } from 'ai'
import { createOpenAI } from '@ai-sdk/openai'
import { createGroq } from '@ai-sdk/groq'
```
- `streamText` — streaming chat with tool support
- `tool()` with Zod schema validation
- `UIMessage` — structured message format
- `convertToModelMessages` — converts UI messages to model format
- `stepCountIs(5)` — prevents runaway tool loops

**Zod**
- Runtime schema validation for tool inputs
- Type inference for TypeScript

### 5.3 AI Models & APIs

| Model | Provider | Usage | Cost |
|-------|----------|-------|------|
| GPT-4o | OpenAI | Primary chat + reasoning | ~$5/M tokens |
| GPT-4o Vision | OpenAI | Image analysis | ~$5/M tokens |
| Whisper-1 | OpenAI | Speech to text | $0.006/min |
| TTS-1 | OpenAI | Text to speech | $15/M chars |
| llama-3.1-8b-instant | Groq | Fallback chat | ~$0.05/M tokens |

---

## 6. FEATURE DOCUMENTATION

### 6.1 Text Chat

**How it works:**
1. User types a question in any language
2. Frontend sends message via `sendMessage({ text })`
3. `DefaultChatTransport` posts to `/api/chat` with language context
4. GPT-4o streams response with potential tool calls
5. Infographic cards auto-render for tool results
6. User can copy any AI response to clipboard

**Token optimization:**
- System prompt: ~250 tokens (compact but comprehensive)
- Response cap: `maxTokens: 1024` per reply
- Tool results are structured data, not free-form text (saves tokens)
- `stopWhen: stepCountIs(5)` limits tool execution chains

### 6.2 Voice Input (Speech-to-Text)

**Flow:**
1. User clicks microphone button → browser asks for permission
2. `MediaRecorder` captures audio at 16kHz with echo cancellation
3. Audio collected in 100ms chunks
4. On stop → Blob assembled and sent to `/api/speech-to-text`
5. Whisper-1 transcribes with language hint
6. Transcribed text auto-fills the input field

**Technical details:**
```typescript
// useVoiceRecording hook
const mediaRecorder = new MediaRecorder(stream, {
  mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4',
})
mediaRecorder.start(100) // 100ms chunks
```

**Language support:** All 12 languages with Whisper language codes passed for accuracy.

### 6.3 Voice Output (Text-to-Speech)

**Flow:**
1. User clicks "Listen" on any AI response
2. `useTextToSpeech` hook sends text to `/api/text-to-speech`
3. OpenAI TTS-1 generates MP3 at 0.95x speed (clearer pronunciation)
4. Audio returned as `audio/mpeg` binary
5. Browser plays via Web Audio API
6. Stop button available during playback

**Text limit:** 4000 characters (OpenAI TTS limit is 4096)

### 6.4 Image Analysis

**Flow:**
1. User clicks camera icon → file picker opens (accepts jpg/png/webp/gif)
2. Image previewed before sending
3. On submit → `FormData` sent to `/api/analyze-image`
4. Backend:
   - Reads file as `Blob`
   - Converts to base64
   - Sends to GPT-4o Vision with agricultural analysis prompt
5. Analysis returned as markdown
6. `ImageAnalysisMessage` component renders with:
   - Image preview
   - Formatted analysis
   - TTS listen button
   - Copy button
   - "Live Video Coming Soon" badge

**Analysis output includes:**
- Identification (crop/pest/disease/soil)
- Health assessment (Healthy / Mild / Moderate / Severe)
- Specific diagnosis
- Organic + chemical treatment options
- Prevention advice
- Urgency level

### 6.5 Infographic Cards

All 6 cards auto-trigger when AI calls the corresponding tool:

**Weather Card** (`getWeatherInfo`)
- Gradient sky background
- Temperature display
- Humidity/Rainfall/Wind gauges (animated fill bars)
- 3-day forecast
- Farming advisory banner

**Crop Calendar** (`getCropCalendar`)
- Phase timeline with color-coded dots
- Sowing/Duration/Harvest grid
- Activity list with timing badges
- Farming tips

**Government Scheme** (`getSchemeInfo`)
- Amber gradient header
- Benefit amount highlighted in green
- Eligibility, How-to-Apply, Documents rows
- Helpline number prominently displayed

**Pest Solution** (`getPestSolution`)
- Severity badge (Low/Moderate/High/Severe)
- Side-by-side Organic vs Chemical options
- Prevention tips
- Safety warning (amber alert box)
- Timing + cost estimates

**Market Price** (`getMarketPrice`)
- MSP vs Market Price side-by-side
- Trend indicator (Above/Below MSP with arrow)
- Best time to sell
- Storage tips
- eNAM link

**Soil Health** (`getSoilRecommendation`)
- N/P/K progress bars (animated)
- pH recommendation
- Organic vs Chemical options
- Improvement tips

### 6.6 Language Selector

12 languages supported with:
- Dropdown menu with native script names
- Globe icon
- Changes: UI greetings, input placeholder, suggested questions, AI system prompt

**Language → AI behavior:**
```typescript
const languageContext = language !== 'en'
  ? `\n\nRESPOND IN: ${language}. Maintain full agricultural accuracy.`
  : ''
```

### 6.7 Workflow Status Indicator

Shows processing transparency:
1. **Understanding your question** (Leaf icon)
2. **Searching knowledge base** (Database icon)
3. **Analysing information** (Brain icon)
4. **Generating response** (Sparkles icon)

Auto-advances through steps with setTimeout. Active step shows bouncing dots. Completed steps show green checkmarks.

Tool-specific indicator appears when AI calls a tool:
- 🌤️ Fetching weather data
- 📅 Loading crop calendar
- 🏛️ Looking up government schemes
- 🔬 Analysing pest symptoms
- 📊 Checking market prices
- 🧪 Analysing soil data

---

## 7. API REFERENCE

### 7.1 POST /api/chat

**Request:**
```json
{
  "messages": [UIMessage array],
  "language": "en|hi|ta|te|kn|ml|bn|mr|gu|pa|or|as"
}
```

**Response:** Server-Sent Events stream (UIMessage format)

**Tools triggered by AI:**
- `getWeatherInfo(location, state)`
- `getCropCalendar(crop, season, region?)`
- `getSchemeInfo(schemeName)`
- `getPestSolution(crop, symptoms)`
- `getMarketPrice(crop, state?)`
- `getSoilRecommendation(soilType, crop, issue?)`

**Model fallback:**
```typescript
if (process.env.OPENAI_API_KEY?.startsWith('sk-')) → GPT-4o
if (process.env.GROQ_API_KEY) → llama-3.1-8b-instant
```

### 7.2 POST /api/speech-to-text

**Request:** `multipart/form-data`
- `audio`: Audio Blob (webm/mp4)
- `language`: Language code string

**Response:**
```json
{
  "text": "transcribed text",
  "language": "hi"
}
```

**Model:** OpenAI Whisper-1

### 7.3 POST /api/text-to-speech

**Request:**
```json
{
  "text": "Text to convert to speech",
  "language": "en"
}
```

**Response:** Binary MP3 audio (`audio/mpeg`)

**Model:** OpenAI TTS-1, voice: `nova`

### 7.4 POST /api/analyze-image

**Request:** `multipart/form-data`
- `image`: Image File (jpg/png/webp/gif)
- `language`: Language code string

**Response:**
```json
{
  "analysis": "Markdown formatted agricultural analysis",
  "language": "en"
}
```

**Model:** OpenAI GPT-4o Vision (`max_tokens: 1500`)

---

## 8. COMPONENT GUIDE

### 8.1 Chat Page (`app/chat/page.tsx`)

**State:**
- `language: LanguageCode` — selected language
- `imageAnalyses: ImageAnalysis[]` — uploaded image results
- `isAnalyzingImage: boolean` — image upload in progress
- `currentTool: string | undefined` — active AI tool name

**Key functions:**
- `handleSendMessage(text)` — calls `sendMessage({ text })`
- `handleImageUpload(file)` — POSTs to `/api/analyze-image`
- `handleClearChat()` — resets messages + image analyses

### 8.2 ChatMessage (`components/chat/chat-message.tsx`)

Renders:
- User/AI message bubbles with gradient styling
- Markdown-rendered AI text
- Infographic cards for tool results
- Copy-to-clipboard button
- TTS listen/stop button
- `ImageAnalysisMessage` for image results

### 8.3 ChatInput (`components/chat/chat-input.tsx`)

Features:
- Auto-resizing textarea (max 150px)
- Voice recording with wave animation
- Image upload (jpg/png/webp/gif)
- Image preview with remove button
- Language-aware placeholder text
- Gradient send button
- Stop generation button when streaming

### 8.4 WorkflowStatus (`components/chat/workflow-status.tsx`)

- 4-step animated workflow indicator
- Shows when `isLoading = true`
- Auto-advances steps via setTimeout
- Tool-specific indicator via `toolName` prop
- Resets on `isActive = false`

### 8.5 InfographicCard (`components/chat/infographic-cards.tsx`)

Auto-selects card type via `toolName`:
```typescript
<InfographicCard toolName={toolName} data={result} />
```

6 card components + `GenericInfoCard` fallback

---

## 9. AI MODEL STRATEGY

### 9.1 Primary: OpenAI GPT-4o

**Strengths:**
- Best reasoning for complex agricultural questions
- Multilingual output quality
- Tool calling accuracy
- Vision for image analysis
- Whisper for voice

**When used:** When `OPENAI_API_KEY` is set and valid (starts with `sk-`)

### 9.2 Fallback: Groq llama-3.1-8b-instant

**Strengths:**
- Sub-second response times
- 10x cheaper than GPT-4o
- Reliable tool calling
- Good multilingual support

**When used:** When OpenAI key is missing or invalid

**Limitation:** Does not support image analysis (fallback to text description)

### 9.3 System Prompt Design

The system prompt is carefully designed for **token efficiency**:

```
Original (verbose): ~800 tokens
Optimized: ~250 tokens
Savings: 69% reduction
```

Key optimization decisions:
- Removed redundant explanations
- Combined related instructions
- Used concise bullet format
- Removed verbose examples
- Added `RESPOND IN: {language}` instead of full language instruction

### 9.4 Tool Design Philosophy

Tools use **async generators** for streaming states:
```typescript
async *execute({ crop }) {
  yield { state: 'loading', message: '...' }  // Shows loading UI
  // ... process data ...
  yield { state: 'ready', ...data }           // Shows infographic card
}
```

No artificial delays — data is computed synchronously and returned immediately for maximum efficiency.

---

## 10. TOKEN EFFICIENCY GUIDE

### 10.1 Per-Request Budget

```
System prompt: ~250 tokens
Average user message: ~30 tokens
Tool invocation: ~50 tokens
Response cap: 1024 tokens
Total per turn: ~1354 tokens max
```

At GPT-4o pricing (~$5/1M tokens):
- Cost per turn: ~$0.007
- Full conversation (10 turns): ~$0.07 ≈ ₹6

### 10.2 Optimizations Applied

1. **Compact system prompt** — 69% reduction from original
2. `maxTokens: 1024` — hard cap on response length
3. `stopWhen: stepCountIs(5)` — prevents tool loop runaway
4. **Structured tool data** — tools return JSON data, not prose (AI doesn't need to re-explain)
5. **Groq fallback** — 100x cheaper for text-only queries

### 10.3 Image Analysis Budget

```
System prompt: ~100 tokens
Image: counted as ~765 tokens (low-res)
Max response: 1500 tokens
Total: ~2365 tokens ≈ $0.012 ≈ ₹1
```

---

## 11. DEPLOYMENT GUIDE

### 11.1 Environment Variables

```env
# Required for full functionality
OPENAI_API_KEY=sk-...

# Optional (for text-only fallback)
GROQ_API_KEY=gsk_...
```

### 11.2 Vercel Deployment

1. Push code to GitHub
2. Connect repository in Vercel dashboard
3. Add environment variables in Project Settings > Environment Variables
4. Deploy

**Build command:** `next build` (default)  
**Framework preset:** Next.js  
**Node version:** 18+

### 11.3 Local Development

```bash
# Install dependencies
npm install

# Run dev server
npm run dev

# Type check
npx tsc --noEmit

# Build for production
npm run build
```

---

## 12. TROUBLESHOOTING

### 12.1 Common Issues

**Chat not working:**
- Check `OPENAI_API_KEY` or `GROQ_API_KEY` is in `.env.local`
- `.env` files do NOT work with Next.js — must be `.env.local`

**Voice not working:**
- Browser must be HTTPS or localhost for microphone access
- User must grant microphone permission
- Check browser console for MediaRecorder errors

**Image upload not working:**
- File must be jpg/png/webp/gif
- `capture="environment"` was intentionally removed — file picker now works on desktop
- Check `/api/analyze-image` response in browser DevTools

**Infographic cards not showing:**
- Cards only show when AI triggers a tool
- Trigger phrases: "weather in Pune", "crop calendar for wheat Kharif", "PM-KISAN scheme", etc.

**Groq fallback errors:**
- Groq does NOT support image analysis — text description fallback is used
- Check `GROQ_API_KEY` format: starts with `gsk_`

### 12.2 Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| "No AI provider configured" | Neither API key set | Add keys to `.env.local` |
| "Failed to transcribe audio" | Whisper API unavailable | Check `OPENAI_API_KEY` |
| "Image analysis is currently unavailable" | Vision API error | Check key quota/validity |
| "Could not access microphone" | Browser permission denied | Allow mic in browser settings |

---

## 13. ROADMAP

### Phase 1 (Complete ✅)
- [x] Multilingual text chat (12 languages)  
- [x] Voice input (Whisper STT)
- [x] Voice output (TTS)
- [x] Image crop analysis
- [x] 6 infographic tool cards
- [x] Groq fallback model
- [x] Bot-initiated language selection modal (with 🌐 and 🇮🇳 flags)
- [x] Vercel Serverless ready (60s optimized API timeouts)
- [x] Token efficiency optimization
- [x] Premium UI matching nature theme

### Phase 2 (Planned)
- 🎥 Live video field analysis (WebRTC + OpenAI Realtime API)
- 📱 PWA with offline message caching
- 🗺️ Real weather API integration (OpenWeatherMap)
- 📦 eNAM live market price integration
- 🔔 Push notifications for pest outbreaks & weather alerts

### Phase 3 (Future)
- 🌐 WhatsApp/Telegram bot version
- 📊 Farm analytics dashboard
- 🗄️ User accounts & chat history persistence
- 🌾 Region-specific crop databases
- 🤝 KVK expert consultation booking
- 🗣️ Offline voice with local Whisper model

---

*VedaKrishi AI — Empowering every Indian farmer with the knowledge they deserve.*

*Built with love, code, and a deep respect for the hands that feed Bharat.* 🌾
