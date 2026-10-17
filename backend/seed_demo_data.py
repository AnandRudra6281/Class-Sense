"""ClassSense Database Demo Seeder.

Pre-populates `classsense.db` with two complete, rich lecture analyses:
1. Calculus: Multivariable Derivatives & Gradient Fields (lecture_sample.wav)
2. Neural Networks: Perceptron Learning in ANN & Linear Separability

Ensures all 12 entities are populated with realistic pedagogical data
ready for an interactive demonstration.
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import delete, select
from app.db.session import async_session_factory
from app.models.lecture import Lecture
from app.models.transcript import TranscriptSegment
from app.models.topic import Topic
from app.models.confusion import ConfusionEvent
from app.models.evidence import Evidence
from app.models.misconception import Misconception
from app.models.prerequisite import PrerequisiteNode
from app.models.intervention import Intervention
from app.models.catchup import StudentCatchUp
from app.models.quiz import QuizQuestion
from app.models.report import Report
from app.models.job import Job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("classsense.seed")


async def seed_demo_lectures():
    async with async_session_factory() as db:
        now = datetime.now(timezone.utc)

        # =========================================================================
        # 1. Calculus Lecture Demo (lec-calculus-demo-001)
        # =========================================================================
        calc_id = "lec-calculus-demo-001"
        logger.info(f"Seeding Calculus demo lecture ({calc_id})...")

        # Clean existing records for idempotency across all child tables
        await db.execute(delete(Job).where(Job.id.in_(["job-calc-demo-001", "job-perc-demo-002"])))
        conf_ids = select(ConfusionEvent.id).where(ConfusionEvent.lecture_id == calc_id)
        catchup_ids = select(StudentCatchUp.id).where(StudentCatchUp.lecture_id == calc_id)
        await db.execute(delete(QuizQuestion).where(QuizQuestion.catchup_id.in_(catchup_ids)))
        await db.execute(delete(StudentCatchUp).where(StudentCatchUp.lecture_id == calc_id))
        await db.execute(delete(Report).where(Report.lecture_id == calc_id))
        await db.execute(delete(Intervention).where(Intervention.lecture_id == calc_id))
        await db.execute(delete(Evidence).where(Evidence.confusion_id.in_(conf_ids)))
        await db.execute(delete(Misconception).where(Misconception.confusion_id.in_(conf_ids)))
        await db.execute(delete(PrerequisiteNode).where(PrerequisiteNode.confusion_id.in_(conf_ids)))
        await db.execute(delete(ConfusionEvent).where(ConfusionEvent.lecture_id == calc_id))
        await db.execute(delete(Topic).where(Topic.lecture_id == calc_id))
        await db.execute(delete(TranscriptSegment).where(TranscriptSegment.lecture_id == calc_id))
        await db.execute(delete(Lecture).where(Lecture.id == calc_id))
        await db.commit()

        calc_lec = Lecture(
            id=calc_id,
            title="Calculus: Multivariable Derivatives & Gradient Fields",
            source_type="upload",
            source_url=None,
            media_path="uploads/raw/lecture_sample.wav",
            audio_path="uploads/audio/lecture_sample_16k_mono.wav",
            duration_seconds=180.0,
            status="analyzed",
            coordinates={"x": 50.0, "y": 72.0, "z": 1.0},
            created_at=now,
            updated_at=now,
        )
        db.add(calc_lec)
        await db.flush()

        # Transcript segments
        calc_segments = [
            TranscriptSegment(
                id="calc-seg-001",
                lecture_id=calc_id,
                start_time=0.0,
                end_time=45.0,
                text="Welcome everyone. Today we are exploring the gradient vector in multivariable calculus. "
                     "When we compute partial derivatives with respect to x and y, we bundle them into a single vector.",
                speaker="Instructor",
                words=[
                    {"word": "Welcome", "start": 0.0, "end": 0.8},
                    {"word": "everyone.", "start": 0.8, "end": 1.5},
                    {"word": "Today", "start": 2.0, "end": 2.5},
                    {"word": "we", "start": 2.5, "end": 2.8},
                    {"word": "explore", "start": 2.8, "end": 3.4},
                    {"word": "the", "start": 3.4, "end": 3.6},
                    {"word": "gradient", "start": 3.6, "end": 4.2},
                    {"word": "vector.", "start": 4.2, "end": 5.0},
                ],
                coordinates={"x": 10.0, "y": 15.0, "z": 0.0},
            ),
            TranscriptSegment(
                id="calc-seg-002",
                lecture_id=calc_id,
                start_time=45.0,
                end_time=95.0,
                text="Now wait... notice how the gradient points perpendicular to the contour lines? "
                     "A common question is: why does it point in the direction of steepest ascent rather than along the slope?",
                speaker="Instructor",
                words=[
                    {"word": "Now", "start": 45.0, "end": 45.4},
                    {"word": "wait...", "start": 45.4, "end": 47.0},
                    {"word": "notice", "start": 47.5, "end": 48.0},
                    {"word": "how", "start": 48.0, "end": 48.2},
                    {"word": "the", "start": 48.2, "end": 48.4},
                    {"word": "gradient", "start": 48.4, "end": 49.0},
                    {"word": "points", "start": 49.0, "end": 49.5},
                    {"word": "perpendicular", "start": 49.5, "end": 50.4},
                    {"word": "to", "start": 50.4, "end": 50.6},
                    {"word": "the", "start": 50.6, "end": 50.8},
                    {"word": "contour", "start": 50.8, "end": 51.4},
                    {"word": "lines?", "start": 51.4, "end": 52.0},
                ],
                coordinates={"x": 35.0, "y": 80.0, "z": 1.0},
            ),
            TranscriptSegment(
                id="calc-seg-003",
                lecture_id=calc_id,
                start_time=95.0,
                end_time=180.0,
                text="By taking the dot product of the gradient with any unit direction vector u, "
                     "we obtain the directional derivative. The maximum value occurs precisely when u points parallel to the gradient.",
                speaker="Instructor",
                words=[
                    {"word": "By", "start": 95.0, "end": 95.3},
                    {"word": "taking", "start": 95.3, "end": 95.8},
                    {"word": "the", "start": 95.8, "end": 96.0},
                    {"word": "dot", "start": 96.0, "end": 96.3},
                    {"word": "product", "start": 96.3, "end": 96.9},
                ],
                coordinates={"x": 80.0, "y": 45.0, "z": 0.0},
            ),
        ]
        db.add_all(calc_segments)

        # Topics
        top_1 = Topic(
            id="calc-top-001",
            lecture_id=calc_id,
            title="Introduction to Partial Derivatives & Vector Bundling",
            summary="Reviewing scalar fields f(x,y) and constructing vector [df/dx, df/dy].",
            start_time=0.0,
            end_time=45.0,
            depth=0,
            coordinates={"x": 10.0, "y": 15.0, "z": 0.0},
        )
        top_2 = Topic(
            id="calc-top-002",
            lecture_id=calc_id,
            title="The Gradient Vector & Steepest Ascent Direction",
            summary="Geometric orientation of the gradient vector relative to level curves f(x,y)=c.",
            start_time=45.0,
            end_time=95.0,
            depth=0,
            coordinates={"x": 50.0, "y": 80.0, "z": 1.0},
        )
        top_3 = Topic(
            id="calc-top-003",
            lecture_id=calc_id,
            title="Directional Derivatives via Dot Product",
            summary="Using unit vectors to evaluate directional rates of change and Cauchy-Schwarz bounds.",
            start_time=95.0,
            end_time=180.0,
            depth=0,
            coordinates={"x": 85.0, "y": 45.0, "z": 0.0},
        )
        db.add_all([top_1, top_2, top_3])
        await db.flush()

        # Confusion Event & Evidence
        conf_calc = ConfusionEvent(
            id="conf-calc-001",
            lecture_id=calc_id,
            segment_id="calc-seg-002",
            timestamp_start=46.0,
            timestamp_end=78.0,
            confusion_score=0.76,
            misconception_text="Cognitive stall on why gradient vector is orthogonal to level sets rather than tangent.",
            evidence_text="Now wait... notice how the gradient points perpendicular to the contour lines? A common question is: why does it point in the direction of steepest ascent?",
            signals={
                "wpm_anomaly_z": 2.1,
                "pause_density": 0.38,
                "disfluency_ratio": 0.12,
                "question_density": 0.65,
                "student_response_gap": 0.40,
                "fused_score": 0.76,
                "ai_confidence": 0.88,
                "primary_signal": "pause_density",
                "baseline_status": "sufficient",
            },
            coordinates={"x": 48.0, "y": 76.0, "z": 1.0},
        )
        db.add(conf_calc)
        await db.flush()

        evi_calc = Evidence(
            id="evi-calc-001",
            confusion_id="conf-calc-001",
            quote="Now wait... notice how the gradient points perpendicular to the contour lines?",
            signal_type="pause_density",
            confidence=0.88,
            timestamp_start=46.0,
            timestamp_end=60.0,
            coordinates={"x": 48.0, "y": 76.0, "z": 1.0},
        )
        db.add(evi_calc)

        # Potential Misconceptions
        misc_calc_1 = Misconception(
            id="misc-calc-001",
            confusion_id="conf-calc-001",
            name="Confusing Directional Derivative with Gradient Magnitude",
            explanation="Students assume the gradient is a scalar value representing slope rather than a vector with directional coordinates.",
            apparent_reason="Over-reliance on single-variable derivative f'(x) intuition without multivariable vector spaces.",
            severity="critical",
            cognitive_load_score=0.89,
            coordinates={"x": 48.0, "y": 89.0, "z": 1.0},
        )
        misc_calc_2 = Misconception(
            id="misc-calc-002",
            confusion_id="conf-calc-001",
            name="Assuming Level Curves Align Tangent to Gradient",
            explanation="Students visualize the gradient pointing along the contour curve rather than orthogonal to it.",
            apparent_reason="Confusion between tangent velocity vectors to curves and normal gradient vectors to level surfaces.",
            severity="high",
            cognitive_load_score=0.74,
            coordinates={"x": 48.0, "y": 74.0, "z": 1.0},
        )
        db.add_all([misc_calc_1, misc_calc_2])

        # Prerequisite Nodes
        prereq_calc_1 = PrerequisiteNode(
            id="prereq-calc-001",
            confusion_id="conf-calc-001",
            concept_name="Partial Derivatives & Tangent Planes",
            gap_description="Gaps in conceptualizing instantaneous rates of change while holding other spatial variables constant.",
            remediation_hint="Review slicing 3D surfaces with planes y=c to visualize 1D cross-sectional curves.",
            depth=1,
            vector_distance=0.182,
            coordinates={"x": 48.0, "y": 55.0, "z": 0.5},
        )
        prereq_calc_2 = PrerequisiteNode(
            id="prereq-calc-002",
            confusion_id="conf-calc-001",
            concept_name="Single-Variable Chain Rule & Slope",
            gap_description="Uncertainty in how rate of change decomposes along composite path parameterizations.",
            remediation_hint="Practice chain rule derivatives d/dt[f(x(t), y(t))] before vector dot-product formulations.",
            depth=2,
            vector_distance=0.245,
            coordinates={"x": 48.0, "y": 40.0, "z": 0.5},
        )
        prereq_calc_3 = PrerequisiteNode(
            id="prereq-calc-003",
            confusion_id="conf-calc-001",
            concept_name="Vector Dot Product & Cauchy-Schwarz Inequality",
            gap_description="Missing geometric intuition that u · v = |u||v|cos(theta) is maximized when theta=0 (parallel alignment).",
            remediation_hint="Prove why cos(theta) <= 1 implies the directional derivative is maximized along the unit gradient.",
            depth=3,
            vector_distance=0.312,
            coordinates={"x": 48.0, "y": 25.0, "z": 0.5},
        )
        db.add_all([prereq_calc_1, prereq_calc_2, prereq_calc_3])

        # Teacher Intervention Package
        interv_calc = Intervention(
            id="interv-calc-001",
            lecture_id=calc_id,
            target_type="teacher",
            title="Instructional Intervention: Anchoring Gradient Orthogonality & Steepest Ascent",
            content={
                "actionable_recap": [
                    "Open class by drawing a topographical hill map: walking along a level path costs zero altitude (rate of change = 0).",
                    "Emphasize that the steepest climb is directly perpendicular to that level path, exactly where altitude rises fastest.",
                    "Explicitly contrast: tangent vector = direction of constant height (0 slope); gradient vector = direction of maximum ascent.",
                ],
                "diagnostic_questions": [
                    {
                        "question": "If you stand on a mountain surface f(x,y)=c and walk tangent to the contour curve, what is the directional derivative in that direction?",
                        "options": ["Maximum possible value |grad f|", "Zero", "Negative gradient", "Undefined"],
                        "correct_option_index": 1,
                        "rationale": "Along a level curve f(x,y) is constant, meaning df/ds = 0. The gradient is orthogonal to this direction.",
                    }
                ],
                "recommended_pacing": "Maintain 135 WPM. Pause 3-5 seconds after sketching contour curves before drawing the perpendicular gradient arrow.",
                "blackboard_analogy": "The Foggy Mountain Hiker: If you can only see 1 foot ahead on a foggy mountain, pointing perpendicular to the contour line ensures you reach the peak fastest.",
            },
            coordinates={"x": 50.0, "y": 75.0, "z": 1.0},
        )
        db.add(interv_calc)

        # Student Catch-Up Module & Quiz
        catchup_calc = StudentCatchUp(
            id="catchup-calc-001",
            lecture_id=calc_id,
            topic_id="calc-top-002",
            title="Demystifying the Gradient Vector: The Foggy Mountain Guide",
            summary="Understanding why the gradient vector points in the direction of steepest ascent and why it is always perpendicular to level curves.",
            concrete_analogy="Imagine standing on a hillside in dense fog. If you walk along the contour curve, your altitude never changes. To climb as steeply as possible, you must step directly at right angles to that contour curve.",
            key_takeaways=[
                "The gradient grad(f) is a vector containing all partial derivatives: [df/dx, df/dy].",
                "Its direction gives the path of steepest ascent on the surface.",
                "Its magnitude |grad(f)| is the exact maximum rate of increase.",
                "The gradient is always orthogonal (perpendicular) to the level curves f(x,y) = constant.",
            ],
            coordinates={"x": 50.0, "y": 70.0, "z": 1.0},
        )
        db.add(catchup_calc)
        await db.flush()

        quiz_calc = QuizQuestion(
            id="quiz-calc-001",
            catchup_id="catchup-calc-001",
            question="Suppose the gradient of a temperature field T(x,y) at point P is grad T = [3, 4]. What is the maximum rate of temperature increase at P?",
            options=["3 degrees/meter", "4 degrees/meter", "5 degrees/meter", "7 degrees/meter"],
            correct_option_index=2,
            hints=[
                {"step": 1, "hint": "Recall that the maximum rate of change equals the magnitude (length) of the gradient vector."},
                {"step": 2, "hint": "Compute the Euclidean norm |grad T| = sqrt(dx^2 + dy^2)."},
                {"step": 3, "hint": "Calculate sqrt(3^2 + 4^2) = sqrt(9 + 16) = sqrt(25)."},
            ],
            explanation="The maximum rate of increase in any direction is given by the length of the gradient: |grad T| = sqrt(3^2 + 4^2) = 5 degrees/meter.",
            coordinates={"x": 50.0, "y": 70.0, "z": 1.0},
        )
        db.add(quiz_calc)

        # Audit Report
        report_calc = Report(
            id="rep-calc-001",
            lecture_id=calc_id,
            title="Pedagogical Quality Audit: Multivariable Calculus Delivery",
            executive_summary=(
                "The lecture demonstrated structured mathematical rigor with strong concept segmentation. "
                "A significant cognitive bottleneck emerged at minute 0:46 regarding gradient orthogonality to level curves. "
                "Deterministic acoustic pacing analysis shows normal-band delivery (134 WPM) with well-timed pause brackets. "
                "Integrating the recommended blackboard mountain analogy and in-class checkpoint question will cement student retention."
            ),
            confusion_density=0.18,
            key_recommendations=[
                "Use the Foggy Mountain Hiker analogy before deriving the directional derivative formula.",
                "Insert an active-learning checkpoint question immediately after showing level curves.",
                "Reinforce vector vs scalar distinctions explicitly during partial derivative bundling.",
            ],
            metrics={
                "total_misconceptions": 2,
                "critical_misconceptions": 1,
                "confusion_spikes": 1,
                "avg_confusion_score": 0.76,
                "avg_wpm": 134.0,
                "wpm_band": "normal",
                "hesitation_pause_count": 3,
                "traced_prerequisites": 3,
            },
            export_format="markdown",
            coordinates={"x": 50.0, "y": 75.0, "z": 1.0},
        )
        db.add(report_calc)

        # Job record
        job_calc = Job(
            id="job-calc-demo-001",
            job_type="one_click_pipeline",
            status="done",
            progress_pct=100,
            error_message=None,
            payload={"lecture_id": calc_id},
            result={"status": "completed", "total_stages": 8, "stages_completed": 8},
            coordinates={"x": 100.0, "y": 100.0, "z": 1.0},
        )
        db.add(job_calc)

        # =========================================================================
        # 2. Enrich Perceptron ANN Lecture (f7ba5cb1-c4db-4290-8200-ef54a9976742)
        # =========================================================================
        perc_id = "f7ba5cb1-c4db-4290-8200-ef54a9976742"
        logger.info(f"Enriching Perceptron ANN lecture ({perc_id})...")

        # Verify lecture exists
        res_p = await db.execute(select(Lecture).where(Lecture.id == perc_id))
        perc_lec = res_p.scalar_one_or_none()
        if perc_lec:
            perc_lec.title = "Neural Networks: Perceptron Learning in ANN & Linear Separability"
            perc_lec.status = "analyzed"

            # Check if misconceptions already exist
            res_m = await db.execute(
                select(Misconception).where(
                    Misconception.confusion_id.in_(
                        select(ConfusionEvent.id).where(ConfusionEvent.lecture_id == perc_id)
                    )
                )
            )
            existing_m = res_m.scalars().all()
            if not existing_m:
                # Find the first 2 confusion events
                res_c = await db.execute(
                    select(ConfusionEvent)
                    .where(ConfusionEvent.lecture_id == perc_id)
                    .order_by(ConfusionEvent.timestamp_start.asc())
                    .limit(2)
                )
                conf_list = res_c.scalars().all()

                if conf_list:
                    c1 = conf_list[0]
                    c2 = conf_list[1] if len(conf_list) > 1 else conf_list[0]

                    m1 = Misconception(
                        id="misc-perc-001",
                        confusion_id=c1.id,
                        name="Assuming Single-Layer Perceptron Can Solve Non-Linear XOR Problems",
                        explanation="Students incorrectly believe tuning the learning rate on a single-layer perceptron enables it to solve XOR classification.",
                        apparent_reason="Missing foundational understanding of hyperplane decision boundaries and geometric linear separability.",
                        severity="critical",
                        cognitive_load_score=0.91,
                        coordinates={"x": 30.0, "y": 91.0, "z": 1.0},
                    )
                    m2 = Misconception(
                        id="misc-perc-002",
                        confusion_id=c2.id,
                        name="Confusing Step Activation with Continuous Sigmoid Differentiability",
                        explanation="Students assume standard backpropagation gradients can be computed directly across hard Heaviside step functions.",
                        apparent_reason="Conflating early Rosenblatt perceptron step thresholding with modern gradient descent activation functions.",
                        severity="high",
                        cognitive_load_score=0.78,
                        coordinates={"x": 55.0, "y": 78.0, "z": 1.0},
                    )
                    db.add_all([m1, m2])

                    # Add prerequisites
                    p1 = PrerequisiteNode(
                        id="prereq-perc-001",
                        confusion_id=c1.id,
                        concept_name="Hyperplane Decision Boundaries & Linear Separability",
                        gap_description="Gaps in visualizing w1*x1 + w2*x2 + b = 0 as a dividing line in 2D or hyperplane in N dimensions.",
                        remediation_hint="Plot truth tables of AND, OR, and XOR on a 2D Cartesian grid to visualize linear separability geometrically.",
                        depth=1,
                        vector_distance=0.165,
                        coordinates={"x": 30.0, "y": 60.0, "z": 0.5},
                    )
                    p2 = PrerequisiteNode(
                        id="prereq-perc-002",
                        confusion_id=c1.id,
                        concept_name="Vector Dot Products & Weighted Sums",
                        gap_description="Difficulty decomposing sigma(w_i * x_i) as an inner product projecting input features onto weight vectors.",
                        remediation_hint="Review vector dot product geometric projection before deriving perceptron weight update equations.",
                        depth=2,
                        vector_distance=0.230,
                        coordinates={"x": 30.0, "y": 45.0, "z": 0.5},
                    )
                    db.add_all([p1, p2])

        await db.commit()
        logger.info("Demo database seeded successfully with rich Calculus and Perceptron datasets!")


if __name__ == "__main__":
    asyncio.run(seed_demo_lectures())
