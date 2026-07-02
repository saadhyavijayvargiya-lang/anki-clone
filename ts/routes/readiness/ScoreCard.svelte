<!--
Copyright: Ankitects Pty Ltd and contributors
Copyright: TopGRE contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { ScoreWithRange } from "@generated/anki/readiness_pb";

    export let title: string;
    export let subtitle: string;
    export let score: ScoreWithRange | undefined;

    function pct(x: number): string {
        return `${Math.round(x * 100)}%`;
    }
</script>

<div class="score-card" class:unavailable={!score?.available}>
    <div class="head">
        <span class="title">{title}</span>
        <span class="subtitle">{subtitle}</span>
    </div>
    {#if score?.available}
        <div class="value">{pct(score.value)}</div>
        <div class="bar">
            <div
                class="bar-range"
                style="left: {score.lower * 100}%; width: {(score.upper - score.lower) * 100}%"
            ></div>
            <div class="bar-point" style="left: {score.value * 100}%"></div>
        </div>
        <div class="range">likely {pct(score.lower)} – {pct(score.upper)}</div>
        <div class="unit">{score.unit}</div>
    {:else}
        <div class="value abstain">—</div>
        <div class="range">withheld: not enough data</div>
    {/if}
</div>

<style lang="scss">
    .score-card {
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1rem 1.25rem;
        background: var(--canvas-elevated);
        min-width: 12rem;
        flex: 1;
    }
    .score-card.unavailable {
        opacity: 0.7;
    }
    .head {
        display: flex;
        flex-direction: column;
    }
    .title {
        font-weight: 700;
        font-size: 1.1rem;
    }
    .subtitle {
        color: var(--fg-subtle);
        font-size: 0.8rem;
    }
    .value {
        font-size: 2.4rem;
        font-weight: 800;
        margin: 0.25rem 0;
    }
    .value.abstain {
        color: var(--fg-subtle);
    }
    .bar {
        position: relative;
        height: 8px;
        border-radius: 4px;
        background: var(--canvas-inset, var(--canvas));
        border: 1px solid var(--border);
        margin: 0.4rem 0;
    }
    .bar-range {
        position: absolute;
        top: 0;
        height: 100%;
        background: var(--accent, #4c8bf5);
        opacity: 0.35;
        border-radius: 4px;
    }
    .bar-point {
        position: absolute;
        top: -2px;
        width: 3px;
        height: 12px;
        background: var(--accent, #4c8bf5);
    }
    .range {
        font-size: 0.85rem;
        color: var(--fg-subtle);
    }
    .unit {
        font-size: 0.75rem;
        color: var(--fg-subtle);
    }
</style>
