import os
import re
import json
import uuid
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple

import fitz  # PyMuPDF
import faiss
import numpy as np
from flask import Flask, request, jsonify, send_from_directory
from groq import Groq
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, CrossEncoder
from transformers import pipeline

MANUAL_STORE = "artifacts/manual_chunks.jsonl"
INDEX_STORE = "artifacts/faiss.index"
META_STORE = "artifacts/faiss_meta.json"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

Path("artifacts").mkdir(exist_ok=True)

app = Flask(__name__, static_folder=".", static_url_path="")

embedder = SentenceTransformer(EMBED_MODEL)
reranker = CrossEncoder(RERANK_MODEL)
local_llm = pipeline("text-generation", model="mistralai/Mistral-7B-Instruct-v0.2")


def clean_text(text: str) -> str:
    text = re.sub(r"-\n", "", text)
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = clean_text(page.get_text("text"))
        pages.append(
            {
                "id": f"page_{i + 1}",
                "page": i + 1,
                "section": f"Page {i + 1}",
                "text": text,
            }
        )
    return pages


def fixed_chunks(text: str, size: int = 500, overlap: int = 100) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def recursive_chunks(pages: List[Dict[str, Any]]) -> List[str]:
    return [p["text"] for p in pages if p.get("text")]


def semantic_chunks(text: str, target_size: int = 500) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], ""
    for sent in sentences:
        if len(current) + len(sent) <= target_size:
            current = f"{current} {sent}".strip()
        else:
            if current:
                chunks.append(current)
            current = sent
    if current:
        chunks.append(current)
    return chunks


def build_artifacts(pdf_path: str, strategy: str = "fixed") -> List[Dict[str, Any]]:
    pages = extract_pdf(pdf_path)
    records: List[Dict[str, Any]] = []

    for page in pages:
        if strategy == "fixed":
            chunks = fixed_chunks(page["text"])
        elif strategy == "recursive":
            chunks = recursive_chunks([page])
        elif strategy == "semantic":
            chunks = semantic_chunks(page["text"])
        else:
            raise ValueError("Invalid strategy. Use fixed, recursive, or semantic.")

        for idx, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            records.append(
                {
                    "id": str(uuid.uuid4()),
                    "page": page["page"],
                    "section": page["section"],
                    "chunk_id": idx + 1,
                    "text": chunk.strip(),
                    "strategy": strategy,
                }
            )

    with open(MANUAL_STORE, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return records


def build_index(records: List[Dict[str, Any]]) -> None:
    texts = [r["text"] for r in records]
    vectors = embedder.encode(texts, convert_to_numpy=True).astype("float32")
    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, INDEX_STORE)

    with open(META_STORE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def dense_retrieve(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    index = faiss.read_index(INDEX_STORE)
    with open(META_STORE, "r", encoding="utf-8") as f:
        meta = json.load(f)

    q_vec = embedder.encode([query], convert_to_numpy=True).astype("float32")
    _, idxs = index.search(q_vec, min(top_k, len(meta)))
    return [meta[i] for i in idxs[0] if i != -1]


def hybrid_retrieve(query: str, top_k: int = 5, alpha: float = 0.6) -> List[Dict[str, Any]]:
    dense_results = dense_retrieve(query, top_k=top_k * 4)
    if not dense_results:
        return []

    tokenized_corpus = [r["text"].split() for r in dense_results]
    bm25 = BM25Okapi(tokenized_corpus)
    sparse_scores = bm25.get_scores(query.split())

    sparse_min = float(np.min(sparse_scores))
    sparse_max = float(np.max(sparse_scores))
    sparse_denom = (sparse_max - sparse_min) if sparse_max != sparse_min else 1.0

    fused: List[Tuple[Dict[str, Any], float]] = []
    for i, item in enumerate(dense_results):
        dense_score = 1.0 / (i + 1)
        sparse_norm = (float(sparse_scores[i]) - sparse_min) / sparse_denom
        final_score = alpha * dense_score + (1.0 - alpha) * sparse_norm
        fused.append((item, final_score))

    fused.sort(key=lambda x: x[1], reverse=True)
    candidates = [item for item, _ in fused[: top_k * 2]]

    pairs = [[query, c["text"]] for c in candidates]
    rerank_scores = reranker.predict(pairs)
    reranked = sorted(zip(candidates, rerank_scores), key=lambda x: x[1], reverse=True)
    return [x[0] for x in reranked[:top_k]]


def generate_answer(query: str, contexts: List[Dict[str, Any]]) -> str:
    context_text = "\n\n".join([f"[Page {c['page']}] {c['text']}" for c in contexts])

    prompt = f"""
Answer strictly from the provided manual context.
If evidence is insufficient, say exactly: INSUFFICIENT EVIDENCE.
Always cite supporting page numbers in your answer (example: [Page 12]).

Context:
{context_text}

Question: {query}
"""

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        client = Groq(api_key=groq_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()

    out = local_llm(prompt, max_new_tokens=300, do_sample=False)
    return out[0]["generated_text"].strip()


def faithfulness_score(answer: str, contexts: List[Dict[str, Any]]) -> float:
    claims = [line.strip() for line in re.split(r"[.\n]+", answer) if line.strip()]
    if not claims:
        return 0.0

    support_hits = 0
    for claim in claims:
        claim_probe = claim.lower()[:40]
        if any(claim_probe in c["text"].lower() for c in contexts):
            support_hits += 1
    return round(support_hits / len(claims), 2)


def citation_coverage(answer: str, contexts: List[Dict[str, Any]]) -> float:
    cited_pages = set(re.findall(r"\[Page\s+(\d+)\]", answer, flags=re.IGNORECASE))
    context_pages = {str(c["page"]) for c in contexts}
    if not context_pages:
        return 0.0
    return round(len(cited_pages.intersection(context_pages)) / len(context_pages), 2)


@app.route("/")
def index() -> Any:
    return send_from_directory(".", "index.html")


@app.route("/query", methods=["POST"])
def query_api() -> Any:
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    contexts = hybrid_retrieve(question, top_k=5)
    answer = generate_answer(question, contexts) if contexts else "INSUFFICIENT EVIDENCE."

    return jsonify(
        {
            "answer": answer,
            "citations": [{"page": c["page"], "section": c["section"]} for c in contexts],
        }
    )


def evaluate() -> None:
    sample_questions = [
        "What is the installation process?",
        "How do I reset the device?",
        "What are safety warnings?",
        "How can I troubleshoot power issues?",
        "What are warranty limitations?",
    ]

    results = []
    failures = []

    for question in sample_questions:
        contexts = hybrid_retrieve(question, top_k=5)
        answer = generate_answer(question, contexts) if contexts else "INSUFFICIENT EVIDENCE."

        faith = faithfulness_score(answer, contexts)
        cite_cov = citation_coverage(answer, contexts)
        precision_at_5 = round(len(contexts) / 5.0, 2)

        row = {
            "question": question,
            "precision_at_5": precision_at_5,
            "faithfulness": faith,
            "citation_coverage": cite_cov,
        }
        results.append(row)

        if faith < 0.6 or "INSUFFICIENT EVIDENCE" in answer.upper():
            failures.append(
                {
                    "question": question,
                    "faithfulness": faith,
                    "answer_preview": answer[:180].replace("\n", " "),
                }
            )

    avg_p5 = round(float(np.mean([r["precision_at_5"] for r in results])), 2)
    avg_faith = round(float(np.mean([r["faithfulness"] for r in results])), 2)
    avg_cov = round(float(np.mean([r["citation_coverage"] for r in results])), 2)

    with open("evaluation_report.md", "w", encoding="utf-8") as f:
        f.write("# Evaluation Report\n\n")
        f.write("## Aggregate Metrics\n\n")
        f.write(f"- Average Precision@5: **{avg_p5}**\n")
        f.write(f"- Average Faithfulness: **{avg_faith}**\n")
        f.write(f"- Average Citation Coverage: **{avg_cov}**\n\n")

        f.write("## Per-Question Metrics\n\n")
        f.write("| Question | P@5 | Faithfulness | Citation Coverage |\n")
        f.write("|---|---:|---:|---:|\n")
        for r in results:
            f.write(
                f"| {r['question']} | {r['precision_at_5']} | {r['faithfulness']} | {r['citation_coverage']} |\n"
            )

        f.write("\n## Failure Analysis\n\n")
        if not failures:
            f.write("- No major failures detected.\n")
        else:
            for fail in failures:
                f.write(
                    f"- **Q:** {fail['question']} | **Faithfulness:** {fail['faithfulness']} | "
                    f"**Answer Preview:** {fail['answer_preview']}...\n"
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest", "serve", "eval"])
    parser.add_argument("--pdf", default="manual.pdf")
    parser.add_argument("--strategy", choices=["fixed", "recursive", "semantic"], default="semantic")
    args = parser.parse_args()

    if args.command == "ingest":
        records = build_artifacts(args.pdf, args.strategy)
        build_index(records)
        print("Ingestion and indexing completed.")
    elif args.command == "eval":
        evaluate()
        print("Evaluation report generated.")
    else:
        app.run(debug=True)
