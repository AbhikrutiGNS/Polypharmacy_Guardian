'use client'

import { useState } from 'react'
import { checkInteraction } from '@/lib/api'
import InteractionResult from './InteractionResult'

export default function InteractionChecker() {

  const [drug1, setDrug1] = useState('')
  const [drug2, setDrug2] = useState('')

  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleCheck = async () => {

    if (!drug1 || !drug2) {
      setError("Please enter both drug names")
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {

      const data = await checkInteraction(drug1, drug2)
      setResult(data)

    } catch {
      setError("Backend unavailable")
    }

    setLoading(false)

  }

  return (

    <div className="bg-white rounded-2xl shadow-xl border border-slate-100 p-8">

      <h2 className="text-xl font-semibold text-slate-800 mb-6">
        Check Drug Interaction
      </h2>

      <div className="grid md:grid-cols-2 gap-4">

        <div className="flex flex-col">
          <label className="text-sm text-slate-600 mb-1">
            Drug 1
          </label>

          <input
            className="border border-slate-300 rounded-lg p-3
            focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            placeholder="e.g. warfarin"
            value={drug1}
            onChange={e => setDrug1(e.target.value)}
          />
        </div>

        <div className="flex flex-col">
          <label className="text-sm text-slate-600 mb-1">
            Drug 2
          </label>

          <input
            className="border border-slate-300 rounded-lg p-3
            focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            placeholder="e.g. aspirin"
            value={drug2}
            onChange={e => setDrug2(e.target.value)}
          />
        </div>

      </div>

      <button
        onClick={handleCheck}
        disabled={loading}
        className="mt-6 bg-indigo-600 hover:bg-indigo-700 text-white
        px-6 py-3 rounded-xl font-medium shadow-md transition disabled:opacity-50"
      >
        {loading ? "Checking..." : "Check Interaction"}
      </button>

      {error && (
        <p className="mt-4 text-red-600 font-medium">
          {error}
        </p>
      )}

      {result && (
        <div className="mt-6">
          <InteractionResult result={result} />
        </div>
      )}

    </div>

  )
}