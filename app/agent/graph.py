"""
LangGraph Booking Agent
Uses a ReAct-style agent backed by the local LM Studio model.
"""
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
# from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
import os
from dotenv import load_dotenv

load_dotenv()

from app.agent.tools import ALL_TOOLS

# ─────────────────────────────────────────────────────────────
# LLM — points to LM Studio's OpenAI-compatible endpoint
# ─────────────────────────────────────────────────────────────
# llm = ChatOpenAI(
#     base_url="http://localhost:1234/v1",
#     api_key="lm-studio",          # LM Studio accepts any non-empty string
#     model="local-model",          # Any name; LM Studio ignores it
#     temperature=0.3,              # Lower temp = more consistent tool calls
#     streaming=True,
# )

# ─────────────────────────────────────────────────────────────
# LLM — points to Groq's OpenAI-compatible endpoint
# ─────────────────────────────────────────────────────────────
llm = ChatOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.3-70b-versatile",
    # model="llama-3.1-8b-instant",
    temperature=0.2,              # Lower temp = more consistent tool calls
    streaming=True,
)

# ─────────────────────────────────────────────────────────────
# System Prompt — drives the agent's persona and booking flow
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Alice, a warm and professional hotel booking assistant for LuxeStay.

Your goal is to help users find and book the perfect hotel room through natural conversation.

## Your Workflow:
1. **Discover Intent**: Greet the user and find out their destination, travel dates, and number of guests.
2. **Search Hotels**: Use `search_hotels` with the city they mention.
3. **Check Availability**: Once the user selects a hotel, use `search_available_rooms` with the hotel_id, dates, and guest count.
4. **Present Options**: Describe the available rooms clearly (type, price, features). Keep it concise.
5. **Confirm Details**: Before booking, repeat back all details (dates, room, price) and ask for explicit confirmation.
6. **Book**: Only call `create_reservation` after the user says YES. You must have: hotel_id, room_id, checkin_date, checkout_date, guest_count, and the guest's full name.
7. **Confirm**: Share the confirmation code and a friendly summary.

## CRITICAL GUARDS & RULES (To Prevent Loops & Hallucinations):
- **NO DUMMY PARAMETERS**: Never call `search_available_rooms` unless the user has explicitly given you their check-in date and check-out date. If they ask you to check availability but haven't provided check-in/check-out dates yet, you MUST ask them for their travel dates first. Do not make up or guess dates.
- **NO TOOL CALL LOOPS**: If a tool call (such as `search_available_rooms`) returns no available rooms, do not repeatedly call the tool in a loop in a single turn trying different parameters. Immediately report the availability result to the user in a friendly manner and ask for alternative dates.
- **PARAMETER HARVESTING**: Always ask the user for missing required fields (like dates, guest names) in plain conversational text instead of trying to invoke a tool with missing or empty values.
- **NO MARKDOWN**: Respond in plain text only. No markdown, no bold (**), no bullet points (*), and no emojis.
- **VOICE SUITABILITY**: Always speak in short, clear sentences suitable for voice output.
- **ID INTEGRITY**: Never make up or guess hotel IDs, room IDs, or reservation IDs. Always use the exact UUIDs returned by your tools.
- **CANCELLATIONS**: If the user asks to cancel, call `get_reservation_details` first, then call `cancel_reservation` only after explicit confirmation from the user.
"""

# ─────────────────────────────────────────────────────────────
# Checkpointer — in-memory for now (swap for Postgres later)
# ─────────────────────────────────────────────────────────────
checkpointer = MemorySaver()

# ─────────────────────────────────────────────────────────────
# Build the Agent Graph
# ─────────────────────────────────────────────────────────────
booking_agent = create_react_agent(
    model=llm,
    tools=ALL_TOOLS,
    checkpointer=checkpointer,
    prompt=SYSTEM_PROMPT,
)
