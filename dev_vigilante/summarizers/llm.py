"""Optional LLM summarizer.

Only invoked when Vigilante Settings enables LLM summaries and supplies an API key.
Uses the standard REST endpoints of the configured provider via ``requests`` (present
in every bench). Any exception propagates to the caller, which falls back to the
heuristic summary.
"""

from __future__ import annotations

import json

import requests

from dev_vigilante.artifact import Artifact

_DEFAULT_MODELS = {
    "Anthropic": "claude-sonnet-5",
    "OpenAI": "gpt-4o-mini",
}

_SYSTEM_PROMPT = (
    "You document ERPNext/Frappe customizations. Given the structured JSON of one "
    "customization and a baseline description, write a single concise sentence (max 40 "
    "words) explaining what it does and why it matters. No preamble, no markdown."
)


def _build_prompt(artifact: Artifact, baseline: str) -> str:
    payload = {
        "type": artifact.type,
        "name": artifact.name,
        "fields": artifact.fields,
        "baseline_summary": baseline,
    }
    return (
        "Customization:\n"
        + json.dumps(payload, sort_keys=True, indent=2, default=str)
        + "\n\nOne-sentence summary:"
    )


def summarize(artifact: Artifact, baseline: str, config: dict) -> str:
    provider = config.get("provider") or "Anthropic"
    model = config.get("model") or _DEFAULT_MODELS.get(provider)
    api_key = config.get("api_key")
    prompt = _build_prompt(artifact, baseline)

    if provider == "Anthropic":
        return _anthropic(api_key, model, prompt)
    if provider == "OpenAI":
        return _openai(api_key, model, prompt)
    raise ValueError(f"Unsupported LLM provider: {provider}")


def _anthropic(api_key: str, model: str, prompt: str) -> str:
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 120,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(block.get("text", "") for block in data.get("content", []))


def _openai(api_key: str, model: str, prompt: str) -> str:
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 120,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]
