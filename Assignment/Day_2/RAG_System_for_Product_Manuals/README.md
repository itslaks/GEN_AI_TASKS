# Manual RAG System

## Setup
```bash
pip install -r requirements.txt
```

## Environment

Copy `.env.example` to `.env` and set your key.

## Ingest PDF

```bash
python rag_manual.py ingest --pdf manual.pdf --strategy fixed
python rag_manual.py ingest --pdf manual.pdf --strategy recursive
python rag_manual.py ingest --pdf manual.pdf --strategy semantic
```

## Run App

```bash
python rag_manual.py serve
```

## Evaluate

```bash
python rag_manual.py eval
```

## Architecture Notes

- Chunking strategies: `fixed`, `recursive`, `semantic`
- Retrieval: FAISS dense retrieval + BM25 sparse fusion + cross-encoder reranking
- LLM behavior: Groq API first, local Mistral fallback if `GROQ_API_KEY` is missing
- Evaluation output: `evaluation_report.md` with Precision@5, faithfulness, citation coverage, and failure analysis

## Production Deployment Notes

Recommended stack:
- Flask API
- Gunicorn
- Nginx reverse proxy
- Redis cache
- Docker container

Example:

```bash
gunicorn -w 4 -b 0.0.0.0:8000 rag_manual:app
```
