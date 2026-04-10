import OpenAI from 'openai'

export const maxDuration = 60

// Language name lookup for proper instruction
const LANGUAGE_NAMES: Record<string, string> = {
  en: 'English', hi: 'Hindi', ta: 'Tamil', te: 'Telugu',
  kn: 'Kannada', ml: 'Malayalam', bn: 'Bengali', mr: 'Marathi',
  gu: 'Gujarati', pa: 'Punjabi', or: 'Odia', as: 'Assamese',
  de: 'German', fr: 'French', es: 'Spanish',
}

export async function POST(req: Request) {
  // Check API key immediately
  if (!process.env.OPENAI_API_KEY) {
    return Response.json(
      { error: 'OpenAI API key not configured', analysis: '❌ Image analysis requires an OpenAI API key. Please configure OPENAI_API_KEY in .env.local' },
      { status: 503 }
    )
  }

  const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY })

  try {
    const formData = await req.formData()
    const imageFile = formData.get('image') as File | null
    const language = (formData.get('language') as string) || 'en'
    const userContext = (formData.get('context') as string) || ''

    if (!imageFile || !(imageFile instanceof Blob)) {
      return Response.json({ error: 'No image file provided' }, { status: 400 })
    }

    // Validate file type
    const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
    const mimeType = imageFile.type || 'image/jpeg'
    if (!validTypes.includes(mimeType)) {
      return Response.json(
        { error: 'Invalid file type. Please upload a JPEG, PNG, WebP, or GIF image.' },
        { status: 400 }
      )
    }

    // Validate file size (max 10MB)
    if (imageFile.size > 10 * 1024 * 1024) {
      return Response.json(
        { error: 'Image too large. Please upload an image smaller than 10MB.' },
        { status: 413 }
      )
    }

    // Convert to base64
    const arrayBuffer = await imageFile.arrayBuffer()
    const base64 = Buffer.from(arrayBuffer).toString('base64')

    const langName = LANGUAGE_NAMES[language] || 'English'
    const langInstruction = language !== 'en'
      ? `IMPORTANT: Respond ENTIRELY in ${langName} (${language}). All text must be in ${langName}.`
      : 'Respond in English.'

    const contextNote = userContext
      ? `Additional context from farmer: "${userContext}"\n`
      : ''

    // Use GPT-4o Vision — concise, structured analysis
    const response = await openai.chat.completions.create({
      model: 'gpt-4o',
      messages: [
        {
          role: 'system',
          content: `You are VedaKrishi AI — an expert agricultural image analyst for Indian farmers. ${langInstruction}

${contextNote}Analyse the uploaded farm image and provide a structured response with these sections:

🔍 **What I See** — Identify crop type, growth stage, and visible conditions
📊 **Health Status** — Rate as: ✅ Healthy | ⚠️ Mild Issue | 🟠 Moderate Issue | 🔴 Severe Issue
🎯 **Diagnosis** — Specific disease name, pest species, or nutrient deficiency (if any)
🌿 **Organic Treatment** — Natural/organic solutions with application method
🧪 **Chemical Treatment** — Recommended pesticide/fungicide with dosage
🛡️ **Prevention** — How to prevent this in future seasons
⏰ **Urgency** — Act within: [timeframe]

Use emojis generously. Be specific, practical, and farmer-friendly. Keep response under 400 words.`,
        },
        {
          role: 'user',
          content: [
            {
              type: 'image_url',
              image_url: {
                url: `data:${mimeType};base64,${base64}`,
                detail: 'high', // High detail for accurate crop disease identification
              },
            },
            {
              type: 'text',
              text: 'Please analyse this image from my farm and provide agricultural advice.',
            },
          ],
        },
      ],
      max_tokens: 800, // Concise but complete analysis
    })

    const analysis = response.choices[0]?.message?.content
    
    if (!analysis) {
      throw new Error('No analysis returned from AI model')
    }

    return Response.json({ analysis, language })

  } catch (error: any) {
    console.error('Image analysis error:', error?.message || error)

    // Specific error messages for common failures
    const errMsg = error?.message || ''
    let userFacingError = 'Image analysis failed. Please try again.'
    
    if (errMsg.includes('invalid_api_key') || errMsg.includes('401')) {
      userFacingError = 'Invalid OpenAI API key. Please check your OPENAI_API_KEY in .env.local'
    } else if (errMsg.includes('insufficient_quota') || errMsg.includes('429')) {
      userFacingError = 'API quota exceeded. Please check your OpenAI billing.'
    } else if (errMsg.includes('too large') || errMsg.includes('413')) {
      userFacingError = 'Image is too large for analysis. Please use a smaller image.'
    } else if (errMsg.includes('could not process image')) {
      userFacingError = 'Could not read the image. Please ensure it is a clear, valid photo.'
    }

    return Response.json(
      {
        analysis: `❌ ${userFacingError}\n\n💡 **Tip:** Take a clear, well-lit photo of the affected crop part (leaf, stem, or root) and try again. Alternatively, describe the symptoms in the chat and I'll help you through text.`,
        language: 'en',
        error: true,
      },
      { status: 500 }
    )
  }
}
