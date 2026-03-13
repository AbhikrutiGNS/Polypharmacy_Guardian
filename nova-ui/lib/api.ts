const API = process.env.NEXT_PUBLIC_API_URL

export async function checkInteraction(drug1:string, drug2:string){

  const res = await fetch(`${API}/interaction`,{
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body:JSON.stringify({drug1,drug2})
  })

  return res.json()
}

export async function getDrugInfo(drug:string){

  const res = await fetch(`${API}/drug-info?drug=${encodeURIComponent(drug)}`)

  return res.json()
}