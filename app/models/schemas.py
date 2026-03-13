from pydantic import BaseModel, Field
from typing import Optional


class InteractionRequest(BaseModel):
    drug1: str = Field(..., min_length=1, example="warfarin")
    drug2: str = Field(..., min_length=1, example="aspirin")


class LLMAssessment(BaseModel):
    risk_estimate: str
    reasoning: str


class InteractionResponse(BaseModel):
    drug1: str
    drug2: str
    resolved_drug1: Optional[str] = None
    resolved_drug2: Optional[str] = None
    severity: str
    description: Optional[str] = None
    source: Optional[str] = None
    confidence: Optional[str] = None
    llm_assessment: Optional[LLMAssessment] = None
    warning: Optional[str] = None


class PlainEnglishDrugInfo(BaseModel):
    what_its_for: Optional[str] = None
    how_it_works: Optional[str] = None
    side_effects: Optional[str] = None
    safety_tip: Optional[str] = None


class DrugInfoResponse(BaseModel):
    name: str
    resolved_name: Optional[str] = None
    drug_class: Optional[str] = None
    indication: Optional[str] = None
    mechanism: Optional[str] = None
    side_effects: Optional[str] = None
    pharmacology: Optional[str] = None
    dosage: Optional[str] = None
    description: Optional[str] = None
    brand_names: Optional[list[str]] = None
    plain_english: Optional[PlainEnglishDrugInfo] = None


class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    fuzzy_index_size: int
