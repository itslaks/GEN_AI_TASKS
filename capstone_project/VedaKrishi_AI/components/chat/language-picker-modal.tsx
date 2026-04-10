'use client'

import { useState } from 'react'
import { Leaf, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import { type LanguageCode } from './language-selector'

interface LanguagePickerProps {
  onSelect: (language: LanguageCode) => void
}

// Quick-pick languages shown as large buttons
const PRIMARY_LANGUAGES = [
  { code: 'en' as LanguageCode, label: 'English', flag: '🌐', sub: 'English' },
  { code: 'hi' as LanguageCode, label: 'हिन्दी', flag: '🇮🇳', sub: 'Hindi' },
  { code: 'ta' as LanguageCode, label: 'தமிழ்', flag: '🇮🇳', sub: 'Tamil' },
  { code: 'te' as LanguageCode, label: 'తెలుగు', flag: '🇮🇳', sub: 'Telugu' },
  { code: 'kn' as LanguageCode, label: 'ಕನ್ನಡ', flag: '🇮🇳', sub: 'Kannada' },
  { code: 'ml' as LanguageCode, label: 'മലയാളം', flag: '🇮🇳', sub: 'Malayalam' },
]

const MORE_LANGUAGES = [
  { code: 'bn' as LanguageCode, label: 'বাংলা', sub: 'Bengali' },
  { code: 'mr' as LanguageCode, label: 'मराठी', sub: 'Marathi' },
  { code: 'gu' as LanguageCode, label: 'ગુજરાતી', sub: 'Gujarati' },
  { code: 'pa' as LanguageCode, label: 'ਪੰਜਾਬੀ', sub: 'Punjabi' },
  { code: 'or' as LanguageCode, label: 'ଓଡ଼ିଆ', sub: 'Odia' },
  { code: 'as' as LanguageCode, label: 'অসমীয়া', sub: 'Assamese' },
  { code: 'de' as LanguageCode, label: 'Deutsch', sub: 'German' },
  { code: 'fr' as LanguageCode, label: 'Français', sub: 'French' },
  { code: 'es' as LanguageCode, label: 'Español', sub: 'Spanish' },
]

export function LanguagePickerModal({ onSelect }: LanguagePickerProps) {
  const [showMore, setShowMore] = useState(false)

  return (
    <div className="flex flex-col items-center justify-center min-h-full px-4 py-8 animate-in fade-in-0 slide-in-from-bottom-4 duration-500">
      {/* Bot Avatar */}
      <div className="relative mb-6">
        <div className="h-20 w-20 rounded-3xl bg-gradient-to-br from-primary via-green-500 to-emerald-600 flex items-center justify-center shadow-xl shadow-primary/25 animate-float">
          <Leaf className="h-10 w-10 text-white" />
        </div>
        <div className="absolute -bottom-1 -right-1 h-6 w-6 rounded-full bg-gradient-to-r from-amber-400 to-orange-500 flex items-center justify-center shadow-md">
          <Sparkles className="h-3.5 w-3.5 text-white" />
        </div>
      </div>

      {/* Greeting */}
      <div className="text-center mb-8 max-w-sm">
        <h2 className="text-xl font-bold text-foreground mb-2">
          Welcome to VedaKrishi AI 🌾
        </h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          I am your AI farming companion. Please choose your preferred language to get started.
        </p>
        <p className="text-xs text-muted-foreground/70 mt-1">
          आपकी भाषा चुनें · உங்கள் மொழியைத் தேர்ந்தெடுக்கவும் · మీ భాషను ఎంచుకోండి
        </p>
      </div>

      {/* Primary Language Buttons */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 w-full max-w-md mb-4">
        {PRIMARY_LANGUAGES.map((lang) => (
          <button
            key={lang.code}
            onClick={() => onSelect(lang.code)}
            className={cn(
              'flex flex-col items-center justify-center gap-1.5 px-4 py-4 rounded-2xl',
              'bg-card border-2 border-border',
              'hover:border-primary hover:bg-primary/5 hover:shadow-md hover:shadow-primary/10',
              'active:scale-95 transition-all duration-200 group cursor-pointer'
            )}
          >
            <span className="text-2xl leading-none">{lang.flag}</span>
            <span className="text-base font-semibold text-foreground group-hover:text-primary transition-colors">
              {lang.label}
            </span>
            <span className="text-[10px] text-muted-foreground">{lang.sub}</span>
          </button>
        ))}
      </div>

      {/* More Languages */}
      {!showMore ? (
        <button
          onClick={() => setShowMore(true)}
          className="text-sm text-primary hover:text-primary/80 underline underline-offset-4 transition-colors mt-2"
        >
          More languages →
        </button>
      ) : (
        <div className="w-full max-w-md animate-in fade-in-0 slide-in-from-top-2 duration-300">
          <p className="text-[10px] text-muted-foreground text-center uppercase tracking-wide mb-3">More Languages</p>
          <div className="grid grid-cols-3 gap-2">
            {MORE_LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => onSelect(lang.code)}
                className={cn(
                  'flex flex-col items-center justify-center gap-1 px-3 py-3 rounded-xl',
                  'bg-card border border-border text-center',
                  'hover:border-primary hover:bg-primary/5',
                  'active:scale-95 transition-all duration-200 cursor-pointer'
                )}
              >
                <span className="text-sm font-semibold text-foreground">{lang.label}</span>
                <span className="text-[10px] text-muted-foreground">{lang.sub}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Skip option */}
      <button
        onClick={() => onSelect('en')}
        className="mt-6 text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors"
      >
        Skip — Continue in English
      </button>
    </div>
  )
}
