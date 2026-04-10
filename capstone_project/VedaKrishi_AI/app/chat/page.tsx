'use client'

import { useState, useRef, useEffect } from 'react'
import { useChat } from '@ai-sdk/react'
import { DefaultChatTransport } from 'ai'
import Link from 'next/link'
import { 
  Leaf, ArrowLeft, Trash2, Sprout, Bug, CloudRain, 
  Droplets, Building2, Wheat, Sparkles,
  MessageCircle, Camera, Video
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatMessage, ImageAnalysisMessage } from '@/components/chat/chat-message'
import { ChatInput } from '@/components/chat/chat-input'
import { LanguageSelector, LanguageCode } from '@/components/chat/language-selector'
import { SuggestedQuestions } from '@/components/chat/suggested-questions'
import { WorkflowStatus } from '@/components/chat/workflow-status'
import { LanguagePickerModal } from '@/components/chat/language-picker-modal'
import { cn } from '@/lib/utils'

interface ImageAnalysis {
  id: string
  imageUrl: string
  analysis: string
  filename?: string
  timestamp: number
}

// Greeting messages per language after user picks
const GREETINGS: Record<string, string> = {
  en: "Hello! I'm VedaKrishi AI 🌾 — your intelligent farming companion. I can help with crop selection, pest control, weather, government schemes, market prices, and more. What can I help you with today?",
  hi: "नमस्ते! मैं VedaKrishi AI 🌾 हूँ — आपका कृषि सहायक। मैं फसल चयन, कीट नियंत्रण, मौसम, सरकारी योजनाओं, बाजार भाव और अन्य विषयों में मदद कर सकता हूँ। आज मैं आपकी क्या सहायता करूँ?",
  ta: "வணக்கம்! நான் VedaKrishi AI 🌾 — உங்கள் விவசாய உதவியாளர். பயிர் தேர்வு, பூச்சி கட்டுப்பாடு, வானிலை, அரசு திட்டங்கள், சந்தை விலை மற்றும் பலவற்றில் உதவ முடியும். இன்று என்ன உதவி வேண்டும்?",
  te: "నమస్కారం! నేను VedaKrishi AI 🌾 — మీ వ్యవసాయ సహాయకుడు. పంట ఎంపిక, కీట నియంత్రణ, వాతావరణం, ప్రభుత్వ పథకాలు, మార్కెట్ ధరలు మరియు మరిన్నింటిలో సహాయం చేయగలను. నేడు మీకు ఏమి కావాలి?",
  kn: "ನಮಸ್ಕಾರ! ನಾನು VedaKrishi AI 🌾 — ನಿಮ್ಮ ಕೃಷಿ ಸಹಾಯಕ. ಬೆಳೆ ಆಯ್ಕೆ, ಕೀಟ ನಿಯಂತ್ರಣ, ಹವಾಮಾನ, ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು, ಮಾರುಕಟ್ಟೆ ಬೆಲೆಗಳು ಮತ್ತು ಇನ್ನಷ್ಟರಲ್ಲಿ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ. ಇಂದು ನಿಮಗೆ ಯಾವ ಸಹಾಯ ಬೇಕು?",
  ml: "നമസ്കാരം! ഞാൻ VedaKrishi AI 🌾 — നിങ്ങളുടെ കൃഷി സഹായി. വിള തിരഞ്ഞെടുക്കൽ, കീടനിയന്ത്രണം, കാലാവസ്ഥ, സർക്കാർ പദ്ധതികൾ, വിലകൾ എന്നിവ ഉൾപ്പെടെ പലതിനും സഹായിക്കാൻ കഴിയും. ഇന്ന് എന്ത് സഹായം വേണം?",
  bn: "নমস্কার! আমি VedaKrishi AI 🌾 — আপনার কৃষি সহায়ক। ফসল নির্বাচন, কীটপতঙ্গ নিয়ন্ত্রণ, আবহাওয়া, সরকারি প্রকল্প এবং বাজার মূল্য বিষয়ে সাহায্য করতে পারি। আজ কী সাহায্য দরকার?",
  mr: "नमस्कार! मी VedaKrishi AI 🌾 — तुमचा शेती सहाय्यक. पिक निवड, कीड नियंत्रण, हवामान, सरकारी योजना, बाजारभाव यांसाठी मदत करू शकतो. आज काय मदत हवी?",
  de: "Hallo! Ich bin VedaKrishi AI 🌾 — Ihr intelligenter Landwirtschaftsassistent. Ich kann bei Fruchtfolge, Schädlingsbekämpfung, Wetter, Förderprogrammen und Marktpreisen helfen. Wie kann ich Ihnen heute helfen?",
  fr: "Bonjour! Je suis VedaKrishi AI 🌾 — votre assistant agricole intelligent. Je peux vous aider sur les cultures, la lutte antiparasitaire, la météo, les subventions et les prix du marché. Comment puis-je vous aider aujourd'hui?",
  es: "¡Hola! Soy VedaKrishi AI 🌾 — tu asistente agrícola inteligente. Puedo ayudarte con selección de cultivos, control de plagas, clima, programas gubernamentales y precios de mercado. ¿En qué puedo ayudarte hoy?",
}

export default function ChatPage() {
  const [language, setLanguage] = useState<LanguageCode>('en')
  const [hasPickedLanguage, setHasPickedLanguage] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)
  const [imageAnalyses, setImageAnalyses] = useState<ImageAnalysis[]>([])
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false)
  const [currentTool, setCurrentTool] = useState<string | undefined>()
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  const { messages, sendMessage, status, setMessages, stop } = useChat({
    transport: new DefaultChatTransport({ 
      api: '/api/chat',
      prepareSendMessagesRequest: ({ id, messages }) => ({
        body: { messages, id, language },
      }),
    }),
  })

  const isLoading = status === 'streaming' || status === 'submitted'

  // Track active tool invocations
  useEffect(() => {
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1]
      if (lastMessage.role === 'assistant' && lastMessage.parts) {
        const activeTool = lastMessage.parts.find(
          (p: any) => p.type === 'tool-invocation' && (p.state === 'call' || p.state === 'partial-call')
        )
        setCurrentTool(activeTool ? (activeTool as any).toolName : undefined)
      }
    }
    if (!isLoading) setCurrentTool(undefined)
  }, [messages, isLoading])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, imageAnalyses, isAnalyzingImage])

  const handleLanguagePick = async (lang: LanguageCode) => {
    setLanguage(lang)
    setHasPickedLanguage(true)
    // Fetch pre-written greeting from API (zero AI tokens, instant response)
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initLang: lang, language: lang, messages: [] }),
      })
      const text = await res.text()
      // Extract the greeting text from the AI data stream format: 0:"..."
      const match = text.match(/^0:"(.*)"/m)
      if (match) {
        const greeting = match[1]
          .replace(/\\n/g, '\n')
          .replace(/\\"/g, '"')
          .replace(/\\\\/g, '\\')
        setMessages([{
          id: 'init-greeting',
          role: 'assistant' as const,
          parts: [{ type: 'text' as const, text: greeting }],
        }])
      }
    } catch {
      // Silently fail - user can still type without greeting
    }
  }

  const handleSendMessage = (text: string) => {
    if (!text.trim()) return
    sendMessage({ text })
  }

  const handleImageUpload = async (file: File) => {
    setIsAnalyzingImage(true)
    setAnalysisError(null)
    const imageUrl = URL.createObjectURL(file)

    try {
      const formData = new FormData()
      formData.append('image', file)
      formData.append('language', language)

      const response = await fetch('/api/analyze-image', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.error || `Server error ${response.status}`)
      }

      const data = await response.json()

      if (data.error) {
        throw new Error(data.analysis || 'Analysis failed')
      }

      setImageAnalyses(prev => [...prev, {
        id: Date.now().toString(),
        imageUrl,
        analysis: data.analysis || 'Unable to analyse the image at this time.',
        filename: file.name,
        timestamp: Date.now(),
      }])
    } catch (error: any) {
      console.error('Image analysis error:', error)
      setAnalysisError(error.message || 'Image analysis failed')
      setImageAnalyses(prev => [...prev, {
        id: Date.now().toString(),
        imageUrl,
        analysis: `❌ **Analysis failed:** ${error.message || 'Please try again or describe the issue in text.'}\n\nTip: Make sure your image is clear and shows the crop/pest/soil clearly.`,
        filename: file.name,
        timestamp: Date.now(),
      }])
    } finally {
      setIsAnalyzingImage(false)
    }
  }

  const handleClearChat = () => {
    setMessages([])
    setImageAnalyses([])
    setAnalysisError(null)
    setHasPickedLanguage(false)
  }

  const handleSelectQuestion = (question: string) => {
    if (!hasPickedLanguage) {
      setHasPickedLanguage(true)
    }
    handleSendMessage(question)
  }

  // All messages are displayable - no filtering needed since we no longer
  // inject fake __INIT__ text messages; greeting comes via API stream directly.
  const displayMessages = messages

  // Show welcome screen after language pick but before any real messages
  const showWelcome = hasPickedLanguage && displayMessages.length === 0 && imageAnalyses.length === 0 && !isLoading

  const quickCategories = [
    { icon: Sprout, label: 'Crops', color: 'text-green-600' },
    { icon: Bug, label: 'Pests', color: 'text-red-500' },
    { icon: CloudRain, label: 'Weather', color: 'text-blue-500' },
    { icon: Droplets, label: 'Irrigation', color: 'text-cyan-500' },
    { icon: Building2, label: 'Schemes', color: 'text-amber-600' },
    { icon: Wheat, label: 'Market', color: 'text-purple-500' },
  ]

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Nature-themed background */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-0 right-0 w-96 h-96 bg-primary/3 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-green-500/3 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 w-64 h-64 bg-amber-500/3 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2" />
      </div>

      {/* Header */}
      <header className="relative z-10 flex items-center justify-between px-4 py-3 border-b border-border bg-background/80 backdrop-blur-md sticky top-0">
        <div className="flex items-center gap-3">
          <Link href="/">
            <Button variant="ghost" size="icon" className="h-9 w-9 hover:bg-primary/10">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-primary to-green-600 text-primary-foreground shadow-md">
              <Leaf className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-base font-bold text-foreground flex items-center gap-1.5">
                VedaKrishi AI
                <span className="flex h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              </h1>
              <p className="text-[11px] text-muted-foreground flex items-center gap-1">
                <Sparkles className="h-3 w-3" />
                Your AI Farming Companion
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {hasPickedLanguage && (
            <LanguageSelector value={language} onChange={(lang) => {
              setLanguage(lang)
            }} />
          )}
          {(messages.length > 0 || imageAnalyses.length > 0) && (
            <Button
              variant="ghost"
              size="icon"
              onClick={handleClearChat}
              className="h-9 w-9 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
              title="Clear chat"
            >
              <Trash2 className="h-5 w-5" />
            </Button>
          )}
        </div>
      </header>

      {/* Chat Area */}
      <div 
        ref={chatContainerRef}
        className="relative z-10 flex-1 overflow-y-auto"
      >
        {/* STEP 1: Language Picker — shown before language selection */}
        {!hasPickedLanguage && (
          <LanguagePickerModal onSelect={handleLanguagePick} />
        )}

        {/* STEP 2: Welcome Screen — shown after language pick, before any messages */}
        {showWelcome && (
          <div className="flex flex-col items-center justify-center min-h-full p-4">
            <div className="text-center mb-8 max-w-lg animate-in fade-in-0 slide-in-from-bottom-4 duration-500">
              <div className="flex justify-center mb-6">
                <div className="relative">
                  <div className="h-20 w-20 rounded-3xl bg-gradient-to-br from-primary via-green-500 to-emerald-600 flex items-center justify-center shadow-xl shadow-primary/20 animate-float">
                    <Leaf className="h-10 w-10 text-white" />
                  </div>
                  <div className="absolute -bottom-1 -right-1 h-6 w-6 rounded-full bg-gradient-to-r from-amber-400 to-orange-500 flex items-center justify-center shadow-md">
                    <Sparkles className="h-3.5 w-3.5 text-white" />
                  </div>
                </div>
              </div>

              {/* Language-aware greeting */}
              <h2 className="text-2xl font-bold text-foreground mb-2">
                {language === 'hi' ? 'नमस्ते किसान भाई! 🙏' :
                 language === 'ta' ? 'வணக்கம் விவசாயி! 🙏' :
                 language === 'te' ? 'నమస్కారం రైతు! 🙏' :
                 language === 'kn' ? 'ನಮಸ್ಕಾರ ರೈತರೇ! 🙏' :
                 language === 'ml' ? 'നമസ്കാരം കർഷകരേ! 🙏' :
                 language === 'bn' ? 'নমস্কার কৃষক! 🙏' :
                 language === 'mr' ? 'नमस्कार शेतकरी! 🙏' :
                 language === 'gu' ? 'નમસ્તે ખેડૂત! 🙏' :
                 language === 'pa' ? 'ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਕਿਸਾਨ! 🙏' :
                 language === 'de' ? 'Guten Tag, Bauer! 🙏' :
                 language === 'fr' ? 'Bonjour, Agriculteur! 🙏' :
                 language === 'es' ? '¡Buenos días, Agricultor! 🙏' :
                 'Hello Farmer! 🌾'}
              </h2>

              <p className="text-muted-foreground text-sm leading-relaxed">
                {language === 'hi' ? 'मैं आपकी खेती में मदद के लिए यहाँ हूँ। फसल, मौसम, कीट, सिंचाई या सरकारी योजनाओं के बारे में पूछें।' :
                 language === 'ta' ? 'உங்கள் விவசாயத்தில் உதவ நான் இங்கே இருக்கிறேன். பயிர்கள், வானிலை, பூச்சிகள் பற்றி கேளுங்கள்.' :
                 language === 'te' ? 'మీ వ్యవసాయంలో సహాయం చేయడానికి నేను ఇక్కడ ఉన్నాను. పంటలు, వాతావరణం గురించి అడగండి.' :
                 language === 'de' ? 'Ich bin hier, um bei Ihrer Landwirtschaft zu helfen. Fragen Sie zu Kulturen, Wetter und Förderprogrammen.' :
                 language === 'fr' ? "Je suis là pour vous aider dans votre agriculture. Posez des questions sur les cultures, la météo et les subventions." :
                 language === 'es' ? 'Estoy aquí para ayudar con su agricultura. Pregunte sobre cultivos, clima y programas de apoyo.' :
                 "I'm here to help with your farming needs. Ask about crops, weather, pests, irrigation, schemes, or upload a photo for instant crop analysis!"}
              </p>
            </div>

            {/* Quick Category Pills */}
            <div className="flex flex-wrap justify-center gap-2 mb-6 animate-in fade-in-0 slide-in-from-bottom-4 duration-500 delay-100">
              {quickCategories.map((cat) => (
                <div
                  key={cat.label}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-card border border-border text-xs font-medium text-muted-foreground"
                >
                  <cat.icon className={cn("h-3.5 w-3.5", cat.color)} />
                  {cat.label}
                </div>
              ))}
            </div>

            {/* Features Grid */}
            <div className="w-full max-w-2xl mb-6 animate-in fade-in-0 slide-in-from-bottom-4 duration-500 delay-200">
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-card border border-border rounded-xl p-3 text-center hover:border-primary/30 transition-colors">
                  <MessageCircle className="h-5 w-5 text-primary mx-auto mb-1.5" />
                  <p className="text-[11px] font-medium text-foreground">Text Chat</p>
                  <p className="text-[9px] text-muted-foreground">15 Languages</p>
                </div>
                <div className="bg-card border border-border rounded-xl p-3 text-center hover:border-primary/30 transition-colors">
                  <Camera className="h-5 w-5 text-primary mx-auto mb-1.5" />
                  <p className="text-[11px] font-medium text-foreground">Photo Analysis</p>
                  <p className="text-[9px] text-muted-foreground">Crop Disease ID</p>
                </div>
                <div className="bg-card border border-border rounded-xl p-3 text-center hover:border-primary/30 transition-colors relative">
                  <Video className="h-5 w-5 text-primary/50 mx-auto mb-1.5" />
                  <p className="text-[11px] font-medium text-foreground/60">Live Video</p>
                  <p className="text-[9px] text-muted-foreground">Coming Soon</p>
                  <div className="absolute top-1 right-1 h-1.5 w-1.5 rounded-full bg-amber-400" />
                </div>
              </div>
            </div>

            {/* Suggested Questions */}
            <div className="w-full max-w-2xl animate-in fade-in-0 slide-in-from-bottom-4 duration-500 delay-300">
              <p className="text-xs text-muted-foreground text-center mb-3">
                {language === 'hi' ? '👇 या इनमें से कोई प्रश्न चुनें:' :
                 language === 'ta' ? '👇 அல்லது இவற்றில் ஒன்றைத் தேர்ந்தெடுக்கவும்:' :
                 language === 'te' ? '👇 లేదా వీటిలో ఒకదాన్ని ఎంచుకోండి:' :
                 '👇 Or choose from these questions:'}
              </p>
              <SuggestedQuestions onSelect={handleSelectQuestion} language={language} />
            </div>
          </div>
        )}

        {/* STEP 3: Chat messages */}
        {hasPickedLanguage && (displayMessages.length > 0 || imageAnalyses.length > 0 || isLoading) && (
          <div className="pb-4">
            {/* Bot greeting as the first "message" visually */}
            {displayMessages.length === 0 && !isLoading && imageAnalyses.length === 0 && (
              <div className="flex gap-3 px-4 py-4 animate-in fade-in-0 slide-in-from-left-4 duration-300">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-green-600 text-white shadow-md">
                  <Leaf className="h-5 w-5" />
                </div>
                <div className="max-w-[80%] bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                  <p className="text-sm text-foreground leading-relaxed">
                    {GREETINGS[language] || GREETINGS.en}
                  </p>
                </div>
              </div>
            )}

            {displayMessages.map((message) => (
              <ChatMessage key={message.id} message={message} language={language} />
            ))}

            {imageAnalyses.map((ia) => (
              <ImageAnalysisMessage
                key={ia.id}
                imageUrl={ia.imageUrl}
                analysis={ia.analysis}
                language={language}
              />
            ))}

            {/* Image Analysis Loading */}
            {isAnalyzingImage && (
              <div className="flex gap-3 px-4 py-4 animate-in fade-in-0 slide-in-from-left-4 duration-300">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-green-600 text-white shadow-md">
                  <Camera className="h-5 w-5" />
                </div>
                <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <div className="flex gap-1">
                      <span className="h-2 w-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="h-2 w-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="h-2 w-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                    <span>📸 Analysing your image with AI Vision...</span>
                  </div>
                </div>
              </div>
            )}

            {/* Analysis error toast */}
            {analysisError && (
              <div className="mx-4 my-2 flex items-center gap-2 bg-destructive/10 border border-destructive/20 text-destructive text-xs rounded-xl px-4 py-2">
                <span>⚠️ {analysisError}</span>
                <button onClick={() => setAnalysisError(null)} className="ml-auto text-destructive/60 hover:text-destructive">✕</button>
              </div>
            )}

            {/* Workflow Status */}
            {isLoading && (
              <WorkflowStatus 
                isActive={true} 
                toolName={currentTool}
                language={language}
              />
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area — only shown after language selection */}
      {hasPickedLanguage && (
        <div className="relative z-10">
          <ChatInput 
            onSend={handleSendMessage}
            onImageUpload={handleImageUpload}
            isLoading={isLoading || isAnalyzingImage}
            language={language}
            onStop={stop}
          />
        </div>
      )}
    </div>
  )
}
