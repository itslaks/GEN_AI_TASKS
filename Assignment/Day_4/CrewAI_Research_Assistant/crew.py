"""
crew.py — Crew assembly and kickoff logic.
"""

import json
import logging
import re
from typing import Any

from crewai import Crew, Process

from config import ResearchConfig
from agents import build_news_fetcher, build_summarizer, build_report_writer
from tasks import build_fetch_task, build_summarize_task, build_report_task

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Any:
    """Extract first JSON array or object from a text blob."""
    # Try direct parse first
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try to find JSON array
    m = re.search(r'(\[.*\])', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Try to find JSON object
    m = re.search(r'(\{.*\})', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None


class ResearchCrew:
    def __init__(self, config: ResearchConfig):
        self.config = config

        # Build agents
        self.fetcher_agent    = build_news_fetcher()
        self.summarizer_agent = build_summarizer()
        self.writer_agent     = build_report_writer()

        # Build tasks (sequential dependency chain)
        self.fetch_task     = build_fetch_task(self.fetcher_agent, config)
        self.summarize_task = build_summarize_task(
            self.summarizer_agent, config, self.fetch_task)
        self.report_task    = build_report_task(
            self.writer_agent, config, self.fetch_task, self.summarize_task)

        # Assemble crew
        self.crew = Crew(
            agents=[self.fetcher_agent, self.summarizer_agent, self.writer_agent],
            tasks=[self.fetch_task, self.summarize_task, self.report_task],
            process=Process.sequential,
            verbose=True,
        )

    def kickoff(self) -> dict:
        """Run the crew and return a structured result dict."""
        print("[Crew] Starting sequential pipeline…\n")
        raw_result = self.crew.kickoff()

        # CrewAI returns a CrewOutput object; .raw is the final task string
        final_text = str(raw_result)

        # Parse task outputs
        articles = []
        summary_obj = {}
        report_text = ""

        task_outputs = getattr(raw_result, "tasks_output", [])
        if len(task_outputs) >= 1:
            fetch_raw = str(task_outputs[0])
            parsed = _extract_json(fetch_raw)
            if isinstance(parsed, list):
                articles = parsed
            else:
                logger.warning("Could not parse fetch task output as JSON list.")

        if len(task_outputs) >= 2:
            summary_raw = str(task_outputs[1])
            parsed = _extract_json(summary_raw)
            if isinstance(parsed, dict):
                summary_obj = parsed
            else:
                summary_obj = {"raw": summary_raw}

        if len(task_outputs) >= 3:
            report_text = str(task_outputs[2])
        else:
            report_text = final_text

        return {
            "topic": self.config.topic,
            "days": self.config.days,
            "region": self.config.region,
            "run_timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "articles": articles,
            "summary": summary_obj,
            "report": report_text,
        }
