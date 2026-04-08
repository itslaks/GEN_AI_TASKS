# 🚀 GEN_AI — Generative AI Projects Collection

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-purple)](https://langchain-ai.github.io/langgraph/)
[![Groq](https://img.shields.io/badge/Groq-LLM-orange)](https://groq.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-VectorDB-green)](https://www.trychroma.com/)

A comprehensive collection of AI-powered projects spanning **5 days** of coursework — covering prompt engineering, RAG pipelines, agentic workflows, LangGraph orchestration, and capstone projects. Each project is self-contained with its own README, requirements, and interactive UI.

---

## 📁 Repository Structure

```
GEN_AI/
├── Hands_on_Lab/          # Hands-on lab exercises (Day 1–3, 4 tasks each)
│   ├── Day_1/             #   Prompt engineering & reasoning agents
│   ├── Day_2/             #   RAG systems & vector search
│   └── Day_3/             #   LangGraph workflows & multi-agent systems
│
├── Assignment/            # Take-home assignments (Day 1–3, Day 4 upcoming)
│   ├── Day_1/             #   Prompt library & debugging prompts
│   ├── Day_2/             #   RAG system + comparison report
│   └── Day_3/             #   Recruitment_Pipeline_Workflow and Debugging_a_Broken_Workflow
│
├── Class_Tasks/           # In-class exercises
│   ├── Day_2/             #   CineAI — movie recommendation engine
│   └── Day_3/             #   ETL chatbot
│
├── .venv/                 # Python virtual environment
├── .gitignore
└── README.md              # ← You are here
```

---

## 🗓️ Course Schedule & Status

| Day | Topic | Hands-on Lab | Assignment | Class Task |
|-----|-------|:------------:|:----------:|:----------:|
| **Day 1** | Prompt Engineering & Agents | ✅ 4 tasks | ✅ 2 docs | — |
| **Day 2** | RAG & Vector Search | ✅ 4 tasks | ✅ 2 items | ✅ CineAI |
| **Day 3** | LangGraph & Multi-Agent | ✅ 4 tasks | ✅ 2 items  | ✅ ETL chatbot |
| **Day 4** | *(Upcoming)* | 🔲 Pending | 🔲 Pending | — |
| **Day 5** | Capstone Project | 🔲 Pending | — | — |

---

## 🧪 Hands-on Lab

### Day 1 — Prompt Engineering & Reasoning Agents

| # | Task | Description | Tech Stack | Port |
|---|------|-------------|------------|------|
| 1 | [Reasoning Agent Web App](Hands_on_Lab/Day_1/Task_1/) | ReAct agent with web search (DuckDuckGo) | Flask, Groq | 8501 |
| 2 | [Math CoT Solver](Hands_on_Lab/Day_1/Task_2/) | Chain-of-Thought math problem solver | FastAPI, Groq | 5500 |
| 3 | [Code Review Agent](Hands_on_Lab/Day_1/Task_3/) | AI-powered Python code analysis & review | FastAPI, Groq, AST | 8034 |
| 4 | [Customer Support Chatbot](Hands_on_Lab/Day_1/Task_4/) | Three prompt patterns for support bots | Flask, Groq | 5000 |

---

### Day 2 — RAG & Vector Search

| # | Task | Description | Tech Stack | Port |
|---|------|-------------|------------|------|
| 1 | [PDF RAG System](Hands_on_Lab/Day_2/Task_1/) | Semantic search & Q&A over PDF documents | Flask, ChromaDB, Groq | 5000 |
| 2 | [FAQ RAG Assistant](Hands_on_Lab/Day_2/Task_2/) | FAQ retrieval-augmented generation | Flask, ChromaDB, Groq | 5000 |
| 3 | [Hybrid Search Engine (NEXUS)](Hands_on_Lab/Day_2/Task_3/) | Combined keyword + semantic search | Flask, ChromaDB, Groq | 5000 |
| 4 | [Multi-Document RAG (NEXUS RAG)](Hands_on_Lab/Day_2/Task_4/) | Multi-file intelligence system with uploads | Flask, ChromaDB, Groq | 5000 |

---

### Day 3 — LangGraph & Multi-Agent Systems

| # | Task | Description | Tech Stack | Port |
|---|------|-------------|------------|------|
| 1 | [LangGraph ETL Pipeline](Hands_on_Lab/Day_3/Task_1/) | Data extraction, transformation & loading | LangGraph, Jupyter | — |
| 2 | [Sentiment Router](Hands_on_Lab/Day_3/Task_2/) | Sentiment-based routing with LangGraph | LangGraph, Flask, HuggingFace | 5000 |
| 3 | [**HITL Content Moderation (NeuralGuard)**](Hands_on_Lab/Day_3/Task_3/) | Human-in-the-loop approval workflow | LangGraph, Flask, Groq | **5001** |
| 4 | [**Multi-Agent Research Pipeline**](Hands_on_Lab/Day_3/Task_4/) | 3-agent system (researcher→writer→editor) | LangGraph, Flask, ChromaDB, Groq | **5000** |

> **Day 3 Highlights:**
> - **Task 3** uses LangGraph `interrupt_before` + `MemorySaver` for true HITL pause/resume
> - **Task 4** orchestrates 3 agents via LangGraph state graph with ChromaDB vector retrieval

---

### Day 4 — *(Upcoming)*

Hands-on lab tasks for Day 4 will be added here.

---

### Day 5 — Capstone Project *(Upcoming)*

The capstone project will be added here.

---

## 📝 Assignments

### Day 1 — Prompt Engineering

| File | Description |
|------|-------------|
| [assignment1_prompt_library.docx](Assignment/Day_1/assignment1_prompt_library.docx) | Curated prompt library for various AI tasks |
| [assignment2_debugging_prompts.docx](Assignment/Day_1/assignment2_debugging_prompts.docx) | Debugging prompts and analysis |

### Day 2 — RAG Systems

| Item | Description |
|------|-------------|
| [Manual RAG System](Assignment/Day_2/RAG_System_for_Product_Manuals/) | RAG pipeline for product manual Q&A |
| [RAG vs Non-RAG Comparison](Assignment/Day_2/RAG_vs_NonRAG_Comparison_Report.docx) | Comparative analysis report |

### Day 3 — *(Upcoming)*

Assignment for Day 3 will be added here.

### Day 4 — *(Upcoming)*

Assignment for Day 4 will be added here.

---

## 🏫 Class Tasks

### Day 2

| Task | Description |
|------|-------------|
| [CineAI — Movie Recommendation Engine](Class_Tasks/Day_2/) | AI-powered movie recommendations with Groq + OMDb API |

### Day 3 — *(Upcoming)*

Class tasks for Day 3 will be added here.

---

## ⚡ Quick Start

### Prerequisites

- **Python 3.10+**
- **Groq API key** — free at [console.groq.com](https://console.groq.com)

### Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd GEN_AI

# 2. Create & activate virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. Navigate to any task and run it
cd Hands_on_Lab/Day_3/Task_4
pip install -r requirements.txt
python app.py
```

Each task has its own `requirements.txt` and detailed README with setup instructions.

---

## 🔧 Tech Stack Overview

| Technology | Used In | Purpose |
|------------|---------|---------|
| **LangGraph** | Day 3 | State-graph workflow orchestration |
| **Groq API** | Day 1–3 | LLM inference (llama-3.1-8b-instant) |
| **ChromaDB** | Day 2–3 | Vector storage & semantic retrieval |
| **Flask** | Day 1–3 | Web backends & API servers |
| **FastAPI** | Day 1 | High-performance API server |
| **LangChain** | Day 2–3 | LLM framework & integrations |
| **HuggingFace** | Day 3 | Sentiment analysis transformers |
| **python-dotenv** | All | Environment variable management |

---

## 🙏 Acknowledgments

- [Groq](https://groq.com/) — fast AI inference (free tier)
- [LangGraph](https://langchain-ai.github.io/langgraph/) — workflow orchestration
- [ChromaDB](https://www.trychroma.com/) — vector database
- [Flask](https://flask.palletsprojects.com/) & [FastAPI](https://fastapi.tiangolo.com/) — web frameworks

---

*Built with ❤️ as part of a Generative AI course by Lakshan*
