'use client'

import { useState, useRef, useCallback } from 'react'

interface UseTextToSpeechOptions {
  language?: string
}

export function useTextToSpeech({ language = 'hi' }: UseTextToSpeechOptions = {}) {
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const currentTextRef = useRef<string>('')

  const speak = useCallback(async (text: string) => {
    if (!text.trim()) return

    // Stop any current playback
    stop()

    setIsLoading(true)
    setError(null)
    currentTextRef.current = text

    try {
      const response = await fetch('/api/text-to-speech', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text, language }),
      })

      if (!response.ok) {
        throw new Error('Failed to generate speech')
      }

      const audioBlob = await response.blob()
      const audioUrl = URL.createObjectURL(audioBlob)

      // Create and play audio
      const audio = new Audio(audioUrl)
      audioRef.current = audio

      audio.onplay = () => {
        setIsSpeaking(true)
        setIsLoading(false)
      }

      audio.onended = () => {
        setIsSpeaking(false)
        URL.revokeObjectURL(audioUrl)
      }

      audio.onerror = () => {
        setIsSpeaking(false)
        setIsLoading(false)
        setError('Failed to play audio')
        URL.revokeObjectURL(audioUrl)
      }

      await audio.play()
    } catch (err) {
      console.error('Text-to-speech error:', err)
      setError('Failed to generate speech. Please try again.')
      setIsLoading(false)
    }
  }, [language])

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      audioRef.current = null
    }
    setIsSpeaking(false)
    setIsLoading(false)
  }, [])

  const toggle = useCallback(async (text: string) => {
    if (isSpeaking) {
      stop()
    } else {
      await speak(text)
    }
  }, [isSpeaking, speak, stop])

  return {
    isSpeaking,
    isLoading,
    error,
    speak,
    stop,
    toggle,
  }
}
