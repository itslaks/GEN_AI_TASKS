import OpenAI from 'openai'

export const maxDuration = 60

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
})

// OpenAI TTS-1 supports multilingual output naturally.
// Voice selection optimised for each language's tone and clarity.
type OpenAIVoice = 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer'

const VOICE_FOR_LANGUAGE: Record<string, OpenAIVoice> = {
  // Indian regional languages
  en: 'nova',     // Clear, warm English
  hi: 'nova',     // Hindi — nova works best
  ta: 'nova',     // Tamil
  te: 'nova',     // Telugu
  kn: 'nova',     // Kannada
  ml: 'nova',     // Malayalam
  bn: 'shimmer',  // Bengali — shimmer for softer tone
  mr: 'nova',     // Marathi
  gu: 'nova',     // Gujarati
  pa: 'alloy',    // Punjabi — alloy for vibrant tone
  or: 'nova',     // Odia
  as: 'nova',     // Assamese
  // International languages
  de: 'onyx',     // German — onyx for deeper, authoritative tone
  fr: 'shimmer',  // French — shimmer for smooth French cadence
  es: 'nova',     // Spanish — nova works well with Spanish
}

// Whisper language code lookup (used for reference, TTS is language-agnostic)
const LANGUAGE_NAMES: Record<string, string> = {
  en: 'English', hi: 'Hindi', ta: 'Tamil', te: 'Telugu',
  kn: 'Kannada', ml: 'Malayalam', bn: 'Bengali', mr: 'Marathi',
  gu: 'Gujarati', pa: 'Punjabi', or: 'Odia', as: 'Assamese',
  de: 'German', fr: 'French', es: 'Spanish',
}

export async function POST(req: Request) {
  try {
    const { text, language = 'en' } = await req.json()

    if (!text || typeof text !== 'string') {
      return Response.json({ error: 'No text provided' }, { status: 400 })
    }

    if (!process.env.OPENAI_API_KEY) {
      return Response.json({ error: 'OpenAI API key not configured' }, { status: 503 })
    }

    // Limit text length for TTS (OpenAI limit is 4096 chars)
    // Trim at sentence boundary if possible
    let truncatedText = text.slice(0, 3800)
    if (text.length > 3800) {
      const lastSentence = truncatedText.lastIndexOf('.')
      if (lastSentence > 2000) truncatedText = truncatedText.slice(0, lastSentence + 1)
    }

    const voice = VOICE_FOR_LANGUAGE[language] || 'nova'
    
    console.log(`TTS: lang=${language} (${LANGUAGE_NAMES[language] || 'Unknown'}), voice=${voice}, chars=${truncatedText.length}`)

    // Generate speech — TTS-1 model handles all listed languages natively
    const mp3Response = await openai.audio.speech.create({
      model: 'tts-1',
      voice,
      input: truncatedText,
      response_format: 'mp3',
      speed: language === 'de' ? 0.92 : 0.96, // Slightly slower for German
    })

    const audioBuffer = await mp3Response.arrayBuffer()

    return new Response(audioBuffer, {
      headers: {
        'Content-Type': 'audio/mpeg',
        'Content-Length': audioBuffer.byteLength.toString(),
        'X-Language': language,
        'X-Voice': voice,
      },
    })
  } catch (error: any) {
    console.error('Text-to-speech error:', error?.message || error)
    return Response.json(
      { error: 'Failed to generate speech. Please check your OpenAI API key.' },
      { status: 500 }
    )
  }
}
