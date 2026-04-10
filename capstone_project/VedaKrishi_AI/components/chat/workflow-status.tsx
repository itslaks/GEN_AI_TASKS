'use client'

import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { Search, Brain, Sparkles, CheckCircle2, Leaf, Database, Cloud } from 'lucide-react'

interface WorkflowStep {
  id: string
  label: string
  icon: typeof Search
  duration: number
}

const WORKFLOW_STEPS: WorkflowStep[] = [
  { id: 'receiving', label: 'Understanding your question', icon: Leaf, duration: 800 },
  { id: 'searching', label: 'Searching knowledge base', icon: Database, duration: 1200 },
  { id: 'analyzing', label: 'Analyzing information', icon: Brain, duration: 1000 },
  { id: 'generating', label: 'Generating response', icon: Sparkles, duration: 600 },
]

interface WorkflowStatusProps {
  isActive: boolean
  toolName?: string
  language?: string
}

const TOOL_LABELS: Record<string, { label: string; icon: typeof Search }> = {
  getWeatherInfo: { label: '🌤️ Fetching weather data', icon: Cloud },
  getCropCalendar: { label: '📅 Loading crop calendar', icon: Leaf },
  getSchemeInfo: { label: '🏛️ Looking up government schemes', icon: Database },
  getPestSolution: { label: '🔬 Analyzing pest symptoms', icon: Search },
  getMarketPrice: { label: '📊 Checking market prices', icon: Database },
  getSoilRecommendation: { label: '🧪 Analyzing soil data', icon: Search },
}

export function WorkflowStatus({ isActive, toolName, language }: WorkflowStatusProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (!isActive) {
      setCurrentStep(0)
      setCompletedSteps(new Set())
      return
    }

    let stepIndex = 0
    const advanceStep = () => {
      if (stepIndex < WORKFLOW_STEPS.length - 1) {
        setCompletedSteps(prev => new Set([...prev, stepIndex]))
        stepIndex++
        setCurrentStep(stepIndex)
      }
    }

    // Auto-advance through steps
    const timers: NodeJS.Timeout[] = []
    let accumulated = 0
    WORKFLOW_STEPS.forEach((step, idx) => {
      if (idx > 0) {
        accumulated += WORKFLOW_STEPS[idx - 1].duration
        timers.push(setTimeout(advanceStep, accumulated))
      }
    })

    return () => {
      timers.forEach(clearTimeout)
    }
  }, [isActive])

  if (!isActive) return null

  const toolInfo = toolName ? TOOL_LABELS[toolName] : null

  return (
    <div className="flex gap-3 px-4 py-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
        <Leaf className="h-5 w-5 text-primary animate-pulse" />
      </div>

      <div className="flex-1 space-y-3">
        {/* Workflow Steps */}
        <div className="flex flex-col gap-2">
          {WORKFLOW_STEPS.map((step, idx) => {
            const isCompleted = completedSteps.has(idx)
            const isCurrent = currentStep === idx
            const isPending = !isCompleted && !isCurrent
            const StepIcon = isCompleted ? CheckCircle2 : step.icon

            return (
              <div
                key={step.id}
                className={cn(
                  'flex items-center gap-2.5 text-sm transition-all duration-300',
                  isCompleted && 'text-primary/60',
                  isCurrent && 'text-primary font-medium',
                  isPending && 'text-muted-foreground/40'
                )}
              >
                <div className={cn(
                  'flex h-6 w-6 items-center justify-center rounded-full transition-all duration-300',
                  isCompleted && 'bg-primary/10',
                  isCurrent && 'bg-primary/20 ring-2 ring-primary/30',
                  isPending && 'bg-muted/30'
                )}>
                  <StepIcon className={cn(
                    'h-3.5 w-3.5 transition-all duration-300',
                    isCurrent && 'animate-pulse',
                    isCompleted && 'text-primary'
                  )} />
                </div>
                <span>{step.label}</span>
                {isCurrent && (
                  <div className="flex gap-1 ml-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Active Tool Indicator */}
        {toolInfo && (
          <div className="flex items-center gap-2 text-sm text-accent font-medium bg-accent/10 rounded-lg px-3 py-2 mt-2 animate-in fade-in duration-200">
            <toolInfo.icon className="h-4 w-4 animate-spin-slow" />
            <span>{toolInfo.label}</span>
          </div>
        )}
      </div>
    </div>
  )
}
