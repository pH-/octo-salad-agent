"""Shared helper for calling the Claude API with web search."""

import json
import os
import urllib.request

MODEL = "claude-sonnet-4-5"


def call_claude(prompt, max_tokens=8000, web_search=True):
    body = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if web_search:
        body["tools"] = [
            {"type": "web_search_20250305", "name": "web_search", "max_uses": 8}
        ]
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.load(resp)
    return "".join(
        b.get("text", "") for b in data["content"] if b.get("type") == "text"
    )


def call_claude_json(prompt, **kw):
    text = call_claude(prompt, **kw).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON in model response:\n{text[:2000]}")
    return json.loads(text[start : end + 1])
