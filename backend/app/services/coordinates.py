from app.schemas.common import Coordinates3D


def compute_coordinates(
    start_time: float,
    lecture_duration: float,
    confusion_score: float = 0.0,
    topic_depth: int = 0,
) -> Coordinates3D:
    """Compute deterministic 3D coordinates for spatial pedagogical visualization.

    Formulas:
    x (Time Position): Normalized timeline position [0.0, 100.0]
        x = (start_time / lecture_duration) * 100.0 (clamped between 0.0 and 100.0)
    y (Confusion Score): Confusion intensity [0.0, 100.0]
        y = confusion_score * 100.0 (clamped between 0.0 and 100.0)
    z (Topic Depth): Hierarchy or prerequisite depth level [0.0, 10.0]
        z = topic_depth * 1.0 (clamped between 0.0 and 10.0)
    """
    # 1. Compute x (time position)
    if lecture_duration <= 0.0 or start_time < 0.0:
        x_val = 0.0
    else:
        x_val = (start_time / lecture_duration) * 100.0
    x_clamped = max(0.0, min(100.0, round(float(x_val), 2)))

    # 2. Compute y (confusion intensity): y = confusion_score [0.0 - 1.0] * 100.0
    score_clamped = max(0.0, min(1.0, float(confusion_score)))
    y_clamped = round(score_clamped * 100.0, 2)

    # 3. Compute z (topic depth)
    z_val = float(max(0, topic_depth))
    z_clamped = max(0.0, min(10.0, round(z_val, 2)))

    return Coordinates3D(x=x_clamped, y=y_clamped, z=z_clamped)
