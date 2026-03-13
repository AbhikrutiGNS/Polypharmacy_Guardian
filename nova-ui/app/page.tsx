'use client'

import { useState } from 'react'
import InteractionChecker from '@/components/InteractionChecker'
import DrugInfo from '@/components/DrugInfo'

export default function Home() {

  const [tab, setTab] = useState<'interaction' | 'drug'>('interaction')

  return (

    <main className="min-h-screen bg-gradient-to-br from-indigo-50 via-blue-50 to-slate-100 p-8">

      <div className="max-w-6xl mx-auto">

        {/* Title Section */}

        <div className="text-center mb-12">

          <h1 className="text-5xl md:text-6xl font-bold text-slate-900 tracking-tight">
            NOVA CHEAL
          </h1>

          <p className="text-slate-600 mt-3 text-lg">
            AI-Powered Drug Safety Assistant
          </p>

        </div>

        {/* Tabs */}

        <div className="flex justify-center mb-10">

          <div className="flex bg-white shadow-lg rounded-xl p-1 border border-slate-200">

            <button
              onClick={() => setTab('interaction')}
              className={`px-6 py-3 rounded-lg text-sm font-semibold transition-all
              ${
                tab === 'interaction'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-700 hover:bg-slate-100'
              }`}
            >
              Interaction Checker
            </button>

            <button
              onClick={() => setTab('drug')}
              className={`px-6 py-3 rounded-lg text-sm font-semibold transition-all
              ${
                tab === 'drug'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-700 hover:bg-slate-100'
              }`}
            >
              Drug Information
            </button>

          </div>

        </div>

        {/* Main Card */}

        <div className="bg-white rounded-2xl shadow-xl border border-slate-100 p-6 md:p-10">

          {tab === 'interaction'
            ? <InteractionChecker />
            : <DrugInfo />
          }

        </div>

      </div>

    </main>

  )
}