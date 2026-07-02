# TopGRE OpenAI proxy (Cloudflare Worker)

Keeps the OpenAI API key **only in Cloudflare**. The Worker injects the real key
server-side; clients authenticate with a separate `PROXY_TOKEN` and never see
the real key. Nothing sensitive is committed or shipped in the app.

```
client (ai_cardgen.py / app)
   │  Authorization: Bearer <PROXY_TOKEN>
   ▼
Cloudflare Worker  ──swaps token for real key──▶  api.openai.com
   (OPENAI_API_KEY + PROXY_TOKEN are Cloudflare secrets)
```

## One-time setup (all from the terminal)

From this folder (`cf-openai-proxy/`):

```bash
npm install                 # already run for you; installs wrangler locally
npx wrangler login          # opens a browser to authorize your Cloudflare account

# Add your secrets (interactive prompts — values are never shown/committed):
npx wrangler secret put OPENAI_API_KEY   # paste your real sk-... key
npx wrangler secret put PROXY_TOKEN      # paste a long random string you invent

npx wrangler deploy         # prints your URL, e.g. https://topgre-openai-proxy.<you>.workers.dev
```

Tip to generate a random PROXY_TOKEN (PowerShell):
```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Max 256 }))
```

## Point TopGRE at the Worker

Set two environment variables for the client (see `../topgre_eval/AI_SETUP.md`):

```powershell
$env:OPENAI_BASE_URL = "https://topgre-openai-proxy.<you>.workers.dev/v1"
$env:OPENAI_API_KEY  = "<the PROXY_TOKEN you chose>"   # NOT the real key
```

The `openai` Python SDK reads both automatically, so `topgre_eval/ai_cardgen.py`
works unchanged — it now talks to your Worker, and the real key stays in
Cloudflare.

## Local testing (optional)
```bash
cp .dev.vars.example .dev.vars    # fill in real key + a token; never commit it
npx wrangler dev                  # serves http://localhost:8787
```

## Security notes
- The Worker only proxies `/v1/*` and rejects requests without the correct
  `PROXY_TOKEN` (constant-time compared), so it isn't an open OpenAI proxy.
- Rotate: `wrangler secret put PROXY_TOKEN` (new value) / `OPENAI_API_KEY`.
- Watch usage/logs: `npx wrangler tail`. Consider Cloudflare AI Gateway in front
  for rate-limiting + caching if you expose it widely.
```
