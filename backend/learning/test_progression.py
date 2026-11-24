import os
import json
import math

from unittest.mock import patch

import django

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

django.setup()

from learning.models import (
    Enrollment,
    LearningDay,
    DayProgress,
    Assessment,
    AssessmentAttempt,
    Question,
    UserAnswer,
    TopicMastery,
    AIGenerationJob,
)

from learning.services.progression_service import (
    ProgressionError,
    calculate_updated_mastery,
    get_recommended_difficulty,
    finalize_learning_day,
    finalize_day_from_best_attempt,
    get_day_finalization_eligibility,
    get_progression_summary,
)

from learning.services.progress_service import (
    get_daily_progress_summary,
    get_enrollment_progress_summary,
)


# ==========================================
# Helper: Print Section
# ==========================================

def print_section(title):

    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


# ==========================================
# Helper: Print JSON
# ==========================================

def print_json(data):

    print(
        json.dumps(
            data,
            indent=4,
            ensure_ascii=False,
            default=str,
        )
    )


# ==========================================
# Helper: Verify Rejected Operation
# ==========================================

def expect_rejection(
    label,
    function,
    *args,
    **kwargs,
):

    try:

        function(*args, **kwargs)

    except ProgressionError as error:

        print(f"{label}: PASSED")
        print(f"Reason: {error}")

        return

    raise AssertionError(
        f"{label}: Operation should "
        "have been rejected."
    )


# ==========================================
# Helper: Capture Progression State
# ==========================================

def capture_progression_state(enrollment):

    return {
        "enrollment": (
            Enrollment.objects.filter(
                pk=enrollment.pk
            ).values().get()
        ),

        "day_progress": list(
            DayProgress.objects.filter(
                learning_day__enrollment=enrollment
            ).order_by("pk").values()
        ),

        "topic_mastery": list(
            TopicMastery.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),
    }


# ==========================================
# Helper: Capture Protected Records
# ==========================================

def capture_protected_records(enrollment):

    return {
        "learning_days": list(
            LearningDay.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),

        "assessments": list(
            Assessment.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),

        "questions": list(
            Question.objects.filter(
                assessment__enrollment=enrollment
            ).order_by("pk").values()
        ),

        "assessment_attempts": list(
            AssessmentAttempt.objects.filter(
                assessment__enrollment=enrollment
            ).order_by("pk").values()
        ),

        "user_answers": list(
            UserAnswer.objects.filter(
                attempt__assessment__enrollment=enrollment
            ).order_by("pk").values()
        ),

        "ai_generation_jobs": list(
            AIGenerationJob.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),
    }


# ==========================================
# Main Test
# ==========================================

def main():

    print_section(
        "CODEMIND AI - LEARNING PROGRESSION TEST"
    )

    # ==========================================
    # 1. Retrieve Existing Enrollment
    # ==========================================

    enrollment = Enrollment.objects.get(
        pk=1,
        language="python",
    )

    print(
        f"Language: "
        f"{enrollment.get_language_display()}"
    )

    print(f"Skill Level: {enrollment.skill_level}")
    print(f"Enrollment Status: {enrollment.status}")
    print(f"Current Day: {enrollment.current_day}")

    assert enrollment.status == "active"

    # ==========================================
    # 2. Retrieve Learning Days
    # ==========================================

    day1 = LearningDay.objects.get(
        enrollment=enrollment,
        day_number=1,
    )

    day2 = LearningDay.objects.get(
        enrollment=enrollment,
        day_number=2,
    )

    progress1 = DayProgress.objects.get(
        learning_day=day1
    )

    progress2 = DayProgress.objects.get(
        learning_day=day2
    )

    print(f"\nDay 1: {day1.title}")
    print(f"Day 1 Status: {progress1.status}")

    print(f"\nDay 2: {day2.title}")
    print(f"Day 2 Status: {progress2.status}")

    if progress1.status == "completed":

        raise RuntimeError(
            "Day 1 is already finalized. "
            "This integration test requires "
            "the original pre-finalization state."
        )

    assert enrollment.current_day == 1

    assert progress1.status == "in_progress"
    assert progress1.lesson_completed
    assert progress1.practical_completed
    assert not progress1.assessment_completed

    assert progress2.status == "locked"

    print("\nInitial Learning State: PASSED")

    # ==========================================
    # 3. Retrieve Evaluated Assessment
    # ==========================================

    print_section(
        "PASSED ASSESSMENT VERIFICATION"
    )

    attempt = AssessmentAttempt.objects.get(
        pk=2,
        assessment__enrollment=enrollment,
        assessment__assessment_type="daily",
        assessment__day_number=1,
    )

    print(f"Attempt ID: {attempt.id}")
    print(f"Status: {attempt.status}")
    print(f"Score: {attempt.percentage}%")
    print(f"Passed: {attempt.passed}")

    assert attempt.status == "evaluated"
    assert attempt.passed
    assert attempt.percentage >= 80

    print("\nPassed Assessment Verification: PASSED")

    # ==========================================
    # 4. Capture Original Records
    # ==========================================

    original_state = capture_progression_state(
        enrollment
    )

    protected_records = capture_protected_records(
        enrollment
    )

    mastery = TopicMastery.objects.get(
        enrollment=enrollment,
        topic__iexact=day1.topic,
    )

    previous_mastery = mastery.mastery_score

    initial_score = mastery.initial_score

    previous_questions = mastery.total_questions

    previous_correct = mastery.correct_answers

    other_mastery_records = list(
        TopicMastery.objects.filter(
            enrollment=enrollment
        ).exclude(
            pk=mastery.pk
        ).order_by("pk").values()
    )

    print_section(
        "ORIGINAL TOPIC MASTERY"
    )

    print(f"Topic: {mastery.topic}")
    print(f"Initial Score: {initial_score}%")
    print(f"Previous Mastery: {previous_mastery}%")

    print(
        f"Previous Questions: "
        f"{previous_questions}"
    )

    print(
        f"Previous Correct Answers: "
        f"{previous_correct}"
    )

    # ==========================================
    # 5. Mastery Calculation Test
    # ==========================================

    print_section(
        "WEIGHTED MASTERY CALCULATION TEST"
    )

    expected_mastery = calculate_updated_mastery(
        previous_mastery,
        attempt.percentage,
    )

    expected_difficulty = (
        get_recommended_difficulty(
            expected_mastery
        )
    )

    print(f"Previous Mastery: {previous_mastery}%")

    print(
        f"Latest Assessment: "
        f"{attempt.percentage}%"
    )

    print(f"Expected Mastery: {expected_mastery}%")

    print(
        f"Expected Difficulty: "
        f"{expected_difficulty}"
    )

    assert calculate_updated_mastery(
        25, 100
    ) == 70.0

    assert calculate_updated_mastery(
        0, 100
    ) == 60.0

    assert calculate_updated_mastery(
        100, 100
    ) == 100.0

    assert calculate_updated_mastery(
        100, 0
    ) == 40.0

    assert get_recommended_difficulty(49) == "basic"

    assert (
        get_recommended_difficulty(50)
        == "intermediate"
    )

    assert (
        get_recommended_difficulty(80)
        == "advanced"
    )

    expect_rejection(
        "Reject Negative Mastery",
        calculate_updated_mastery,
        -10,
        100,
    )

    expect_rejection(
        "Reject Invalid Assessment Score",
        calculate_updated_mastery,
        25,
        110,
    )

    expect_rejection(
        "Reject Non-Finite Mastery",
        calculate_updated_mastery,
        float("nan"),
        100,
    )

    print("\nMastery Calculation Test: PASSED")

    # ==========================================
    # 6. Finalization Eligibility
    # ==========================================

    print_section(
        "DAY FINALIZATION ELIGIBILITY"
    )

    eligibility = get_day_finalization_eligibility(
        day1
    )

    print_json(eligibility)

    assert eligibility["eligible"]

    assert (
        eligibility["passed_attempt_id"]
        == attempt.id
    )

    assert not eligibility["reasons"]

    print("\nFinalization Eligibility: PASSED")

    # ==========================================
    # 7. Locked Day Protection
    # ==========================================

    print_section(
        "LOCKED DAY PROTECTION"
    )

    day2_eligibility = (
        get_day_finalization_eligibility(day2)
    )

    print_json(day2_eligibility)

    assert not day2_eligibility["eligible"]

    expect_rejection(
        "Finalize Locked Day",
        finalize_day_from_best_attempt,
        day2,
    )

    print("\nLocked Day Protection: PASSED")

    # ==========================================
    # 8. Initial Assessment Protection
    # ==========================================

    print_section(
        "INITIAL ASSESSMENT PROTECTION"
    )

    initial_attempt = (
        AssessmentAttempt.objects.filter(
            assessment__enrollment=enrollment,
            assessment__assessment_type="initial",
            status="evaluated",
        ).first()
    )

    assert initial_attempt is not None

    expect_rejection(
        "Finalize Using Initial Assessment",
        finalize_learning_day,
        initial_attempt,
    )

    print("\nInitial Assessment Protection: PASSED")

    # ==========================================
    # 9. Transactional Rollback Test
    # ==========================================

    print_section(
        "TRANSACTIONAL ROLLBACK TEST"
    )

    state_before_failure = (
        capture_progression_state(enrollment)
    )

    with patch(
        "learning.services.progression_service."
        "_unlock_next_learning_day",
        side_effect=ProgressionError(
            "Simulated next-day unlocking failure."
        ),
    ) as mocked_unlock:

        expect_rejection(
            "Simulated Unlocking Failure",
            finalize_learning_day,
            attempt,
        )

        assert mocked_unlock.called

    state_after_failure = (
        capture_progression_state(enrollment)
    )

    assert (
        state_before_failure
        == state_after_failure
    )

    print("Enrollment Changes Rolled Back: True")
    print("Day Progress Changes Rolled Back: True")
    print("Topic Mastery Changes Rolled Back: True")

    print("\nTransactional Rollback Test: PASSED")

    # ==========================================
    # 10. Actual Day 1 Finalization
    # ==========================================

    print_section(
        "FINALIZE DAY 1 LEARNING PROGRESS"
    )

    result = finalize_learning_day(
        attempt
    )

    print_json(result)

    assert result["passed"]
    assert result["day_completed"]
    assert result["assessment_completed"]

    assert not result["already_finalized"]

    assert result["day_status"] == "completed"

    assert result["current_day"] == 2

    assert result["completed_days"] == 1

    assert result["locked_days"] == 28

    assert (
        result["overall_progress_percentage"]
        == 3.33
    )

    assert not result["course_completed"]

    assert result["next_day"]["day_number"] == 2

    assert (
        result["next_day"]["status"]
        == "unlocked"
    )

    print("\nDay 1 Finalization: PASSED")

    # ==========================================
    # 11. Verify Day 1 Database State
    # ==========================================

    print_section(
        "DAY 1 DATABASE VERIFICATION"
    )

    progress1.refresh_from_db()

    print(f"Status: {progress1.status}")

    print(
        f"Lesson Completed: "
        f"{progress1.lesson_completed}"
    )

    print(
        f"Practical Completed: "
        f"{progress1.practical_completed}"
    )

    print(
        f"Assessment Completed: "
        f"{progress1.assessment_completed}"
    )

    print(f"Best Score: {progress1.best_score}%")

    print(f"Completed At: {progress1.completed_at}")

    assert progress1.status == "completed"

    assert progress1.lesson_completed
    assert progress1.practical_completed
    assert progress1.assessment_completed

    assert progress1.completed_at is not None

    assert math.isclose(
        progress1.best_score,
        attempt.percentage,
    )

    print("\nDay 1 Database Verification: PASSED")

    # ==========================================
    # 12. Verify Topic Mastery Updates
    # ==========================================

    print_section(
        "TOPIC MASTERY UPDATE VERIFICATION"
    )

    mastery.refresh_from_db()

    print(f"Topic: {mastery.topic}")
    print(f"Initial Score: {mastery.initial_score}%")

    print(f"Previous Mastery: {previous_mastery}%")

    print(
        f"Updated Mastery: "
        f"{mastery.mastery_score}%"
    )

    print(
        f"Recommended Difficulty: "
        f"{mastery.recommended_difficulty}"
    )

    print(
        f"Total Questions: "
        f"{mastery.total_questions}"
    )

    print(
        f"Correct Answers: "
        f"{mastery.correct_answers}"
    )

    evaluated_correct_answers = (
        UserAnswer.objects.filter(
            attempt=attempt,
            is_correct=True,
        ).count()
    )

    assert mastery.initial_score == initial_score

    assert math.isclose(
        mastery.mastery_score,
        expected_mastery,
    )

    assert (
        mastery.recommended_difficulty
        == expected_difficulty
    )

    assert (
        mastery.total_questions
        == previous_questions + 5
    )

    assert (
        mastery.correct_answers
        == previous_correct
        + evaluated_correct_answers
    )

    assert mastery.last_practiced_at is not None

    current_other_mastery = list(
        TopicMastery.objects.filter(
            enrollment=enrollment
        ).exclude(
            pk=mastery.pk
        ).order_by("pk").values()
    )

    assert (
        other_mastery_records
        == current_other_mastery
    )

    print("Original Diagnostic Score Preserved: True")

    print("Other Topic Mastery Records Unchanged: True")

    print("\nTopic Mastery Update: PASSED")

    # ==========================================
    # 13. Verify Day 2 Unlocking
    # ==========================================

    print_section(
        "NEXT DAY UNLOCKING VERIFICATION"
    )

    progress2.refresh_from_db()
    day2.refresh_from_db()

    print(f"Day Number: {day2.day_number}")
    print(f"Title: {day2.title}")
    print(f"Status: {progress2.status}")
    print(f"Unlocked At: {progress2.unlocked_at}")

    print(
        f"Content Generated: "
        f"{day2.is_content_generated}"
    )

    assert progress2.status == "unlocked"

    assert progress2.unlocked_at is not None

    assert not progress2.lesson_completed

    assert not progress2.practical_completed

    assert not progress2.assessment_completed

    assert progress2.completed_at is None

    assert not day2.is_content_generated

    print("\nDay 2 Unlocking: PASSED")

    # ==========================================
    # 14. Verify Remaining Days
    # ==========================================

    print_section(
        "FUTURE DAY PROTECTION"
    )

    future_days = DayProgress.objects.filter(
        learning_day__enrollment=enrollment,
        learning_day__day_number__gte=3,
    )

    locked_count = future_days.filter(
        status="locked"
    ).count()

    print(f"Future Days: {future_days.count()}")
    print(f"Locked Future Days: {locked_count}")

    assert future_days.count() == 28
    assert locked_count == 28

    print("\nFuture Day Protection: PASSED")

    # ==========================================
    # 15. Verify Enrollment
    # ==========================================

    print_section(
        "ENROLLMENT PROGRESSION VERIFICATION"
    )

    enrollment.refresh_from_db()

    print(f"Current Day: {enrollment.current_day}")
    print(f"Status: {enrollment.status}")
    print(f"Skill Level: {enrollment.skill_level}")

    assert enrollment.current_day == 2

    assert enrollment.status == "active"

    assert (
        enrollment.skill_level
        == original_state["enrollment"]["skill_level"]
    )

    assert (
        enrollment.strengths
        == original_state["enrollment"]["strengths"]
    )

    assert (
        enrollment.weaknesses
        == original_state["enrollment"]["weaknesses"]
    )

    print("\nEnrollment Progression: PASSED")

    # ==========================================
    # 16. Duplicate Finalization Protection
    # ==========================================

    print_section(
        "DUPLICATE FINALIZATION PROTECTION"
    )

    state_before_duplicate = (
        capture_progression_state(enrollment)
    )

    repeated_result = finalize_learning_day(
        attempt
    )

    print_json(repeated_result)

    assert repeated_result["already_finalized"]

    assert repeated_result["day_completed"]

    assert repeated_result["mastery_updates"] == []

    state_after_duplicate = (
        capture_progression_state(enrollment)
    )

    assert (
        state_before_duplicate
        == state_after_duplicate
    )

    print("Mastery Updated Again: False")
    print("Question Counters Increased Again: False")
    print("Completion Timestamp Changed: False")
    print("Unlock Timestamp Changed: False")

    print("\nDuplicate Finalization Test: PASSED")

    # ==========================================
    # 17. Best Attempt Finalization Protection
    # ==========================================

    print_section(
        "BEST ATTEMPT FINALIZATION PROTECTION"
    )

    best_attempt_result = (
        finalize_day_from_best_attempt(day1)
    )

    assert best_attempt_result["already_finalized"]

    assert (
        best_attempt_result["attempt_id"]
        == attempt.id
    )

    assert (
        capture_progression_state(enrollment)
        == state_before_duplicate
    )

    print("Existing Finalization Reused: True")

    print("\nBest Attempt Finalization: PASSED")

    # ==========================================
    # 18. Completed Day Eligibility
    # ==========================================

    print_section(
        "COMPLETED DAY ELIGIBILITY"
    )

    completed_eligibility = (
        get_day_finalization_eligibility(day1)
    )

    print_json(completed_eligibility)

    assert not completed_eligibility["eligible"]

    assert completed_eligibility[
        "assessment_completed"
    ]

    print("\nCompleted Day Eligibility: PASSED")

    # ==========================================
    # 19. Verify Daily Progress Summary
    # ==========================================

    print_section(
        "DAILY PROGRESS SUMMARY"
    )

    day1_summary = get_daily_progress_summary(
        day1
    )

    print_json(day1_summary)

    assert (
        day1_summary["completion_percentage"]
        == 100.0
    )

    assert day1_summary["status"] == "completed"

    assert not day1_summary["assessment_eligible"]

    print("\nDaily Progress Summary: PASSED")

    # ==========================================
    # 20. Verify Enrollment Progress Summary
    # ==========================================

    print_section(
        "ENROLLMENT PROGRESS SUMMARY"
    )

    enrollment_summary = (
        get_enrollment_progress_summary(
            enrollment
        )
    )

    print_json(enrollment_summary)

    completed_days = DayProgress.objects.filter(
        learning_day__enrollment=enrollment,
        status="completed",
    ).count()

    total_days = LearningDay.objects.filter(
        enrollment=enrollment
    ).count()

    overall_percentage = round(
        completed_days / total_days * 100,
        2,
    )

    assert completed_days == 1
    assert total_days == 30
    assert overall_percentage == 3.33

    print("\nEnrollment Progress Summary: PASSED")

    # ==========================================
    # 21. Verify Protected Records
    # ==========================================

    print_section(
        "EXISTING DATA PRESERVATION"
    )

    current_protected_records = (
        capture_protected_records(enrollment)
    )

    for key in protected_records:

        unchanged = (
            protected_records[key]
            == current_protected_records[key]
        )

        print(
            f"{key.replace('_', ' ').title()} "
            f"Unchanged: {unchanged}"
        )

        assert unchanged, (
            f"Protected records modified: {key}"
        )

    print("\nExisting Data Preservation: PASSED")

    # ==========================================
    # 22. Retrieve Progression Summary
    # ==========================================

    print_section(
        "FINAL PROGRESSION SUMMARY"
    )

    progression_summary = (
        get_progression_summary(enrollment)
    )

    print_json(progression_summary)

    assert not progression_summary[
        "course_completed"
    ]

    assert (
        progression_summary[
            "current_day_progress"
        ]["day_number"]
        == 2
    )

    print("\nProgression Summary: PASSED")

    # ==========================================
    # 23. Final Test Summary
    # ==========================================

    print_section(
        "LEARNING PROGRESSION TEST PASSED!"
    )

    print(f"\nEnrollment ID: {enrollment.id}")

    print(f"Day 1 Status: {progress1.status}")
    print("Day 1 Completion: 100%")

    print(
        f"Day 1 Assessment Score: "
        f"{progress1.best_score}%"
    )

    print(f"Day 2 Status: {progress2.status}")

    print(f"Current Learning Day: {enrollment.current_day}")

    print(f"Completed Days: {completed_days}/30")

    print(f"Overall Progress: {overall_percentage}%")

    print(f"Remaining Locked Days: {locked_count}")

    print(f"\nTopic: {mastery.topic}")

    print(f"Initial Score: {mastery.initial_score}%")

    print(f"Previous Mastery: {previous_mastery}%")

    print(f"Updated Mastery: {mastery.mastery_score}%")

    print(
        f"Mastery Improvement: "
        f"{mastery.mastery_score - previous_mastery:.2f}"
        " percentage points"
    )

    print(
        f"Recommended Difficulty: "
        f"{mastery.recommended_difficulty}"
    )

    print("\nTransactional Rollback: PASSED")
    print("Duplicate Finalization: PASSED")
    print("Existing Data Preservation: PASSED")

    print("Additional AI Generation Jobs: 0")

    print("\nDay 2 is ready for personalized learning.")


if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print_section(
            "LEARNING PROGRESSION TEST FAILED!"
        )

        print(f"Error: {error}")

        print(
            "\nInspect the error before continuing."
        )

        print(
            "If actual finalization already succeeded, "
            "database changes may have been committed."
        )

        raise