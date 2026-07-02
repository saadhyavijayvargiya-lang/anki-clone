// Copyright: Ankitects Pty Ltd and contributors
// Copyright: TopGRE contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

use crate::collection::Collection;
use crate::error::Result;

impl crate::services::ReadinessService for Collection {
    fn points_at_stake_queue(
        &mut self,
        input: anki_proto::readiness::PointsAtStakeRequest,
    ) -> Result<anki_proto::readiness::PointsAtStakeResponse> {
        self.points_at_stake_queue(&input.search, input.limit as usize)
    }

    fn get_readiness(
        &mut self,
        input: anki_proto::readiness::GetReadinessRequest,
    ) -> Result<anki_proto::readiness::ReadinessResponse> {
        self.readiness(&input.search)
    }

    fn record_exam_attempt(
        &mut self,
        input: anki_proto::readiness::RecordExamAttemptRequest,
    ) -> Result<()> {
        self.record_exam_attempt(&input.move_type, input.correct, input.milliseconds)
    }

    fn evaluate_performance_model(
        &mut self,
        input: anki_proto::readiness::GetReadinessRequest,
    ) -> Result<anki_proto::readiness::PerformanceEvalResponse> {
        Ok(self.performance_eval(&input.search))
    }

    fn most_dangerous_cards(
        &mut self,
        input: anki_proto::readiness::PointsAtStakeRequest,
    ) -> Result<anki_proto::readiness::PointsAtStakeResponse> {
        self.dangerous_cards(&input.search, input.limit as usize)
    }
}
