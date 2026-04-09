"""
CrewAI Research Assistant — Entry Point
Usage: python main.py --topic "AI/ML enterprise software" --days 7 --region global --items 10
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from crew import ResearchCrew
from config import ResearchConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CrewAI Research Assistant: fetch, summarize, and report industry news."
    )
    parser.add_argument(
        "--topic", type=str,
        default="AI/ML enterprise software",
        help="Industry/topic keywords (default: 'AI/ML enterprise software')"
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Lookback window in days (default: 7)"
    )
    parser.add_argument(
        "--region", type=str, default="global",
        help="Region filter (default: global)"
    )
    parser.add_argument(
        "--items", type=int, default=10,
        help="Max news items to fetch (default: 10)"
    )
    parser.add_argument(
        "--output-dir", type=str, default="./output",
        help="Directory for output files (default: ./output)"
    )
    return parser.parse_args()


def self_check(result: dict) -> list[str]:
    """Validate final output against success criteria."""
    failures = []

    articles = result.get("articles", [])
    if not articles:
        failures.append("FAIL: No articles fetched.")
    else:
        missing_urls = [a for a in articles if not a.get("url")]
        if missing_urls:
            failures.append(f"FAIL: {len(missing_urls)} articles missing URLs (citations).")

        missing_dates = [a for a in articles if not a.get("date")]
        if missing_dates:
            failures.append(f"WARN: {len(missing_dates)} articles missing dates.")

    if not result.get("summary"):
        failures.append("FAIL: Key-point summary is empty.")

    report = result.get("report", "")
    if len(report) < 500:
        failures.append("FAIL: Report too short (< 500 chars) — likely incomplete.")

    required_sections = ["Executive Summary", "Top Stories", "Key Trends", "Implications", "Watchlist"]
    for section in required_sections:
        if section not in report:
            failures.append(f"WARN: Report missing section: '{section}'")

    return failures


def main():
    args = parse_args()

    config = ResearchConfig(
        topic=args.topic,
        days=args.days,
        region=args.region,
        max_items=args.items,
        output_dir=Path(args.output_dir),
    )

    print(f"\n{'='*60}")
    print(f"  CrewAI Research Assistant")
    print(f"{'='*60}")
    print(f"  Topic   : {config.topic}")
    print(f"  Lookback: last {config.days} days")
    print(f"  Region  : {config.region}")
    print(f"  Items   : up to {config.max_items}")
    print(f"  Output  : {config.output_dir}")
    print(f"{'='*60}\n")

    config.output_dir.mkdir(parents=True, exist_ok=True)

    crew = ResearchCrew(config)
    result = crew.kickoff()

    # Self-check
    print("\n[Self-Check] Validating output constraints...")
    issues = self_check(result)
    if issues:
        for issue in issues:
            print(f"  ⚠  {issue}")
    else:
        print("  ✓  All constraints satisfied.")

    # Write JSON artifact
    json_path = config.output_dir / "research_artifact.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[Output] JSON artifact  → {json_path}")

    # Write Markdown report
    md_path = config.output_dir / "research_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result.get("report", "# Report generation failed."))
    print(f"[Output] Markdown report → {md_path}")

    print(f"\n{'='*60}")
    print("  Run complete.")
    print(f"{'='*60}\n")

    return 0 if not any(i.startswith("FAIL") for i in issues) else 1


if __name__ == "__main__":
    sys.exit(main())
