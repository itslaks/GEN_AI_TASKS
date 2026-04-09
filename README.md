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
├── Hands_on_Lab/          # Hands-on lab exercises (Day 1–4)
│   ├── Day_1/             #   Prompt engineering & reasoning agents
│   ├── Day_2/             #   RAG systems & vector search
│   ├── Day_3/             #   LangGraph workflows & multi-agent systems
│   └── Day_4/             #   CrewAI orchestration & advanced RAG
│
├── Assignment/            # Take-home assignments (Day 1–4)
│   ├── Day_1/             #   Prompt library & debugging prompts
│   ├── Day_2/             #   RAG system + comparison report
│   ├── Day_3/             #   Recruitment & Debugging workflows
│   └── Day_4/             #   CrewAI researcher & Enterprise Copilot
│
├── Class_Tasks/           # In-class exercises
│   ├── Day_2/             #   CineAI — movie recommendation engine
│   ├── Day_3/             #   ETL chatbot (LangGraph + RAG)
│   └── Day_4/             #   DataPulse (Data Extraction Agent)
│
├── .venv/                 # Python virtual environment
├── .gitignore
└── README.md              # ← You are here
```

---

## 🗓️ Course Schedule & Status

| Day       | Topic                       | Hands-on Lab | Assignment |   Class Task   |
| --------- | --------------------------- | :----------: | :--------: | :------------: |
| **Day 1** | Prompt Engineering & Agents |  ✅ 4 tasks  | ✅ 2 docs  |       —        |
| **Day 2** | RAG & Vector Search         |  ✅ 4 tasks  | ✅ 2 items |   ✅ CineAI    |
| **Day 3** | LangGraph & Multi-Agent     |  ✅ 4 tasks  | ✅ 2 items | ✅ ETL chatbot |
| **Day 4** | CrewAI & Advanced RAG       |  ✅ 3 tasks  | ✅ 2 items |  ✅ DataPulse  |
| **Day 5** | Capstone Project            |  🔲 Pending  |     —      |       —        |

---

## 🧪 Hands-on Lab

### Day 1 — Prompt Engineering & Reasoning Agents

| #   | Task                                                   | Description                              | Tech Stack         | Port |
| --- | ------------------------------------------------------ | ---------------------------------------- | ------------------ | ---- |
| 1   | [Reasoning Agent Web App](Hands_on_Lab/Day_1/Task_1/)  | ReAct agent with web search (DuckDuckGo) | Flask, Groq        | 8501 |
| 2   | [Math CoT Solver](Hands_on_Lab/Day_1/Task_2/)          | Chain-of-Thought math problem solver     | FastAPI, Groq      | 5500 |
| 3   | [Code Review Agent](Hands_on_Lab/Day_1/Task_3/)        | AI-powered Python code analysis & review | FastAPI, Groq, AST | 8034 |
| 4   | [Customer Support Chatbot](Hands_on_Lab/Day_1/Task_4/) | Three prompt patterns for support bots   | Flask, Groq        | 5000 |

---

### Day 2 — RAG & Vector Search

| #   | Task                                                         | Description                                 | Tech Stack            | Port |
| --- | ------------------------------------------------------------ | ------------------------------------------- | --------------------- | ---- |
| 1   | [PDF RAG System](Hands_on_Lab/Day_2/Task_1/)                 | Semantic search & Q&A over PDF documents    | Flask, ChromaDB, Groq | 5000 |
| 2   | [FAQ RAG Assistant](Hands_on_Lab/Day_2/Task_2/)              | FAQ retrieval-augmented generation          | Flask, ChromaDB, Groq | 5000 |
| 3   | [Hybrid Search Engine (NEXUS)](Hands_on_Lab/Day_2/Task_3/)   | Combined keyword + semantic search          | Flask, ChromaDB, Groq | 5000 |
| 4   | [Multi-Document RAG (NEXUS RAG)](Hands_on_Lab/Day_2/Task_4/) | Multi-file intelligence system with uploads | Flask, ChromaDB, Groq | 5000 |

---

### Day 3 — LangGraph & Multi-Agent Systems

| #   | Task                                                                    | Description                               | Tech Stack                       | Port     |
| --- | ----------------------------------------------------------------------- | ----------------------------------------- | -------------------------------- | -------- |
| 1   | [LangGraph ETL Pipeline](Hands_on_Lab/Day_3/Task_1/)                    | Data extraction, transformation & loading | LangGraph, Jupyter               | —        |
| 2   | [Sentiment Router](Hands_on_Lab/Day_3/Task_2/)                          | Sentiment-based routing with LangGraph    | LangGraph, Flask, HuggingFace    | 5000     |
| 3   | [**HITL Content Moderation (NeuralGuard)**](Hands_on_Lab/Day_3/Task_3/) | Human-in-the-loop approval workflow       | LangGraph, Flask, Groq           | **5001** |
| 4   | [**Multi-Agent Research Pipeline**](Hands_on_Lab/Day_3/Task_4/)         | 3-agent system (researcher→writer→editor) | LangGraph, Flask, ChromaDB, Groq | **5000** |

> **Day 3 Highlights:**
>
> - **Task 3** uses LangGraph `interrupt_before` + `MemorySaver` for true HITL pause/resume
> - **Task 4** orchestrates 3 agents via LangGraph state graph with ChromaDB vector retrieval

---

### Day 4 — CrewAI Orchestration & Advanced RAG

| #   | Task                                                                           | Description                                     | Tech Stack                  | Port |
| --- | ------------------------------------------------------------------------------ | ----------------------------------------------- | --------------------------- | ---- |
| 1   | [**AgroRAG — Agri Intelligence**](Hands_on_Lab/Day_4/agri_RAG_deployment_app/) | RAG system for farmers with weather integration | FastAPI, FAISS, GPT-4o-mini | 8000 |
| 2   | [**CREW/AI — Content Terminal**](Hands_on_Lab/Day_4/research_with_crew_ai/)    | 3-agent pipeline for blog post generation       | CrewAI, Flask, OpenAI       | 5000 |
| 3   | [CrewAI CLI Project](Hands_on_Lab/Day_4/research_app_created_in_crew_ai/)      | Template for scalable multi-agent crews         | CrewAI, UV, Python          | —    |

> **Day 4 Highlights:**
>
> - **AgroRAG** features a persistent FAISS index and local fallback logic for high reliability
> - **Content Terminal** demonstrates sequential delegation between Researcher, Writer, and Editor agents

---

### Day 5 — Capstone Project _(Upcoming)_

The capstone project will be added here.

---

## 📝 Assignments

### Day 1 — Prompt Engineering

| File                                                                                      | Description                                 |
| ----------------------------------------------------------------------------------------- | ------------------------------------------- |
| [assignment1_prompt_library.docx](Assignment/Day_1/assignment1_prompt_library.docx)       | Curated prompt library for various AI tasks |
| [assignment2_debugging_prompts.docx](Assignment/Day_1/assignment2_debugging_prompts.docx) | Debugging prompts and analysis              |

### Day 2 — RAG Systems

| Item                                                                               | Description                         |
| ---------------------------------------------------------------------------------- | ----------------------------------- |
| [Manual RAG System](Assignment/Day_2/RAG_System_for_Product_Manuals/)              | RAG pipeline for product manual Q&A |
| [RAG vs Non-RAG Comparison](Assignment/Day_2/RAG_vs_NonRAG_Comparison_Report.docx) | Comparative analysis report         |

### Day 3 — LangGraph Workflows

| Item                                                                                                    | Description                                |
| ------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| [Recruitment Pipeline](Assignment/Day_3/Recruitment_Pipeline_Workflow/Recruitment_Pipeline.ipynb)       | Multi-agent hiring workflow with LangGraph |
| [Broken Workflow Debug](Assignment/Day_3/Debugging_a_Broken_Workflow/Work_Flow_Broken_Code_fixed.ipynb) | Debugged and optimized LangGraph state     |

### Day 4 — CrewAI & Enterprise Systems

| Item                                                                                     | Description                                            |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| [CrewAI Research Assistant](Assignment/Day_4/CrewAI_Research_Assistant/DOCUMENTATION.md) | Advanced multi-agent research & analysis engine        |
| [NexusSchema Copilot](Assignment/Day_4/Enterprise_knowledge_copilot/)                    | Enterprise-grade data extraction & knowledge retrieval |

---

## 🏫 Class Tasks

### Day 2

| Task                                        | Description                                         | Tech Stack  |
| ------------------------------------------- | --------------------------------------------------- | ----------- |
| [CineAI — Movie Engine](Class_Tasks/Day_2/) | Premium recommendation engine with weighted metrics | Flask, Groq |

### Day 3

| Task                                          | Description                                      | Tech Stack       |
| --------------------------------------------- | ------------------------------------------------ | ---------------- |
| [ETL Chatbot](Class_Tasks/Day_3/ETL_chatbot/) | Intelligent data processor with RAG capabilities | LangGraph, Flask |

### Day 4

| Task                                         | Description                                  | Tech Stack                |
| -------------------------------------------- | -------------------------------------------- | ------------------------- |
| [DataPulse — Extraction](Class_Tasks/Day_4/) | Structured entity extraction from messy text | Flask, OpenAI GPT-4o-mini |

---

## ⚡ Quick Start

### Prerequisites

- **Python 3.10+**
- **Groq API key** — free at [console.groq.com](https://console.groq.com)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/itslaks/GEN_AI_TASKS.git
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

| Technology        | Used In  | Purpose                                  |
| ----------------- | -------- | ---------------------------------------- |
| **CrewAI**        | Day 4    | Multi-agent orchestration & processes    |
| **LangGraph**     | Day 3    | State-graph workflow orchestration       |
| **OpenAI API**    | Day 4    | High-reasoning LLM (GPT-4o-mini)         |
| **Groq API**      | Day 1–3  | Ultra-fast LLM inference                 |
| **ChromaDB**      | Day 2–3  | Vector storage & semantic retrieval      |
| **FAISS**         | Day 4    | Lightweight local vector search          |
| **FastAPI**       | Day 1, 4 | High-performance asynchronous web APIs   |
| **Flask**         | Day 1–4  | Web backends & API servers               |
| **LangChain**     | Day 2–4  | LLM framework & modular integrations     |
| **HuggingFace**   | Day 3    | Sentence-transformers & sentiment models |
| **python-dotenv** | All      | Global environment variable management   |

---

## 🙏 Acknowledgments

- [CrewAI](https://www.crewai.com/) — multi-agent orchestration
- [Groq](https://groq.com/) — fast AI inference
- [OpenAI](https://openai.com/) — foundation models (GPT-4o-mini)
- [LangGraph](https://langchain-ai.github.io/langgraph/) — stateful workflow orchestration
- [ChromaDB](https://www.trychroma.com/) & [FAISS](https://faiss.ai/) — vector databases
- [FastAPI](https://fastapi.tiangolo.com/) & [Flask](https://flask.palletsprojects.com/) — web frameworks

---

_Built with ❤️ as part of a Generative AI course by Lakshan_
