from datetime import datetime, timezone
import pytest
from app.models.job import JobStatus
from app.schemas.common import Coordinates3D
from app.schemas.domain import (
    LectureSchema,
    JobSchema,
    WordTimestamp,
    TranscriptSegmentSchema,
    TopicSchema,
    ConfusionEventSchema,
    EvidenceSchema,
    MisconceptionSchema,
    PrerequisiteNodeSchema,
    InterventionSchema,
    StudentCatchUpSchema,
    QuizQuestionSchema,
    PracticeHintSchema,
    ReportSchema,
)


def test_all_12_domain_schemas_carry_coordinates():
    now = datetime.now(timezone.utc)
    c = Coordinates3D(x=10.0, y=50.0, z=2.0)

    # 1. Lecture
    lec = LectureSchema(
        id="lec-1", title="AI Lecture", source_type="upload", duration_seconds=120.0,
        status="done", coordinates=c, created_at=now, updated_at=now
    )
    assert lec.coordinates.x == 10.0

    # 2. Job
    job = JobSchema(
        id="job-1", job_type="transcription", status=JobStatus.DONE, progress_pct=100,
        coordinates=c, created_at=now, updated_at=now
    )
    assert job.coordinates.y == 50.0

    # 3. TranscriptSegment
    seg = TranscriptSegmentSchema(
        id="seg-1", lecture_id="lec-1", start_time=0.0, end_time=10.0, text="Hello world",
        words=[WordTimestamp(word="Hello", start=0.0, end=0.5)], coordinates=c
    )
    assert seg.coordinates.z == 2.0

    # 4. Topic
    top = TopicSchema(
        id="top-1", lecture_id="lec-1", title="Intro", summary="Summary",
        start_time=0.0, end_time=60.0, depth=0, coordinates=c
    )
    assert top.title == "Intro"

    # 5. ConfusionEvent
    conf = ConfusionEventSchema(
        id="cnf-1", lecture_id="lec-1", timestamp_start=15.0, timestamp_end=25.0,
        confusion_score=0.75, misconception_text="Misconception", evidence_text="Evidence text",
        signals={"wpm": 120.0}, coordinates=c
    )
    assert conf.confusion_score == 0.75

    # 6. Evidence
    ev = EvidenceSchema(
        id="ev-1", confusion_id="cnf-1", quote="evidence quote", signal_type="acoustic_wpm",
        confidence=0.9, coordinates=c
    )
    assert ev.signal_type == "acoustic_wpm"

    # 7. Misconception
    misc = MisconceptionSchema(
        id="misc-1", confusion_id="cnf-1", name="Slope Confusion", explanation="Expl",
        apparent_reason="Reason", severity="high", cognitive_load_score=0.8, coordinates=c
    )
    assert misc.severity == "high"

    # 8. PrerequisiteNode
    prereq = PrerequisiteNodeSchema(
        id="pr-1", confusion_id="cnf-1", concept_name="Linear Algebra", gap_description="Gap",
        remediation_hint="Hint", depth=1, vector_distance=0.15, coordinates=c
    )
    assert prereq.concept_name == "Linear Algebra"

    # 9. Intervention
    intv = InterventionSchema(
        id="intv-1", lecture_id="lec-1", target_type="teacher", title="Action Plan",
        content={"action": "recap"}, coordinates=c
    )
    assert intv.target_type == "teacher"

    # 10. StudentCatchUp
    catch = StudentCatchUpSchema(
        id="sc-1", lecture_id="lec-1", title="Catchup Guide", summary="Summary",
        concrete_analogy="Analogy", key_takeaways=["Takeaway 1"], coordinates=c
    )
    assert len(catch.key_takeaways) == 1

    # 11. QuizQuestion
    quiz = QuizQuestionSchema(
        id="qz-1", catchup_id="sc-1", question="What is gradient?", options=["A", "B"],
        correct_option_index=0, hints=[PracticeHintSchema(step=1, hint="Think of slope")],
        explanation="Slope of function", coordinates=c
    )
    assert quiz.correct_option_index == 0

    # 12. Report
    rep = ReportSchema(
        id="rep-1", lecture_id="lec-1", title="Audit Report", executive_summary="Exec Summary",
        confusion_density=0.3, key_recommendations=["Slow down pacing"], metrics={},
        export_format="json", coordinates=c
    )
    assert rep.confusion_density == 0.3
