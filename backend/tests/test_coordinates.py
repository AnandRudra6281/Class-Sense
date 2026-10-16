from app.services.coordinates import compute_coordinates


def test_compute_coordinates_nominal():
    coords = compute_coordinates(
        start_time=120.0,
        lecture_duration=600.0,
        confusion_score=0.45,
        topic_depth=2,
    )
    # x = 120 / 600 * 100 = 20.0
    assert coords.x == 20.0
    # y = 0.45 * 100 = 45.0
    assert coords.y == 45.0
    # z = 2.0
    assert coords.z == 2.0


def test_compute_coordinates_clamping_and_zero_division():
    # Division by zero or negative time
    coords_zero = compute_coordinates(start_time=-10.0, lecture_duration=0.0)
    assert coords_zero.x == 0.0
    assert coords_zero.y == 0.0
    assert coords_zero.z == 0.0

    # Over duration clamping
    coords_overflow = compute_coordinates(
        start_time=700.0,
        lecture_duration=600.0,
        confusion_score=1.5,
        topic_depth=15,
    )
    assert coords_overflow.x == 100.0
    assert coords_overflow.y == 100.0
    assert coords_overflow.z == 10.0
