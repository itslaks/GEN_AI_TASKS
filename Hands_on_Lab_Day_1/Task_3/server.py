"""
server.py — FastAPI web server for the Code Review Agent UI.
Runs on 127.0.0.1:8034
"""

import os
import sys
import json
import base64
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Make sure Task_3 root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import run_review
from analyzer import analyze

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Code Review Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ────────────────────────────────────────────────────────────────────
class ReviewRequest(BaseModel):
    code: str
    max_rounds: int = 2
    verbose: bool = False


# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    return {"status": "ok", "port": 8034}


@app.post("/review")
async def review_code(req: ReviewRequest):
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="No code provided.")
    if len(req.code) > 100_000:
        raise HTTPException(status_code=400, detail="Code too large (max 100KB).")

    log.info("Review request: %d chars, %d rounds", len(req.code), req.max_rounds)
    try:
        result = run_review(req.code, max_rounds=req.max_rounds, verbose=req.verbose)
        return JSONResponse(content=result)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/upload")
async def upload_file(file: UploadFile = File(...), max_rounds: int = Form(2)):
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files are accepted.")

    content = await file.read()
    if len(content) > 100_000:
        raise HTTPException(status_code=400, detail="File too large (max 100KB).")

    code = content.decode("utf-8", errors="replace")
    log.info("Upload review: %s (%d bytes)", file.filename, len(content))
    try:
        result = run_review(code, max_rounds=max_rounds, verbose=False)
        result["filename"] = file.filename
        return JSONResponse(content=result)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/analyze-only")
async def analyze_only(req: ReviewRequest):
    """Quick AST-only analysis — no LLM call."""
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="No code provided.")
    findings = analyze(req.code)
    return JSONResponse(content=findings.to_dict())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8034, reload=False)
