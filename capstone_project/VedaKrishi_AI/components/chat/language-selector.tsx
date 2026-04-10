'use client'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Globe } from 'lucide-react'
import { SUPPORTED_LANGUAGES, type LanguageCode } from '@/lib/languages'

// Pre-split to avoid TypeScript over-narrowing during .filter()
const indianLangs = SUPPORTED_LANGUAGES.filter(l => l.group === 'indian')
const intlLangs   = SUPPORTED_LANGUAGES.filter(l => l.group === 'international')

export type { LanguageCode }
export { SUPPORTED_LANGUAGES }

interface LanguageSelectorProps {
  value: LanguageCode
  onChange: (value: LanguageCode) => void
}

export function LanguageSelector({ value, onChange }: LanguageSelectorProps) {
  const selected = SUPPORTED_LANGUAGES.find(l => l.code === value)

  return (
    <Select value={value} onValueChange={(v) => onChange(v as LanguageCode)}>
      <SelectTrigger className="w-auto gap-2 bg-secondary/50 border-border hover:bg-secondary h-9">
        <Globe className="h-4 w-4 text-muted-foreground shrink-0" />
        <SelectValue>
          <span className="flex items-center gap-1.5">
            <span>{selected?.flag}</span>
            <span>{selected?.nativeName ?? selected?.name}</span>
          </span>
        </SelectValue>
      </SelectTrigger>
      <SelectContent className="max-h-80">
        <div className="px-2 py-1 text-[10px] text-muted-foreground uppercase tracking-wide font-medium">
          Indian Languages
        </div>
        {indianLangs.map((lang) => (
          <SelectItem key={lang.code} value={lang.code}>
            <span className="flex items-center gap-2">
              <span>{lang.flag}</span>
              <span className="font-medium">{lang.nativeName}</span>
              <span className="text-muted-foreground text-xs">({lang.name})</span>
            </span>
          </SelectItem>
        ))}
        <div className="px-2 py-1 text-[10px] text-muted-foreground uppercase tracking-wide font-medium mt-1 border-t border-border pt-2">
          International
        </div>
        {intlLangs.map((lang) => (
          <SelectItem key={lang.code} value={lang.code}>
            <span className="flex items-center gap-2">
              <span>{lang.flag}</span>
              <span className="font-medium">{lang.nativeName}</span>
              <span className="text-muted-foreground text-xs">({lang.name})</span>
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
