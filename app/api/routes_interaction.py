from fastapi import APIRouter
from app.models.schemas import InteractionRequest, InteractionResponse
from app.agent.agent_controller import handle_interaction_query

router = APIRouter(prefix="/api", tags=["interaction"])


@router.post("/check_interaction", response_model=InteractionResponse)
def check_interaction(req: InteractionRequest) -> InteractionResponse:
    result = handle_interaction_query(req.drug1.strip(), req.drug2.strip())
    return InteractionResponse(**result)
