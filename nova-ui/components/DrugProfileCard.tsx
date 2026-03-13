import { Pill, Activity, Stethoscope, AlertTriangle } from "lucide-react"

export default function DrugProfileCard({ profile }: { profile: any }) {

  return (

    <div className="mt-6 bg-white border border-slate-200 rounded-2xl shadow-md p-6">

      {/* Drug Name */}

      <div className="flex items-center gap-2 mb-4">

        <Pill className="text-indigo-600" size={20} />

        <h2 className="text-xl font-semibold text-slate-900">
          {profile.name}
        </h2>

      </div>

      {/* Info Grid */}

      <div className="grid md:grid-cols-2 gap-x-8 gap-y-4 text-sm text-slate-700">

        <div>
          <p className="font-medium text-slate-600">Class</p>
          <p>{profile.drug_class || "Not available"}</p>
        </div>

        <div>
          <p className="font-medium text-slate-600">Indication</p>
          <p>{profile.indication || "Not available"}</p>
        </div>

        <div>
          <p className="font-medium text-slate-600">Mechanism</p>
          <p>{profile.mechanism || "Not available"}</p>
        </div>

        <div>
          <p className="font-medium text-slate-600">Dosage</p>
          <p>{profile.dosage || "Not available"}</p>
        </div>

      </div>

      {/* Side Effects */}

      {profile.side_effects && (

        <div className="mt-5 border-t pt-4">

          <div className="flex items-center gap-2 mb-2">

            <AlertTriangle className="text-orange-500" size={18} />

            <p className="font-medium text-slate-800">
              Side Effects
            </p>

          </div>

          <p className="text-sm text-slate-700 leading-relaxed">
            {profile.side_effects}
          </p>

        </div>

      )}

    </div>

  )
}