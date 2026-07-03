# Copyright: Crux contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Optional AI assist for Crux, routed through the token-gated Cloudflare proxy
so the OpenAI key never touches the client.

Configuration is via environment variables (nothing is hardcoded or shipped).
Either naming scheme works; Crux-specific vars win if both are present:
  CRUX_AI_PROXY_URL / OPENAI_BASE_URL    the proxy base (with or without /v1)
  CRUX_AI_PROXY_TOKEN / OPENAI_API_KEY   the PROXY_TOKEN (never the real key)
  CRUX_AI_MODEL / TOPGRE_AI_MODEL        optional, defaults to gpt-4o-mini

Every call has a short timeout and fails soft (returns None), so the app never
hangs and always has a deterministic fallback. AI is strictly additive."""

from __future__ import annotations

import json
import os
import urllib.request


def _first(*keys: str) -> str:
    for key in keys:
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return ""


def _base_url() -> str:
    return _first("CRUX_AI_PROXY_URL", "OPENAI_BASE_URL")


def _token() -> str:
    return _first("CRUX_AI_PROXY_TOKEN", "OPENAI_API_KEY")


def _model() -> str:
    return _first("CRUX_AI_MODEL", "TOPGRE_AI_MODEL") or "gpt-4o-mini"


def _endpoint(base: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/v1"):
        return b + "/chat/completions"
    return b + "/v1/chat/completions"


def ai_available() -> bool:
    return bool(_base_url() and _token())


def chat(system: str, user: str, timeout: float = 10.0) -> str | None:
    """Return the assistant text, or None on any failure/misconfiguration."""
    base = _base_url()
    token = _token()
    model = _model()
    if not base or not token:
        return None
    endpoint = _endpoint(base)
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "max_tokens": 320,
        }
    ).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    # A browser-like User-Agent avoids Cloudflare bot protection (error 1010),
    # which blocks the default urllib agent on workers.dev.
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        return text.strip() or None
    except Exception:
        return None
