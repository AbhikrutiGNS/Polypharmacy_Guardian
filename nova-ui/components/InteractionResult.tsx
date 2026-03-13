import { AlertTriangle, CheckCircle } from "lucide-react"

export default function InteractionResult({ result }: { result: any }) {

  if (result.severity === "NONE_FOUND") {
    return (
      <div className="mt-6 flex items-center gap-3 bg-green-100 border border-green-200 text-green-800 p-4 rounded-xl">
        <CheckCircle size={20} />
        <span className="font-medium">
          No known interaction found between these drugs.
        </span>
      </div>
    )
  }

  const severityStyles: Record<string, string> = {
    HIGH: "bg-red-100 text-red-800 border-red-200",
    MODERATE: "bg-orange-100 text-orange-800 border-orange-200",
    LOW: "bg-yellow-100 text-yellow-800 border-yellow-200",
  }

  const severityColor =
    severityStyles[result.severity] || "bg-slate-100 text-slate-700"

  return (
    <div className="mt-6 border border-slate-200 rounded-2xl shadow-md p-6 bg-white">

      {/* Severity badge */}
      <div className="flex items-center gap-3 mb-4">

        <div className={`px-3 py-1 rounded-full text-sm font-semibold border ${severityColor}`}>
          {result.severity} RISK
        </div>

        <AlertTriangle className="text-slate-500" size={18} />

      </div>

      {/* Description */}
      <p className="text-slate-700 leading-relaxed">
        {result.description}
      </p>

      {/* Source */}
      <p className="text-sm text-slate-500 mt-3">
        Source: <span className="font-medium">{result.source}</span>
      </p>

      {/* Ingredient details */}
      {result.all_pairs?.length > 1 && (

        <div className="mt-6">

          <p className="font-semibold text-slate-800 mb-2">
            Ingredient-level details
          </p>

          <div className="border rounded-lg overflow-hidden">

            {result.all_pairs.map((p: any, i: number) => (

              <div
                key={i}
                className="flex justify-between text-sm px-4 py-2 border-b last:border-none"
              >

                <span className="text-slate-700">
                  {p.rxcui_pair}
                </span>

                <span className="font-medium">
                  {p.severity}
                </span>

              </div>

            ))}

          </div>

        </div>

      )}

    </div>
  )
}