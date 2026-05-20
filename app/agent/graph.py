"""
LangGraph Booking Agent
Uses a custom StateGraph workflow to manage booking states, progressive state extraction, and security routing.
"""
import os
import json
from dotenv import load_dotenv
from typing import Literal
from uuid import UUID

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

from app.agent.tools import ALL_TOOLS
from app.agent.state import AgentState

# ─────────────────────────────────────────────────────────────
# LLM — points to Groq's OpenAI-compatible endpoint
# ─────────────────────────────────────────────────────────────
primary_llm = ChatOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    model="openai/gpt-oss-120b",
    temperature=0.2,              # Lower temp = more consistent tool calls
    max_tokens=512,
    streaming=True
)

fallback_llm = ChatOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    model="qwen/qwen3-32b",
    temperature=0.2,
    max_tokens=512,
    streaming=True
)

# Bind tools to both models and set up automatic fallback
llm_with_tools = primary_llm.bind_tools(ALL_TOOLS).with_fallbacks([
    fallback_llm.bind_tools(ALL_TOOLS)
])

# Fast and lightweight models for pure conversation/chit-chat & intent classification
fast_llm = ChatOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.1-8b-instant",
    temperature=0.4,              # Slightly warmer for conversational chitchat
    max_tokens=512,
    streaming=True
)

classifier_llm = ChatOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.1-8b-instant",
    temperature=0.0,              # Fully deterministic for intent classification
    max_tokens=10,
    streaming=False
)

# ─────────────────────────────────────────────────────────────
# System Prompt — drives the agent's persona and booking flow
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Alice, a warm and professional hotel booking assistant for LuxeStay.

Your goal is to help users find and book the perfect hotel room through natural conversation.
Keep responses short and concise. Do not repeat yourself.

## Your Workflow:
1. **Discover Intent**: Greet the user and find out their destination, travel dates, and number of guests.
2. **Search Hotels**: Use `search_hotels` with the city or country they mention. Only call this for new locations not already in your system banner under "Known Hotels".
3. **Get Hotel Details**: If the user asks about room types, general pricing, amenities, or features of a hotel without specifying check-in/out dates, use `get_hotel_details` with the hotel_id from your "Known Hotels" cache.
4. **Check Availability & Handle Full Bookings**:
   - Once the user selects a hotel and provides check-in/check-out dates, use `search_available_rooms` with the hotel_id, dates, and guest count.
   - **Alternative Dates**: If `search_available_rooms` returns no results or indicates the hotel is fully booked for those dates, you MUST call `get_alternative_available_dates` with the hotel_id and check-in date. Present these alternative available dates clearly to the user so they can choose a different range.
5. **Present Options**: Describe the available rooms clearly (type, price, features). Keep it concise.
6. **Confirm Details**: Before booking, repeat back all details (dates, room, price) and ask for explicit confirmation.
7. **Book**: Only call `create_reservation` after the user says YES. You must have: hotel_id, room_id, checkin_date, checkout_date, guest_count, and the guest's full name.
8. **Confirm**: Share the confirmation code and a friendly summary.

## CRITICAL GUARDS & RULES (To Prevent Loops & Hallucinations):
- **USE CACHED HOTEL IDs**: If the user mentions a hotel that already appears under "Known Hotels" in your system banner, use that exact hotel_id directly. Do NOT call `search_hotels` again for the same location.
- **CONTEXT SWITCHING**: If the user switches to a different hotel or city not in your cache, call `search_hotels` for the new location first. All prior room/date context is automatically reset when you switch hotels.
- **NO DUMMY PARAMETERS**: Never call `search_available_rooms` unless the user has explicitly given you their check-in date and check-out date. If they ask about pricing without dates, use `get_hotel_details` instead. Do not make up or guess dates.
- **NEVER CLAIM USER SPECIFIED DATES**: Never say "for the dates you specified" unless the user actually said so.
- **NO TOOL CALL LOOPS**: If a tool returns no results, report it immediately and ask for alternatives. Do not retry with different parameters in the same turn.
- **PARAMETER HARVESTING**: Ask the user for missing required fields in plain conversational text.
- **ID INTEGRITY**: Never make up or guess hotel IDs, room IDs, or reservation IDs. Always use the exact UUIDs returned by your tools or shown in your system banner.
- **CANCELLATIONS**: If the user asks to cancel, call `get_reservation_details` first, then call `cancel_reservation` only after explicit confirmation from the user.
"""

# ─────────────────────────────────────────────────────────────
# Custom Workflow Nodes
# ─────────────────────────────────────────────────────────────

async def auth_check_node(state: AgentState) -> dict:
    """Security check node. Verifies user authentication details are loaded."""
    if not state.get("user_id"):
        return {
            "messages": [
                SystemMessage(
                    content="Security check failed: No authenticated user session was detected. Please log in first."
                )
            ]
        }
    return {}


# ─────────────────────────────────────────────────────────────
# Classifier Prompt — determines if database/tool calls are needed
# ─────────────────────────────────────────────────────────────
CLASSIFY_PROMPT = """You are an intent classifier for a hotel booking assistant.
Analyze the user's latest message and decide if we need to call a database tool.
We have tools for: searching hotels by city/country, getting hotel details/pricing, checking room availability, creating bookings, and cancelling bookings.

Respond with "TOOL" if the user's message is asking to:
- Search for hotels, cities, countries, or destinations.
- Check room availability, prices, dates, or guest counts.
- Create, confirm, or modify a booking.
- View, check, or cancel a reservation.
- Anything requiring live database queries.

Respond with "CHITCHAT" ONLY if the message is:
- A greeting (e.g., "hello", "hi", "hey", "good morning").
- A parting (e.g., "bye", "goodbye", "have a nice day").
- Conversational filler, acknowledgment or agreement (e.g., "ok", "cool", "thank you", "thanks", "great", "yes", "no").
- A simple query about the assistant's name/identity.
- A question that can be answered entirely using the information already present in the "CURRENT SESSION CONTEXT" in the system banner (e.g., repeating a confirmation code or hotel address already shown).

User's Latest Message: {user_message}
Response (either TOOL or CHITCHAT):"""


from datetime import datetime

async def agent_node(state: AgentState, config: RunnableConfig) -> dict:
    """Core agent node. Formats the progressive state variables into a system banner."""
    now_str = datetime.now().strftime("%A, %B %d, %Y")

    # 1. Compile currently saved state values into a dynamic system banner
    state_banner = f"\n\n[LUXESTAY SYSTEM BANNER - CURRENT SESSION CONTEXT]\n"
    state_banner += f"- Current Date: {now_str}\n"
    state_banner += f"- Authenticated User: {state.get('user_name') or 'Guest'} (ID: {state.get('user_id') or 'None'})\n"

    # Surface the hotel search cache so the LLM can re-use IDs without re-searching
    searched = state.get("searched_hotels") or {}
    if searched:
        state_banner += "- Known Hotels (use these exact IDs, do NOT call search_hotels again for these):" + "\n"
        for name, hid in searched.items():
            state_banner += f"    * {name} → hotel_id: {hid}\n"
    else:
        state_banner += "- Known Hotels: None yet\n"

    # Currently focused hotel & room
    state_banner += f"- Currently Focused Hotel: {state.get('hotel_name') or 'None'} (ID: {state.get('hotel_id') or 'None'})\n"
    state_banner += f"- Selected Room ID: {state.get('room_id') or 'None'}\n"
    state_banner += f"- Check-in Date: {state.get('checkin_date') or 'None'}\n"
    state_banner += f"- Check-out Date: {state.get('checkout_date') or 'None'}\n"
    state_banner += f"- Guest Count: {state.get('guest_count') or 'None'}\n"
    if state.get("confirmation_code"):
        state_banner += f"- Active Booking Confirmation Code: {state.get('confirmation_code')}\n"
    if state.get("reservation_id"):
        state_banner += f"- Active Reservation ID: {state.get('reservation_id')}\n"

    # 2. Extract context mode and dynamic formatting instructions
    mode = config.get("configurable", {}).get("mode", "text")
    mode_rules = ""
    if mode == "voice":
        mode_rules = """
\n## VOICE FORMATTING RULES:
- **NO MARKDOWN**: Respond in plain conversational text only. Do NOT use markdown symbols, asterisks (** or *), bullet points, dashes, hash headers (#), or emojis.
- **VOICE SUITABILITY**: Keep your sentences short, simple, and naturally conversational so they sound perfect when read aloud by our Text-to-Speech system. Do not display lists or grids.
"""
    else:
        mode_rules = """
\n## TEXT FORMATTING RULES:
- **USE PREMIUM MARKDOWN**: Elevate the user experience by formatting your response beautifully! Use bolding (**), bullet lists, and section headers (#, ##).
- **STRUCTURED LISTS & TABLES**: When listing hotels, room types, or alternative dates, present them using beautiful markdown lists, bold details, or elegant markdown tables!
- **EMOJIS**: Use relevant emojis (🏨, 📅, 🔑, 🌟, ✨, etc.) tastefully to make the interface feel lively and premium.
"""

    full_prompt = SYSTEM_PROMPT + state_banner + mode_rules

    # 3. Format message history for LLM invocation
    formatted_messages = [{"role": "system", "content": full_prompt}] + state["messages"]

    # 4. Dynamic routing logic:
    # Check if we should use the fast LLM (llama-3.1-8b-instant) or the heavy LLM with tools.
    # We default to using the heavy model with tools (llm_with_tools) to ensure safety.
    use_fast_llm = False
    
    last_msg = state["messages"][-1] if state["messages"] else None
    if last_msg and last_msg.__class__.__name__ == "HumanMessage":
        user_text = str(last_msg.content)
        classification_prompt = [
            {"role": "system", "content": CLASSIFY_PROMPT.format(user_message=user_text)}
        ]
        try:
            class_response = await classifier_llm.ainvoke(classification_prompt)
            classification = class_response.content.strip().upper()
            if "CHITCHAT" in classification and "TOOL" not in classification:
                use_fast_llm = True
        except Exception:
            # Fallback to heavy model on any classification error
            use_fast_llm = False

    # 5. Invoke selected model
    if use_fast_llm:
        response = await fast_llm.ainvoke(formatted_messages)
    else:
        response = await llm_with_tools.ainvoke(formatted_messages)
        
    return {"messages": [response]}


async def state_extractor_node(state: AgentState) -> dict:
    """
    Progressive state saving node. Deterministically captures variables from the most recent
    AI tool-call round-trip (args + results). Handles:
      - search_hotels     : caches all returned hotel name→id pairs into searched_hotels
      - get_hotel_details : saves hotel_id/hotel_name; resets room/dates on hotel switch
      - search_available_rooms: saves hotel_id/dates; resets room_id on hotel switch
      - create_reservation: saves all booking fields
      - cancel_reservation: saves reservation_id
    """
    updates = {}
    messages = state["messages"]

    # Find the most recent AIMessage that carried tool calls
    last_ai_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage) and messages[i].tool_calls:
            last_ai_idx = i
            break

    if last_ai_idx is None:
        return {}

    last_ai = messages[last_ai_idx]
    # Collect all ToolMessages that immediately follow the AI tool-call message
    tool_messages_after = [
        m for m in messages[last_ai_idx + 1:]
        if isinstance(m, ToolMessage)
    ]

    # ── 1. Capture state from tool call ARGUMENTS ─────────────────────────────
    for tc in last_ai.tool_calls:
        args = tc.get("args", {})
        name = tc.get("name", "")

        if name == "get_hotel_details":
            new_hotel_id = str(args["hotel_id"])
            # Detect hotel context switch → clear stale room and date context
            if state.get("hotel_id") and state["hotel_id"] != new_hotel_id:
                updates["room_id"] = None
                updates["checkin_date"] = None
                updates["checkout_date"] = None
            updates["hotel_id"] = new_hotel_id

        elif name == "search_available_rooms":
            new_hotel_id = str(args["hotel_id"])
            # Detect hotel context switch → clear stale room_id
            if state.get("hotel_id") and state["hotel_id"] != new_hotel_id:
                updates["room_id"] = None
            updates["hotel_id"] = new_hotel_id
            if "checkin_date" in args:  updates["checkin_date"] = args["checkin_date"]
            if "checkout_date" in args: updates["checkout_date"] = args["checkout_date"]
            if "guests" in args:        updates["guest_count"] = int(args["guests"])

        elif name == "create_reservation":
            if "hotel_id" in args:    updates["hotel_id"] = str(args["hotel_id"])
            if "room_id" in args:     updates["room_id"] = str(args["room_id"])
            if "checkin_date" in args: updates["checkin_date"] = args["checkin_date"]
            if "checkout_date" in args: updates["checkout_date"] = args["checkout_date"]
            if "guest_count" in args:  updates["guest_count"] = int(args["guest_count"])

        elif name == "cancel_reservation":
            if "reservation_id" in args: updates["reservation_id"] = str(args["reservation_id"])

    # ── 2. Parse ToolMessage RESULTS ──────────────────────────────────────────
    for tm in tool_messages_after:
        try:
            payload = json.loads(tm.content)
        except Exception:
            continue  # raw text, skip

        if isinstance(payload, dict):
            # Booking confirmation result
            if "confirmation_code" in payload:
                updates["confirmation_code"] = str(payload["confirmation_code"])
            if "reservation_id" in payload:
                updates["reservation_id"] = str(payload["reservation_id"])

            # get_hotel_details result → cache hotel name + update focused hotel_name
            if "hotel_id" in payload and "name" in payload:
                hotel_cache = dict(state.get("searched_hotels") or {})
                hotel_cache[payload["name"]] = payload["hotel_id"]
                updates["searched_hotels"] = hotel_cache
                updates["hotel_name"] = payload["name"]

        elif isinstance(payload, list):
            # search_hotels result → cache ALL returned hotels into searched_hotels
            hotel_cache = dict(state.get("searched_hotels") or {})
            changed = False
            for item in payload:
                if isinstance(item, dict) and "hotel_id" in item and "name" in item:
                    hotel_cache[item["name"]] = item["hotel_id"]
                    changed = True
            if changed:
                updates["searched_hotels"] = hotel_cache

    return updates


# ─────────────────────────────────────────────────────────────
# Routing & Control Flow
# ─────────────────────────────────────────────────────────────

def route_auth(state: AgentState) -> Literal["agent", "__end__"]:
    """Routes execution to agent if authenticated, else terminates."""
    if not state.get("user_id"):
        return "__end__"
    return "agent"


def route_agent_action(state: AgentState) -> Literal["tools", "state_extractor"]:
    """Routes to tools node if a tool call is pending, else extracts state and finishes."""
    last_msg = state["messages"][-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tools"
    return "state_extractor"


def route_extractor(state: AgentState) -> Literal["agent", "__end__"]:
    """Routes back to the agent if we just ran tools, else terminates graph execution."""
    last_msg = state["messages"][-1]
    if isinstance(last_msg, ToolMessage):
        return "agent"
    return "__end__"


# ─────────────────────────────────────────────────────────────
# Build the Agent Graph Workflow
# ─────────────────────────────────────────────────────────────

workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("auth_check", auth_check_node)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(ALL_TOOLS))
workflow.add_node("state_extractor", state_extractor_node)

# Set Entry Edge
workflow.add_edge(START, "auth_check")

# Set Conditional Auth Edge
workflow.add_conditional_edges(
    "auth_check",
    route_auth,
)

# Set Conditional Agent Edge
workflow.add_conditional_edges(
    "agent",
    route_agent_action,
)

# Set Tool Edge to state_extractor
workflow.add_edge("tools", "state_extractor")

# Set Conditional Extractor Edge
workflow.add_conditional_edges(
    "state_extractor",
    route_extractor,
)

# Compile Graph with persistent memory
checkpointer = MemorySaver()
booking_agent = workflow.compile(checkpointer=checkpointer)
