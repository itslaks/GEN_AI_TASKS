import os
import time
from typing import TypedDict, List, Dict, Any, Literal
from flask import Flask, request, jsonify, send_from_directory
from transformers import pipeline
from langchain_groq import ChatGroq
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv()

# Define state typed dict
class WorkflowState(TypedDict):
    history: List[Dict[str, str]]
    query: str
    sentiment_label: str
    sentiment_score: float
    route: str
    response_text: str
    metrics: Dict[str, Any]
    errors: List[str]

# Load API Key
groq_api_key = os.environ.get("GROQ_API_KEY", "")

# Load HuggingFace Sentiment Analysis
# Graceful fallback to NEUTRAL if model fails to load
_sentiment_analyzer = None
try:
    # Uses subset of models optimized for CPUs by default
    _sentiment_analyzer = pipeline(
        "sentiment-analysis",
        model="distilbert-base-uncased-finetuned-sst-2-english",
        device=-1
    )
except Exception as e:
    print(f"Warning: Failed to load sentiment model: {e}")

# Setup LLM with fallback
try:
    primary_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.7, api_key=groq_api_key)
    fallback_llm = ChatOllama(model="mistral", temperature=0.7)
    llm = primary_llm.with_fallbacks([fallback_llm])
except Exception as e:
    # If groq not set or unavailable, fallback purely to local Ollama mistral
    llm = ChatOllama(model="mistral", temperature=0.7)

# LangGraph Nodes
def analyze_sentiment(state: WorkflowState) -> WorkflowState:
    start_time = time.time()
    query = state.get("query", "").strip()
    
    # Defaults
    label = "NEUTRAL"
    score = 0.0
    route = "NEUTRAL"
    errors = state.get("errors", [])
    if not errors:
        errors = []
    
    if not query:
        errors.append("Empty or whitespace query provided.")
    elif _sentiment_analyzer:
        try:
            result = _sentiment_analyzer(query)[0]
            label = result["label"].upper()
            score = result["score"]
            # Threshold logic: Must be confident (> 0.6)
            if score < 0.6:
                route = "NEUTRAL"
            elif label == "POSITIVE":
                route = "POSITIVE"
            elif label == "NEGATIVE":
                route = "NEGATIVE"
            else:
                route = "NEUTRAL"
        except Exception as e:
            errors.append(f"Model error: {e}")
            route = "NEUTRAL"
    else:
        errors.append("Sentiment model not loaded.")
        route = "NEUTRAL"
    
    metrics = state.get("metrics", {})
    if not metrics:
        metrics = {}
    metrics["sentiment_time_ms"] = round((time.time() - start_time) * 1000, 2)
    
    print(f"[Node: analyze_sentiment] Label: {label}, Score: {score}, Route: {route}")
    
    return {
        "sentiment_label": label,
        "sentiment_score": score,
        "route": route,
        "errors": errors,
        "metrics": metrics
    }

def route_decision(state: WorkflowState) -> str:
    return state.get("route", "NEUTRAL")

def generate_response(state: WorkflowState, system_prompt: str, node_name: str) -> WorkflowState:
    start_time = time.time()
    query = state.get("query", "")
    
    try:
        messages = [SystemMessage(content=system_prompt)]
        
        # Inject conversation history
        for msg in state.get("history", []):
            role = msg.get("role", "user")
            text = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=text))
            elif role == "assistant":
                messages.append(AIMessage(content=text))
                
        # Append current query
        messages.append(HumanMessage(content=query if query else "(Empty query)"))
        
        response = llm.invoke(messages)
        content = response.content
    except Exception as e:
        content = f"Sorry, an error occurred while processing your request: {e}"
        state.setdefault("errors", []).append(str(e))
        
    metrics = state.get("metrics", {})
    metrics[f"{node_name}_time_ms"] = round((time.time() - start_time) * 1000, 2)
    print(f"[Node: {node_name}] Generated response snippet: {content[:50]}...")
    
    return {"response_text": content, "metrics": metrics}

def positive_handler(state: WorkflowState) -> WorkflowState:
    prompt = "You are an expert conversational analyst. The user's input was routed to the POSITIVE branch. Analyze their mindset, emotional state, and conversational intent (e.g., affection, joy, excitement). Do NOT answer their query directly. Instead, provide a brief psychological breakdown of how they are feeling."
    return generate_response(state, prompt, "positive_handler")

def negative_handler(state: WorkflowState) -> WorkflowState:
    prompt = "You are an expert conversational analyst. The user's input was routed to the NEGATIVE branch. Analyze their mindset, emotional state, and intent (e.g., sadness, frustration, seeking comfort). Note: If they just said a polite greeting like 'How was your day?', point out they are likely just curious and caring, not actually negative. Do NOT answer their query directly. Instead, provide a brief psychological breakdown."
    return generate_response(state, prompt, "negative_handler")

def neutral_handler(state: WorkflowState) -> WorkflowState:
    prompt = "You are an expert conversational analyst. The user's input was routed to the NEUTRAL branch. Analyze their mindset, emotional state, and intent (e.g., curiosity, politeness, casual conversation starter). Do NOT answer their query directly. Instead, provide a brief psychological breakdown of what conversation they are trying to initiate."
    return generate_response(state, prompt, "neutral_handler")

# Build the Graph
workflow = StateGraph(WorkflowState)
workflow.add_node("analyze_sentiment", analyze_sentiment)
workflow.add_node("POSITIVE", positive_handler)
workflow.add_node("NEGATIVE", negative_handler)
workflow.add_node("NEUTRAL", neutral_handler)

workflow.set_entry_point("analyze_sentiment")
workflow.add_conditional_edges("analyze_sentiment", route_decision)
workflow.add_edge("POSITIVE", END)
workflow.add_edge("NEGATIVE", END)
workflow.add_edge("NEUTRAL", END)

app_graph = workflow.compile()

# Flask App setup
app = Flask(__name__, static_folder=".", static_url_path="")

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy" if _sentiment_analyzer else "degraded",
        "models": {
            "sentiment_analyzer_loaded": bool(_sentiment_analyzer)
        }
    })

@app.route("/api/process", methods=["POST"])
def process_query():
    data = request.json or {}
    query = data.get("query", "")
    history = data.get("history", [])
    
    initial_state = {
        "history": history,
        "query": query,
        "sentiment_label": "",
        "sentiment_score": 0.0,
        "route": "",
        "response_text": "",
        "metrics": {"total_calls": 1},
        "errors": []
    }
    
    t0 = time.time()
    result = app_graph.invoke(initial_state)
    result["metrics"]["total_time_ms"] = round((time.time() - t0) * 1000, 2)
    
    print("\n--- FINAL SUMMARY ---")
    print(f"Sentiment: {result.get('sentiment_label')} ({result.get('sentiment_score')})")
    print(f"Route: {result.get('route')}")
    print(f"Metrics: {result.get('metrics')}")
    print("---------------------\n")
    
    return jsonify({
        "sentiment_label": result.get("sentiment_label"),
        "sentiment_score": result.get("sentiment_score"),
        "route": result.get("route"),
        "response_text": result.get("response_text"),
        "metrics": result.get("metrics"),
        "errors": result.get("errors")
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
