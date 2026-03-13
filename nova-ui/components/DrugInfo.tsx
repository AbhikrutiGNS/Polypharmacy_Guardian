'use client'

import { useState } from 'react'
import { getDrugInfo } from '@/lib/api'
import DrugProfileCard from './DrugProfileCard'

export default function DrugInfo() {

  const [drug, setDrug] = useState('')
  const [profiles, setProfiles] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const search = async () => {

    if (!drug) {
      setError("Please enter a drug name")
      return
    }

    setLoading(true)
    setError(null)
    setProfiles([])

    try {

      const data = await getDrugInfo(drug)
      setProfiles(data.profiles || [])

      if (!data.profiles || data.profiles.length === 0) {
        setError("No information found for this drug")
      }

    } catch {
      setError("Backend unavailable")
    }

    setLoading(false)

  }

  return (

    <div className="bg-white p-8 rounded-2xl shadow-xl border border-slate-100">

      <h2 className="text-xl font-semibold text-slate-800 mb-6">
        Drug Information
      </h2>

      {/* Input */}

      <div className="flex flex-col gap-3">

        <input
          placeholder="e.g. paracetamol, dolo 650"
          className="border border-slate-300 rounded-lg p-3
          focus:ring-2 focus:ring-indigo-500 focus:outline-none"
          value={drug}
          onChange={e => setDrug(e.target.value)}
        />

        <button
          onClick={search}
          disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-700 text-white
          px-6 py-3 rounded-xl font-medium shadow-md transition disabled:opacity-50"
        >
          {loading ? "Searching..." : "Lookup Drug"}
        </button>

      </div>

      {/* Error */}

      {error && (
        <p className="mt-4 text-red-600 font-medium">
          {error}
        </p>
      )}

      {/* Profiles */}

      {profiles.length > 0 && (

        <div className="mt-8 space-y-6">

          {profiles.map((p, i) => (
            <DrugProfileCard key={i} profile={p} />
          ))}

        </div>

      )}

    </div>

  )
}