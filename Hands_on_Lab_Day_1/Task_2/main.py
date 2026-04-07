"""
Math CoT Solver - FastAPI + Groq API with Chain-of-Thought prompting
"""

import os
import json
import logging
import asyncio
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_SECONDS = 30
MAX_RETRIES = 2

SYSTEM_PROMPT = """You are an expert math solver. Your job is to solve multi-step math problems accurately.

INTERNAL PROCESS (never shown to user):
- Reason step-by-step internally.
- Verify your answer using substitution or an alternate method.

OUTPUT RULES (strict):
- You MUST respond with ONLY a valid JSON object. No prose before or after.
- Never expose your internal chain-of-thought verbatim.
- The step_summary must be concise, user-friendly, high-level bullet points.
- If the problem is not a math problem, set final_answer to "Not a math problem".

JSON SCHEMA:
{
  "final_answer": "<the numeric or symbolic answer>",
  "step_summary": ["<step 1>", "<step 2>", "..."],
  "verification": "<brief sanity check or null>"
}

Rules:
- step_summary: 2-6 items max, each <= 25 words.
- verification: one sentence or null.
- final_answer: concise. Include units if applicable.
"""


class SolveRequest(BaseModel):
    problem: str

    @field_validator("problem")
    @classmethod
    def validate_problem(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Problem cannot be empty.")
        if len(v) > 2000:
            raise ValueError("Problem too long (max 2000 characters).")
        return v


class SolveResponse(BaseModel):
    final_answer: str
    step_summary: list[str]
    verification: Optional[str]


class HealthResponse(BaseModel):
    status: str


app = FastAPI(title="Math CoT Solver", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="."), name="static")


@app.get("/")
async def serve_index():
    return FileResponse("index.html")


async def call_groq(problem: str) -> dict:
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured.")

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.1,
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Solve this math problem:\n\n{problem}"},
        ],
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    last_error: Exception = Exception("Unknown error")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info("Groq request attempt %d", attempt)
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.post(GROQ_URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                raw = data["choices"][0]["message"]["content"].strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                log.info("Groq responded OK")
                return json.loads(raw)
        except json.JSONDecodeError as e:
            log.warning("JSON parse error: %s", e)
            last_error = HTTPException(status_code=502, detail="LLM returned non-JSON. Try rephrasing.")
        except httpx.HTTPStatusError as e:
            log.warning("Groq HTTP error %d", e.response.status_code)
            if e.response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid GROQ_API_KEY.")
            last_error = HTTPException(status_code=502, detail=f"Groq API error: {e.response.status_code}")
        except httpx.TimeoutException:
            log.warning("Groq timeout on attempt %d", attempt)
            last_error = HTTPException(status_code=504, detail="Groq API timed out.")
        except Exception as e:
            log.error("Unexpected error: %s", e)
            last_error = HTTPException(status_code=500, detail="Unexpected server error.")

        if attempt < MAX_RETRIES:
            await asyncio.sleep(1.5 * attempt)

    raise last_error


@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok"}


@app.post("/solve", response_model=SolveResponse)
async def solve(req: SolveRequest):
    log.info("Solving: %.120s", req.problem)
    result = await call_groq(req.problem)

    if not isinstance(result.get("final_answer"), str):
        raise HTTPException(status_code=502, detail="Malformed response from LLM.")
    if not isinstance(result.get("step_summary"), list):
        result["step_summary"] = []

    return SolveResponse(
        final_answer=result["final_answer"],
        step_summary=[str(s) for s in result["step_summary"]],
        verification=result.get("verification") or None,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)