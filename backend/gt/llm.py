"""Optional LLM polish (free tiers): Groq first, then Gemini. Returns None when unavailable — callers fall back to templates."""
import logging

import httpx

from gt.config import env

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
log = logging.getLogger(__name__)
_ERRORS = (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError)


def complete(prompt: str, max_tokens: int = 400, http=None) -> str | None:
    http = http or httpx
    if key := env("GROQ_API_KEY"):
        try:
            model = env("GROQ_MODEL") or "openai/gpt-oss-120b"
            # gpt-oss reasons before answering; at default effort that used 78 of 80 tokens and returned ""
            low = {"reasoning_effort": "low"} if model.startswith("openai/gpt-oss") else {}
            r = http.post(GROQ_URL, headers={"Authorization": f"Bearer {key}"}, timeout=30, json={
                "model": model, "max_tokens": max_tokens, "temperature": 0.2, **low,
                "messages": [{"role": "user", "content": prompt}]})
            if r.status_code == 200 and (out := (r.json()["choices"][0]["message"]["content"] or "").strip()):
                return out
            log.warning("groq HTTP %s (empty answer = token limit hit)", r.status_code)
        except _ERRORS as e:
            log.warning("groq failed: %r", e)
    if key := env("GEMINI_API_KEY"):
        try:
            r = http.post(GEMINI_URL.format(model=env("GEMINI_MODEL") or "gemini-flash-latest"),
                          headers={"x-goog-api-key": key}, timeout=30, json={
                              "contents": [{"parts": [{"text": prompt}]}],
                              # thinking off: on flash models it ate 384 of 400 tokens and cut the answer short
                              "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2,
                                                   "thinkingConfig": {"thinkingBudget": 0}}})
            if r.status_code == 200 and (out := r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()):
                return out
            log.warning("gemini HTTP %s (empty answer = token limit hit)", r.status_code)
        except _ERRORS as e:
            log.warning("gemini failed: %r", e)
    return None
