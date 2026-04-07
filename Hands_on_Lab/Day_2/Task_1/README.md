# Document Indexing with ChromaDB MVP Blueprint

## 1. Use Case Definition

- **User uploads/selects a product manual PDF (≈100 pages).**
- **System indexes it into ChromaDB and enables:**
  - a) Keyword-like search (top chunks based on semantic similarity).
  - b) Q&A ("Ask the manual") with citations (page numbers + chunk refs).
- **Output must be grounded in retrieved chunks; never invent details.**

## 2. Minimal but Scalable Architecture (LangChain-Centric)

- **Ingestion Chain:**
  - PDF load (pypdf via LangChain PyPDFLoader) → clean text (remove headers/footers) → chunking (RecursiveCharacterTextSplitter) → embeddings (OpenAI) → ChromaDB upsert.
- **Retrieval Chain:**
  - Similarity search (top-k) + optional MMR (Maximal Marginal Relevance) for diversity.
- **Answering Chain:**
  - LLM (OpenAI GPT-3.5-turbo) uses retrieved chunks to answer with citations.
- **Persistence:**
  - ChromaDB persisted locally (disk) with collection per manual/version (e.g., collection name = manual_id).

## 3. Data Inputs and Processing Details

- **PDF Parsing:**
  - Via pypdf (LangChain PyPDFLoader).
  - Handle headers/footers: detect and remove common patterns (e.g., page numbers, company logos via regex).
  - Page breaks: preserved in metadata as page_number.
- **Chunking Strategy:**
  - chunk_size=1000 characters, overlap=200 characters.
  - Rationale: Balances context retention (overlap) with granularity for manual sections; 1000 chars ≈ 150-250 words, suitable for product manuals.
- **Metadata per Chunk:**
  - manual_id (e.g., hash of PDF), filename, page_number(s) (list if chunk spans pages), section_heading (extracted from text, e.g., first line if starts with capital), chunk_id (UUID).
- **Deduplication and Re-index:**
  - Hash PDF content (SHA256); store hash in collection metadata.
  - On upload, check hash; if changed, delete old collection and re-index.

## 4. Models and Tools

- **LangChain Integrations:**
  - PyPDFLoader for PDF loading.
  - Chroma for vector store.
  - RecursiveCharacterTextSplitter for chunking.
  - RetrievalQA or ConversationalRetrievalChain for Q&A.
- **Embeddings Model:**
  - HuggingFace sentence-transformers/all-MiniLM-L6-v2 (free, local; assumption: effective for general text).
- **LLM Selection:**
  - Ollama Mistral (free, local; assumption: good performance for Q&A; requires Ollama running locally).
- **Offline Mode:**
  - Search-only without LLM: return top chunks with snippets and page refs.

## 5. Simple Interface (FastAPI + HTML)

- **UI Choice:** FastAPI with server-rendered HTML (Jinja2) for simple, custom dark theme.
- **Theme:** Dark background with neon brown accents (glow effects on buttons/inputs).
- **Required Features:**
  - Upload/select PDF (multipart form).
  - Button: "Index / Re-index" (triggers ingestion).
  - Query input (text input) with toggle: "Search" vs "Ask" (select).
  - Top-k selector (select: 3/5/8).
  - Results panel:
    - Answer (for Ask, with citations).
    - Retrieved sources: page numbers + snippets.
  - Error handling: unsupported PDF (check file type), indexing failures (redirect with error).

## 6. MVP Feature Set

- Single manual indexing + query first; optional support for multiple manuals via manual_id (future).
- Local persistence for ChromaDB (persist_directory="./chroma_db").
- No user accounts, no advanced analytics, no complex agent workflows.

## 7. Tech Stack and Deployment

- **Core:** Python 3.10, LangChain, pypdf, chromadb, fastapi, uvicorn, jinja2, sentence-transformers, langchain-community, langchain-ollama.
- **Deployment:** Local dev; run `python app.py` or `uvicorn app:app --reload`.
- **Prerequisites:** Ollama installed and running with Mistral model (`ollama pull mistral`).

## 8. Workflow Diagram Explanation

- **Indexing Workflow:**
  - PDF upload → PyPDFLoader loads pages → Clean text (regex) → RecursiveCharacterTextSplitter chunks → OpenAI embeddings → ChromaDB.upsert (with metadata).
- **Querying Workflow:**
  - User query → OpenAI embed query → ChromaDB.similarity_search (top-k) → (if Ask: LLM with retrieved chunks) → Answer + citations.

## Implementation Notes

- **Assumptions:** OpenAI models used; API keys required. If no keys, offline mode only.
- **Self-Check:** All requirements addressed; interface includes all features; MVP scope maintained.