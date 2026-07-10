import logging
from backend.langgraph.graph import app
from backend.langgraph.state import AgentState

logger = logging.getLogger(__name__)

def run_agent(user_message: str, history: list = None, model_override: str = "gemma2-9b-it", user_id: int | None = None) -> dict:
    """
    Interface to run the LangGraph agent state machine.
    Inputs:
        user_message: the latest text query from the user.
        history: past list of messages e.g. [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        model_override: selected model (e.g. gemma2-9b-it, llama-3.3-70b-versatile)
        user_id: optional authenticated user id for saving interaction logs.
    Returns:
        A dictionary containing:
            - response: conversational response text
            - extracted_fields: structured JSON containing doctor visit entities (for log intent)
            - tool_triggered: tool that was run
    """
    if history is None:
        history = []

    # Construct messages list for state
    messages = list(history)
    messages.append({"role": "user", "content": user_message})

    # Prepare initial state
    initial_state = AgentState(
        messages=messages,
        intent=None,
        extracted_fields=None,
        tool_triggered=None,
        tool_result=None,
        final_response=None,
        model_override=model_override,
        user_id=user_id
    )

    try:
        # Run graph
        final_state = app.invoke(initial_state)
        
        return {
            "response": final_state.get("final_response") or "I processed your request but was unable to compile a response.",
            "extracted_fields": final_state.get("extracted_fields"),
            "tool_triggered": final_state.get("tool_triggered")
        }
    except Exception as e:
        logger.error(f"Error executing agent graph: {e}")
        return {
            "response": f"An error occurred while communicating with the agent: {str(e)}",
            "extracted_fields": None,
            "tool_triggered": "None"
        }
