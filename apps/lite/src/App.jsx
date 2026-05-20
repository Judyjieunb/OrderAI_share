import React, { useState } from 'react'
import {
  TrendingUp, LineChart, Shirt, ShoppingCart, BarChart2,
  Hexagon, Loader2,
} from 'lucide-react'
import { useAuth } from './contexts/AuthContext.jsx'
import { useBrandSeason } from './contexts/BrandSeasonContext.jsx'
import SeasonClosing from './components/SeasonClosing.jsx'
import Dashboard from './components/Dashboard.jsx'
import StyleMapping from './components/StyleMapping.jsx'
import OrderSuggest from './components/OrderSuggest.jsx'
import SizeAssortment from './components/SizeAssortment.jsx'

// Lite — Full(src/App.jsx) 골격 그대로 복제. Step 0(Brand Index Setup)만 제거.
// 5개 화면 (SeasonClosing/Dashboard/StyleMapping/OrderSuggest/SizeAssortment)은
// Step 7에서 Full로부터 복제·변형 후 채운다 (현재는 Placeholder).

const steps = [
  { id: 'step1', label: 'Step 1', title: 'Sales Performance', desc: '전 시즌 마감판매 실적을 카테고리·아이템·스타일 단위로 진단합니다.', icon: TrendingUp },
  { id: 'step2', label: 'Step 2', title: 'Case Study', desc: '전 시즌 스타일별 실적추이를 주차별로 분석하여, 우리가 놓친 기회비용은 없었는지 점검합니다.', icon: LineChart },
  { id: 'step3', label: 'Step 3', title: 'Style Match', desc: '과거 스타일과 신규 스타일 간 ML유사도 매핑 결과를 확인 하고 확정해주세요. 다음 Step4 발주수량 제안에 유사스타일 실적이 활용됩니다.', icon: Shirt },
  { id: 'step4', label: 'Step 4', title: 'Order Suggest', desc: '유사스타일 잠재수요 및 기회비용 계산을 바탕으로 스타일별 발주추천 수량을 검토합니다.', icon: ShoppingCart },
  { id: 'step5', label: 'Step 5', title: 'Size Assortment', desc: '컬러별 사이즈 아소트를 최적화하여 최종 사이즈별 발주 수량을 산출합니다.', icon: BarChart2 },
]


export default function App() {
  const { user, isLoading } = useAuth()
  const { brand, season } = useBrandSeason()
  const [activeStep, setActiveStep] = useState('step1')

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">DCS AI 인증 정보를 확인하고 있습니다...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center bg-white rounded-xl shadow-lg p-8 max-w-md">
          <p className="text-slate-700 font-medium mb-2">인증 정보 없음</p>
          <p className="text-slate-500 text-sm">DCS AI에서 인증 정보를 받지 못했습니다.<br/>DCS AI 포털을 통해 접속해 주세요.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* Header + Navigation (sticky together) */}
      <div className="sticky top-0 z-50">
        <header className="bg-slate-900 text-white shadow-lg">
          <div className="max-w-[1400px] mx-auto px-8 py-[34px]">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="relative flex items-center justify-center w-10 h-10">
                  <Hexagon className="w-10 h-10 text-indigo-400 fill-indigo-500/10 stroke-[1.2]" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-1.5 h-1.5 bg-white rounded-full shadow-[0_0_8px_white]" />
                  </div>
                </div>
                <h1 className="text-3xl font-bold tracking-tight text-slate-100">
                  Initial Order Simulator <span className="text-xs font-normal text-slate-400 ml-1 opacity-70">v1.0</span>
                </h1>
              </div>
              <BrandSeasonSelector />
            </div>
          </div>
        </header>

        {/* Navigation Tabs */}
        <nav className="bg-white border-b border-gray-200 shadow-sm">
          <div className="max-w-[1400px] mx-auto px-8">
            <div className="flex items-center space-x-6 overflow-x-auto no-scrollbar">
              {steps.map((step) => {
                const isActive = activeStep === step.id
                return (
                  <button
                    key={step.id}
                    onClick={() => setActiveStep(step.id)}
                    className={`relative py-4 text-sm font-medium transition-all duration-200 border-b-2 flex items-center gap-2 whitespace-nowrap
                      ${isActive
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-800 hover:border-gray-300'
                      }`}
                  >
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${isActive ? 'bg-blue-50 text-blue-700' : 'bg-gray-100 text-gray-400'}`}>
                      {step.label}
                    </span>
                    <span>{step.title}</span>
                  </button>
                )
              })}
            </div>
          </div>
        </nav>
      </div>

      {/* Content */}
      <main className="max-w-[1400px] mx-auto px-8 py-8 min-h-[calc(100vh-130px)]">
        <PageHeader step={steps.find(s => s.id === activeStep)} />
        {activeStep === 'step1' && <SeasonClosing />}
        {activeStep === 'step2' && <Dashboard />}
        {activeStep === 'step3' && <StyleMapping />}
        {activeStep === 'step4' && <OrderSuggest />}
        {activeStep === 'step5' && <SizeAssortment />}
      </main>
    </div>
  )
}

function PageHeader({ step }) {
  if (!step) return null
  const Icon = step.icon
  return (
    <header className="mb-8">
      <div className="flex items-center gap-3 mb-2">
        <Icon className="w-8 h-8 text-blue-600" />
        <h1 className="text-2xl font-bold text-gray-900">{step.title}</h1>
      </div>
      <p className="text-sm text-gray-500 ml-11">{step.desc}</p>
    </header>
  )
}

function BrandSeasonSelector() {
  const { brand, season, brands, seasons, setBrand, setSeason, loading } = useBrandSeason()

  if (loading) {
    return (
      <div className="text-xs text-slate-400 flex items-center gap-2">
        <Loader2 className="w-3 h-3 animate-spin" />
        브랜드 권한 로드 중…
      </div>
    )
  }

  if (!brands.length) {
    return <div className="text-xs text-amber-300">조회 가능한 브랜드 없음</div>
  }

  return (
    <div className="flex items-center gap-2">
      <select
        value={brand}
        onChange={(e) => setBrand(e.target.value)}
        className="bg-slate-800 border border-slate-700 text-slate-100 rounded-md px-2.5 py-1.5 text-sm font-medium uppercase focus:outline-none focus:border-indigo-400 hover:border-slate-500 transition-colors"
      >
        {brands.map((b) => (
          <option key={b} value={b}>{b}</option>
        ))}
      </select>
      <select
        value={season}
        onChange={(e) => setSeason(e.target.value)}
        disabled={!seasons.length}
        className="bg-slate-800 border border-slate-700 text-slate-100 rounded-md px-2.5 py-1.5 text-sm font-medium uppercase focus:outline-none focus:border-indigo-400 hover:border-slate-500 transition-colors disabled:opacity-50"
      >
        {seasons.length === 0 && <option>—</option>}
        {seasons.map((s) => (
          <option key={s.season_code} value={s.season_code}>{s.season_code}</option>
        ))}
      </select>
    </div>
  )
}

