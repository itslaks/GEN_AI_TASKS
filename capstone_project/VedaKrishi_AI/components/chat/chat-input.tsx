'use client'

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Send, Mic, MicOff, Loader2, StopCircle, Camera, X, Video } from 'lucide-react'
import { useVoiceRecording } from '@/hooks/use-voice-recording'

interface ChatInputProps {
  onSend: (message: string) => void
  onImageUpload?: (file: File) => void
  isLoading: boolean
  language: string
  onStop?: () => void
}

const LANGUAGE_PLACEHOLDERS: Record<string, string> = {
  en: 'Ask about crops, weather, schemes...',
  hi: 'फसल, मौसम, योजनाओं के बारे में पूछें...',
  ta: 'பயிர்கள், வானிலை, திட்டங்கள் பற்றி கேளுங்கள்...',
  te: 'పంటలు, వాతావరణం, పథకాల గురించి అడగండి...',
  kn: 'ಬೆಳೆಗಳು, ಹವಾಮಾನ, ಯೋಜನೆಗಳ ಬಗ್ಗೆ ಕೇಳಿ...',
  ml: 'വിളകൾ, കാലാവസ്ഥ, പദ്ധതികൾ ചോദിക്കൂ...',
  bn: 'ফসল, আবহাওয়া, প্রকল্প সম্পর্কে জিজ্ঞাসা করুন...',
  mr: 'पिके, हवामान, योजनांबद्दल विचारा...',
  gu: 'પાક, હવામાન, યોજનાઓ વિશે પૂછો...',
  pa: 'ਫ਼ਸਲਾਂ, ਮੌਸਮ, ਸਕੀਮਾਂ ਬਾਰੇ ਪੁੱਛੋ...',
  or: 'ଫସଲ, ପାଣିପାଗ, ଯୋଜନା ବିଷୟରେ ପଚାରନ୍ତୁ...',
  as: 'শস্য, বতৰ, আঁচনি সম্পর্কে সুধক...',
}

const RECORDING_LABELS: Record<string, string> = {
  en: '🎙️ Listening... Tap to stop',
  hi: '🎙️ सुन रहा हूँ... रोकने के लिए टैप करें',
  ta: '🎙️ கேட்கிறேன்... நிறுத்த தட்டவும்',
  te: '🎙️ వింటున్నాను... ఆపడానికి నొక్కండి',
  kn: '🎙️ ಕೇಳುತ್ತಿದ್ದೇನೆ... ನಿಲ್ಲಿಸಲು ಟ್ಯಾಪ್ ಮಾಡಿ',
  ml: '🎙️ കേൾക്കുന്നു... നിർത്താൻ ടാപ്പ് ചെയ്യൂ',
  bn: '🎙️ শুনছি... বন্ধ করতে ট্যাপ করুন',
}

export function ChatInput({ onSend, onImageUpload, isLoading, language, onStop }: ChatInputProps) {
  const [input, setInput] = useState('')
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  const { isRecording, isTranscribing, startRecording, stopRecording, error: voiceError } = useVoiceRecording({
    language,
    onTranscription: (text) => {
      setInput(prev => prev ? `${prev} ${text}` : text)
    },
  })

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`
    }
  }, [input])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const hasImage = selectedFile && onImageUpload
    const hasText = input.trim()
    if (!hasImage && !hasText) return

    // Send image first (with optional context message)
    if (hasImage) {
      onImageUpload(selectedFile!)
      // If text also provided, add as a follow-up message context
      if (hasText) {
        // Small delay so image analysis and text don't race
        setTimeout(() => {
          onSend(input)
        }, 100)
      }
      setSelectedFile(null)
      setImagePreview(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } else if (hasText) {
      onSend(input)
    }
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleVoiceClick = () => {
    if (isRecording) {
      stopRecording()
    } else {
      startRecording()
    }
  }

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      const reader = new FileReader()
      reader.onload = (ev) => {
        setImagePreview(ev.target?.result as string)
      }
      reader.readAsDataURL(file)
    }
  }

  const removeImage = () => {
    setSelectedFile(null)
    setImagePreview(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="border-t border-border bg-background/90 backdrop-blur-md p-4">
      {/* Voice Error */}
      {voiceError && (
        <div className="text-destructive text-sm mb-2 px-2 bg-destructive/10 rounded-lg py-2">{voiceError}</div>
      )}

      {/* Image Preview */}
      {imagePreview && (
        <div className="mb-3 relative inline-block">
          <div className="rounded-xl overflow-hidden border-2 border-primary/30 shadow-md">
            <img 
              src={imagePreview} 
              alt="Upload preview" 
              className="max-h-32 max-w-48 object-cover"
            />
          </div>
          <button
            type="button"
            onClick={removeImage}
            className="absolute -top-2 -right-2 h-6 w-6 bg-destructive text-white rounded-full flex items-center justify-center hover:bg-destructive/90 shadow-md transition-transform hover:scale-110"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Voice Recording Visualization */}
      {isRecording && (
        <div className="mb-3 flex items-center justify-center gap-3 bg-destructive/5 border border-destructive/20 rounded-2xl py-3 px-4">
          <div className="voice-wave flex items-end gap-[3px] h-8">
            {[...Array(12)].map((_, i) => (
              <div
                key={i}
                className="w-[3px] bg-destructive rounded-full voice-bar"
                style={{
                  animationDelay: `${i * 0.1}s`,
                  height: '4px',
                }}
              />
            ))}
          </div>
          <span className="text-sm text-destructive font-medium">
            {RECORDING_LABELS[language] || RECORDING_LABELS.en}
          </span>
        </div>
      )}

      {isTranscribing && (
        <div className="mb-3 text-center text-sm text-muted-foreground flex items-center justify-center gap-2 bg-muted/50 rounded-2xl py-3">
          <Loader2 className="h-4 w-4 animate-spin" />
          Processing your voice...
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="flex items-end gap-2">
        {/* Image Upload Button */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={handleImageSelect}
          className="hidden"
          id="image-upload"
        />
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading || isRecording}
          className="h-11 w-11 shrink-0 rounded-full border-border hover:border-primary hover:bg-primary/5 transition-all"
          title="Upload crop/soil photo for analysis"
        >
          <Camera className="h-5 w-5 text-muted-foreground" />
        </Button>

        {/* Voice Recording Button */}
        <Button
          type="button"
          variant={isRecording ? "destructive" : "outline"}
          size="icon"
          onClick={handleVoiceClick}
          disabled={isTranscribing}
          className={cn(
            "h-11 w-11 shrink-0 rounded-full transition-all",
            isRecording && "animate-pulse shadow-lg shadow-destructive/25",
            !isRecording && "border-border hover:border-primary hover:bg-primary/5"
          )}
          title={isRecording ? "Stop recording" : "Start voice input"}
        >
          {isTranscribing ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : isRecording ? (
            <MicOff className="h-5 w-5" />
          ) : (
            <Mic className="h-5 w-5 text-muted-foreground" />
          )}
        </Button>

        {/* Text Input */}
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isRecording ? "🎙️ Listening..." : (LANGUAGE_PLACEHOLDERS[language] || LANGUAGE_PLACEHOLDERS.en)}
            disabled={isRecording || isTranscribing}
            rows={1}
            className={cn(
              "w-full resize-none rounded-2xl border bg-card px-4 py-3 pr-12",
              "text-foreground placeholder:text-muted-foreground",
              "focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "transition-all duration-200",
              "border-border hover:border-primary/40",
            )}
          />
          
          {isRecording && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <span className="flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-destructive opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-destructive"></span>
              </span>
            </div>
          )}
        </div>

        {/* Send/Stop Button */}
        {isLoading ? (
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={onStop}
            className="h-11 w-11 shrink-0 rounded-full border-destructive/30 hover:bg-destructive/10"
            title="Stop generating"
          >
            <StopCircle className="h-5 w-5 text-destructive" />
          </Button>
        ) : (
          <Button
            type="submit"
            disabled={(!input.trim() && !selectedFile) || isRecording || isTranscribing}
            className="h-11 w-11 shrink-0 rounded-full bg-gradient-to-r from-primary to-green-600 hover:from-primary/90 hover:to-green-600/90 shadow-md hover:shadow-lg transition-all disabled:opacity-50"
            title="Send message"
          >
            <Send className="h-5 w-5" />
          </Button>
        )}
      </form>

      {/* Feature hint */}
      <div className="mt-2 flex items-center justify-center gap-4 text-[10px] text-muted-foreground/60">
        <span className="flex items-center gap-1"><Camera className="h-3 w-3" /> Photo Analysis</span>
        <span className="flex items-center gap-1"><Mic className="h-3 w-3" /> Voice Input</span>
        <span className="flex items-center gap-1 opacity-60"><Video className="h-3 w-3" /> Live Video (Coming Soon)</span>
      </div>
    </div>
  )
}
