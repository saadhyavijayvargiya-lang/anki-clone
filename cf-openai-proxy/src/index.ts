// Copyright: TopGRE contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Token-gated OpenAI proxy for TopGRE.
//
// The real OpenAI key never leaves Cloudflare: it is stored as the secret
// OPENAI_API_KEY and injected here, server-side. Clients authenticate with a
// separate PROXY_TOKEN (also a secret) and never see the real key. This lets us
// call OpenAI from scripts/apps without shipping the key anywhere.

export interface Env {
    // Set with: wrangler secret put OPENAI_API_KEY
    OPENAI_API_KEY: string;
    // Set with: wrangler secret put PROXY_TOKEN   (a long random string you pick)
    PROXY_TOKEN: string;
}

const UPSTREAM = "https://api.openai.com";

export default {
    async fetch(req: Request, env: Env): Promise<Response> {
        if (req.method === "OPTIONS") {
            return new Response(null, { status: 204, headers: corsHeaders() });
        }

        const url = new URL(req.url);

        // Simple health check.
        if (url.pathname === "/" || url.pathname === "/health") {
            return json({ ok: true, service: "topgre-openai-proxy" }, 200);
        }

        // Only proxy the OpenAI REST surface (e.g. /v1/chat/completions).
        if (!url.pathname.startsWith("/v1/")) {
            return json({ error: "not found" }, 404);
        }

        // Require our proxy token (NOT the real OpenAI key) as the bearer.
        const presented = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "");
        if (!env.PROXY_TOKEN || !timingSafeEqual(presented, env.PROXY_TOKEN)) {
            return json({ error: "unauthorized" }, 401);
        }

        // Forward to OpenAI with the real key injected server-side.
        const headers = new Headers(req.headers);
        headers.set("Authorization", `Bearer ${env.OPENAI_API_KEY}`);
        headers.delete("Host");

        const upstream = await fetch(UPSTREAM + url.pathname + url.search, {
            method: req.method,
            headers,
            body: req.method === "GET" || req.method === "HEAD" ? undefined : req.body,
        });

        // Stream the response back, adding permissive CORS.
        const respHeaders = new Headers(upstream.headers);
        for (const [k, v] of Object.entries(corsHeaders())) {
            respHeaders.set(k, v);
        }
        return new Response(upstream.body, { status: upstream.status, headers: respHeaders });
    },
};

function corsHeaders(): Record<string, string> {
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    };
}

function json(obj: unknown, status: number): Response {
    return new Response(JSON.stringify(obj), {
        status,
        headers: { "Content-Type": "application/json", ...corsHeaders() },
    });
}

// Constant-time comparison to avoid leaking the token via timing.
function timingSafeEqual(a: string, b: string): boolean {
    if (a.length !== b.length) {
        return false;
    }
    let mismatch = 0;
    for (let i = 0; i < a.length; i++) {
        mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
    }
    return mismatch === 0;
}
