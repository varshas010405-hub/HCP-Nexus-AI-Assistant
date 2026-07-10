from fastapi import APIRouter, Depends, HTTPException
from backend.schemas.schemas import ChatRequest, ChatResponse
from backend.langgraph.agent import run_agent
from backend.routers.auth import get_current_user_optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Agent Chat"])

@router.post("/chat", response_model=ChatResponse)
def chat_with_agent(payload: ChatRequest, current_user: object = Depends(get_current_user_optional)):
    """
    Interact with the LangGraph agent. Evaluates user intent, triggers tools,
    saves logs to database, and responds conversationally.
    """
    try:
        logger.info("/chat called with message: %s", payload.message)
        result = run_agent(
            user_message=payload.message,
            history=payload.history,
            model_override=payload.model_override,
            user_id=getattr(current_user, 'id', None)
        )
        logger.info("/chat result: %s", result)
        return ChatResponse(
            response=result["response"],
            extracted_fields=result["extracted_fields"],
            tool_triggered=result["tool_triggered"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent runtime error: {str(e)}")
