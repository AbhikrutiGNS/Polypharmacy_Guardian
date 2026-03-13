from fastapi import APIRouter, HTTPException
from app.models.schemas import DrugInfoResponse, PlainEnglishDrugInfo
from app.services.drug_info_service import get_drug_info
from app.llm.llm_provider import simplify_drug_info

router = APIRouter(prefix="/api", tags=["drug_info"])


@router.get("/drug_info", response_model=DrugInfoResponse)
def drug_info(drug: str) -> DrugInfoResponse:
    if not drug.strip():
        raise HTTPException(status_code=400, detail="Drug name cannot be empty.")

    info = get_drug_info(drug.strip())
    if not info:
        raise HTTPException(
            status_code=404,
            detail=f"No information found for '{drug}'. Check spelling or try the generic name.",
        )

    # LLM simplification — always runs, rewrites scary clinical text into plain English
    plain = None
    if info.get("indication") or info.get("mechanism") or info.get("side_effects"):
        raw = simplify_drug_info(
            drug_name=info["name"],
            indication=info.get("indication") or "",
            mechanism=info.get("mechanism") or "",
            side_effects=info.get("side_effects") or "",
        )
        if raw:
            plain = PlainEnglishDrugInfo(**raw)

    return DrugInfoResponse(
        name=info["name"],
        resolved_name=info["name"],
        drug_class=info.get("drug_class"),
        indication=info.get("indication"),
        mechanism=info.get("mechanism"),
        side_effects=info.get("side_effects"),
        pharmacology=info.get("pharmacology"),
        dosage=info.get("dosage"),
        description=info.get("description"),
        brand_names=info.get("brand_names") or [],
        plain_english=plain,
    )
