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
            r = http.post(GROQ_URL, headers={"Authorization": f"Bearer {key}"}, timeout=30, json={
                "model": env("GROQ_MODEL") or "llama-3.3-70b-versatile", "max_tokens": max_tokens,
                "temperature": 0.2, "messages": [{"role": "user", "content": prompt}]})
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            log.warning("groq HTTP %s", r.status_code)
        except _ERRORS as e:
            log.warning("groq failed: %r", e)
    if key := env("GEMINI_API_KEY"):
        try:
            r = http.post(GEMINI_URL.format(model=env("GEMINI_MODEL") or "gemini-2.0-flash"),
                          headers={"x-goog-api-key": key}, timeout=30, json={
                              "contents": [{"parts": [{"text": prompt}]}],
                              "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2}})
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            log.warning("gemini HTTP %s", r.status_code)
        except _ERRORS as e:
            log.warning("gemini failed: %r", e)
    return None
