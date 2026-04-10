'use client'

import { UIMessage } from 'ai'
import { cn } from '@/lib/utils'
import { Leaf, User, Volume2, VolumeX, Loader2, Copy, Check, Camera, Video } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTextToSpeech } from '@/hooks/use-text-to-speech'
import { InfographicCard } from '@/components/chat/infographic-cards'
import ReactMarkdown from 'react-markdown'
import { useState } from 'react'

interface ChatMessageProps {
  message: UIMessage
  language: string
}

function getMessageText(message: UIMessage): string {
  if (!message.parts || !Array.isArray(message.parts)) return ''
  return message.parts
    .filter((p): p is { type: 'text'; text: string } => p.type === 'text')
    .map((p) => p.text)
    .join('')
}

export function ChatMessage({ message, language }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const messageText = getMessageText(message)
  const { isSpeaking, isLoading: ttsLoading, toggle, stop } = useTextToSpeech({ language })
  const [copied, setCopied] = useState(false)

  const handleSpeakClick = () => {
    if (isSpeaking) {
      stop()
    } else {
      toggle(messageText)
    }
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(messageText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className={cn(
        'flex gap-3 px-4 py-4 animate-in fade-in-0 duration-300',
        isUser ? 'flex-row-reverse slide-in-from-right-4' : 'flex-row slide-in-from-left-4'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'flex h-9 w-9 shrink-0 items-center justify-center rounded-full shadow-md transition-transform hover:scale-105',
          isUser 
            ? 'bg-accent text-accent-foreground' 
            : 'bg-gradient-to-br from-primary to-green-600 text-primary-foreground'
        )}
      >
        {isUser ? <User className="h-5 w-5" /> : <Leaf className="h-5 w-5" />}
      </div>

      {/* Message Content */}
      <div
        className={cn(
          'flex flex-col gap-2 max-w-[85%] md:max-w-[75%]',
          isUser ? 'items-end' : 'items-start'
        )}
      >
        <div
          className={cn(
            'rounded-2xl px-4 py-3 shadow-sm',
            isUser
              ? 'bg-gradient-to-br from-primary to-green-700 text-primary-foreground rounded-tr-sm'
              : 'bg-card border border-border text-card-foreground rounded-tl-sm'
          )}
        >
          {message.parts?.map((part, index) => {
            if (part.type === 'text') {
              return (
                <div key={index} className={cn(
                  'prose prose-sm max-w-none',
                  isUser ? 'prose-invert' : 'dark:prose-invert'
                )}>
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
                      ul: ({ children }) => <ul className="mb-2 list-disc pl-4 space-y-1">{children}</ul>,
                      ol: ({ children }) => <ol className="mb-2 list-decimal pl-4 space-y-1">{children}</ol>,
                      li: ({ children }) => <li className="mb-0.5">{children}</li>,
                      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                      h1: ({ children }) => <h1 className="text-lg font-bold mb-2">{children}</h1>,
                      h2: ({ children }) => <h2 className="text-base font-bold mb-2">{children}</h2>,
                      h3: ({ children }) => <h3 className="text-sm font-bold mb-1">{children}</h3>,
                      code: ({ children }) => <code className="bg-muted/30 px-1 py-0.5 rounded text-xs">{children}</code>,
                    }}
                  >
                    {part.text}
                  </ReactMarkdown>
                </div>
              )
            }
            
            if (part.type === 'tool-invocation') {
              return (
                <ToolInvocationDisplay key={index} toolInvocation={part} />
              )
            }
            
            return null
          })}
        </div>

        {/* Action Buttons for assistant messages */}
        {!isUser && messageText && (
          <div className="flex items-center gap-1">
            {/* Voice playback */}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSpeakClick}
              disabled={ttsLoading}
              className="h-7 px-2 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-full"
            >
              {ttsLoading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : isSpeaking ? (
                <>
                  <VolumeX className="h-3.5 w-3.5 mr-1" />
                  <span className="text-[11px]">Stop</span>
                </>
              ) : (
                <>
                  <Volume2 className="h-3.5 w-3.5 mr-1" />
                  <span className="text-[11px]">Listen</span>
                </>
              )}
            </Button>

            {/* Copy */}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              className="h-7 px-2 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-full"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 mr-1 text-green-500" />
                  <span className="text-[11px] text-green-500">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5 mr-1" />
                  <span className="text-[11px]">Copy</span>
                </>
              )}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Image Analysis Message ────────────────────────────────────────────────────

interface ImageAnalysisMessageProps {
  imageUrl: string
  analysis: string
  language: string
}

export function ImageAnalysisMessage({ imageUrl, analysis, language }: ImageAnalysisMessageProps) {
  const { isSpeaking, isLoading: ttsLoading, toggle, stop } = useTextToSpeech({ language })
  const [copied, setCopied] = useState(false)

  return (
    <div className="flex gap-3 px-4 py-4 animate-in fade-in-0 slide-in-from-left-4 duration-300">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-green-600 text-primary-foreground shadow-md">
        <Camera className="h-5 w-5" />
      </div>
      <div className="flex flex-col gap-2 max-w-[85%] md:max-w-[75%] items-start">
        {/* Image Preview */}
        <div className="rounded-2xl overflow-hidden border border-border shadow-sm">
          <div className="bg-gradient-to-r from-primary to-green-600 px-4 py-2 flex items-center gap-2">
            <Camera className="h-4 w-4 text-white" />
            <span className="text-white text-xs font-semibold">Image Analysis</span>
            <span className="ml-auto text-white/60 text-[10px] flex items-center gap-1">
              <Video className="h-3 w-3" />
              Live video coming soon
            </span>
          </div>
          <div className="max-h-48 overflow-hidden">
            <img src={imageUrl} alt="Uploaded crop" className="w-full h-full object-cover" />
          </div>
          <div className="p-4 bg-card">
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <ReactMarkdown
                components={{
                  p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed text-sm">{children}</p>,
                  ul: ({ children }) => <ul className="mb-2 list-disc pl-4 text-sm">{children}</ul>,
                  strong: ({ children }) => <strong className="font-semibold text-primary">{children}</strong>,
                }}
              >
                {analysis}
              </ReactMarkdown>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => isSpeaking ? stop() : toggle(analysis)}
            disabled={ttsLoading}
            className="h-7 px-2 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-full"
          >
            {ttsLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> :
             isSpeaking ? <><VolumeX className="h-3.5 w-3.5 mr-1" /><span className="text-[11px]">Stop</span></> :
             <><Volume2 className="h-3.5 w-3.5 mr-1" /><span className="text-[11px]">Listen</span></>}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={async () => { await navigator.clipboard.writeText(analysis); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
            className="h-7 px-2 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-full"
          >
            {copied ? <><Check className="h-3.5 w-3.5 mr-1 text-green-500" /><span className="text-[11px] text-green-500">Copied</span></> :
             <><Copy className="h-3.5 w-3.5 mr-1" /><span className="text-[11px]">Copy</span></>}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── Tool Invocation Display with Infographic Cards ────────────────────────────

function ToolInvocationDisplay({ toolInvocation }: { toolInvocation: any }) {
  const { toolName, state } = toolInvocation

  const toolLabels: Record<string, string> = {
    getWeatherInfo: '🌤️ Weather Information',
    getCropCalendar: '📅 Crop Calendar',
    getSchemeInfo: '🏛️ Government Scheme',
    getPestSolution: '🔬 Pest Solution',
    getMarketPrice: '📊 Market Price',
    getSoilRecommendation: '🧪 Soil Health',
  }

  if (state === 'partial-call' || state === 'call') {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-2 animate-pulse">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Fetching {toolLabels[toolName] || toolName}...</span>
      </div>
    )
  }

  if (state === 'result' && toolInvocation.result) {
    const result = toolInvocation.result
    
    if (result.state === 'loading') {
      return (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-2 animate-pulse">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>{result.message || 'Loading...'}</span>
        </div>
      )
    }

    if (result.state === 'ready') {
      return <InfographicCard toolName={toolName} data={result} />
    }
  }

  return null
}
