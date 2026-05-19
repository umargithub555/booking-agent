"""
Agent State Definition
Defines the shared state object that flows through all LangGraph nodes.
"""
from typing import Annotated, Dict, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Full conversation history (LangGraph manages append-only updates)
    messages: Annotated[list, add_messages]

    # Authenticated user context (injected at session start)
    user_id: Optional[str]
    user_name: Optional[str]

    # Hotel discovery cache — populated by search_hotels, persists for the whole session
    # Maps hotel name (str) → hotel_id (str) so the LLM can look up IDs without re-searching
    searched_hotels: Optional[Dict[str, str]]

    # Collected booking intent (filled progressively during the conversation)
    hotel_id: Optional[str]       # UUID of the currently focused hotel
    hotel_name: Optional[str]     # Human-readable name of the currently focused hotel
    room_id: Optional[str]        # UUID of the selected room
    checkin_date: Optional[str]   # ISO format: YYYY-MM-DD
    checkout_date: Optional[str]  # ISO format: YYYY-MM-DD
    guest_count: Optional[int]

    # Completed booking result
    reservation_id: Optional[str]
    confirmation_code: Optional[str]
