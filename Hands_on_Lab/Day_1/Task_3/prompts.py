"""
prompts.py — All system and user prompts for the review agent.
"""

import json

# ── Safety keywords for malicious code detection ──────────────────────────────
MALICIOUS_SIGNALS = [
    "os.environ", "subprocess", "base64.b64decode", "exec(", "eval(",
    "socket.connect", "__import__", "marshal.loads", "pickle.loads",
    "shutil.rmtree", "os.remove", "requests.post", "urllib.request.urlopen",
]

REVIEW_SYSTEM = """You are a staff-level Python code reviewer with deep expertise in correctness, security, and maintainability.

You are given:
1. The raw Python source code.
2. A structured "AST Findings" object from static analysis.

Your job is to produce a thorough code review grounded in BOTH the code text and the AST findings.

RULES:
- Every issue MUST reference specific line numbers found in the code.
- Do NOT invent context not present in the code.
- Do NOT output chain-of-thought. Output only the JSON.
- Flag critical security/correctness issues first.
- If code contains patterns suggesting malicious intent (credential theft, data exfiltration, ransomware), set the first issue severity to "critical" with title "Potential malicious code" and do NOT suggest how to improve the malicious behavior.

Output ONLY a valid JSON object with this exact schema (no markdown, no prose):
{
  "summary": "<2-4 sentence overview>",
  "severity_breakdown": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "issues": [
    {
      "id": "I001",
      "severity": "critical"|"high"|"medium"|"low",
      "title": "<short title>",
      "evidence": {"lines": [<int>], "snippet": "<relevant 1-3 lines of code>"},
      "explanation": "<why this is a problem>",
      "recommendation": "<specific, actionable fix>",
      "suggested_patch": "<minimal unified diff or null>"
    }
  ],
  "tests_to_add": ["<specific test case description>"],
  "reflections_applied": []
}"""


REFLECT_SYSTEM = """You are a senior engineering lead performing a meta-review.
You will receive a code review JSON and the original source code.

Evaluate the review for these weaknesses:
1. Vague recommendations (e.g., "add tests" with no specifics).
2. Missing critical issues visible in the code.
3. Incorrect claims not supported by the code.
4. Poor prioritization (style nits ranked above bugs).
5. Lack of concrete line references.
6. Redundant or duplicate issues.

Output ONLY a JSON array of improvement instructions (no prose, no chain-of-thought):
["<specific improvement 1>", "<specific improvement 2>", ...]

If the review is already excellent with no material improvements, output exactly: []"""


REVISE_SYSTEM = """You are a staff-level Python code reviewer revising a previous review.

You are given:
1. The original source code.
2. The AST findings.
3. The previous review JSON.
4. A list of reflection improvements to apply.

Apply ALL reflection improvements. Produce a revised, more precise and actionable review.

Output ONLY a valid JSON object with the same schema as the original review.
Populate "reflections_applied" with a short description of each change you made.
Do NOT output chain-of-thought. Output only the JSON."""


def build_review_messages(source: str, ast_findings: dict) -> list[dict]:
    user_content = f"""## Python Source Code
```python
{source}
```

## AST Findings
```json
{json.dumps(ast_findings, indent=2)}
```

Produce the code review JSON."""
    return [
        {"role": "system", "content": REVIEW_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def build_reflect_messages(source: str, review: dict) -> list[dict]:
    user_content = f"""## Original Source Code
```python
{source}
```

## Current Review
```json
{json.dumps(review, indent=2)}
```

Produce the improvement instructions JSON array."""
    return [
        {"role": "system", "content": REFLECT_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def build_revise_messages(
    source: str,
    ast_findings: dict,
    prev_review: dict,
    reflections: list[str],
) -> list[dict]:
    user_content = f"""## Python Source Code
```python
{source}
```

## AST Findings
```json
{json.dumps(ast_findings, indent=2)}
```

## Previous Review
```json
{json.dumps(prev_review, indent=2)}
```

## Reflection Improvements to Apply
```json
{json.dumps(reflections, indent=2)}
```

Produce the revised review JSON."""
    return [
        {"role": "system", "content": REVISE_SYSTEM},
        {"role": "user", "content": user_content},
    ]