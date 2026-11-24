import os
import sys
import json

import django

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction

from learning.models import (
    Enrollment,
    LearningDay,
    DayProgress,
    AIGenerationJob,
    TopicMastery,
    AssessmentAttempt,
)

from learning.services.progress_service import (
    LearningProgressError,
    start_learning_day,
    mark_lesson_completed,
    mark_practical_completed,
    check_daily_assessment_eligibility,
    require_daily_assessment_eligibility,
    get_daily_progress_summary,
    get_enrollment_progress_summary,
    calculate_daily_completion_percentage,
)


User = get_user_model()


# ==========================================
# Helper: Print Section
# ==========================================

def print_section(title):

    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


# ==========================================
# Helper: Verify Rejected Operation
# ==========================================

def expect_rejection(function, learning_day, label):

    try:

        function(learning_day)

    except LearningProgressError as error:

        print(f"{label}: PASSED")
        print(f"Reason: {error}")

        return

    raise AssertionError(
        f"{label}: Operation should have been rejected."
    )


# ==========================================
# Helper: Display Daily Progress
# ==========================================

def display_progress(learning_day):

    summary = get_daily_progress_summary(
        learning_day
    )

    print(f"Day Number: {summary['day_number']}")
    print(f"Status: {summary['status']}")

    print(
        "Lesson Completed:",
        summary["lesson_completed"],
    )

    print(
        "Practical Completed:",
        summary["practical_completed"],
    )

    print(
        "Assessment Completed:",
        summary["assessment_completed"],
    )

    print(
        "Assessment Eligible:",
        summary["assessment_eligible"],
    )

    print(
        "Daily Completion:",
        f"{summary['completion_percentage']}%",
    )

    if summary["assessment_blocking_reasons"]:

        print("\nAssessment Blocking Reasons:")

        for reason in summary[
            "assessment_blocking_reasons"
        ]:

            print(f"- {reason}")

    return summary


# ==========================================
# Main Test
# ==========================================

@transaction.atomic
def main():

    print_section(
        "CODEMIND AI - LEARNING PROGRESS TEST"
    )

    # ==========================================
    # 1. Retrieve Existing Enrollment
    # ==========================================

    user = User.objects.filter(
        is_superuser=True
    ).first()

    if not user:

        raise RuntimeError(
            "No superuser found."
        )

    enrollment = Enrollment.objects.filter(
        user=user,
        language="python",
    ).first()

    if not enrollment:

        raise RuntimeError(
            "Python enrollment not found."
        )

    print(f"User: {user.username}")

    print(
        f"Language: "
        f"{enrollment.get_language_display()}"
    )

    print(f"Skill Level: {enrollment.skill_level}")
    print(f"Enrollment Status: {enrollment.status}")
    print(f"Current Day: {enrollment.current_day}")

    assert enrollment.status == "active"

    assert enrollment.current_day == 1

    # ==========================================
    # 2. Retrieve Day 1 and Day 2
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

    assert day1.is_content_generated, (
        "Generate Day 1 lesson first."
    )

    assert progress1.status == "unlocked", (
        "This test requires Day 1 to be unlocked "
        "and not yet started."
    )

    assert not progress1.lesson_completed

    assert not progress1.practical_completed

    assert not progress1.assessment_completed

    assert progress2.status == "locked"

    # Preserve existing database information

    original_job_count = (
        AIGenerationJob.objects.filter(
            enrollment=enrollment
        ).count()
    )

    original_mastery = list(
        TopicMastery.objects.filter(
            enrollment=enrollment
        ).order_by("pk").values()
    )

    original_assessment_attempts = list(
        AssessmentAttempt.objects.filter(
            assessment__enrollment=enrollment
        ).order_by("pk").values()
    )

    original_day_count = (
        LearningDay.objects.filter(
            enrollment=enrollment
        ).count()
    )

    original_progress_count = (
        DayProgress.objects.filter(
            learning_day__enrollment=enrollment
        ).count()
    )

    # ==========================================
    # 3. Verify Initial Progress
    # ==========================================

    print_section(
        "INITIAL PROGRESS VERIFICATION"
    )

    initial_summary = display_progress(day1)

    assert initial_summary["status"] == "unlocked"

    assert initial_summary[
        "completion_percentage"
    ] == 0.0

    assert not initial_summary[
        "assessment_eligible"
    ]

    print("\nInitial Progress Test: PASSED")

    # ==========================================
    # 4. Test Locked Day Protection
    # ==========================================

    print_section(
        "LOCKED DAY PROTECTION TEST"
    )

    expect_rejection(
        start_learning_day,
        day2,
        "Start Locked Day",
    )

    expect_rejection(
        mark_lesson_completed,
        day2,
        "Complete Locked Lesson",
    )

    expect_rejection(
        mark_practical_completed,
        day2,
        "Complete Locked Practical Tasks",
    )

    expect_rejection(
        require_daily_assessment_eligibility,
        day2,
        "Access Locked Assessment",
    )

    progress2.refresh_from_db()

    assert progress2.status == "locked"

    assert not progress2.lesson_completed

    assert not progress2.practical_completed

    assert not progress2.assessment_completed

    print("\nLocked Day Protection: PASSED")

    # ==========================================
    # 5. Test Invalid Activity Sequence
    # ==========================================

    print_section(
        "ACTIVITY PREREQUISITE TEST"
    )

    expect_rejection(
        mark_lesson_completed,
        day1,
        "Complete Lesson Before Starting Day",
    )

    expect_rejection(
        mark_practical_completed,
        day1,
        "Complete Practical Before Starting Day",
    )

    expect_rejection(
        require_daily_assessment_eligibility,
        day1,
        "Access Assessment Before Activities",
    )

    print("\nActivity Prerequisite Test: PASSED")

    # ==========================================
    # 6. Start Learning Day
    # ==========================================

    print_section(
        "START LEARNING DAY TEST"
    )

    progress = start_learning_day(day1)

    assert progress.status == "in_progress"

    assert not progress.lesson_completed

    assert not progress.practical_completed

    assert not progress.assessment_completed

    assert (
        calculate_daily_completion_percentage(
            progress
        ) == 0.0
    )

    display_progress(day1)

    print("\nStart Learning Day Test: PASSED")

    # ==========================================
    # 7. Test Duplicate Start Request
    # ==========================================

    print_section(
        "DUPLICATE START REQUEST TEST"
    )

    progress.refresh_from_db()

    original_updated_at = progress.updated_at

    repeated_progress = start_learning_day(
        day1
    )

    repeated_progress.refresh_from_db()

    assert repeated_progress.id == progress.id

    assert repeated_progress.status == "in_progress"

    assert (
        repeated_progress.updated_at
        == original_updated_at
    )

    print("Same Progress Record Returned: True")
    print("Unnecessary Database Update: False")

    print("\nDuplicate Start Request Test: PASSED")

    # ==========================================
    # 8. Verify Practical Prerequisite
    # ==========================================

    print_section(
        "PRACTICAL PREREQUISITE TEST"
    )

    expect_rejection(
        mark_practical_completed,
        day1,
        "Complete Practical Before Lesson",
    )

    expect_rejection(
        require_daily_assessment_eligibility,
        day1,
        "Access Assessment Before Lesson",
    )

    print("\nPractical Prerequisite Test: PASSED")

    # ==========================================
    # 9. Complete Lesson
    # ==========================================

    print_section(
        "LESSON COMPLETION TEST"
    )

    progress = mark_lesson_completed(
        day1
    )

    assert progress.lesson_completed

    assert not progress.practical_completed

    assert not progress.assessment_completed

    assert progress.status == "in_progress"

    assert (
        calculate_daily_completion_percentage(
            progress
        ) == 33.33
    )

    summary = display_progress(day1)

    assert not summary["assessment_eligible"]

    print("\nLesson Completion Test: PASSED")

    # ==========================================
    # 10. Test Duplicate Lesson Completion
    # ==========================================

    print_section(
        "DUPLICATE LESSON COMPLETION TEST"
    )

    progress.refresh_from_db()

    original_updated_at = progress.updated_at

    repeated_progress = mark_lesson_completed(
        day1
    )

    repeated_progress.refresh_from_db()

    assert repeated_progress.id == progress.id

    assert repeated_progress.lesson_completed

    assert (
        repeated_progress.updated_at
        == original_updated_at
    )

    print("Same Progress Record Returned: True")
    print("Unnecessary Database Update: False")

    print("\nDuplicate Lesson Completion: PASSED")

    # ==========================================
    # 11. Verify Assessment Still Locked
    # ==========================================

    print_section(
        "ASSESSMENT PREREQUISITE TEST"
    )

    expect_rejection(
        require_daily_assessment_eligibility,
        day1,
        "Access Assessment Before Practical Tasks",
    )

    eligibility = (
        check_daily_assessment_eligibility(
            day1
        )
    )

    assert not eligibility["eligible"]

    print("\nAssessment Prerequisite Test: PASSED")

    # ==========================================
    # 12. Complete Practical Tasks
    # ==========================================

    print_section(
        "PRACTICAL COMPLETION TEST"
    )

    progress = mark_practical_completed(
        day1
    )

    assert progress.lesson_completed

    assert progress.practical_completed

    assert not progress.assessment_completed

    assert progress.status == "in_progress"

    assert (
        calculate_daily_completion_percentage(
            progress
        ) == 66.67
    )

    summary = display_progress(day1)

    assert summary["assessment_eligible"]

    print("\nPractical Completion Test: PASSED")

    # ==========================================
    # 13. Test Duplicate Practical Completion
    # ==========================================

    print_section(
        "DUPLICATE PRACTICAL COMPLETION TEST"
    )

    progress.refresh_from_db()

    original_updated_at = progress.updated_at

    repeated_progress = mark_practical_completed(
        day1
    )

    repeated_progress.refresh_from_db()

    assert repeated_progress.id == progress.id

    assert repeated_progress.practical_completed

    assert (
        repeated_progress.updated_at
        == original_updated_at
    )

    print("Same Progress Record Returned: True")
    print("Unnecessary Database Update: False")

    print("\nDuplicate Practical Completion: PASSED")

    # ==========================================
    # 14. Verify Daily Assessment Eligibility
    # ==========================================

    print_section(
        "DAILY ASSESSMENT ELIGIBILITY TEST"
    )

    eligibility = (
        require_daily_assessment_eligibility(
            day1
        )
    )

    print(
        json.dumps(
            eligibility,
            indent=4,
        )
    )

    assert eligibility["eligible"]

    assert eligibility["lesson_completed"]

    assert eligibility["practical_completed"]

    assert not eligibility["assessment_completed"]

    assert eligibility["reasons"] == []

    print("\nDaily Assessment Eligibility: PASSED")

    # ==========================================
    # 15. Verify Overall Learning Progress
    # ==========================================

    print_section(
        "OVERALL LEARNING PROGRESS"
    )

    summary = get_enrollment_progress_summary(
        enrollment
    )

    print(
        json.dumps(
            summary,
            indent=4,
        )
    )

    assert summary["total_days"] == 30

    assert summary["completed_days"] == 0

    assert summary["pending_days"] == 30

    assert summary["unlocked_days"] == 0

    assert summary["in_progress_days"] == 1

    assert summary["locked_days"] == 29

    assert summary["generated_lessons"] == 1

    assert summary["completed_lessons"] == 1

    assert summary["completed_practicals"] == 1

    assert summary["completed_assessments"] == 0

    assert summary[
        "overall_progress_percentage"
    ] == 0.0

    assert summary[
        "average_assessment_score"
    ] is None

    assert summary["current_day"] == 1

    print("\nOverall Progress Test: PASSED")

    # ==========================================
    # 16. Verify Existing Data Preservation
    # ==========================================

    print_section(
        "EXISTING DATA PRESERVATION TEST"
    )

    enrollment.refresh_from_db()
    day1.refresh_from_db()
    day2.refresh_from_db()
    progress2.refresh_from_db()

    current_job_count = (
        AIGenerationJob.objects.filter(
            enrollment=enrollment
        ).count()
    )

    current_mastery = list(
        TopicMastery.objects.filter(
            enrollment=enrollment
        ).order_by("pk").values()
    )

    current_assessment_attempts = list(
        AssessmentAttempt.objects.filter(
            assessment__enrollment=enrollment
        ).order_by("pk").values()
    )

    current_day_count = (
        LearningDay.objects.filter(
            enrollment=enrollment
        ).count()
    )

    current_progress_count = (
        DayProgress.objects.filter(
            learning_day__enrollment=enrollment
        ).count()
    )

    assert (
        current_job_count == original_job_count
    )

    assert (
        current_mastery == original_mastery
    )

    assert (
        current_assessment_attempts
        == original_assessment_attempts
    )

    assert (
        current_day_count == original_day_count
    )

    assert (
        current_progress_count
        == original_progress_count
    )

    assert enrollment.current_day == 1

    assert enrollment.status == "active"

    assert day1.is_content_generated

    assert not day2.is_content_generated

    assert progress2.status == "locked"

    print("AI Jobs Unchanged: True")
    print("Topic Mastery Unchanged: True")
    print("Assessment Attempts Unchanged: True")
    print("Roadmap Preserved: True")
    print("Progress Records Preserved: True")
    print("Day 2 Remains Locked: True")
    print("Additional AI API Calls: 0")

    print("\nExisting Data Preservation: PASSED")

    # ==========================================
    # 17. Final Results
    # ==========================================

    print_section(
        "FINAL LEARNING PROGRESS STATE"
    )

    display_progress(day1)

    print("\nDay 2 Status: locked")
    print("Overall Course Progress: 0.0%")
    print("Daily Assessment Ready: True")

    print_section(
        "LEARNING PROGRESS TEST PASSED!"
    )

    print(
        "\nAll progress changes saved successfully."
    )

    print(
        "Day 1 is ready for daily assessment generation."
    )


if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print("\n" + "=" * 60)
        print("LEARNING PROGRESS TEST FAILED!")
        print("=" * 60)

        print(f"Error: {error}")

        print(
            "Test database changes have been rolled back."
        )

        raise