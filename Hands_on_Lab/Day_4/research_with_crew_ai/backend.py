"""
CREW/AI — Content Generation Backend
=====================================
3-agent CrewAI pipeline: Researcher → Writer → Editor
Domain: Digital Life / Internet Literacy
Deploy-ready for Vercel (serverless) and local Flask dev.

Made by Lakshan
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from dotenv import load_dotenv

# ── Load Environment Variables ──────────────────────────────────────────────
load_dotenv()

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("crew_ai")

# ── Dependency check ─────────────────────────────────────────────────────────
try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except ImportError:
    sys.exit("❌  Missing Flask. Run: pip install flask flask-cors")

try:
    from crewai import Agent, Task, Crew, Process
except ImportError:
    sys.exit("❌  Missing CrewAI. Run: pip install crewai")

try:
    # We use LiteLLM string format for CrewAI 1.x compatibility
    pass 
except ImportError:
    pass

# ── Configuration ─────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL_NAME     = os.environ.get("MODEL_NAME", "gpt-4o-mini")
MAX_TOKENS     = int(os.environ.get("MAX_TOKENS", "4096"))
DEFAULT_WORDS  = int(os.environ.get("DEFAULT_WORDS", "1200"))
DEFAULT_TONE   = os.environ.get("DEFAULT_TONE", "trustworthy and practical")
DEFAULT_AUD    = os.environ.get("DEFAULT_AUDIENCE", "general internet users")

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, origins="*")

# ────────────────────────────────────────────────────────────────────────────
#  INPUT VALIDATION
# ────────────────────────────────────────────────────────────────────────────
def validate_input(data: dict) -> tuple[dict, str | None]:
    """Return (cleaned_data, error_message). error_message is None on success."""
    topic = (data.get("topic") or "").strip()
    if not topic:
        return {}, "Field 'topic' is required and cannot be empty."
    if len(topic) > 500:
        return {}, "Field 'topic' must be ≤ 500 characters."

    audience = (data.get("audience") or DEFAULT_AUD).strip() or DEFAULT_AUD
    tone     = (data.get("tone")     or DEFAULT_TONE).strip() or DEFAULT_TONE

    try:
        length = int(data.get("length_words", DEFAULT_WORDS))
    except (TypeError, ValueError):
        return {}, "'length_words' must be an integer."
    if not (100 <= length <= 5000):
        return {}, "'length_words' must be between 100 and 5000."

    return {"topic": topic, "audience": audience, "tone": tone, "length": length}, None


# ────────────────────────────────────────────────────────────────────────────
#  LLM FACTORY
# ────────────────────────────────────────────────────────────────────────────
def build_llm():
    if not OPENAI_API_KEY:
        raise EnvironmentError("OPENAI_API_KEY is not set. Add it to your .env file.")
    return MODEL_NAME


# ────────────────────────────────────────────────────────────────────────────
#  AGENT DEFINITIONS
# ────────────────────────────────────────────────────────────────────────────
def build_agents(llm):
    researcher = Agent(
        role="Senior Digital Literacy Researcher",
        goal=(
            "Produce a thorough, factually-cautious research brief on a given topic "
            "within the Digital Life / Internet Literacy domain. Your brief must be "
            "structured, practical, and free of fabricated citations."
        ),
        backstory=(
            "You are a veteran researcher who specialises in digital safety, privacy, "
            "cybersecurity hygiene, platform literacy, and online wellbeing. You never "
            "fabricate sources—instead you suggest credible categories of sources to verify. "
            "You flag misinformation risks and highlight protective steps for readers."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    writer = Agent(
        role="Digital Literacy Content Writer",
        goal=(
            "Write a polished, reader-friendly blog post using the researcher's brief. "
            "The post must be practical, include actionable checklists, and contain "
            "a 'What to do today' section."
        ),
        backstory=(
            "You are an expert content writer who translates complex digital-safety topics "
            "into accessible, empowering guidance for everyday internet users. You use a "
            "trustworthy, modern, non-alarmist voice, structure your writing with clear "
            "H2/H3 headings, short paragraphs, and bullet lists."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    editor = Agent(
        role="Editorial Quality Controller",
        goal=(
            "Review and tighten the draft blog post. Remove fluff, ensure consistent voice, "
            "add factual-caution language where needed, flag any policy-violating content, "
            "and output the final polished Markdown."
        ),
        backstory=(
            "You are a meticulous editor who cares deeply about accuracy, readability, "
            "and reader safety. You never publish content that could enable harm. You "
            "enforce a 'trustworthy, modern, practical, non-alarmist' tone and ensure "
            "every factual claim is hedged appropriately."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    return researcher, writer, editor


# ────────────────────────────────────────────────────────────────────────────
#  TASK DEFINITIONS
# ────────────────────────────────────────────────────────────────────────────
def build_tasks(researcher, writer, editor, topic: str, audience: str, tone: str, length: int):

    research_task = Task(
        description=f"""
You are the Researcher. Produce a STRUCTURED RESEARCH BRIEF on the following topic:

TOPIC: {topic}
TARGET AUDIENCE: {audience}

Your brief MUST include all of these sections:
1. Key Concepts — define the 4–6 core concepts the audience must understand.
2. Target Audience Assumptions — what prior knowledge do they have? What fears/misconceptions?
3. Do / Don't Guidance — 5 concrete dos and 5 donts for the audience.
4. Common Misconceptions — list 3–5 widespread myths and the truth behind each.
5. Safety & Privacy Checklist — 6–8 actionable safety steps related to the topic.
6. Suggested Sources to Verify — list 6–10 categories or named organisations
   (e.g. "CISA official advisories", "EFF.org privacy guides", "Google Safety Centre")
   that the writer/editor should verify. DO NOT fabricate quotes or specific URLs.
   Label clearly: "These are suggested categories — verify before publishing."

Tone: factual, cautious, thorough. No fabricated statistics.
""",
        expected_output=(
            "A structured research brief in plain text with all 6 sections clearly labelled. "
            "No markdown headings needed—plain numbered sections are fine."
        ),
        agent=researcher,
    )

    write_task = Task(
        description=f"""
You are the Writer. Using the Research Brief produced by the Researcher, write a complete
blog post in Markdown format.

TOPIC: {topic}
AUDIENCE: {audience}
TONE: {tone}
TARGET LENGTH: approximately {length} words

MANDATORY STRUCTURE:
- Title (H1) — compelling, SEO-friendly
- Short intro paragraph (hook the reader)
- At least 4 H2 sections covering the topic thoroughly
- Use H3 subheadings within sections where helpful
- Bullet lists and short paragraphs throughout
- A boxed "Quick Checklist" section (use > blockquote or a markdown checklist)
- A "What to Do Today" section (3–5 immediate actions the reader can take right now)
- A brief conclusion paragraph
- A "Suggested Sources to Verify" section with the list from the brief
  (label them clearly as suggested, not verified)

STYLE RULES:
- Trustworthy, modern, practical, NON-ALARMIST
- Write for {audience}
- Short sentences. Active voice. No jargon without explanation.
- Do NOT fabricate statistics, percentages, or quotes.
- Do NOT provide instructions that could enable fraud, hacking, or harm.
  If a risk is discussed, ALWAYS provide the protective countermeasure.
""",
        expected_output=(
            "A complete blog post in Markdown format, ~"
            + str(length)
            + " words, with all mandatory sections present."
        ),
        agent=writer,
        context=[research_task],
    )

    edit_task = Task(
        description=f"""
You are the Editor. Your job is to review the Writer's draft and produce the FINAL version.

Editing checklist (apply all):
1. Tighten prose — cut filler words, redundant phrases, padding.
2. Ensure consistent voice: {tone}.
3. Check every factual claim — if unverifiable, soften with "may", "can", "often", etc.
4. Confirm NO content enables harm (hacking, fraud, abuse). If found, remove and add safe alternative.
5. Ensure "Quick Checklist" and "What to Do Today" sections are present and actionable.
6. Ensure "Suggested Sources" are labelled as unverified suggestions, not live links.
7. Fix any formatting issues — consistent H2/H3 use, proper bullet syntax.
8. Confirm the tone is non-alarmist and empowering, not fear-mongering.
9. Output the final blog post in clean Markdown only (no editor notes in the output).

After the blog post, append a JSON metadata block in this EXACT format (on its own line):
<!-- METADATA
{{
  "title": "...",
  "meta_description": "...",
  "outline": ["Section 1 title", "Section 2 title", ...],
  "citations": ["Suggested source 1", "Suggested source 2", ...],
  "word_count": 1200,
  "model": "{MODEL_NAME}",
  "tokens": "unknown"
}}
-->
""",
        expected_output=(
            "The final polished blog post in Markdown, followed by the <!-- METADATA ... --> block."
        ),
        agent=editor,
        context=[write_task],
    )

    return research_task, write_task, edit_task


# ────────────────────────────────────────────────────────────────────────────
#  CREW RUNNER
# ────────────────────────────────────────────────────────────────────────────
def run_crew(topic: str, audience: str, tone: str, length: int) -> dict:
    """Build and kick off the 3-agent sequential crew. Returns structured output dict."""

    logger.info("▶ [SYS] Initialising CrewAI pipeline")
    logger.info(f"  Topic    : {topic}")
    logger.info(f"  Audience : {audience}")
    logger.info(f"  Tone     : {tone}")
    logger.info(f"  Words    : {length}")

    llm = build_llm()

    logger.info("▶ [SYS] Building agents...")
    researcher, writer, editor = build_agents(llm)

    logger.info("▶ [SYS] Building tasks...")
    research_task, write_task, edit_task = build_tasks(
        researcher, writer, editor, topic, audience, tone, length
    )

    crew = Crew(
        agents=[researcher, writer, editor],
        tasks=[research_task, write_task, edit_task],
        process=Process.sequential,
        verbose=True,
    )

    logger.info("▶ [RES] Researcher starting...")
    t0 = time.time()
    result = crew.kickoff()
    elapsed = round(time.time() - t0, 1)

    logger.info(f"▶ [EDI] Crew finished in {elapsed}s — parsing output...")

    raw_output = str(result)

    # ── Parse metadata block ──────────────────────────────────────────────
    metadata = {
        "title": f"Digital Literacy Guide: {topic[:60]}",
        "meta_description": f"A practical guide on: {topic[:120]}",
        "outline": [],
        "citations": [],
        "word_count": len(raw_output.split()),
        "model": MODEL_NAME,
        "tokens": "unknown",
        "elapsed_seconds": elapsed,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    blog_post = raw_output
    if "<!-- METADATA" in raw_output:
        parts = raw_output.split("<!-- METADATA", 1)
        blog_post = parts[0].strip()
        meta_raw = parts[1].split("-->", 1)[0].strip()
        try:
            parsed_meta = json.loads(meta_raw)
            metadata.update(parsed_meta)
            metadata["word_count"] = len(blog_post.split())
            metadata["elapsed_seconds"] = elapsed
            metadata["generated_at"] = datetime.utcnow().isoformat() + "Z"
        except json.JSONDecodeError as e:
            logger.warning(f"Metadata JSON parse failed: {e}")

    metadata["word_count"] = len(blog_post.split())
    logger.info(f"▶ [SYS] Output ready — {metadata['word_count']} words")

    return {
        "success": True,
        "blog_post": blog_post,
        "metadata": metadata,
        "citations": metadata.get("citations", []),
        "summary": {
            "agents_used": ["Researcher", "Writer", "Editor"],
            "workflow": "sequential",
            "elapsed_seconds": elapsed,
            "tokens_used": metadata.get("tokens", "unknown"),
            "cost_estimate": "unknown — check OpenAI dashboard",
        },
    }


# ────────────────────────────────────────────────────────────────────────────
#  HTTP ROUTES
# ────────────────────────────────────────────────────────────────────────────




@app.route("/", methods=["GET"])
def index():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return jsonify({
            "service": "CREW/AI Content Generation API",
            "version": "2.0.0",
            "status": "online",
            "error": "index.html not found",
            "agents": ["Researcher", "Writer", "Editor"],
        })


@app.route("/health", methods=["GET"])
def health():
    has_key = bool(OPENAI_API_KEY)
    return jsonify({
        "status": "ok",
        "openai_key_set": has_key,
        "model": MODEL_NAME,
    }), 200


@app.route("/generate", methods=["POST"])
def generate():
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json(silent=True) or {}
    cleaned, err = validate_input(data)
    if err:
        logger.warning(f"Input validation failed: {err}")
        return jsonify({"error": err}), 400

    if not OPENAI_API_KEY:
        return jsonify({"error": "OPENAI_API_KEY is not configured on the server."}), 503

    try:
        logger.info(f"[/generate] New request → topic: {cleaned['topic'][:60]}")
        result = run_crew(
            topic=cleaned["topic"],
            audience=cleaned["audience"],
            tone=cleaned["tone"],
            length=cleaned["length"],
        )
        return jsonify(result), 200

    except EnvironmentError as e:
        logger.error(f"Environment error: {e}")
        return jsonify({"error": str(e)}), 503

    except Exception as e:
        logger.exception("Unexpected error during crew execution")
        return jsonify({
            "error": "An unexpected error occurred. Check server logs for details.",
            "detail": str(e),
        }), 500


# ── Vercel serverless handler ──────────────────────────────────────────────
# Vercel looks for `app` (WSGI) or a function named `handler`.
# Exporting `app` is sufficient for Vercel's Python runtime.
handler = app  # alias for Vercel


# ────────────────────────────────────────────────────────────────────────────
#  LOCAL DEV ENTRY POINT
# ────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    if not OPENAI_API_KEY:
        logger.warning("⚠  OPENAI_API_KEY is not set — /generate will fail at runtime.")

    logger.info(f"🚀 CREW/AI backend starting on http://localhost:{port}")
    logger.info(f"   Model  : {MODEL_NAME}")
    logger.info(f"   Debug  : {debug}")

    app.run(host="0.0.0.0", port=port, debug=debug)
