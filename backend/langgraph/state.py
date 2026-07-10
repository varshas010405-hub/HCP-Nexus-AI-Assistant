from typing import TypedDict, List, Dict, Any, Optional
from backend.schemas.schemas import ExtractedDetails

class AgentState(TypedDict):
    messages: List[Dict[str, str]]  # list of {"role": "user"|"assistant", "content": "text"}
    intent: Optional[str]           # log, edit, search, summarize, schedule, insights, general
    extracted_fields: Optional[Dict[str, Any]]
    tool_triggered: Optional[str]   # Name of the tool that was run
    tool_result: Optional[Dict[str, Any]]
    final_response: Optional[str]
    model_override: Optional[str]   # Option to override default model
    user_id: Optional[int]
