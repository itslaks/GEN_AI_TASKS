import OpenAI from 'openai'

export const maxDuration = 60

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
})

// Language code mapping for Whisper
const LANGUAGE_CODES: Record<string, string> = {
  en: 'en',
  hi: 'hi',
  ta: 'ta',
  te: 'te',
  kn: 'kn',
  ml: 'ml',
  bn: 'bn',
  mr: 'mr',
  gu: 'gu',
  pa: 'pa',
  or: 'or',
  as: 'as',
}

export async function POST(req: Request) {
  try {
    const formData = await req.formData()
    const audioFile = formData.get('audio') as Blob
    const language = formData.get('language') as string || 'hi'

    if (!audioFile) {
      return Response.json({ error: 'No audio file provided' }, { status: 400 })
    }

    // Convert Blob to File for OpenAI API
    const file = new File([audioFile], 'audio.webm', { type: audioFile.type })

    // Use Whisper for speech-to-text with language hint
    const transcription = await openai.audio.transcriptions.create({
      file,
      model: 'whisper-1',
      language: LANGUAGE_CODES[language] || 'hi',
      response_format: 'json',
    })

    return Response.json({ 
      text: transcription.text,
      language: language,
    })
  } catch (error) {
    console.error('Speech-to-text error:', error)
    return Response.json(
      { error: 'Failed to transcribe audio' },
      { status: 500 }
    )
  }
}
