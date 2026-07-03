<!--
Copyright: Crux contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import { onMount } from "svelte";

    import { recordExamAttempt } from "@generated/backend";

    type DrillCard = {
        chain: string;
        moveType: string;
        problem: string;
        method: string;
        execute: string;
        options: string[];
    };

    const LABELS: Record<string, string> = {
        "open-closed-sets": "Open / closed sets",
        "interior-closure-boundary": "Interior, closure, boundary",
        "bases-subbases": "Bases and subbases",
        "continuity": "Continuity",
        "homeomorphism": "Homeomorphism",
        "compactness": "Compactness",
        "connectedness": "Connectedness",
        "separation": "Separation",
        "examples": "Examples and counterexamples",
    };

    function label(mt: string): string {
        return LABELS[mt] ?? mt;
    }

    let cards: DrillCard[] = [];
    let loading = true;
    let loadError = "";

    let idx = 0;
    let chosen: string | null = null;
    let revealed = false;
    let methodShown = false;
    let questionStart = Date.now();

    let answered = 0;
    let correctCount = 0;
    const missedTypes: Record<string, number> = {};

    let explainText = "";
    let explainLoading = false;

    $: card = cards[idx];
    $: done = !loading && cards.length > 0 && idx >= cards.length;
    $: progress = cards.length ? Math.round((idx / cards.length) * 100) : 0;

    async function loadDrill(): Promise<void> {
        loading = true;
        loadError = "";
        try {
            const res = await fetch("/_anki/cruxRoutingDrill", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ limit: 12 }),
            });
            if (!res.ok) {
                throw new Error(`${res.status}`);
            }
            const data = await res.json();
            cards = data.cards ?? [];
            reset();
        } catch (err) {
            loadError = String(err);
        } finally {
            loading = false;
        }
    }

    function reset(): void {
        idx = 0;
        chosen = null;
        revealed = false;
        methodShown = false;
        answered = 0;
        correctCount = 0;
        for (const k of Object.keys(missedTypes)) {
            delete missedTypes[k];
        }
        questionStart = Date.now();
    }

    async function choose(option: string): Promise<void> {
        if (revealed || !card) {
            return;
        }
        chosen = option;
        revealed = true;
        const correct = option === card.moveType;
        answered += 1;
        if (correct) {
            correctCount += 1;
        } else {
            missedTypes[card.moveType] = (missedTypes[card.moveType] ?? 0) + 1;
        }
        const ms = Math.min(Date.now() - questionStart, 30 * 60 * 1000);
        try {
            await recordExamAttempt(
                { moveType: card.moveType, correct, milliseconds: ms },
                { alertOnError: false },
            );
        } catch {
            // Recording is best-effort; keep the drill flowing.
        }
    }

    async function explain(): Promise<void> {
        if (!card || explainLoading) {
            return;
        }
        explainLoading = true;
        try {
            const res = await fetch("/_anki/cruxAiExplain", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    problem: card.problem,
                    moveType: card.moveType,
                    method: card.method,
                }),
            });
            const data = await res.json();
            explainText = data.text;
        } catch {
            explainText = "Could not load an explanation right now.";
        } finally {
            explainLoading = false;
        }
    }

    function showMethod(): void {
        methodShown = true;
    }

    function next(): void {
        idx += 1;
        chosen = null;
        revealed = false;
        methodShown = false;
        explainText = "";
        questionStart = Date.now();
    }

    function onKey(e: KeyboardEvent): void {
        if (loading || done || !card) {
            return;
        }
        if (!revealed) {
            const n = Number.parseInt(e.key, 10);
            if (n >= 1 && n <= card.options.length) {
                choose(card.options[n - 1]);
            }
        } else if (!methodShown) {
            if (e.key === "Enter" || e.key === " " || e.key.toLowerCase() === "m") {
                e.preventDefault();
                showMethod();
            }
        } else if (e.key === "Enter" || e.key.toLowerCase() === "n") {
            next();
        } else if (e.key.toLowerCase() === "e") {
            explain();
        }
    }

    $: missedList = Object.entries(missedTypes).sort((a, b) => b[1] - a[1]);

    onMount(loadDrill);
</script>

<svelte:window on:keydown={onKey} />

<div class="bg" aria-hidden="true">
    <span class="blob blob-a"></span>
    <span class="blob blob-b"></span>
</div>

<main class="router">
    <header class="head">
        <div class="brand"><span class="mark">Crux</span><span class="tag">Router drill</span></div>
        <p class="lede">
            Read the problem, then pick the type it calls for. Routing to the
            right method is the skill the exam tests, so this drills the decision,
            not the recall.
        </p>
    </header>

    {#if loading}
        <div class="panel state">Loading routing problems.</div>
    {:else if loadError}
        <div class="panel state">
            Could not load the drill ({loadError}). Open the deck and try again.
        </div>
    {:else if cards.length === 0}
        <div class="panel state">
            No decision chains found yet. Add cards tagged
            <code>chain::</code>, <code>step::</code>, and <code>move::</code>,
            or run the demo seed, then reopen this drill.
        </div>
    {:else if done}
        <section class="panel summary">
            <h2>Session complete</h2>
            <div class="score-big">
                {correctCount}<span class="of">/ {answered}</span>
            </div>
            <p class="score-sub">routed to the right type</p>
            {#if missedList.length}
                <div class="missed">
                    <span class="missed-title">Review these types</span>
                    <ul>
                        {#each missedList as [mt, n]}
                            <li><span class="dot"></span>{label(mt)} <span class="mn">missed {n}</span></li>
                        {/each}
                    </ul>
                </div>
            {:else}
                <p class="perfect">Clean run. Every problem routed correctly.</p>
            {/if}
            <button class="btn primary" on:click={loadDrill}>New session</button>
        </section>
    {:else if card}
        <div class="bar-wrap">
            <div class="bar"><div class="bar-fill" style="width:{progress}%"></div></div>
            <div class="counter">
                <span>Question {idx + 1} of {cards.length}</span>
                <span class="tally">{correctCount}/{answered} routed</span>
            </div>
        </div>

        <section class="panel problem">
            <span class="p-key">Problem</span>
            <p class="p-text">{card.problem}</p>
        </section>

        <section class="choices">
            <span class="c-key">Which type does this call for?</span>
            <div class="grid">
                {#each card.options as opt, i}
                    <button
                        class="opt"
                        class:correct={revealed && opt === card.moveType}
                        class:wrong={revealed && opt === chosen && opt !== card.moveType}
                        class:dim={revealed && opt !== card.moveType && opt !== chosen}
                        disabled={revealed}
                        on:click={() => choose(opt)}
                    >
                        <span class="kbd">{i + 1}</span>
                        {label(opt)}
                    </button>
                {/each}
            </div>
        </section>

        {#if revealed}
            <section class="panel reveal">
                <div class="verdict {chosen === card.moveType ? 'ok' : 'no'}">
                    {chosen === card.moveType ? "Routed correctly" : "Misrouted"}
                    <span class="right-type">{label(card.moveType)}</span>
                </div>

                {#if !methodShown}
                    <div class="recall">
                        <span class="m-key">Now recall the move</span>
                        <p class="recall-hint">
                            What move solves a {label(card.moveType)} problem? Think
                            it through, then check.
                        </p>
                        <button class="btn primary" on:click={showMethod}>Show the move</button>
                    </div>
                {:else}
                    <div class="move">
                        <span class="m-key">The move</span>
                        <p>{card.method}</p>
                    </div>
                    {#if card.execute}
                        <div class="move">
                            <span class="m-key">Then</span>
                            <p>{card.execute}</p>
                        </div>
                    {/if}
                    {#if explainText}
                        <div class="explain">
                            <span class="m-key">Why this routes here</span>
                            <p>{explainText}</p>
                        </div>
                    {/if}
                    <div class="reveal-actions">
                        <button class="btn ghost" on:click={explain} disabled={explainLoading}>
                            {explainLoading ? "Thinking" : "Explain why"}
                        </button>
                        <button class="btn primary" on:click={next}>
                            {idx + 1 >= cards.length ? "See results" : "Next problem"}
                        </button>
                    </div>
                {/if}
            </section>
        {/if}
    {/if}
</main>

<style lang="scss">
    :global(html),
    :global(body) {
        margin: 0;
        background: #f8fafc;
    }

    .router {
        --ct-primary: #4f46e5;
        --ct-secondary: #7c3aed;
        --ct-ink: #0f172a;
        --ct-muted: #64748b;
        --ct-surface: #ffffff;
        --ct-border: #e2e8f0;
        --ct-border-soft: #eef2f7;
        --ct-indigo-50: #eef2ff;
        --ct-gradient: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        --ct-shadow: 0 4px 20px -2px rgba(79, 70, 229, 0.1);
        --ct-shadow-hover: 0 10px 25px -5px rgba(79, 70, 229, 0.18);

        position: relative;
        z-index: 1;
        max-width: 44rem;
        margin: 0 auto;
        padding: 2.25rem 1.5rem 4rem;
        color: var(--ct-ink);
        line-height: 1.6;
        color-scheme: light;
        font-family:
            "Plus Jakarta Sans", "Segoe UI Variable", "Segoe UI", system-ui,
            -apple-system, sans-serif;
    }

    .bg {
        position: fixed;
        inset: 0;
        z-index: 0;
        overflow: hidden;
        pointer-events: none;
    }
    .blob {
        position: absolute;
        border-radius: 50%;
        filter: blur(80px);
        opacity: 0.4;
    }
    .blob-a {
        width: 30rem;
        height: 30rem;
        top: -10rem;
        right: -6rem;
        background: radial-gradient(circle, #c7d2fe, transparent 70%);
    }
    .blob-b {
        width: 24rem;
        height: 24rem;
        bottom: -8rem;
        left: -8rem;
        background: radial-gradient(circle, #ddd6fe, transparent 70%);
    }

    .head {
        margin-bottom: 1.25rem;
    }
    .brand {
        display: flex;
        align-items: baseline;
        gap: 0.55rem;
    }
    .mark {
        font-size: 1.7rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        background: var(--ct-gradient);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
    }
    .tag {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--ct-muted);
    }
    .lede {
        margin: 0.45rem 0 0;
        color: var(--ct-muted);
        font-size: 0.95rem;
        max-width: 36rem;
    }

    .panel {
        background: var(--ct-surface);
        border: 1px solid var(--ct-border-soft);
        border-radius: 16px;
        padding: 1.25rem 1.4rem;
        box-shadow: var(--ct-shadow);
        margin-bottom: 1.1rem;
    }
    .state {
        color: var(--ct-muted);
    }
    code {
        background: var(--ct-indigo-50);
        color: var(--ct-primary);
        padding: 0.05rem 0.35rem;
        border-radius: 5px;
        font-size: 0.85em;
    }

    .bar-wrap {
        margin-bottom: 1.1rem;
    }
    .bar {
        height: 8px;
        border-radius: 999px;
        background: var(--ct-indigo-50);
        overflow: hidden;
    }
    .bar-fill {
        height: 100%;
        border-radius: 999px;
        background: var(--ct-gradient);
        transition: width 0.3s ease-out;
    }
    .counter {
        display: flex;
        justify-content: space-between;
        margin-top: 0.4rem;
        font-size: 0.8rem;
        color: var(--ct-muted);
    }
    .tally {
        font-weight: 600;
        color: var(--ct-primary);
    }

    .problem {
        margin-bottom: 1.1rem;
    }
    .p-key,
    .c-key,
    .m-key {
        display: block;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--ct-primary);
        margin-bottom: 0.4rem;
    }
    .p-text {
        margin: 0;
        font-size: 1.15rem;
        font-weight: 600;
        line-height: 1.5;
        color: var(--ct-ink);
    }

    .choices {
        margin-bottom: 1.1rem;
    }
    .grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.7rem;
    }
    @media (max-width: 34rem) {
        .grid {
            grid-template-columns: 1fr;
        }
    }
    .opt {
        font: inherit;
        text-align: left;
        font-weight: 600;
        padding: 0.85rem 1rem;
        border-radius: 12px;
        border: 1.5px solid var(--ct-border);
        background: var(--ct-surface);
        color: var(--ct-ink);
        cursor: pointer;
        box-shadow: var(--ct-shadow);
        transition:
            transform 0.15s ease-out,
            border-color 0.15s ease-out,
            box-shadow 0.15s ease-out;
    }
    .opt:hover:not(:disabled) {
        transform: translateY(-2px);
        border-color: var(--ct-primary);
        box-shadow: var(--ct-shadow-hover);
    }
    .opt:focus-visible {
        outline: none;
        border-color: var(--ct-primary);
        box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.2);
    }
    .opt:disabled {
        cursor: default;
    }
    .kbd {
        display: inline-grid;
        place-items: center;
        width: 1.4rem;
        height: 1.4rem;
        margin-right: 0.5rem;
        border-radius: 6px;
        background: var(--ct-indigo-50);
        color: var(--ct-primary);
        font-size: 0.72rem;
        font-weight: 700;
        vertical-align: middle;
    }
    .opt.correct .kbd,
    .opt.wrong .kbd {
        background: rgba(255, 255, 255, 0.6);
    }
    .opt.correct {
        border-color: #10b981;
        background: rgba(16, 185, 129, 0.1);
        color: #047857;
    }
    .opt.wrong {
        border-color: #e11d48;
        background: rgba(225, 29, 72, 0.08);
        color: #be123c;
    }
    .opt.dim {
        opacity: 0.5;
    }

    .reveal .verdict {
        font-weight: 700;
        font-size: 0.95rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.9rem;
    }
    .verdict.ok {
        color: #047857;
    }
    .verdict.no {
        color: #be123c;
    }
    .right-type {
        font-weight: 600;
        color: var(--ct-ink);
        background: var(--ct-indigo-50);
        padding: 0.15rem 0.55rem;
        border-radius: 999px;
        font-size: 0.85rem;
    }
    .move {
        margin-bottom: 0.75rem;
    }
    .move p {
        margin: 0;
        color: var(--ct-ink);
    }
    .recall .recall-hint {
        margin: 0 0 0.85rem;
        color: var(--ct-muted);
        line-height: 1.5;
    }
    .explain {
        margin: 0.25rem 0 0.75rem;
        padding: 0.75rem 0.9rem;
        border-radius: 12px;
        background: rgba(79, 70, 229, 0.06);
        border: 1px solid rgba(79, 70, 229, 0.18);
    }
    .explain p {
        margin: 0;
        color: var(--ct-ink);
        line-height: 1.55;
    }
    .reveal-actions {
        display: flex;
        gap: 0.6rem;
        align-items: center;
        flex-wrap: wrap;
    }

    .btn {
        font: inherit;
        font-weight: 600;
        padding: 0.6rem 1.3rem;
        border-radius: 999px;
        border: none;
        cursor: pointer;
        margin-top: 0.4rem;
    }
    .btn.primary {
        color: #fff;
        background: var(--ct-gradient);
        box-shadow: 0 4px 14px 0 rgba(79, 70, 229, 0.3);
        transition:
            transform 0.18s ease-out,
            box-shadow 0.18s ease-out;
    }
    .btn.primary:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 22px 0 rgba(79, 70, 229, 0.4);
    }
    .btn.ghost {
        background: var(--ct-surface);
        border: 1px solid var(--ct-border);
        color: #334155;
        box-shadow: var(--ct-shadow);
        transition:
            transform 0.18s ease-out,
            box-shadow 0.18s ease-out;
    }
    .btn.ghost:hover {
        transform: translateY(-2px);
        box-shadow: var(--ct-shadow-hover);
    }
    .btn:focus-visible {
        outline: none;
        box-shadow:
            0 0 0 2px #fff,
            0 0 0 4px var(--ct-primary);
    }

    .summary {
        text-align: center;
    }
    .summary h2 {
        margin: 0 0 0.5rem;
        font-size: 1.3rem;
    }
    .score-big {
        font-size: 3.2rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1;
        background: var(--ct-gradient);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
    }
    .of {
        color: var(--ct-muted);
        -webkit-text-fill-color: var(--ct-muted);
        font-size: 1.4rem;
        font-weight: 700;
        margin-left: 0.3rem;
    }
    .score-sub {
        color: var(--ct-muted);
        margin: 0.3rem 0 1.2rem;
    }
    .missed {
        text-align: left;
        background: var(--ct-indigo-50);
        border-radius: 12px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 1.2rem;
    }
    .missed-title {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--ct-primary);
    }
    .missed ul {
        list-style: none;
        margin: 0.5rem 0 0;
        padding: 0;
    }
    .missed li {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.25rem 0;
        font-weight: 500;
    }
    .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--ct-gradient);
        flex: none;
    }
    .mn {
        margin-left: auto;
        color: var(--ct-muted);
        font-size: 0.82rem;
        font-weight: 400;
    }
    .perfect {
        color: #047857;
        font-weight: 600;
        margin-bottom: 1.2rem;
    }

    @media (prefers-reduced-motion: reduce) {
        .opt,
        .btn.primary,
        .btn.ghost,
        .bar-fill {
            transition: none;
        }
        .opt:hover:not(:disabled),
        .btn.primary:hover,
        .btn.ghost:hover {
            transform: none;
        }
    }
</style>
