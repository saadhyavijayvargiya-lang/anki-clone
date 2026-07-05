// Copyright: Ankitects Pty Ltd and contributors
// Copyright: TopGRE contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! TopGRE readiness engine.
//!
//! The core spiky idea: GRE topology problems map to a small, finite library of
//! proof "moves". The score bottleneck is routing a new problem to the right
//! move, and doing it fast enough (triage). This module implements a new,
//! triage-aware review order ("points at stake"): due/new cards are ranked by
//! exam leverage (topic weight) x student weakness (1 - FSRS retrievability),
//! divided by the expected time to solve, so the highest value-per-minute cards
//! come first.

pub(crate) mod service;

use std::collections::HashMap;
use std::collections::HashSet;

use fsrs::FSRS;
use fsrs::FSRS5_DEFAULT_DECAY;
use serde::Deserialize;
use serde::Serialize;

use crate::prelude::*;
use crate::scheduler::timing::SchedTimingToday;
use crate::search::SortMode;

/// Collection-config key under which exam-attempt performance data is stored.
/// Config syncs, so recorded attempts flow to the phone for free.
const PERF_KEY: &str = "topgrePerf";

/// Minimum recorded exam attempts before Performance is estimated at all.
const PERF_MIN_ATTEMPTS: u32 = 10;

/// Performance data persisted in collection config.
#[derive(Debug, Default, Serialize, Deserialize)]
struct PerfData {
    #[serde(default)]
    moves: HashMap<String, MoveStats>,
    #[serde(default)]
    attempts: Vec<Attempt>,
}

#[derive(Debug, Default, Clone, Copy, Serialize, Deserialize)]
struct MoveStats {
    correct: u32,
    total: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Attempt {
    mt: String,
    correct: bool,
    ms: u32,
    ts: i64,
}

/// Wilson score 95% interval for a binomial proportion. Returns
/// (point estimate, lower, upper), all clamped to [0,1].
fn wilson(correct: f64, n: f64) -> (f64, f64, f64) {
    if n <= 0.0 {
        return (0.0, 0.0, 0.0);
    }
    let z = 1.96;
    let p = correct / n;
    let denom = 1.0 + z * z / n;
    let center = (p + z * z / (2.0 * n)) / denom;
    let margin = z * ((p * (1.0 - p) + z * z / (4.0 * n)) / n).sqrt() / denom;
    (p, (center - margin).clamp(0.0, 1.0), (center + margin).clamp(0.0, 1.0))
}

/// The point-set topology outline TopGRE targets. Coverage is measured against
/// this list (a card is "covered" if it carries a matching `move::<type>` tag).
pub const TOPOLOGY_OUTLINE: &[&str] = &[
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

/// Give-up thresholds: no Readiness score is shown until all are met. (A good
/// system knows when it does not know.) Full GRE 200-990 is never projected -
/// topology is ~10% of the exam, so a full-scale number would be a fabrication.
const GIVEUP_MIN_REVIEWS: u32 = 150;
const GIVEUP_MIN_COVERAGE: f64 = 0.5;
const GIVEUP_MIN_ATTEMPTS: u32 = 30;

/// Exam leverage and typical time cost for a topology move-type.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct MoveProfile {
    /// Relative exam leverage of this move-type (roughly 0..1).
    pub weight: f64,
    /// Expected minutes to solve a problem of this move-type.
    pub minutes: f64,
}

/// Default leverage/time profile per move-type. Weights reflect how much a
/// move-type moves the topology subscore; minutes reflect typical solve time.
/// Overridable later via collection config; kept as a pure fn for testability.
pub fn default_move_profile(move_type: &str) -> MoveProfile {
    match move_type {
        "compactness" => MoveProfile { weight: 1.0, minutes: 3.0 },
        "connectedness" => MoveProfile { weight: 0.9, minutes: 2.5 },
        "homeomorphism" => MoveProfile { weight: 0.85, minutes: 2.5 },
        "separation" => MoveProfile { weight: 0.8, minutes: 2.0 },
        "continuity" => MoveProfile { weight: 0.7, minutes: 1.5 },
        "examples" => MoveProfile { weight: 0.6, minutes: 1.0 },
        _ => MoveProfile { weight: 0.5, minutes: 2.0 },
    }
}

/// Value at stake = exam leverage x how weak the student is (clamped to [0,1]).
pub fn value_at_stake(weight: f64, weakness: f64) -> f64 {
    weight * weakness.clamp(0.0, 1.0)
}

/// Triage efficiency = value per expected minute of study (SPOV2). Minutes are
/// floored so a near-zero estimate can't produce an infinite score.
pub fn time_efficiency(value: f64, minutes: f64) -> f64 {
    value / minutes.max(0.25)
}

/// Mean and a 95% confidence interval (clamped to [0,1]) for a set of values.
fn mean_ci(values: &[f64]) -> (f64, f64, f64) {
    let n = values.len() as f64;
    let mean = values.iter().sum::<f64>() / n;
    let variance = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n;
    let margin = 1.96 * variance.sqrt() / n.sqrt();
    (mean, (mean - margin).clamp(0.0, 1.0), (mean + margin).clamp(0.0, 1.0))
}

/// An abstaining score (the give-up rule): value/range are meaningless.
fn unavailable_score(unit: &str) -> anki_proto::readiness::ScoreWithRange {
    anki_proto::readiness::ScoreWithRange {
        available: false,
        value: 0.0,
        lower: 0.0,
        upper: 0.0,
        unit: unit.to_string(),
    }
}

impl Collection {
    /// Build the triage-aware "points at stake" review order.
    ///
    /// Considers cards that are ready to study now (due or new) matching the
    /// optional `search`, scores each, and returns them sorted by time
    /// efficiency descending. This is a pure read: it does not mutate the
    /// collection, so undo is unaffected.
    pub fn points_at_stake_queue(
        &mut self,
        search: &str,
        limit: usize,
    ) -> Result<anki_proto::readiness::PointsAtStakeResponse> {
        let query = if search.trim().is_empty() {
            "(is:due or is:new) -is:suspended".to_string()
        } else {
            format!("({search}) (is:due or is:new) -is:suspended")
        };
        let cids = self.search_cards(&query, SortMode::NoOrder)?;
        let timing = self.timing_today()?;

        // Per-move-type miss rate (1 - exam accuracy) from recorded attempts, so
        // triage surfaces the types you actually miss on the exam, not just the
        // quickest cards. A type you ace (e.g. examples) should not dominate.
        let perf = self.load_perf_data();
        let mut miss: HashMap<String, f64> = HashMap::new();
        for (mt, stats) in &perf.moves {
            if stats.total > 0 {
                miss.insert(mt.clone(), 1.0 - (stats.correct as f64 / stats.total as f64));
            }
        }

        let mut cards: Vec<anki_proto::readiness::PointsAtStakeCard> =
            Vec::with_capacity(cids.len());
        for cid in cids {
            let card = self.storage.get_card(cid)?.or_not_found(cid)?;
            let move_type = self.move_type_for_card(&card)?;
            let profile = default_move_profile(&move_type);
            let weakness = 1.0 - self.card_retrievability(&card, &timing);
            let miss_rate = *miss.get(&move_type).unwrap_or(&0.0);
            // Points at stake = exam weight x weakness x (1 + exam miss-rate).
            let value = value_at_stake(profile.weight, weakness) * (1.0 + miss_rate);
            let efficiency = time_efficiency(value, profile.minutes);
            cards.push(anki_proto::readiness::PointsAtStakeCard {
                card_id: cid.0,
                move_type,
                points_at_stake: value,
                topic_weight: profile.weight,
                weakness,
                time_efficiency: efficiency,
            });
        }

        // Order by points at stake (danger) descending, so the highest-value
        // cards come first. Interleaved (default) mixes move-types; blocked
        // practice (ablation) groups by move-type first. Ties by card_id.
        let interleaving = self.interleaving_enabled();
        cards.sort_by(|a, b| {
            let grouped = if interleaving {
                std::cmp::Ordering::Equal
            } else {
                a.move_type.cmp(&b.move_type)
            };
            grouped
                .then(
                    b.points_at_stake
                        .partial_cmp(&a.points_at_stake)
                        .unwrap_or(std::cmp::Ordering::Equal),
                )
                .then(a.card_id.cmp(&b.card_id))
        });
        if limit > 0 {
            cards.truncate(limit);
        }

        Ok(anki_proto::readiness::PointsAtStakeResponse { cards })
    }

    /// Compute the three honest scores (Memory / Performance / Readiness) with
    /// ranges, coverage, evidence, and the give-up rule. Scores that lack data
    /// are returned with `available = false` instead of a fabricated number.
    pub fn readiness(
        &mut self,
        search: &str,
    ) -> Result<anki_proto::readiness::ReadinessResponse> {
        use anki_proto::readiness::ReadinessResponse;
        use anki_proto::readiness::ScoreWithRange;

        // Empty search = whole collection. `deck:*` reliably matches all cards.
        let query = if search.trim().is_empty() {
            "deck:*".to_string()
        } else {
            search.to_string()
        };
        let cids = self.search_cards(&query, SortMode::NoOrder)?;
        let timing = self.timing_today()?;

        let mut retrievabilities: Vec<f64> = Vec::new();
        let mut graded_reviews: u32 = 0;
        let mut covered: HashSet<String> = HashSet::new();
        // move-type -> (sum retrievability, count) for the "best next" hint.
        let mut per_move: HashMap<String, (f64, u32)> = HashMap::new();

        for cid in cids {
            let card = self.storage.get_card(cid)?.or_not_found(cid)?;
            graded_reviews = graded_reviews.saturating_add(card.reps);
            let move_type = self.move_type_for_card(&card)?;
            if move_type != "unknown" {
                covered.insert(move_type.clone());
            }
            if card.memory_state.is_some() {
                let r = self.card_retrievability(&card, &timing);
                retrievabilities.push(r);
                let entry = per_move.entry(move_type).or_insert((0.0, 0));
                entry.0 += r;
                entry.1 += 1;
            }
        }

        let coverage = covered.len() as f64 / TOPOLOGY_OUTLINE.len() as f64;

        // Performance is estimated from recorded exam-style attempts (stored in
        // collection config, so it syncs to the phone).
        let perf = self.load_perf_data();
        let total_correct: u32 = perf.moves.values().map(|m| m.correct).sum();
        let exam_attempts: u32 = perf.moves.values().map(|m| m.total).sum();

        let mut reasons: Vec<String> = Vec::new();
        let mut missing: Vec<String> = Vec::new();

        // ---- Memory (FSRS) ----
        let memory = if retrievabilities.is_empty() {
            missing.push("No reviewed cards yet, so memory can't be estimated.".into());
            unavailable_score("recall probability")
        } else {
            let (mean, lower, upper) = mean_ci(&retrievabilities);
            reasons.push(format!(
                "Memory from {} reviewed cards (mean recall {:.0}%).",
                retrievabilities.len(),
                mean * 100.0
            ));
            ScoreWithRange {
                available: true,
                value: mean,
                lower,
                upper,
                unit: "recall probability".into(),
            }
        };

        // ---- Performance (from recorded exam-style attempts) ----
        let performance = if exam_attempts >= PERF_MIN_ATTEMPTS {
            let (value, lower, upper) = wilson(total_correct as f64, exam_attempts as f64);
            reasons.push(format!(
                "Performance from {exam_attempts} exam-style attempts ({total_correct} correct)."
            ));
            ScoreWithRange {
                available: true,
                value,
                lower,
                upper,
                unit: "P(correct on new question)".into(),
            }
        } else {
            missing.push(format!(
                "Only {exam_attempts} exam-style attempts \
                 (need {PERF_MIN_ATTEMPTS} to estimate Performance)."
            ));
            unavailable_score("P(correct on new question)")
        };

        // ---- Readiness give-up rule (thresholds are config-tunable) ----
        let (min_reviews, min_coverage, min_attempts) = self.giveup_thresholds();
        if coverage + f64::EPSILON < min_coverage {
            missing.push(format!(
                "Topology coverage {:.0}% is below the {:.0}% minimum.",
                coverage * 100.0,
                min_coverage * 100.0
            ));
        }
        if graded_reviews < min_reviews {
            missing.push(format!(
                "Only {graded_reviews} graded reviews (need {min_reviews})."
            ));
        }
        let readiness_ready = performance.available
            && exam_attempts >= min_attempts
            && coverage + f64::EPSILON >= min_coverage
            && graded_reviews >= min_reviews;
        let readiness = if readiness_ready {
            // Widen the interval to reflect uncertainty from uncovered material.
            let widen = (1.0 - coverage) * 0.1;
            ScoreWithRange {
                available: true,
                value: performance.value,
                lower: (performance.lower - widen).clamp(0.0, 1.0),
                upper: (performance.upper + widen).clamp(0.0, 1.0),
                unit: "topology-cluster P(correct)".into(),
            }
        } else {
            reasons.push(
                "Readiness withheld until there is enough evidence \
                 (a good system knows when it doesn't know)."
                    .into(),
            );
            unavailable_score("topology-cluster P(correct)")
        };

        let best_next = self.best_next_move(&covered, &per_move);

        Ok(ReadinessResponse {
            memory: Some(memory),
            performance: Some(performance),
            readiness: Some(readiness),
            coverage,
            graded_reviews,
            exam_attempts,
            reasons,
            missing,
            updated_at: TimestampSecs::now().0,
            best_next,
        })
    }

    fn load_perf_data(&self) -> PerfData {
        self.get_config_optional::<PerfData, _>(PERF_KEY)
            .unwrap_or_default()
    }

    /// The study feature under test: interleaving (mix move-types in a session)
    /// vs blocked practice (group by move-type). Default on. Toggling this is the
    /// A/B "ablation" lever.
    fn interleaving_enabled(&self) -> bool {
        self.get_config_optional::<bool, _>("topgreInterleaving")
            .unwrap_or(true)
    }

    /// Give-up thresholds (min graded reviews, min coverage, min attempts),
    /// config-overridable so the honesty line is tunable and A/B-testable.
    fn giveup_thresholds(&self) -> (u32, f64, u32) {
        (
            self.get_config_optional::<u32, _>("topgreMinReviews")
                .unwrap_or(GIVEUP_MIN_REVIEWS),
            self.get_config_optional::<f64, _>("topgreMinCoverage")
                .unwrap_or(GIVEUP_MIN_COVERAGE),
            self.get_config_optional::<u32, _>("topgreMinAttempts")
                .unwrap_or(GIVEUP_MIN_ATTEMPTS),
        )
    }

    /// Held-out evaluation of the Performance model against a simpler baseline.
    /// Attempts are split by time (70% train / 30% test). The move-aware model
    /// predicts per-move-type train accuracy (Beta-smoothed); the baseline
    /// predicts the global train accuracy for everything. Lower log loss wins.
    pub fn performance_eval(
        &self,
        _search: &str,
    ) -> anki_proto::readiness::PerformanceEvalResponse {
        use anki_proto::readiness::PerformanceEvalResponse;

        let mut attempts = self.load_perf_data().attempts;
        attempts.sort_by_key(|a| a.ts);
        let n = attempts.len();
        if n < 20 {
            return PerformanceEvalResponse {
                available: false,
                note: format!("Need >= 20 attempts for held-out eval (have {n})."),
                ..Default::default()
            };
        }

        let split = (n as f64 * 0.7) as usize;
        let (train, test) = attempts.split_at(split);

        let mut per_move: HashMap<String, (u32, u32)> = HashMap::new();
        let mut g_correct = 0u32;
        for a in train {
            let e = per_move.entry(a.mt.clone()).or_insert((0, 0));
            e.1 += 1;
            if a.correct {
                e.0 += 1;
                g_correct += 1;
            }
        }
        let global_p = (g_correct as f64 + 1.0) / (train.len() as f64 + 2.0);
        let clamp = |p: f64| p.clamp(1e-6, 1.0 - 1e-6);

        let (mut model_ll, mut base_ll) = (0.0f64, 0.0f64);
        let (mut model_hits, mut base_hits) = (0u32, 0u32);
        for a in test {
            let p_model = match per_move.get(&a.mt) {
                Some((c, t)) if *t > 0 => (*c as f64 + 1.0) / (*t as f64 + 2.0),
                _ => global_p,
            };
            let y = if a.correct { 1.0 } else { 0.0 };
            model_ll -= y * clamp(p_model).ln() + (1.0 - y) * (1.0 - clamp(p_model)).ln();
            base_ll -= y * clamp(global_p).ln() + (1.0 - y) * (1.0 - clamp(global_p)).ln();
            if (p_model >= 0.5) == a.correct {
                model_hits += 1;
            }
            if (global_p >= 0.5) == a.correct {
                base_hits += 1;
            }
        }
        let tc = test.len() as f64;
        let model_log_loss = model_ll / tc;
        let baseline_log_loss = base_ll / tc;
        PerformanceEvalResponse {
            available: true,
            train_count: train.len() as u32,
            test_count: test.len() as u32,
            model_log_loss,
            baseline_log_loss,
            model_accuracy: model_hits as f64 / tc,
            baseline_accuracy: base_hits as f64 / tc,
            beats_baseline: model_log_loss < baseline_log_loss,
            note: "Time-split held-out eval: move-aware model vs global-average \
                   baseline (log loss, lower is better)."
                .into(),
        }
    }

    /// Record one exam-style question attempt for a move-type. Persisted to
    /// collection config (which syncs). Feeds the Performance/Readiness scores.
    pub fn record_exam_attempt(
        &mut self,
        move_type: &str,
        correct: bool,
        milliseconds: u32,
    ) -> Result<()> {
        let mt = if move_type.trim().is_empty() {
            "unknown".to_string()
        } else {
            move_type.to_ascii_lowercase()
        };
        let mut data = self.load_perf_data();
        let stats = data.moves.entry(mt.clone()).or_default();
        stats.total += 1;
        if correct {
            stats.correct += 1;
        }
        data.attempts.push(Attempt {
            mt,
            correct,
            ms: milliseconds,
            ts: TimestampSecs::now().0,
        });
        // Keep the stored attempt log bounded (aggregates in `moves` are exact).
        let len = data.attempts.len();
        if len > 1000 {
            data.attempts.drain(0..len - 1000);
        }
        self.set_config_json(PERF_KEY, &data, false)?;
        Ok(())
    }

    /// The single best next thing to study: the first uncovered outline topic,
    /// else the weakest covered move-type.
    fn best_next_move(
        &self,
        covered: &HashSet<String>,
        per_move: &HashMap<String, (f64, u32)>,
    ) -> String {
        for topic in TOPOLOGY_OUTLINE {
            if !covered.contains(*topic) {
                return format!("Add cards for '{topic}' (not covered yet)");
            }
        }
        let weakest = per_move
            .iter()
            .map(|(mt, (sum, count))| (mt, sum / *count as f64))
            .min_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
        match weakest {
            Some((mt, _)) => format!("Review '{mt}' (your weakest covered move)"),
            None => "Start reviewing to generate a recommendation".to_string(),
        }
    }

    /// Cram session: rank ALL cards in scope (any status, not just due) by how
    /// "dangerous" they are = exam leverage x memory weakness x (1 + how often
    /// you miss that move-type on exam attempts). Highest danger first.
    pub fn dangerous_cards(
        &mut self,
        search: &str,
        limit: usize,
    ) -> Result<anki_proto::readiness::PointsAtStakeResponse> {
        let query = if search.trim().is_empty() {
            "-is:suspended".to_string()
        } else {
            format!("({search}) -is:suspended")
        };
        let cids = self.search_cards(&query, SortMode::NoOrder)?;
        let timing = self.timing_today()?;

        // Per-move-type miss rate (1 - accuracy) from recorded exam attempts.
        let perf = self.load_perf_data();
        let mut miss: HashMap<String, f64> = HashMap::new();
        for (mt, stats) in &perf.moves {
            if stats.total > 0 {
                miss.insert(mt.clone(), 1.0 - (stats.correct as f64 / stats.total as f64));
            }
        }

        let mut cards: Vec<anki_proto::readiness::PointsAtStakeCard> =
            Vec::with_capacity(cids.len());
        for cid in cids {
            let card = self.storage.get_card(cid)?.or_not_found(cid)?;
            let move_type = self.move_type_for_card(&card)?;
            let profile = default_move_profile(&move_type);
            let weakness = 1.0 - self.card_retrievability(&card, &timing);
            let miss_rate = *miss.get(&move_type).unwrap_or(&0.0);
            let danger = profile.weight * weakness * (1.0 + miss_rate);
            cards.push(anki_proto::readiness::PointsAtStakeCard {
                card_id: cid.0,
                move_type,
                points_at_stake: danger,
                topic_weight: profile.weight,
                weakness,
                // Reuse this field to surface the exam miss-rate multiplier.
                time_efficiency: 1.0 + miss_rate,
            });
        }

        cards.sort_by(|a, b| {
            b.points_at_stake
                .partial_cmp(&a.points_at_stake)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then(a.card_id.cmp(&b.card_id))
        });
        if limit > 0 {
            cards.truncate(limit);
        }
        Ok(anki_proto::readiness::PointsAtStakeResponse { cards })
    }

    /// The move-type a card drills, read from a `move::<type>` tag on its note.
    /// Falls back to "unknown" when no such tag is present.
    fn move_type_for_card(&mut self, card: &Card) -> Result<String> {
        let note = self
            .storage
            .get_note(card.note_id)?
            .or_not_found(card.note_id)?;
        for tag in &note.tags {
            // Tags preserve case in Anki, so match the prefix case-insensitively
            // and normalise the move-type to lowercase (profile keys are lower).
            let lower = tag.to_ascii_lowercase();
            if let Some(rest) = lower.strip_prefix("move::") {
                if !rest.is_empty() {
                    return Ok(rest.to_string());
                }
            }
        }
        Ok("unknown".to_string())
    }

    /// Current FSRS retrievability in [0,1]. Returns 0.0 (fully weak, so maximal
    /// weakness) when the card has no memory state yet (new cards / FSRS off) or
    /// its elapsed time can't be determined. Elapsed time is derived from the
    /// revlog/due inference (never from card edit time), matching the browser.
    fn card_retrievability(&self, card: &Card, timing: &SchedTimingToday) -> f64 {
        match (card.memory_state, card.seconds_since_last_review(timing)) {
            (Some(state), Some(seconds_elapsed)) => {
                let decay = card.decay.unwrap_or(FSRS5_DEFAULT_DECAY);
                FSRS::new(None)
                    .unwrap()
                    .current_retrievability_seconds(state.into(), seconds_elapsed, decay)
                    as f64
            }
            _ => 0.0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn value_and_efficiency_math() {
        assert_eq!(value_at_stake(1.0, 0.5), 0.5);
        // weakness is clamped into [0,1]
        assert_eq!(value_at_stake(1.0, 2.0), 1.0);
        assert_eq!(value_at_stake(0.8, -1.0), 0.0);
        // efficiency is value per minute, with a minutes floor of 0.25
        assert_eq!(time_efficiency(0.5, 2.0), 0.25);
        assert_eq!(time_efficiency(1.0, 0.0), 4.0);
    }

    #[test]
    fn move_profiles_have_expected_defaults() {
        assert_eq!(
            default_move_profile("compactness"),
            MoveProfile { weight: 1.0, minutes: 3.0 }
        );
        assert_eq!(
            default_move_profile("examples"),
            MoveProfile { weight: 0.6, minutes: 1.0 }
        );
        // anything unrecognised gets the conservative default
        assert_eq!(
            default_move_profile("not-a-move"),
            MoveProfile { weight: 0.5, minutes: 2.0 }
        );
    }

    fn add_move_note(col: &mut Collection, move_type: &str) {
        let mut note = col.basic_notetype().new_note();
        *note.fields_mut() = vec!["q".to_string(), "a".to_string()];
        note.tags = vec![format!("move::{move_type}")];
        col.add_note(&mut note, DeckId(1)).unwrap();
    }

    #[test]
    fn queue_orders_new_cards_by_points_at_stake() {
        let mut col = Collection::new();
        // New cards -> weakness 1.0 and no exam attempts -> miss 0, so points at
        // stake = exam weight. Highest exam weight leads (not the quickest type):
        //   compactness 1.0
        //   continuity  0.7
        //   examples    0.6
        add_move_note(&mut col, "compactness");
        add_move_note(&mut col, "examples");
        add_move_note(&mut col, "continuity");

        let resp = col.points_at_stake_queue("", 0).unwrap();
        let order: Vec<&str> = resp.cards.iter().map(|c| c.move_type.as_str()).collect();
        assert_eq!(order, vec!["compactness", "continuity", "examples"]);

        // New cards have no memory state -> maximal weakness.
        assert!(resp.cards.iter().all(|c| (c.weakness - 1.0).abs() < 1e-9));
        // Points at stake is strictly descending.
        for pair in resp.cards.windows(2) {
            assert!(pair[0].points_at_stake >= pair[1].points_at_stake);
        }
        // The limit is respected and keeps the highest-value card.
        let limited = col.points_at_stake_queue("", 2).unwrap();
        assert_eq!(limited.cards.len(), 2);
        assert_eq!(limited.cards[0].move_type, "compactness");
    }

    #[test]
    fn queue_prioritizes_types_you_miss_on_exam() {
        let mut col = Collection::new();
        // You ace examples but keep missing compactness on exam attempts. Even
        // though examples is the "quick" type, compactness should lead triage.
        add_move_note(&mut col, "compactness");
        add_move_note(&mut col, "examples");
        for _ in 0..10 {
            col.record_exam_attempt("examples", true, 1000).unwrap();
            col.record_exam_attempt("compactness", false, 1000).unwrap();
        }

        let resp = col.points_at_stake_queue("", 0).unwrap();
        assert_eq!(resp.cards[0].move_type, "compactness");
    }

    #[test]
    fn strong_memory_lowers_weakness() {
        use crate::card::FsrsMemoryState;

        let mut col = Collection::new();
        add_move_note(&mut col, "compactness");
        let mut card = col.get_first_card();
        // Simulate a well-remembered card reviewed just now: high stability +
        // ~zero elapsed time => retrievability near 1 => weakness near 0.
        card.memory_state = Some(FsrsMemoryState { stability: 100.0, difficulty: 5.0 });
        card.last_review_time = Some(TimestampSecs::now());

        let timing = col.timing_today().unwrap();
        let retrievability = col.card_retrievability(&card, &timing);
        assert!(
            retrievability > 0.8,
            "expected high retrievability for freshly-reviewed strong memory, got {retrievability}"
        );
        // Contrast: a new card (no memory state) is maximally weak.
        let new_card = col.get_first_card();
        assert_eq!(col.card_retrievability(&new_card, &timing), 0.0);
    }

    #[test]
    fn readiness_gives_up_on_empty_collection() {
        let mut col = Collection::new();
        let r = col.readiness("").unwrap();
        assert!(!r.memory.unwrap().available);
        assert!(!r.performance.unwrap().available);
        assert!(!r.readiness.unwrap().available);
        assert_eq!(r.coverage, 0.0);
        assert_eq!(r.exam_attempts, 0);
        // Honesty: it must explain what's missing.
        assert!(!r.missing.is_empty());
    }

    #[test]
    fn readiness_reports_memory_but_abstains_on_readiness() {
        use crate::card::FsrsMemoryState;

        let mut col = Collection::new();
        add_move_note(&mut col, "compactness");
        let mut card = col.get_first_card();
        card.memory_state = Some(FsrsMemoryState { stability: 80.0, difficulty: 5.0 });
        card.last_review_time = Some(TimestampSecs::now());
        card.reps = 5;
        col.storage.update_card(&card).unwrap();

        let r = col.readiness("").unwrap();
        let memory = r.memory.unwrap();
        // Memory is real and honest (value inside its own range).
        assert!(memory.available);
        assert!(memory.value > 0.8);
        assert!(memory.lower <= memory.value && memory.value <= memory.upper);
        // Performance + Readiness abstain: no exam attempts yet.
        assert!(!r.performance.unwrap().available);
        assert!(!r.readiness.unwrap().available);
        // One of nine outline topics covered.
        assert!(r.coverage > 0.0 && r.coverage < 1.0);
        assert!(!r.best_next.is_empty());
        assert!(!r.reasons.is_empty());
    }

    #[test]
    fn wilson_interval_basics() {
        let (p, lo, hi) = wilson(8.0, 10.0);
        assert!((p - 0.8).abs() < 1e-9);
        assert!(lo > 0.0 && lo < p && hi > p && hi <= 1.0);
        // No data -> zeroed.
        assert_eq!(wilson(0.0, 0.0), (0.0, 0.0, 0.0));
    }

    #[test]
    fn performance_lights_up_after_enough_attempts() {
        let mut col = Collection::new();
        add_move_note(&mut col, "compactness");

        // Below the threshold: Performance abstains.
        for _ in 0..5 {
            col.record_exam_attempt("compactness", true, 1000).unwrap();
        }
        let r = col.readiness("").unwrap();
        assert_eq!(r.exam_attempts, 5);
        assert!(!r.performance.unwrap().available);

        // Cross the threshold with a mix of correct/incorrect.
        for i in 0..10 {
            col.record_exam_attempt("connectedness", i % 2 == 0, 1500).unwrap();
        }
        let r = col.readiness("").unwrap();
        assert_eq!(r.exam_attempts, 15);
        let perf = r.performance.unwrap();
        assert!(perf.available);
        // 10 correct of 15 -> ~0.67, inside its own interval.
        assert!((perf.value - 10.0 / 15.0).abs() < 1e-6);
        assert!(perf.lower <= perf.value && perf.value <= perf.upper);
        // Readiness still abstains: coverage + review thresholds not met.
        assert!(!r.readiness.unwrap().available);
    }

    #[test]
    fn interleaving_toggle_changes_queue_grouping() {
        let mut col = Collection::new();
        add_move_note(&mut col, "compactness");
        add_move_note(&mut col, "examples");
        add_move_note(&mut col, "compactness");

        // Interleaved (default): highest points at stake first -> compactness
        // (exam weight 1.0) leads over examples (0.6).
        let inter = col.points_at_stake_queue("", 0).unwrap();
        assert_eq!(inter.cards[0].move_type, "compactness");

        // Blocked (ablation): grouped by move-type alphabetically.
        col.set_config_json("topgreInterleaving", &false, false).unwrap();
        let blocked = col.points_at_stake_queue("", 0).unwrap();
        let order: Vec<&str> = blocked.cards.iter().map(|c| c.move_type.as_str()).collect();
        assert_eq!(order, vec!["compactness", "compactness", "examples"]);
    }

    #[test]
    fn held_out_eval_beats_baseline_when_move_type_carries_signal() {
        let mut col = Collection::new();
        // Strong signal: examples always right, compactness always wrong.
        for i in 0..40 {
            if i % 2 == 0 {
                col.record_exam_attempt("examples", true, 1000).unwrap();
            } else {
                col.record_exam_attempt("compactness", false, 1000).unwrap();
            }
        }
        let eval = col.performance_eval("");
        assert!(eval.available);
        assert!(eval.train_count > 0 && eval.test_count > 0);
        // The move-aware model should beat the global-average baseline.
        assert!(eval.beats_baseline, "model {} vs baseline {}", eval.model_log_loss, eval.baseline_log_loss);
        assert!(eval.model_accuracy >= eval.baseline_accuracy);
    }

    #[test]
    fn held_out_eval_abstains_without_enough_data() {
        let mut col = Collection::new();
        for _ in 0..5 {
            col.record_exam_attempt("examples", true, 1000).unwrap();
        }
        assert!(!col.performance_eval("").available);
    }

    #[test]
    fn cram_ranks_by_danger_with_exam_miss_rate() {
        let mut col = Collection::new();
        // continuity (weight 0.7) vs examples (weight 0.6); both new -> weakness 1.
        // Without misses, continuity outranks examples on weight alone.
        add_move_note(&mut col, "continuity");
        add_move_note(&mut col, "examples");

        let base = col.dangerous_cards("", 0).unwrap();
        assert_eq!(base.cards[0].move_type, "continuity");

        // Now we keep missing examples questions -> its danger multiplier rises,
        // flipping it above continuity (0.6*2.0 = 1.2 > 0.7).
        for _ in 0..4 {
            col.record_exam_attempt("examples", false, 1000).unwrap();
        }
        let after = col.dangerous_cards("", 0).unwrap();
        assert_eq!(after.cards[0].move_type, "examples");
        assert!(after.cards[0].points_at_stake > after.cards[1].points_at_stake);
    }
}
