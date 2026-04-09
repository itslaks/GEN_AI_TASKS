"""
tasks.py — Task definitions wired to agents.
"""

from crewai import Task
from crewai import Agent
from config import ResearchConfig


def build_fetch_task(agent: Agent, config: ResearchConfig) -> Task:
    return Task(
        description=(
            f"Fetch the latest news articles about '{config.topic}'. "
            f"Use ALL available tools (RSS fetcher, Hacker News, GDELT) in sequence. "
            f"For each tool pass this JSON input: "
            f'{{"topic": "{config.topic}", "days": {config.days}, "max_items": {config.max_items}}}. '
            f"After fetching from all sources, MERGE the results and DEDUPLICATE by URL. "
            f"Return ONLY the final deduplicated JSON array (max {config.max_items} items). "
            f"Each item must have: id, title, publisher, date, url, summary. "
            f"If any source fails, log the error and continue with the rest."
        ),
        expected_output=(
            f"A JSON array of up to {config.max_items} unique, recent news article objects. "
            "Each object: {id, title, publisher, date (ISO-8601), url, summary}. "
            "No duplicates. All items within the last "
            f"{config.days} days where date is available."
        ),
        agent=agent,
    )


def build_summarize_task(agent: Agent, config: ResearchConfig, fetch_task: Task) -> Task:
    return Task(
        description=(
            f"Given the list of news articles about '{config.topic}' produced by the "
            "News Fetcher, produce a structured research synthesis. "
            "Your output must be a valid JSON object with these keys:\n"
            "  - key_facts: list of strings (specific data points, numbers, announcements)\n"
            "  - trends: list of strings (patterns across multiple articles)\n"
            "  - quotes: list of {text, source_url} objects\n"
            "  - risks: list of strings (concerns, threats, warnings)\n"
            "  - opportunities: list of strings (positive signals, growth areas)\n"
            "  - article_count: integer\n"
            "Every fact, trend, risk, and opportunity MUST reference at least one "
            "article URL from the fetched list. Format: 'Claim text [source: URL]'"
        ),
        expected_output=(
            "A JSON object with keys: key_facts, trends, quotes, risks, opportunities, "
            "article_count. Every item references a source URL from the fetched articles."
        ),
        agent=agent,
        context=[fetch_task],
    )


def build_report_task(agent: Agent, config: ResearchConfig,
                      fetch_task: Task, summarize_task: Task) -> Task:
    from datetime import date
    today = date.today().isoformat()

    return Task(
        description=(
            f"Using the fetched articles and the research synthesis, write a complete "
            f"Markdown executive report about '{config.topic}'. "
            f"Today's date: {today}. Region focus: {config.region}.\n\n"
            "The report MUST contain ALL of these sections in order:\n"
            "1. # [Topic] Intelligence Briefing — [Date]\n"
            "2. ## Executive Summary  (3-5 sentences, no bullets)\n"
            "3. ## Top Stories  (Markdown table: | # | Title | Publisher | Date | Link |)\n"
            "4. ## Key Trends  (numbered list, each with ≥1 citation URL)\n"
            "5. ## Implications for Enterprise Decision-Makers  (3-5 bullet points)\n"
            "6. ## Watchlist  (3-5 items to monitor, each with a one-line rationale)\n"
            "7. ## Methodology  (brief note on sources, time window, region)\n\n"
            "Rules:\n"
            "- Every claim in Key Trends and Implications must have an inline citation: "
            "([Source Name](URL))\n"
            "- Do NOT invent articles or URLs not present in the fetched data.\n"
            "- Keep total length between 600 and 1500 words.\n"
            "- Use professional, neutral tone — no hype, no filler."
        ),
        expected_output=(
            "A complete Markdown document with all 7 sections, properly formatted, "
            "600-1500 words, containing a Top Stories table and inline citations "
            "throughout Key Trends and Implications sections."
        ),
        agent=agent,
        context=[fetch_task, summarize_task],
    )
