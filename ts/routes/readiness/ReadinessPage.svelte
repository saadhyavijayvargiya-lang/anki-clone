<!--
Copyright: Ankitects Pty Ltd and contributors
Copyright: TopGRE contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import { onMount } from "svelte";

    import { bridgeCommand } from "@tslib/bridgecommand";
    import type {
        PointsAtStakeCard,
        ReadinessResponse,
    } from "@generated/anki/readiness_pb";
    import {
        getReadiness,
        pointsAtStakeQueue,
        recordExamAttempt,
    } from "@generated/backend";

    import ScoreCard from "./ScoreCard.svelte";

    export let info: ReadinessResponse;

    // Mirrors TOPOLOGY_OUTLINE in rslib/src/readiness/mod.rs.
    const MOVE_TYPES = [
        "open-closed-sets",
        "interior-closure-boundary",
        "bases-subbases",
        "continuity",
        "homeomorphism",
        "compactness",
        "connectedness",
        "separation",
        "examples",
    ];

    let queue: PointsAtStakeCard[] = [];
    let moveType = MOVE_TYPES[5]; // compactness
    let questionStart = Date.now();
    let recording = false;
    let feedback = "";
    let busyAction = "";

    let coachText = "";
    let coachSource = "";
    let coachLoading = false;

    async function getPlan(): Promise<void> {
        coachLoading = true;
        try {
            const res = await fetch("/_anki/cruxAiCoach", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: "{}",
            });
            const data = await res.json();
            coachText = data.text;
            coachSource = data.source;
        } catch {
            coachText = "Could not build a plan right now.";
            coachSource = "";
        } finally {
            coachLoading = false;
        }
    }

    function pct(x: number): string {
        return `${Math.round(x * 100)}%`;
    }

    $: updated = info.updatedAt
        ? new Date(Number(info.updatedAt) * 1000).toLocaleString()
        : "not yet";

    async function refresh(): Promise<void> {
        info = await getReadiness({ search: "" });
        queue = (await pointsAtStakeQueue({ search: "", limit: 6 })).cards;
    }

    function resetTimer(): void {
        questionStart = Date.now();
    }

    async function record(correct: boolean): Promise<void> {
        if (recording) {
            return;
        }
        recording = true;
        const ms = Math.min(Date.now() - questionStart, 30 * 60 * 1000);
        try {
            await recordExamAttempt({ moveType, correct, milliseconds: ms });
            feedback = `Logged a ${correct ? "correct" : "missed"} ${moveType} attempt at ${(ms / 1000).toFixed(0)}s.`;
            resetTimer();
            await refresh();
        } finally {
            recording = false;
        }
    }

    function runCram(): void {
        busyAction = "cram";
        bridgeCommand("topgre:cram");
    }

    function runTriage(): void {
        busyAction = "triage";
        feedback = "Reordering new cards by points at stake.";
        bridgeCommand("topgre:triage");
        setTimeout(() => {
            busyAction = "";
            refresh();
        }, 400);
    }

    onMount(() => {
        refresh();
    });
</script>

<div class="bg" aria-hidden="true">
    <span class="blob blob-a"></span>
    <span class="blob blob-b"></span>
    <span class="blob blob-c"></span>
</div>

<main class="readiness">
    <header class="hero">
        <span class="pill">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z" /><path d="M6 12v5c3 3 9 3 12 0v-5" /></svg>
            GRE Math Subject Test · Topology cluster
        </span>

        <h1>How ready are you, <span class="grad">really</span>?</h1>
        <p class="lede">
            Three scores you can trust, scoped to the point-set topology cluster.
            Topology is only part of the exam, so nothing here fabricates a full
            200 to 990 result.
        </p>

        <div class="actions">
            <button class="btn primary" on:click={runCram} disabled={busyAction === "cram"}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0011 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 11-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 002.5 2.5z" /></svg>
                Cram most dangerous
            </button>
            <button class="btn ghost" on:click={runTriage} disabled={busyAction === "triage"}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5h10M11 9h7M11 15h10M11 19h7" /><path d="M3 8l3-3 3 3M6 5v14" /></svg>
                Reorder triage
            </button>
            <button class="btn ghost" on:click={refresh} disabled={recording}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 11-2.64-6.36M21 3v6h-6" /></svg>
                Refresh
            </button>
        </div>

        {#if info.bestNext}
            <div class="best-next">
                <span class="bn-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" /><path d="M19 3v4M17 5h4M5 18v2M4 19h2" /></svg>
                </span>
                <div>
                    <span class="bn-label">Best next move</span>
                    <span class="bn-text">{info.bestNext}</span>
                </div>
            </div>
        {/if}
    </header>

    <section class="stats" aria-label="Summary">
        <div class="stat">
            <span class="stat-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l9 5-9 5-9-5 9-5z" /><path d="M3 12l9 5 9-5M3 17l9 5 9-5" /></svg></span>
            <span class="stat-num">{pct(info.coverage)}</span>
            <span class="stat-label">Outline coverage</span>
        </div>
        <div class="stat">
            <span class="stat-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5" /></svg></span>
            <span class="stat-num">{info.gradedReviews}</span>
            <span class="stat-label">Graded reviews</span>
        </div>
        <div class="stat">
            <span class="stat-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 013 3L7 19l-4 1 1-4z" /></svg></span>
            <span class="stat-num">{info.examAttempts}</span>
            <span class="stat-label">Exam attempts</span>
        </div>
        <div class="stat">
            <span class="stat-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg></span>
            <span class="stat-num small">{updated}</span>
            <span class="stat-label">Last updated</span>
        </div>
    </section>

    <section class="scores">
        <ScoreCard title="Memory" subtitle="recall a taught fact" score={info.memory}>
            <svg slot="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 22h4" /><path d="M12 2a7 7 0 00-4 12.7c.6.5 1 1.3 1 2.1h6c0-.8.4-1.6 1-2.1A7 7 0 0012 2z" /></svg>
        </ScoreCard>
        <ScoreCard title="Performance" subtitle="answer a new exam question" score={info.performance}>
            <svg slot="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></svg>
        </ScoreCard>
        <ScoreCard title="Readiness" subtitle="topology-cluster projection" score={info.readiness} highlight>
            <svg slot="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l6-6 4 4 8-8" /><path d="M21 7v5h-5" /></svg>
        </ScoreCard>
    </section>

    <section class="panel coach">
        <div class="panel-head coach-head">
            <div>
                <h2>Crux coach</h2>
                <p>A concrete plan from the triage engine, sharpened by AI when it is configured.</p>
            </div>
            <button class="btn ghost" on:click={getPlan} disabled={coachLoading}>
                {coachLoading ? "Thinking" : "Get plan"}
            </button>
        </div>
        {#if coachText}
            <div class="coach-body">
                <p>{coachText}</p>
                <span class="coach-badge {coachSource === 'ai' ? 'ai' : ''}">
                    {coachSource === "ai" ? "AI plan" : "engine plan"}
                </span>
            </div>
        {/if}
    </section>

    <section class="panel">
        <div class="panel-head">
            <h2>Triage queue</h2>
            <p>Ranked in Rust by points at stake: exam weight times weakness over expected minutes.</p>
        </div>
        {#if queue.length}
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Move</th>
                            <th>Weakness</th>
                            <th>At stake</th>
                            <th>Value / min</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each queue as card, i}
                            <tr>
                                <td><span class="rank">{i + 1}</span></td>
                                <td class="move">{card.moveType}</td>
                                <td>
                                    <div class="weak">
                                        <div class="weak-track"><div class="weak-fill" style="width: {card.weakness * 100}%"></div></div>
                                        <span>{pct(card.weakness)}</span>
                                    </div>
                                </td>
                                <td class="mono">{card.pointsAtStake.toFixed(2)}</td>
                                <td class="mono">{card.timeEfficiency.toFixed(2)}</td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        {:else}
            <p class="empty">No due or new cards right now. Reorder triage or start a cram run.</p>
        {/if}
    </section>

    <section class="panel">
        <div class="panel-head">
            <h2>Record exam practice</h2>
            <p>Work a real problem on paper, log the move it needed and whether you got it. This feeds Performance (needs 10 or more attempts).</p>
        </div>
        <div class="practice">
            <label class="field">
                <span class="field-label">Move type</span>
                <select bind:value={moveType} on:change={resetTimer}>
                    {#each MOVE_TYPES as mt}
                        <option value={mt}>{mt}</option>
                    {/each}
                </select>
            </label>
            <div class="verdict">
                <button class="btn good" disabled={recording} on:click={() => record(true)}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5" /></svg>
                    Got it
                </button>
                <button class="btn bad" disabled={recording} on:click={() => record(false)}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12" /></svg>
                    Missed it
                </button>
            </div>
        </div>
        {#if feedback}
            <p class="feedback">{feedback}</p>
        {/if}
    </section>

    {#if info.reasons.length || info.missing.length}
        <section class="evidence-grid">
            {#if info.reasons.length}
                <div class="panel note">
                    <h2>Evidence</h2>
                    <ul>
                        {#each info.reasons as reason}<li>{reason}</li>{/each}
                    </ul>
                </div>
            {/if}
            {#if info.missing.length}
                <div class="panel note muted">
                    <h2>What is missing</h2>
                    <ul>
                        {#each info.missing as item}<li>{item}</li>{/each}
                    </ul>
                </div>
            {/if}
        </section>
    {/if}
</main>

<style lang="scss">
    :global(html),
    :global(body) {
        margin: 0;
        background: #f8fafc;
    }

    .readiness {
        /* Corporate Trust tokens */
        --ct-bg: #f8fafc;
        --ct-surface: #ffffff;
        --ct-primary: #4f46e5;
        --ct-secondary: #7c3aed;
        --ct-ink: #0f172a;
        --ct-muted: #64748b;
        --ct-success: #10b981;
        --ct-border: #e2e8f0;
        --ct-border-soft: #eef2f7;
        --ct-indigo-50: #eef2ff;
        --ct-gradient: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        --ct-shadow: 0 4px 20px -2px rgba(79, 70, 229, 0.1);
        --ct-shadow-hover:
            0 10px 25px -5px rgba(79, 70, 229, 0.15),
            0 8px 10px -6px rgba(79, 70, 229, 0.1);
        --ct-btn-shadow: 0 4px 14px 0 rgba(79, 70, 229, 0.3);

        position: relative;
        z-index: 1;
        max-width: 68rem;
        margin: 0 auto;
        padding: 2.5rem 1.5rem 4rem;
        color: var(--ct-ink);
        font-family:
            "Plus Jakarta Sans", "Segoe UI Variable", "Segoe UI", system-ui,
            -apple-system, "Helvetica Neue", Arial, sans-serif;
        line-height: 1.6;
        color-scheme: light;
    }

    /* Atmospheric background */
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
        opacity: 0.45;
    }
    .blob-a {
        width: 34rem;
        height: 34rem;
        top: -12rem;
        right: -8rem;
        background: radial-gradient(circle, #c7d2fe, transparent 70%);
    }
    .blob-b {
        width: 30rem;
        height: 30rem;
        top: 24rem;
        left: -12rem;
        background: radial-gradient(circle, #ddd6fe, transparent 70%);
    }
    .blob-c {
        width: 22rem;
        height: 22rem;
        bottom: -8rem;
        right: 10%;
        background: radial-gradient(circle, #a7f3d0, transparent 70%);
        opacity: 0.3;
    }

    /* Hero */
    .hero {
        margin-bottom: 2rem;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.78rem;
        font-weight: 600;
        color: var(--ct-primary);
        background: var(--ct-indigo-50);
        border: 1px solid #e0e7ff;
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
    }
    .pill svg {
        width: 0.95rem;
        height: 0.95rem;
    }
    h1 {
        font-size: clamp(2rem, 4vw, 3.25rem);
        font-weight: 800;
        letter-spacing: -0.03em;
        line-height: 1.08;
        margin: 0.9rem 0 0.6rem;
        text-wrap: balance;
    }
    .grad {
        background: var(--ct-gradient);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
    }
    .lede {
        max-width: 40rem;
        color: var(--ct-muted);
        font-size: 1.02rem;
        margin: 0 0 1.5rem;
    }

    .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
    }
    .btn {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        font: inherit;
        font-weight: 600;
        font-size: 0.95rem;
        padding: 0.7rem 1.25rem;
        border-radius: 999px;
        cursor: pointer;
        border: 1px solid transparent;
        transition:
            transform 0.2s ease-out,
            box-shadow 0.2s ease-out,
            background 0.2s ease-out;
    }
    .btn svg {
        width: 1.05rem;
        height: 1.05rem;
    }
    .btn:disabled {
        opacity: 0.55;
        pointer-events: none;
    }
    .btn.primary {
        background: var(--ct-gradient);
        color: #fff;
        box-shadow: var(--ct-btn-shadow);
    }
    .btn.primary:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 22px 0 rgba(79, 70, 229, 0.4);
    }
    .btn.ghost {
        background: var(--ct-surface);
        border-color: var(--ct-border);
        color: #334155;
        box-shadow: var(--ct-shadow);
    }
    .btn.ghost:hover {
        transform: translateY(-2px);
        border-color: #cbd5e1;
        background: #f8fafc;
    }
    .btn:focus-visible {
        outline: none;
        box-shadow:
            0 0 0 2px #fff,
            0 0 0 4px var(--ct-primary);
    }

    .best-next {
        display: flex;
        align-items: center;
        gap: 0.85rem;
        margin-top: 1.5rem;
        padding: 0.9rem 1.1rem;
        border-radius: 14px;
        background:
            linear-gradient(var(--ct-surface), var(--ct-surface)) padding-box,
            var(--ct-gradient) border-box;
        border: 1.5px solid transparent;
        box-shadow: var(--ct-shadow);
    }
    .bn-icon {
        display: grid;
        place-items: center;
        width: 2.5rem;
        height: 2.5rem;
        border-radius: 10px;
        background: var(--ct-gradient);
        color: #fff;
        flex: none;
    }
    .bn-icon svg {
        width: 1.2rem;
        height: 1.2rem;
    }
    .bn-label {
        display: block;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--ct-primary);
    }
    .bn-text {
        color: var(--ct-ink);
        font-weight: 500;
    }

    /* Stats */
    .stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 1rem;
        margin-bottom: 2.25rem;
    }
    .stat {
        background: var(--ct-surface);
        border: 1px solid var(--ct-border-soft);
        border-radius: 14px;
        padding: 1.1rem 1.2rem;
        box-shadow: var(--ct-shadow);
    }
    .stat-ico {
        display: grid;
        place-items: center;
        width: 2.25rem;
        height: 2.25rem;
        border-radius: 10px;
        background: var(--ct-indigo-50);
        color: var(--ct-primary);
        margin-bottom: 0.6rem;
    }
    .stat-ico svg {
        width: 1.15rem;
        height: 1.15rem;
    }
    .stat-num {
        display: block;
        font-size: 1.75rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1.1;
        color: var(--ct-ink);
    }
    .stat-num.small {
        font-size: 0.95rem;
        font-weight: 700;
    }
    .stat-label {
        font-size: 0.8rem;
        color: var(--ct-muted);
    }

    /* Scores */
    .scores {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        gap: 1.25rem;
        margin-bottom: 2.25rem;
    }

    /* Panels */
    .panel {
        background: var(--ct-surface);
        border: 1px solid var(--ct-border-soft);
        border-radius: 16px;
        padding: 1.4rem 1.6rem;
        box-shadow: var(--ct-shadow);
        margin-bottom: 1.5rem;
    }
    .panel-head {
        margin-bottom: 1rem;
    }
    .panel h2 {
        font-size: 1.15rem;
        font-weight: 700;
        margin: 0 0 0.15rem;
    }
    .panel-head p {
        margin: 0;
        color: var(--ct-muted);
        font-size: 0.88rem;
    }
    .coach-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
    }
    .coach-head .btn {
        flex: none;
    }
    .coach-body {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-top: 0.9rem;
        padding-top: 0.9rem;
        border-top: 1px solid var(--ct-border-soft);
    }
    .coach-body p {
        margin: 0;
        color: var(--ct-ink);
        line-height: 1.55;
    }
    .coach-badge {
        flex: none;
        align-self: flex-start;
        font-size: 0.65rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--ct-muted);
        background: var(--ct-border-soft);
        padding: 0.2rem 0.5rem;
        border-radius: 999px;
    }
    .coach-badge.ai {
        color: #fff;
        background: var(--ct-gradient);
    }

    .table-wrap {
        overflow-x: auto;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }
    thead th {
        text-align: left;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--ct-muted);
        padding: 0 0.6rem 0.6rem;
    }
    tbody td {
        padding: 0.65rem 0.6rem;
        border-top: 1px solid var(--ct-border-soft);
        vertical-align: middle;
    }
    tbody tr:hover td {
        background: #fafbff;
    }
    .rank {
        display: inline-grid;
        place-items: center;
        width: 1.7rem;
        height: 1.7rem;
        border-radius: 8px;
        background: var(--ct-indigo-50);
        color: var(--ct-primary);
        font-weight: 700;
        font-size: 0.8rem;
    }
    .move {
        font-weight: 600;
        color: var(--ct-ink);
    }
    .mono {
        font-variant-numeric: tabular-nums;
        color: var(--ct-muted);
    }
    .weak {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .weak-track {
        width: 5rem;
        height: 6px;
        border-radius: 999px;
        background: var(--ct-indigo-50);
        overflow: hidden;
    }
    .weak-fill {
        height: 100%;
        border-radius: 999px;
        background: var(--ct-gradient);
    }
    .empty {
        color: var(--ct-muted);
        font-size: 0.9rem;
        margin: 0;
    }

    /* Practice */
    .practice {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-end;
        gap: 1rem;
    }
    .field {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
    }
    .field-label {
        font-size: 0.82rem;
        font-weight: 600;
        color: #334155;
    }
    select {
        font: inherit;
        padding: 0.55rem 0.75rem;
        min-width: 14rem;
        border: 1px solid var(--ct-border);
        border-radius: 8px;
        background: var(--ct-surface);
        color: var(--ct-ink);
        transition:
            border-color 0.15s ease-out,
            box-shadow 0.15s ease-out;
    }
    select:focus-visible {
        outline: none;
        border-color: var(--ct-primary);
        box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.18);
    }
    .verdict {
        display: flex;
        gap: 0.6rem;
    }
    .btn.good {
        background: rgba(16, 185, 129, 0.1);
        border-color: rgba(16, 185, 129, 0.4);
        color: #047857;
    }
    .btn.good:hover {
        transform: translateY(-2px);
        background: rgba(16, 185, 129, 0.16);
    }
    .btn.bad {
        background: rgba(225, 29, 72, 0.08);
        border-color: rgba(225, 29, 72, 0.35);
        color: #be123c;
    }
    .btn.bad:hover {
        transform: translateY(-2px);
        background: rgba(225, 29, 72, 0.14);
    }
    .feedback {
        margin: 1rem 0 0;
        font-size: 0.88rem;
        color: var(--ct-success);
        font-weight: 500;
    }

    /* Evidence */
    .evidence-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 1.5rem;
    }
    .note ul {
        margin: 0;
        padding-left: 1.1rem;
    }
    .note li {
        margin-bottom: 0.35rem;
        font-size: 0.9rem;
    }
    .note.muted {
        color: var(--ct-muted);
    }

    @media (prefers-reduced-motion: reduce) {
        .btn,
        :global(.score-card) {
            transition: none;
        }
        .btn:hover,
        .btn.primary:hover,
        .btn.ghost:hover,
        .btn.good:hover,
        .btn.bad:hover {
            transform: none;
        }
    }
</style>
