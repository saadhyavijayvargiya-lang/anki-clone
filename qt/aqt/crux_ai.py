# Copyright: Crux contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Optional AI assist for Crux, routed through the token-gated Cloudflare proxy
so the OpenAI key never touches the client.

Configuration is via environment variables (nothing is hardcoded or shipped):
  CRUX_AI_PROXY_URL    e.g. https://your-worker.workers.dev
  CRUX_AI_PROXY_TOKEN  the PROXY_TOKEN secret set on the worker
  CRUX_AI_MODEL        optional, defaults to gpt-4o-mini

Every call has a short timeout and fails soft (returns None), so the app never
hangs and always has a deterministic fallback. AI is strictly additive."""

from __future__ import annotations

import json
import os
import urllib.request


def _cfg(key: str) -> str:
    return os.environ.get(key, "").strip()


def ai_available() -> bool:
    return bool(_cfg("CRUX_AI_PROXY_URL") and _cfg("CRUX_AI_PROXY_TOKEN"))


def chat(system: str, user: str, timeout: float = 10.0) -> str | None:
    """Return the assistant text, or None on any failure/misconfiguration."""
    url = _cfg("CRUX_AI_PROXY_URL")
    token = _cfg("CRUX_AI_PROXY_TOKEN")
    model = _cfg("CRUX_AI_MODEL") or "gpt-4o-mini"
    if not url or not token:
        return None
    endpoint = url.rstrip("/") + "/v1/chat/completions"
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
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        return text.strip() or None
    except Exception:
        return None
