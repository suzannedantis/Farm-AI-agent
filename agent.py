import streamlit as st
from typing import TypedDict, Optional
from langchain_groq import ChatGroq
from langchain_community.tools import DuckDuckGoSearchRun
from langgraph.graph import StateGraph, START, END

from weather import get_weather_full, format_weather_for_llm


# ==========================================
# Agent State Schema
# ==========================================
class AgriState(TypedDict):
    # Inputs
    query: str
    location: str
    crop_type: str
    growing_stage: str
    language: str
    image_diagnosis: str          # Pre-filled by vision module if image uploaded
    past_issues: str              # From memory DB

    # Intermediate
    disease_class: str            # fungal / bacterial / pest / nutrient / abiotic / unknown
    confidence: str               # high / medium / low
    planned_search_query: str
    weather_raw: dict
    weather_summary: str
    search_data: str
    escalate: bool

    # Output
    final_advice: str
    explanation: str              # Explainability panel content


# ==========================================
# Disease Classification Router
# ==========================================
DISEASE_CATEGORIES = {
    "fungal": ["mold", "mildew", "blight", "rust", "rot", "spots", "lesion", "fungus", "powdery"],
    "bacterial": ["bacterial", "wilt", "canker", "ooze", "slime", "water-soaked"],
    "pest": ["insect", "bug", "worm", "caterpillar", "aphid", "mite", "whitefly",
             "holes", "eaten", "chewed", "larvae"],
    "nutrient": ["yellow", "yellowing", "pale", "purple", "brown tips", "stunted",
                 "deficiency", "chlorosis", "necrosis"],
    "abiotic": ["drought", "heat", "cold", "frost", "sunburn", "waterlogged", "dry",
                "wilting", "scorched"],
    "viral": ["mosaic", "curl", "distort", "streak", "ring spot", "virus"],
}

SEVERE_KEYWORDS = ["blight", "rot", "wilt", "severe", "dying", "dead", "total loss",
                   "spreading fast", "black rot", "fire blight"]


def classify_disease(query: str, image_diagnosis: str) -> str:
    """Simple keyword-based pre-classifier to route the search strategy."""
    combined = (query + " " + image_diagnosis).lower()
    scores = {cat: 0 for cat in DISEASE_CATEGORIES}
    for cat, keywords in DISEASE_CATEGORIES.items():
        for kw in keywords:
            if kw in combined:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


def check_escalation(query: str, image_diagnosis: str) -> bool:
    """Determine if issue is severe enough to recommend expert escalation."""
    combined = (query + " " + image_diagnosis).lower()
    return any(kw in combined for kw in SEVERE_KEYWORDS)


# ==========================================
# Build and Run the Agent
# ==========================================
def run_agent(
    user_location: str,
    user_query: str,
    crop_type: str,
    growing_stage: str,
    language: str,
    image_diagnosis: str,
    past_issues: str,
    api_key: str,
    log_container,
) -> dict:

    llm = ChatGroq(
        temperature=0.2,
        model_name="llama-3.3-70b-versatile",
        api_key=api_key,
    )
    search_tool = DuckDuckGoSearchRun()

    def _log(msg: str):
        log_container.markdown(msg)

    # ------------------------------------------------------------------
    # NODE 1: Classifier — determines disease category & escalation flag
    # ------------------------------------------------------------------
    def classifier_node(state: AgriState):
        _log("🔬 **Classifier:** Categorizing the disease type...")
        disease_class = classify_disease(state["query"], state.get("image_diagnosis", ""))
        escalate = check_escalation(state["query"], state.get("image_diagnosis", ""))
        _log(f"📋 **Disease Category:** `{disease_class.upper()}`")
        if escalate:
            _log("🚨 **Severity Alert:** Issue flagged as potentially severe.")
        return {"disease_class": disease_class, "escalate": escalate}

    # ------------------------------------------------------------------
    # NODE 2: Planner — formulates targeted search query
    # ------------------------------------------------------------------
    def planner_node(state: AgriState):
        _log("🧠 **Planner:** Formulating research strategy...")

        context_parts = [
            f"Crop: {state.get('crop_type', 'unknown crop')}",
            f"Stage: {state.get('growing_stage', 'unknown stage')}",
            f"Disease category: {state.get('disease_class', 'unknown')}",
            f"Symptom: {state['query']}",
        ]
        if state.get("image_diagnosis"):
            context_parts.append(f"Visual diagnosis: {state['image_diagnosis'][:200]}")

        prompt = (
            f"A farmer reports the following about their crop:\n"
            f"{chr(10).join(context_parts)}\n\n"
            f"Generate a precise web search query (max 7 words) targeting organic agricultural "
            f"remedies specific to this EXACT disease category ({state.get('disease_class', 'unknown')}). "
            f"Focus the query based on the category:\n"
            f"- fungal → search for fungicide spray or soil treatment\n"
            f"- pest → search for organic pest control or repellent\n"
            f"- nutrient → search for soil amendment or fertilizer\n"
            f"- bacterial → search for copper spray or bactericide\n"
            f"- abiotic → search for stress management technique\n"
            f"Output ONLY the search query, no quotes, no explanation."
        )
        response = llm.invoke(prompt)
        search_query = response.content.strip().strip('"')
        _log(f"🔍 **Search Query:** `{search_query}`")
        return {"planned_search_query": search_query}

    # ------------------------------------------------------------------
    # NODE 3: Executor — fetches weather + runs search
    # ------------------------------------------------------------------
    def executor_node(state: AgriState):
        _log(f"🌤️ **Executor:** Fetching 7-day forecast for {state['location']}...")
        weather_raw = get_weather_full(state["location"])
        weather_summary = format_weather_for_llm(weather_raw)
        _log(f"🌡️ **Weather:** `{weather_raw.get('current_temp', '?')}°C — "
             f"{weather_raw.get('current_condition', '')}`")

        risk_count = len(weather_raw.get("risk_windows", []))
        if risk_count:
            _log(f"⚠️ **{risk_count} weather risk window(s) detected in the next 7 days**")

        _log("🌐 **Executor:** Searching agricultural databases...")
        try:
            search_results = search_tool.invoke(state["planned_search_query"])
        except Exception:
            search_results = "Web search failed. Proceeding with general agricultural knowledge."

        return {
            "weather_raw": weather_raw,
            "weather_summary": weather_summary,
            "search_data": search_results,
        }

    # ------------------------------------------------------------------
    # NODE 4: Synthesizer — builds final treatment plan
    # ------------------------------------------------------------------
    def synthesizer_node(state: AgriState):
        _log("✍️ **Synthesizer:** Drafting treatment plan...")

        lang_instruction = ""
        if state.get("language") and state["language"] != "English":
            lang_instruction = f"\nIMPORTANT: Write the entire response in {state['language']}."

        past_context = ""
        if state.get("past_issues"):
            past_context = f"\nFarmer's Past Issues (for context):\n{state['past_issues']}\n"

        image_context = ""
        if state.get("image_diagnosis"):
            image_context = f"\nVisual Diagnosis from Photo:\n{state['image_diagnosis']}\n"

        prompt = f"""You are an expert agricultural AI assistant specializing in organic farming.

Farmer's Report:
- Crop: {state.get('crop_type', 'unspecified')}
- Growing Stage: {state.get('growing_stage', 'unspecified')}
- Issue Description: {state['query']}
- Disease Category (pre-classified): {state.get('disease_class', 'unknown').upper()}
- Location: {state['location']}
{image_context}
Weather Data:
{state['weather_summary']}

Web Research Findings:
{state['search_data'][:2000]}
{past_context}

Instructions:
1. Provide a **3-step organic treatment plan** tailored to the disease category.
2. For each step, mention **commonly available materials** (e.g., neem oil, baking soda, compost).
3. Reference the **weather forecast** — flag optimal treatment windows and any days to avoid (rain/high wind).
4. Add a **Confidence Level** (High/Medium/Low) with a brief reason.
5. If confidence is Low or the disease seems severe, add a **⚠️ Escalation Notice** recommending contact with a local agricultural extension officer.
6. Keep it empathetic, practical, and free of jargon.
7. Use markdown formatting (headers, bullet points, bold).
{lang_instruction}"""

        response = llm.invoke(prompt)
        advice = response.content

        # Build explainability content
        explanation = (
            f"**Disease Category Detected:** {state.get('disease_class', 'unknown').upper()}\n\n"
            f"**Search Query Used:** `{state.get('planned_search_query', '')}`\n\n"
            f"**Weather Summary:**\n```\n{state['weather_summary']}\n```\n\n"
            f"**Raw Search Snippets:**\n> {state['search_data'][:800]}..."
        )

        # Auto-assess confidence for DB storage
        confidence = "high"
        if "low confidence" in advice.lower() or "uncertain" in advice.lower():
            confidence = "low"
        elif "medium confidence" in advice.lower() or "consult" in advice.lower():
            confidence = "medium"

        return {"final_advice": advice, "explanation": explanation, "confidence": confidence}

    # ------------------------------------------------------------------
    # Build Graph
    # ------------------------------------------------------------------
    workflow = StateGraph(AgriState)
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("synthesizer", synthesizer_node)

    workflow.add_edge(START, "classifier")
    workflow.add_edge("classifier", "planner")
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "synthesizer")
    workflow.add_edge("synthesizer", END)

    agri_agent = workflow.compile()

    initial_state = {
        "query": user_query,
        "location": user_location,
        "crop_type": crop_type,
        "growing_stage": growing_stage,
        "language": language,
        "image_diagnosis": image_diagnosis,
        "past_issues": past_issues,
        "disease_class": "",
        "confidence": "",
        "planned_search_query": "",
        "weather_raw": {},
        "weather_summary": "",
        "search_data": "",
        "escalate": False,
        "final_advice": "",
        "explanation": "",
    }

    return agri_agent.invoke(initial_state)
