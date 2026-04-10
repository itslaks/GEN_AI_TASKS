'use client'

import { cn } from '@/lib/utils'
import { 
  Cloud, Droplets, Wind, Thermometer, Sun, CloudRain,
  Sprout, Calendar, Clock, MapPin,
  Building2, CreditCard, FileText, Phone, CheckCircle2,
  Bug, Shield, AlertTriangle, Leaf,
  TrendingUp, TrendingDown, Store, Package,
  Beaker, Layers, Wheat,
} from 'lucide-react'

// ─── Weather Infographic Card ──────────────────────────────────────────────────

interface WeatherCardProps {
  data: {
    location?: string
    temperature?: number
    humidity?: number
    condition?: string
    rainfall_probability?: number
    wind_speed?: number
    farming_advisory?: string
    forecast_3day?: string
  }
}

export function WeatherInfoCard({ data }: WeatherCardProps) {
  const temp = data.temperature || 30
  const humidity = data.humidity || 65
  const rainfall = data.rainfall_probability || 30
  const isRainy = (data.condition || '').toLowerCase().includes('rain')

  return (
    <div className="rounded-2xl overflow-hidden mt-2 border border-border bg-gradient-to-br from-sky-50 via-blue-50 to-emerald-50 dark:from-sky-950/30 dark:via-blue-950/20 dark:to-emerald-950/20">
      {/* Header */}
      <div className="bg-gradient-to-r from-sky-500 to-blue-600 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-white">
          {isRainy ? <CloudRain className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
          <span className="font-semibold text-sm">Weather Report</span>
        </div>
        {data.location && (
          <div className="flex items-center gap-1 text-white/80 text-xs">
            <MapPin className="h-3 w-3" />
            <span>{data.location}</span>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="p-4 space-y-4">
        {/* Temperature & Condition */}
        <div className="flex items-center justify-between">
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold text-foreground">{temp}°</span>
            <span className="text-lg text-muted-foreground">C</span>
          </div>
          <div className="text-right">
            <p className="text-sm font-medium text-foreground">{data.condition || 'Clear'}</p>
            {data.forecast_3day && (
              <p className="text-xs text-muted-foreground mt-1">{data.forecast_3day}</p>
            )}
          </div>
        </div>

        {/* Metrics Row */}
        <div className="grid grid-cols-3 gap-3">
          {/* Humidity */}
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 text-center">
            <Droplets className="h-5 w-5 text-blue-500 mx-auto mb-1" />
            <p className="text-xs text-muted-foreground">Humidity</p>
            <p className="text-lg font-bold text-foreground">{humidity}%</p>
            <div className="mt-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div 
                className="h-full bg-blue-500 rounded-full transition-all duration-1000" 
                style={{ width: `${humidity}%` }} 
              />
            </div>
          </div>

          {/* Rainfall */}
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 text-center">
            <CloudRain className="h-5 w-5 text-indigo-500 mx-auto mb-1" />
            <p className="text-xs text-muted-foreground">Rainfall</p>
            <p className="text-lg font-bold text-foreground">{rainfall}%</p>
            <div className="mt-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div 
                className="h-full bg-indigo-500 rounded-full transition-all duration-1000" 
                style={{ width: `${rainfall}%` }} 
              />
            </div>
          </div>

          {/* Wind */}
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 text-center">
            <Wind className="h-5 w-5 text-teal-500 mx-auto mb-1" />
            <p className="text-xs text-muted-foreground">Wind</p>
            <p className="text-lg font-bold text-foreground">{data.wind_speed || 10}</p>
            <p className="text-[10px] text-muted-foreground">km/h</p>
          </div>
        </div>

        {/* Farming Advisory */}
        {data.farming_advisory && (
          <div className="bg-primary/10 rounded-xl px-4 py-3 flex items-start gap-2">
            <Sprout className="h-4 w-4 text-primary mt-0.5 shrink-0" />
            <p className="text-sm text-foreground leading-relaxed">{data.farming_advisory}</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Crop Calendar Infographic Card ────────────────────────────────────────────

interface CropCalendarCardProps {
  data: {
    crop?: string
    season?: string
    region?: string
    sowing_period?: string
    harvesting_period?: string
    growing_duration?: string
    activities?: Array<{ phase: string; timing: string; task: string }>
    tips?: string
  }
}

export function CropCalendarCard({ data }: CropCalendarCardProps) {
  const phaseColors = [
    'from-amber-400 to-orange-500',
    'from-green-400 to-emerald-500',
    'from-emerald-400 to-teal-500',
    'from-teal-400 to-cyan-500',
    'from-yellow-400 to-amber-500',
  ]

  return (
    <div className="rounded-2xl overflow-hidden mt-2 border border-border bg-gradient-to-br from-green-50 via-emerald-50 to-lime-50 dark:from-green-950/30 dark:via-emerald-950/20 dark:to-lime-950/20">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-600 to-emerald-600 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-white">
          <Calendar className="h-5 w-5" />
          <span className="font-semibold text-sm">Crop Calendar</span>
        </div>
        <div className="flex items-center gap-3 text-white/80 text-xs">
          {data.crop && <span className="bg-white/20 px-2 py-0.5 rounded-full">{data.crop}</span>}
          {data.season && <span className="bg-white/20 px-2 py-0.5 rounded-full">{data.season}</span>}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-4">
        {/* Key Dates */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 text-center">
            <Sprout className="h-5 w-5 text-green-500 mx-auto mb-1" />
            <p className="text-xs text-muted-foreground">Sowing</p>
            <p className="text-sm font-semibold text-foreground">{data.sowing_period || 'Jun-Jul'}</p>
          </div>
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 text-center">
            <Clock className="h-5 w-5 text-emerald-500 mx-auto mb-1" />
            <p className="text-xs text-muted-foreground">Duration</p>
            <p className="text-sm font-semibold text-foreground">{data.growing_duration || '90-120 days'}</p>
          </div>
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 text-center">
            <Wheat className="h-5 w-5 text-amber-500 mx-auto mb-1" />
            <p className="text-xs text-muted-foreground">Harvest</p>
            <p className="text-sm font-semibold text-foreground">{data.harvesting_period || 'Oct-Nov'}</p>
          </div>
        </div>

        {/* Timeline */}
        {data.activities && data.activities.length > 0 && (
          <div className="space-y-0">
            {data.activities.map((activity, idx) => (
              <div key={idx} className="flex gap-3 items-start">
                {/* Timeline Dot & Line */}
                <div className="flex flex-col items-center">
                  <div className={cn(
                    'h-3 w-3 rounded-full mt-1.5 bg-gradient-to-r',
                    phaseColors[idx % phaseColors.length]
                  )} />
                  {idx < (data.activities?.length || 0) - 1 && (
                    <div className="w-0.5 h-full min-h-[2rem] bg-border" />
                  )}
                </div>
                {/* Content */}
                <div className="pb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-primary">{activity.phase}</span>
                    <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{activity.timing}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{activity.task}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Tips */}
        {data.tips && (
          <div className="bg-primary/10 rounded-xl px-4 py-3 flex items-start gap-2">
            <Leaf className="h-4 w-4 text-primary mt-0.5 shrink-0" />
            <p className="text-xs text-foreground leading-relaxed">{data.tips}</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Government Scheme Infographic Card ────────────────────────────────────────

interface SchemeCardProps {
  data: {
    name?: string
    benefit?: string
    eligibility?: string
    howToApply?: string
    documents?: string
    deadline?: string
    helpline?: string
  }
}

export function SchemeInfoCard({ data }: SchemeCardProps) {
  return (
    <div className="rounded-2xl overflow-hidden mt-2 border border-border bg-gradient-to-br from-amber-50 via-orange-50 to-yellow-50 dark:from-amber-950/30 dark:via-orange-950/20 dark:to-yellow-950/20">
      {/* Header */}
      <div className="bg-gradient-to-r from-amber-600 to-orange-600 px-4 py-3">
        <div className="flex items-center gap-2 text-white">
          <Building2 className="h-5 w-5" />
          <span className="font-semibold text-sm">Government Scheme</span>
        </div>
        {data.name && (
          <p className="text-white/90 text-lg font-bold mt-1">{data.name}</p>
        )}
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Benefit Highlight */}
        {data.benefit && (
          <div className="bg-gradient-to-r from-green-100 to-emerald-100 dark:from-green-900/20 dark:to-emerald-900/20 rounded-xl p-4 text-center">
            <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Benefit</p>
            <p className="text-lg font-bold text-green-700 dark:text-green-400">{data.benefit}</p>
          </div>
        )}

        {/* Details Grid */}
        <div className="space-y-2">
          {data.eligibility && (
            <div className="flex items-start gap-2.5 bg-white/60 dark:bg-white/5 rounded-xl p-3">
              <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-foreground">Eligibility</p>
                <p className="text-xs text-muted-foreground">{data.eligibility}</p>
              </div>
            </div>
          )}

          {data.howToApply && (
            <div className="flex items-start gap-2.5 bg-white/60 dark:bg-white/5 rounded-xl p-3">
              <FileText className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-foreground">How to Apply</p>
                <p className="text-xs text-muted-foreground">{data.howToApply}</p>
              </div>
            </div>
          )}

          {data.documents && (
            <div className="flex items-start gap-2.5 bg-white/60 dark:bg-white/5 rounded-xl p-3">
              <CreditCard className="h-4 w-4 text-purple-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-foreground">Documents Required</p>
                <p className="text-xs text-muted-foreground">{data.documents}</p>
              </div>
            </div>
          )}
        </div>

        {/* Helpline */}
        {data.helpline && (
          <div className="bg-primary/10 rounded-xl px-4 py-3 flex items-center gap-2">
            <Phone className="h-4 w-4 text-primary shrink-0" />
            <p className="text-xs text-foreground">Helpline: <span className="font-semibold">{data.helpline}</span></p>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Pest Solution Infographic Card ────────────────────────────────────────────

interface PestCardProps {
  data: {
    crop?: string
    symptoms_reported?: string
    possible_issue?: string
    severity?: string
    organic_solution?: string
    chemical_solution?: string
    prevention?: string
    safety_note?: string
    when_to_apply?: string
    cost_estimate?: string
  }
}

export function PestSolutionCard({ data }: PestCardProps) {
  const severityColors: Record<string, string> = {
    'Low': 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    'Moderate': 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    'High': 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    'Severe': 'bg-red-200 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  }

  return (
    <div className="rounded-2xl overflow-hidden mt-2 border border-border bg-gradient-to-br from-red-50 via-orange-50 to-amber-50 dark:from-red-950/30 dark:via-orange-950/20 dark:to-amber-950/20">
      {/* Header */}
      <div className="bg-gradient-to-r from-red-500 to-orange-500 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-white">
          <Bug className="h-5 w-5" />
          <span className="font-semibold text-sm">Pest & Disease Analysis</span>
        </div>
        {data.severity && (
          <span className={cn(
            'text-xs px-2 py-0.5 rounded-full font-medium',
            severityColors[data.severity] || 'bg-gray-100 text-gray-600'
          )}>
            {data.severity}
          </span>
        )}
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Diagnosis */}
        {data.possible_issue && (
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3">
            <p className="text-xs font-semibold text-foreground mb-1">🔍 Diagnosis</p>
            <p className="text-xs text-muted-foreground">{data.possible_issue}</p>
          </div>
        )}

        {/* Treatment Comparison */}
        <div className="grid grid-cols-2 gap-2">
          {data.organic_solution && (
            <div className="bg-green-50 dark:bg-green-900/20 rounded-xl p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <Leaf className="h-4 w-4 text-green-600" />
                <p className="text-xs font-semibold text-green-700 dark:text-green-400">Organic</p>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{data.organic_solution}</p>
            </div>
          )}
          {data.chemical_solution && (
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <Beaker className="h-4 w-4 text-blue-600" />
                <p className="text-xs font-semibold text-blue-700 dark:text-blue-400">Chemical</p>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{data.chemical_solution}</p>
            </div>
          )}
        </div>

        {/* Prevention */}
        {data.prevention && (
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 flex items-start gap-2">
            <Shield className="h-4 w-4 text-primary mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-foreground">Prevention</p>
              <p className="text-xs text-muted-foreground">{data.prevention}</p>
            </div>
          </div>
        )}

        {/* Safety Warning */}
        {data.safety_note && (
          <div className="bg-amber-100/80 dark:bg-amber-900/20 rounded-xl px-4 py-3 flex items-start gap-2 border border-amber-200 dark:border-amber-800">
            <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
            <p className="text-xs text-amber-800 dark:text-amber-300 font-medium">{data.safety_note}</p>
          </div>
        )}

        {/* Cost & Timing */}
        {(data.cost_estimate || data.when_to_apply) && (
          <div className="flex gap-2 text-xs">
            {data.when_to_apply && (
              <span className="bg-muted px-2.5 py-1 rounded-full text-muted-foreground">⏰ {data.when_to_apply}</span>
            )}
            {data.cost_estimate && (
              <span className="bg-muted px-2.5 py-1 rounded-full text-muted-foreground">💰 {data.cost_estimate}</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Market Price Infographic Card ─────────────────────────────────────────────

interface MarketPriceCardProps {
  data: {
    crop?: string
    market_state?: string
    msp?: string
    market_price?: string
    price_trend?: string
    best_time_to_sell?: string
    storage_tip?: string
    nearby_mandis?: string
  }
}

export function MarketPriceCard({ data }: MarketPriceCardProps) {
  const isAboveMSP = (data.price_trend || '').includes('Above')
  
  return (
    <div className="rounded-2xl overflow-hidden mt-2 border border-border bg-gradient-to-br from-violet-50 via-purple-50 to-indigo-50 dark:from-violet-950/30 dark:via-purple-950/20 dark:to-indigo-950/20">
      {/* Header */}
      <div className="bg-gradient-to-r from-violet-600 to-purple-600 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-white">
          <Store className="h-5 w-5" />
          <span className="font-semibold text-sm">Market Price</span>
        </div>
        {data.crop && (
          <span className="text-white/90 text-xs bg-white/20 px-2 py-0.5 rounded-full">{data.crop}</span>
        )}
        {data.market_state && (
          <span className="text-white/70 text-xs">{data.market_state}</span>
        )}
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Price Display */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 text-center">
            <p className="text-xs text-muted-foreground mb-1">MSP</p>
            <p className="text-xl font-bold text-foreground">{data.msp || '₹2,000'}</p>
          </div>
          <div className={cn(
            'rounded-xl p-3 text-center',
            isAboveMSP ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'
          )}>
            <p className="text-xs text-muted-foreground mb-1">Market Price</p>
            <p className="text-xl font-bold text-foreground">{data.market_price || '₹2,200'}</p>
          </div>
        </div>

        {/* Trend */}
        {data.price_trend && (
          <div className={cn(
            'rounded-xl px-4 py-2 flex items-center justify-center gap-2 text-sm font-semibold',
            isAboveMSP 
              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' 
              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
          )}>
            {isAboveMSP ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
            <span>{data.price_trend}</span>
          </div>
        )}

        {/* Advice */}
        <div className="space-y-2">
          {data.best_time_to_sell && (
            <div className="flex items-start gap-2 bg-white/60 dark:bg-white/5 rounded-xl p-3">
              <Clock className="h-4 w-4 text-purple-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-foreground">Best Time to Sell</p>
                <p className="text-xs text-muted-foreground">{data.best_time_to_sell}</p>
              </div>
            </div>
          )}
          {data.storage_tip && (
            <div className="flex items-start gap-2 bg-white/60 dark:bg-white/5 rounded-xl p-3">
              <Package className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-foreground">Storage Tip</p>
                <p className="text-xs text-muted-foreground">{data.storage_tip}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Soil Health Infographic Card ──────────────────────────────────────────────

interface SoilCardProps {
  data: {
    soil_type?: string
    crop?: string
    issue?: string
    nitrogen?: string
    phosphorus?: string
    potassium?: string
    ph_recommendation?: string
    organic_matter?: string
    organic_option?: string
    chemical_option?: string
    green_manure?: string
    improvement_tip?: string
  }
}

export function SoilHealthCard({ data }: SoilCardProps) {
  // Parse numeric values for gauges
  const extractNum = (s: string | undefined) => parseInt((s || '0').replace(/[^0-9]/g, '')) || 0
  const nVal = extractNum(data.nitrogen)
  const pVal = extractNum(data.phosphorus)
  const kVal = extractNum(data.potassium)
  const maxNPK = 150

  return (
    <div className="rounded-2xl overflow-hidden mt-2 border border-border bg-gradient-to-br from-amber-50 via-yellow-50 to-lime-50 dark:from-amber-950/30 dark:via-yellow-950/20 dark:to-lime-950/20">
      {/* Header */}
      <div className="bg-gradient-to-r from-amber-700 to-yellow-600 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-white">
          <Layers className="h-5 w-5" />
          <span className="font-semibold text-sm">Soil Health Report</span>
        </div>
        <div className="flex items-center gap-2 text-white/80 text-xs">
          {data.soil_type && <span className="bg-white/20 px-2 py-0.5 rounded-full">{data.soil_type}</span>}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-4">
        {/* NPK Gauges */}
        <div className="grid grid-cols-3 gap-3">
          {/* Nitrogen */}
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 text-center">
            <p className="text-xs font-semibold text-blue-600 mb-1">N</p>
            <p className="text-xs text-muted-foreground mb-1">Nitrogen</p>
            <div className="relative h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full transition-all duration-1000" style={{ width: `${Math.min((nVal / maxNPK) * 100, 100)}%` }} />
            </div>
            <p className="text-sm font-bold text-foreground mt-1">{data.nitrogen || '0'}</p>
          </div>

          {/* Phosphorus */}
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 text-center">
            <p className="text-xs font-semibold text-green-600 mb-1">P</p>
            <p className="text-xs text-muted-foreground mb-1">Phosphorus</p>
            <div className="relative h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div className="h-full bg-green-500 rounded-full transition-all duration-1000" style={{ width: `${Math.min((pVal / maxNPK) * 100, 100)}%` }} />
            </div>
            <p className="text-sm font-bold text-foreground mt-1">{data.phosphorus || '0'}</p>
          </div>

          {/* Potassium */}
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 text-center">
            <p className="text-xs font-semibold text-orange-600 mb-1">K</p>
            <p className="text-xs text-muted-foreground mb-1">Potassium</p>
            <div className="relative h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div className="h-full bg-orange-500 rounded-full transition-all duration-1000" style={{ width: `${Math.min((kVal / maxNPK) * 100, 100)}%` }} />
            </div>
            <p className="text-sm font-bold text-foreground mt-1">{data.potassium || '0'}</p>
          </div>
        </div>

        {/* pH */}
        {data.ph_recommendation && (
          <div className="bg-white/60 dark:bg-white/5 rounded-xl p-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Beaker className="h-4 w-4 text-purple-500" />
              <span className="text-xs font-semibold text-foreground">pH Level</span>
            </div>
            <span className="text-xs text-muted-foreground">{data.ph_recommendation}</span>
          </div>
        )}

        {/* Treatment Options */}
        <div className="grid grid-cols-2 gap-2">
          {data.organic_option && (
            <div className="bg-green-50 dark:bg-green-900/20 rounded-xl p-3">
              <div className="flex items-center gap-1.5 mb-1">
                <Leaf className="h-3.5 w-3.5 text-green-600" />
                <p className="text-xs font-semibold text-green-700 dark:text-green-400">Organic</p>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{data.organic_option}</p>
            </div>
          )}
          {data.chemical_option && (
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-3">
              <div className="flex items-center gap-1.5 mb-1">
                <Beaker className="h-3.5 w-3.5 text-blue-600" />
                <p className="text-xs font-semibold text-blue-700 dark:text-blue-400">Chemical</p>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{data.chemical_option}</p>
            </div>
          )}
        </div>

        {/* Improvement Tip */}
        {data.improvement_tip && (
          <div className="bg-primary/10 rounded-xl px-4 py-3 flex items-start gap-2">
            <Sprout className="h-4 w-4 text-primary mt-0.5 shrink-0" />
            <p className="text-xs text-foreground leading-relaxed">{data.improvement_tip}</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Card Selector ─────────────────────────────────────────────────────────────

interface InfographicCardProps {
  toolName: string
  data: Record<string, unknown>
}

export function InfographicCard({ toolName, data }: InfographicCardProps) {
  switch (toolName) {
    case 'getWeatherInfo':
      return <WeatherInfoCard data={data as WeatherCardProps['data']} />
    case 'getCropCalendar':
      return <CropCalendarCard data={data as CropCalendarCardProps['data']} />
    case 'getSchemeInfo':
      return <SchemeInfoCard data={data as SchemeCardProps['data']} />
    case 'getPestSolution':
      return <PestSolutionCard data={data as PestCardProps['data']} />
    case 'getMarketPrice':
      return <MarketPriceCard data={data as MarketPriceCardProps['data']} />
    case 'getSoilRecommendation':
      return <SoilHealthCard data={data as SoilCardProps['data']} />
    default:
      return <GenericInfoCard toolName={toolName} data={data} />
  }
}

// ─── Generic Fallback Card ─────────────────────────────────────────────────────

function GenericInfoCard({ toolName, data }: { toolName: string; data: Record<string, unknown> }) {
  return (
    <div className="rounded-2xl overflow-hidden mt-2 border border-border bg-secondary/30">
      <div className="bg-primary/80 px-4 py-2">
        <span className="text-primary-foreground text-xs font-semibold uppercase tracking-wide">{toolName.replace(/([A-Z])/g, ' $1').trim()}</span>
      </div>
      <div className="p-3 space-y-1.5 text-sm">
        {Object.entries(data).map(([key, value]) => {
          if (key === 'state' && value === 'ready') return null
          if (key === 'state' && value === 'loading') return null
          if (typeof value === 'object') return null
          return (
            <div key={key} className="flex gap-2">
              <span className="text-muted-foreground capitalize text-xs whitespace-nowrap">{key.replace(/_/g, ' ')}:</span>
              <span className="text-foreground text-xs font-medium">{String(value)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
