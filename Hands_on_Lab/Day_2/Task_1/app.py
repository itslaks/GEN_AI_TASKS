from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import io
import hashlib
from pypdf import PdfReader
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaLLM
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import tempfile
import re
from uuid import uuid4

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Simple state for MVP (single user)
current_manual_id = None
current_filename = None
file_content = None

def clean_text(text: str) -> str:
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        if re.match(r"^\d+$", line):
            continue
        if len(line) < 5:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)

def extract_pdf_pages(pdf_bytes: bytes) -> list[dict]:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        cleaned = clean_text(raw_text)
        if not cleaned.strip():
            continue
        pages.append({"page": index, "text": cleaned})
    return pages

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "manual_id": current_manual_id, "filename": current_filename})

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    global current_manual_id, current_filename, file_content
    if not file.filename.endswith(".pdf"):
        return RedirectResponse(url="/", status_code=303)
    file_content = await file.read()
    current_manual_id = hashlib.sha256(file_content).hexdigest()[:16]
    current_filename = file.filename
    return RedirectResponse(url="/", status_code=303)

@app.post("/index")
async def index_pdf():
    global current_manual_id, current_filename, file_content
    if not current_manual_id or not file_content:
        return RedirectResponse(url="/", status_code=303)

    pages = extract_pdf_pages(file_content)
    if not pages:
        return RedirectResponse(url="/", status_code=303)

    os.makedirs("./chroma_db", exist_ok=True)
    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        client.delete_collection(name=current_manual_id)
    except Exception:
        pass

    embedding_function = SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2",
        device="cpu",
    )
    collection = client.create_collection(
        name=current_manual_id,
        metadata={"filename": current_filename},
        embedding_function=embedding_function,
    )

    ids = []
    documents = []
    metadatas = []
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    for page in pages:
        chunks = splitter.create_documents(
            [page["text"]],
            metadatas=[
                {
                    "manual_id": current_manual_id,
                    "filename": current_filename,
                    "page": page["page"],
                    "chunk_id": str(uuid4()),
                    "section_heading": page["text"].split("\n")[0][:120],
                }
            ],
        )
        for chunk in chunks:
            ids.append(chunk.metadata["chunk_id"])
            metadatas.append(chunk.metadata)
            documents.append(chunk.page_content)

    collection.add(ids=ids, metadatas=metadatas, documents=documents)
    return RedirectResponse(url="/", status_code=303)

@app.post("/query")
async def query_manual(request: Request, query: str = Form(...), mode: str = Form(...), k: int = Form(...)):
    if not current_manual_id:
        return templates.TemplateResponse("index.html", {"request": request, "error": "No manual indexed.", "manual_id": current_manual_id, "filename": current_filename})
    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        collection = client.get_collection(name=current_manual_id)
    except ValueError:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": "Manual not indexed.",
                "manual_id": current_manual_id,
                "filename": current_filename,
            },
        )

    results = {"type": "search", "docs": []}
    try:
        query_embedding = collection.embeddings.embed_query(query)
        search = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        hits = search["documents"][0]
        metas = search["metadatas"][0]
        dists = search["distances"][0]
        results["docs"] = [
            {
                "page": meta.get("page", "N/A"),
                "content": hit[:300],
                "heading": meta.get("section_heading", ""),
                "distance": round(dist, 4),
            }
            for hit, meta, dist in zip(hits, metas, dists)
        ]
    except Exception:
        results["error"] = "Search is temporarily unavailable."

    if mode == "Ask" and results.get("docs"):
        try:
            llm = OllamaLLM(model="mistral", temperature=0.0)
            context = "\n\n".join(
                [f"Page {doc['page']}: {doc['content']}" for doc in results["docs"]]
            )
            prompt = (
                "Answer the question using only the retrieved manual chunks below. "
                "Do not invent information. Include page citations when available.\n\n"
                f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
            )
            answer = llm.invoke(prompt)
            results = {
                "type": "ask",
                "answer": answer,
                "sources": results["docs"],
            }
        except Exception as e:
            results["error"] = f"LLM error: {str(e)}. Try Search mode."

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "results": results,
            "manual_id": current_manual_id,
            "filename": current_filename,
        },
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)