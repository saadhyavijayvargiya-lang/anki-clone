<!--
Copyright: Ankitects Pty Ltd and contributors
Copyright: TopGRE contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import { onMount } from "svelte";

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

    function pct(x: number): string {
        return `${Math.round(x * 100)}%`;
    }

    $: updated = info.updatedAt
        ? new Date(Number(info.updatedAt) * 1000).toLocaleString()
        : "";

    async function refresh(): Promise<void> {
        info = await getReadiness({ search: "" });
        queue = (await pointsAtStakeQueue({ search: "", limit: 5 })).cards;
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
            await recordExamAttempt({
                moveType,
                correct,
                milliseconds: ms,
            });
            feedback = `Recorded ${correct ? "correct" : "missed"} ${moveType} attempt (${(ms / 1000).toFixed(0)}s).`;
            resetTimer();
            await refresh();
        } finally {
            recording = false;
        }
    }

    onMount(() => {
        refresh();
    });
</script>

<div class="readiness">
    <h1>TopGRE Readiness</h1>
    <p class="scope">
        GRE Mathematics Subject Test — point-set topology cluster. Topology is
        only part of the exam, so we never fabricate a full 200–990 score.
    </p>

    <div class="cards">
        <ScoreCard
            title="Memory"
            subtitle="recall a taught fact"
            score={info.memory}
        />
        <ScoreCard
            title="Performance"
            subtitle="answer a new exam question"
            score={info.performance}
        />
        <ScoreCard
            title="Readiness"
            subtitle="topology-cluster projection"
            score={info.readiness}
        />
    </div>

    <div class="meta">
        <span>Coverage: <strong>{pct(info.coverage)}</strong> of the topology outline</span>
        <span>Graded reviews: <strong>{info.gradedReviews}</strong></span>
        <span>Exam attempts: <strong>{info.examAttempts}</strong></span>
        {#if updated}<span>Updated: {updated}</span>{/if}
    </div>

    {#if info.bestNext}
        <div class="best-next"><strong>Best next:</strong> {info.bestNext}</div>
    {/if}

    <section class="panel">
        <h2>Triage queue — study these first</h2>
        <p class="hint">
            Ranked in Rust by exam leverage × weakness ÷ expected minutes
            (points at stake).
        </p>
        {#if queue.length}
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Move</th>
                        <th>Weakness</th>
                        <th>At stake</th>
                        <th>Value/min</th>
                    </tr>
                </thead>
                <tbody>
                    {#each queue as card, i}
                        <tr>
                            <td>{i + 1}</td>
                            <td>{card.moveType}</td>
                            <td>{pct(card.weakness)}</td>
                            <td>{card.pointsAtStake.toFixed(2)}</td>
                            <td>{card.timeEfficiency.toFixed(2)}</td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        {:else}
            <p class="hint">No due or new cards right now.</p>
        {/if}
    </section>

    <section class="panel">
        <h2>Record exam practice</h2>
        <p class="hint">
            Work a real practice problem on paper, then log the move-type it
            needed and whether you got it. This feeds the Performance model
            (needs 10+ attempts).
        </p>
        <div class="practice-row">
            <select bind:value={moveType} on:change={resetTimer}>
                {#each MOVE_TYPES as mt}
                    <option value={mt}>{mt}</option>
                {/each}
            </select>
            <button
                class="good"
                disabled={recording}
                on:click={() => record(true)}>Got it right</button
            >
            <button
                class="bad"
                disabled={recording}
                on:click={() => record(false)}>Missed it</button
            >
        </div>
        {#if feedback}
            <p class="feedback">{feedback}</p>
        {/if}
    </section>

    {#if info.reasons.length}
        <section>
            <h2>Evidence</h2>
            <ul>
                {#each info.reasons as reason}
                    <li>{reason}</li>
                {/each}
            </ul>
        </section>
    {/if}

    {#if info.missing.length}
        <section class="missing">
            <h2>What's missing</h2>
            <ul>
                {#each info.missing as item}
                    <li>{item}</li>
                {/each}
            </ul>
        </section>
    {/if}
</div>

<style lang="scss">
    .readiness {
        max-width: 52rem;
        margin: 0 auto;
        padding: 1.5rem;
        font-size: var(--font-size);
    }
    h1 {
        margin-bottom: 0.25rem;
    }
    .scope {
        color: var(--fg-subtle);
        margin-top: 0;
    }
    .cards {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        margin: 1.25rem 0;
    }
    .meta {
        display: flex;
        flex-wrap: wrap;
        gap: 1.25rem;
        color: var(--fg-subtle);
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
    .best-next {
        border: 1px solid var(--border);
        border-left: 4px solid var(--accent, #4c8bf5);
        border-radius: 6px;
        padding: 0.75rem 1rem;
        background: var(--canvas-elevated);
        margin-bottom: 1.25rem;
    }
    section {
        margin-bottom: 1.25rem;
    }
    section h2 {
        font-size: 1rem;
        margin-bottom: 0.35rem;
    }
    section.missing {
        color: var(--fg-subtle);
    }
    .panel {
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1rem 1.25rem;
        background: var(--canvas-elevated);
    }
    .hint {
        color: var(--fg-subtle);
        font-size: 0.85rem;
        margin: 0.25rem 0 0.5rem;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }
    th,
    td {
        text-align: left;
        padding: 0.3rem 0.5rem;
        border-bottom: 1px solid var(--border);
    }
    .practice-row {
        display: flex;
        gap: 0.6rem;
        align-items: center;
        flex-wrap: wrap;
    }
    select {
        padding: 0.35rem 0.5rem;
        border: 1px solid var(--border);
        border-radius: 6px;
        background: var(--canvas);
        color: var(--fg);
    }
    button {
        padding: 0.4rem 0.9rem;
        border-radius: 6px;
        border: 1px solid var(--border);
        cursor: pointer;
        font-weight: 600;
    }
    button.good {
        background: #2e7d3218;
        border-color: #2e7d32;
        color: #2e7d32;
    }
    button.bad {
        background: #c6282818;
        border-color: #c62828;
        color: #c62828;
    }
    .feedback {
        color: var(--fg-subtle);
        font-size: 0.85rem;
        margin-top: 0.5rem;
    }
    ul {
        margin: 0;
        padding-left: 1.2rem;
    }
</style>
