from typing import Annotated, Union
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel
from pathlib import Path
import logging

from .config import settings
from .tools import (
    check_red_flag,
    map_symptoms,
    find_clinics,
    get_doctors,
    get_slots,
    book_appointment,
)

logger = logging.getLogger(__name__)

# --- Load System Prompt ---
SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.txt"
try:
    SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
except Exception as e:
    logger.error(f"Failed to load system prompt: {e}")
    SYSTEM_PROMPT = "You are a helpful medical assistant for Vinmec."

# --- State ---
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# --- Tools list ---
TOOLS = [
    check_red_flag,
    map_symptoms,
    find_clinics,
    get_doctors,
    get_slots,
    book_appointment,
]

# --- LLM Setup ---
def get_llm() -> Union[BaseChatModel, None]:
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set. Graph-based agent will be limited or disabled.")
        return None
    
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=0,
        api_key=settings.openai_api_key
    )

llm = get_llm()

if llm:
    llm_with_tools = llm.bind_tools(TOOLS)
else:
    llm_with_tools = None

# --- Agent node ---
def agent_node(state: AgentState) -> AgentState:
    messages = state["messages"]

    # Inject system prompt if not present
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    if not llm_with_tools:
        # Fallback response if no LLM (e.g., mock mode)
        return {"messages": [AIMessage(content="[Mock Mode] I cannot process this request without an OpenAI API Key. Please configure OPENAI_API_KEY in your .env file.")]}

    response = llm_with_tools.invoke(messages)

    # Logging tool calls
    if response.tool_calls:
        for tc in response.tool_calls:
            logger.info(f"[Tool Call] {tc['name']}({tc['args']})")
    else:
        logger.info("[Agent] Responding directly")

    return {"messages": [response]}

# --- Build graph ---
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.add_node("tools", ToolNode(TOOLS))

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")

graph = builder.compile()