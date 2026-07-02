# TopGRE AI setup — where to put your API key

The AI card generator is **off by default**. It turns on only when an API key is
present in your environment. Nothing is hardcoded and no key is committed.

## 1. Get a key
Create an OpenAI API key (https://platform.openai.com/api-keys). Any
OpenAI-compatible provider works if you also set a base URL (see step 4).

## 2. Set the key — pick ONE method

### Method A (recommended): environment variable
The code reads the key from the environment variable **`OPENAI_API_KEY`**.

PowerShell — current session only:
```powershell
$env:OPENAI_API_KEY = "sk-...yourkey..."
```

PowerShell — persist for future sessions:
```powershell
setx OPENAI_API_KEY "sk-...yourkey..."
```
(reopen the terminal after `setx`).

That is the only thing you must do. The exact place the code reads it:
`topgre_eval/ai_cardgen.py`, constant `API_KEY_ENV = "OPENAI_API_KEY"` (line ~34),
used by `ai_enabled()` and by `OpenAI()` in `generate_cards()`.

### Method B: a local .env you don't commit
Create `topgre_eval/.env` (already gitignore-able) with:
```
OPENAI_API_KEY=sk-...yourkey...
```
then load it before running:
```powershell
Get-Content topgre_eval\.env | ForEach-Object { if ($_ -match '^(.+?)=(.+)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }
```

### Method C (most secure): Cloudflare Worker proxy — key lives in Cloudflare, not on any machine
Use the Worker in `cf-openai-proxy/`. The real key is a Cloudflare secret you add
from the terminal; the client only ever holds a `PROXY_TOKEN`. Full steps in
`cf-openai-proxy/README.md`; the short version:
```bash
cd cf-openai-proxy
npx wrangler login
npx wrangler secret put OPENAI_API_KEY    # paste your real sk-... key
npx wrangler secret put PROXY_TOKEN       # paste a long random string
npx wrangler deploy                       # prints https://topgre-openai-proxy.<you>.workers.dev
```
Then point the client at the Worker (the SDK reads both automatically):
```powershell
$env:OPENAI_BASE_URL = "https://topgre-openai-proxy.<you>.workers.dev/v1"
$env:OPENAI_API_KEY  = "<the PROXY_TOKEN you chose>"   # NOT the real key
```
This is the recommended option if the desktop app or the phone build ever calls
the AI at runtime, so the key is never embedded in an installer or APK.

## 3. Install the client (one time)
```powershell
out\pyenv\Scripts\python -m pip install openai
```

## 4. Optional model / provider overrides (no code edit needed)
```powershell
$env:TOPGRE_AI_MODEL = "gpt-4o-mini"     # default model
# For a non-OpenAI compatible endpoint, also set:
$env:OPENAI_BASE_URL = "https://your-endpoint/v1"
```

## 5. Run it
Generate cards from ONE source, then auto-check them against the gold set:
```powershell
out\pyenv\Scripts\python topgre_eval\ai_cardgen.py --source path\to\chapter.txt --name "Munkres ch.3"
```
Check an existing set without generating:
```powershell
out\pyenv\Scripts\python topgre_eval\ai_cardgen.py --check-only topgre_eval\generated_cards.json
```

## What the pipeline guarantees (challenge 7f)
- **Named source + traceability:** every generated card must contain an exact
  `source_quote` copied from the source; cards that don't are dropped.
- **Checked before use:** `check_cards()` classifies each card as
  correct-useful / wrong / correct-but-bad against `sample_data/gold.jsonl`,
  with a cutoff (`PASS_CUTOFF = 0.80`) fixed before looking at results; failing
  cards are blocked.
- **Beats a baseline:** `keyword_baseline_move_type()` is the simple method the
  AI move-type routing must beat on held-out labelled problems.
- **Runs with AI off:** with no key set, generation is disabled and the app +
  the three scores still work from the non-AI engine.

Note: `sample_data/gold.jsonl` ships with 14 starter pairs — expand it to the
full 50 required by the challenge before reporting final numbers.
