"""
agents.py — Three-agent definitions for the Research Assistant crew.
"""

from crewai import Agent
from tools import RSSFetcherTool, HackerNewsTool, GDELTTool


def build_news_fetcher() -> Agent:
    """
    Agent 1: News Fetcher
    Responsibility: Collect raw articles from multiple free sources, deduplicate,
    enforce recency, and return a structured list with full citations.
    """
    return Agent(
        role="Senior News Intelligence Analyst",
        goal=(
            "Collect the most recent, credible news articles on the assigned topic "
            "from multiple free public sources. Deduplicate by URL, filter to the "
            "specified time window, and return a clean JSON list where every item "
            "includes: title, publisher, date (ISO-8601), url, and a short summary."
        ),
        backstory=(
            "You are a veteran intelligence analyst who spent 15 years tracking "
            "technology markets for a global research firm. You have an obsessive "
            "commitment to source quality and recency — a stale headline is worse "
            "than no headline. You never fabricate articles; if a fetch fails you "
            "skip it gracefully and note the failure. You always cite sources."
        ),
        tools=[RSSFetcherTool(), HackerNewsTool(), GDELTTool()],
        verbose=True,
        max_iter=5,
        allow_delegation=False,
    )


def build_summarizer() -> Agent:
    """
    Agent 2: Key-Point Summarizer
    Responsibility: Read raw articles and extract structured insights:
    facts, trends, notable quotes, risks, and opportunities.
    """
    return Agent(
        role="Principal Research Synthesist",
        goal=(
            "Analyze the list of fetched articles and produce a structured synthesis "
            "that covers: (1) key facts and data points, (2) emerging trends, "
            "(3) notable quotes or statements, (4) risks and concerns, "
            "(5) opportunities. Every claim must be attributed to its source URL."
        ),
        backstory=(
            "You are a former McKinsey principal who specialized in technology "
            "due-diligence. You read 200+ articles a week and have a gift for "
            "spotting the signal in the noise. You write bullet-point syntheses "
            "that CEOs can absorb in 3 minutes. You never generalize without "
            "citing specific evidence from the provided articles."
        ),
        tools=[],          # works purely on the fetcher's output
        verbose=True,
        max_iter=3,
        allow_delegation=False,
    )


def build_report_writer() -> Agent:
    """
    Agent 3: Report Writer
    Responsibility: Transform the synthesis into a polished Markdown executive report
    with all required sections and inline citations.
    """
    return Agent(
        role="Executive Research Writer",
        goal=(
            "Produce a professional, publication-ready Markdown report from the "
            "research synthesis. The report MUST contain exactly these sections: "
            "Executive Summary, Top Stories (table with title/publisher/date/url), "
            "Key Trends, Implications for Enterprise Decision-Makers, and Watchlist "
            "(3-5 items to monitor). Embed citation URLs inline for every major claim."
        ),
        backstory=(
            "You are a former Harvard Business Review editor who now writes "
            "technology briefings for Fortune 500 boards. Your reports are known "
            "for clarity, precision, and zero fluff. You structure every report "
            "identically so readers always know where to look. You never include "
            "a claim without linking it to a source."
        ),
        tools=[],          # works purely on the synthesist's output
        verbose=True,
        max_iter=3,
        allow_delegation=False,
    )
