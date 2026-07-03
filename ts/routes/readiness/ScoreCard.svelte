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
    export let highlight = false;

    function pct(x: number): string {
        return `${Math.round(x * 100)}%`;
    }

    $: available = !!score?.available;
    $: value = score ? score.value * 100 : 0;
    $: lower = score ? score.lower * 100 : 0;
    $: upper = score ? score.upper * 100 : 0;
</script>

<div class="score-card" class:highlight class:unavailable={!available}>
    {#if highlight}
        <span class="tag">Headline</span>
    {/if}
    <div class="top">
        <span class="icon"><slot name="icon" /></span>
        <div class="head">
            <span class="title">{title}</span>
            <span class="subtitle">{subtitle}</span>
        </div>
    </div>

    {#if available && score}
        <div class="value">{pct(score.value)}</div>
        <div class="bar" role="img" aria-label="{title} {pct(score.value)}, likely {pct(score.lower)} to {pct(score.upper)}">
            <div class="band" style="left: {lower}%; width: {Math.max(upper - lower, 0)}%"></div>
            <div class="fill" style="width: {value}%"></div>
            <div class="knob" style="left: {value}%"></div>
        </div>
        <div class="range">likely {pct(score.lower)} to {pct(score.upper)}</div>
        <div class="unit">{score.unit}</div>
    {:else}
        <div class="value abstain">n/a</div>
        <div class="bar empty"></div>
        <div class="range withheld">Withheld: not enough data yet</div>
    {/if}
</div>

<style lang="scss">
    .score-card {
        position: relative;
        background: var(--ct-surface);
        border: 1px solid var(--ct-border-soft);
        border-radius: 16px;
        padding: 1.25rem 1.35rem 1.4rem;
        box-shadow: var(--ct-shadow);
        transition:
            transform 0.2s ease-out,
            box-shadow 0.2s ease-out;
    }
    .score-card:hover {
        transform: translateY(-4px);
        box-shadow: var(--ct-shadow-hover);
    }
    .score-card.highlight {
        border-color: transparent;
        background:
            linear-gradient(var(--ct-surface), var(--ct-surface)) padding-box,
            var(--ct-gradient) border-box;
        border: 1.5px solid transparent;
        box-shadow: var(--ct-shadow-hover);
    }
    .score-card.unavailable {
        box-shadow: none;
        border-style: dashed;
    }
    .score-card.unavailable:hover {
        transform: none;
        box-shadow: none;
    }

    .tag {
        position: absolute;
        top: -0.6rem;
        right: 1.1rem;
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #fff;
        background: var(--ct-gradient);
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        box-shadow: 0 0 18px rgba(79, 70, 229, 0.45);
    }

    .top {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.65rem;
    }
    .icon {
        display: grid;
        place-items: center;
        width: 2.75rem;
        height: 2.75rem;
        border-radius: 12px;
        background: var(--ct-indigo-50);
        color: var(--ct-primary);
        flex: none;
    }
    .icon :global(svg) {
        width: 1.35rem;
        height: 1.35rem;
    }
    .head {
        display: flex;
        flex-direction: column;
        line-height: 1.2;
    }
    .title {
        font-weight: 700;
        font-size: 1.02rem;
        color: var(--ct-ink);
    }
    .subtitle {
        color: var(--ct-muted);
        font-size: 0.78rem;
    }

    .value {
        font-size: 2.75rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 1;
        color: var(--ct-ink);
        margin: 0.35rem 0 0.55rem;
    }
    .value.abstain {
        color: var(--ct-muted);
    }

    .bar {
        position: relative;
        height: 9px;
        border-radius: 999px;
        background: var(--ct-indigo-50);
        overflow: visible;
    }
    .bar.empty {
        background: repeating-linear-gradient(
            90deg,
            var(--ct-border) 0 6px,
            transparent 6px 12px
        );
        opacity: 0.5;
    }
    .band {
        position: absolute;
        top: 0;
        height: 100%;
        border-radius: 999px;
        background: rgba(124, 58, 237, 0.18);
    }
    .fill {
        position: absolute;
        top: 0;
        left: 0;
        height: 100%;
        border-radius: 999px;
        background: var(--ct-gradient);
    }
    .knob {
        position: absolute;
        top: 50%;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #fff;
        border: 3px solid var(--ct-primary);
        transform: translate(-50%, -50%);
        box-shadow: 0 0 12px rgba(79, 70, 229, 0.5);
    }
    .range {
        margin-top: 0.6rem;
        font-size: 0.82rem;
        color: var(--ct-muted);
    }
    .range.withheld {
        color: var(--ct-muted);
        font-style: italic;
    }
    .unit {
        font-size: 0.72rem;
        color: var(--ct-muted);
        margin-top: 0.1rem;
    }
</style>
