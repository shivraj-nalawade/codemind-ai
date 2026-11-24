import os
import json
import copy

from unittest.mock import patch

import django

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
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

from learning.services.adaptive_roadmap_service import (
    RoadmapAdaptationError,
    adapt_personalized_roadmap,
    build_adaptation_context,
    get_adaptable_days,
    get_adaptation_eligibility,
    get_roadmap_adaptation_history,
    is_day_adaptable,
    validate_adaptation_response,
)


# ==========================================
# Helper Functions
# ==========================================

def print_section(title):

    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def print_json(data):

    print(
        json.dumps(
            data,
            indent=4,
            ensure_ascii=False,
            default=str,
        )
    )


def expect_rejection(
    label,
    function,
    *args,
    **kwargs,
):

    try:

        function(*args, **kwargs)

    except RoadmapAdaptationError as error:

        print(f"{label}: PASSED")
        print(f"Reason: {error}")

        return

    raise AssertionError(
        f"{label}: Invalid operation was accepted."
    )


# ==========================================
# Capture Roadmap Records
# ==========================================

def capture_roadmap(enrollment):

    return {
        day["id"]: day
        for day in LearningDay.objects.filter(
            enrollment=enrollment
        ).order_by("day_number").values()
    }


# ==========================================
# Capture Protected Records
# ==========================================

def capture_protected_records(enrollment):

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

        "topic_mastery": list(
            TopicMastery.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),

        "previous_ai_jobs": list(
            AIGenerationJob.objects.filter(
                enrollment=enrollment
            ).exclude(
                job_type="roadmap_adaptation"
            ).order_by("pk").values()
        ),
    }


# ==========================================
# Build Mock Valid Adaptation
# ==========================================

def build_mock_adaptation(context):

    adapted_days = []

    for day in context["upcoming_lessons"]:

        adapted_days.append({
            "learning_day_id": (
                day["learning_day_id"]
            ),
            "day_number": day["day_number"],
            "title": day["title"],
            "topic": day["topic"],
            "difficulty": (
                day["recommended_difficulty"]
            ),
            "learning_objectives": copy.deepcopy(
                day["learning_objectives"]
            ),
            "estimated_minutes": (
                day["estimated_minutes"]
            ),
            "adaptation_reason": (
                "Adjust difficulty according to "
                "the learner's current topic mastery."
            ),
        })

    return {
        "language": context["language"],
        "completed_day": context["completed_day"],
        "adaptation_summary": (
            "Mock adaptation for validation testing."
        ),
        "adapted_days": adapted_days,
    }


# ==========================================
# Main Test
# ==========================================

def main():

    print_section(
        "CODEMIND AI - ADAPTIVE ROADMAP TEST"
    )

    # ==========================================
    # 1. Retrieve Existing Enrollment
    # ==========================================

    enrollment = Enrollment.objects.get(
        pk=1,
        language="python",
    )

    print(f"Enrollment ID: {enrollment.id}")

    print(
        f"Language: "
        f"{enrollment.get_language_display()}"
    )

    print(f"Skill Level: {enrollment.skill_level}")
    print(f"Current Day: {enrollment.current_day}")
    print(f"Status: {enrollment.status}")

    assert enrollment.status == "active"
    assert enrollment.current_day == 2

    day1 = LearningDay.objects.get(
        enrollment=enrollment,
        day_number=1,
    )

    day1_progress = DayProgress.objects.get(
        learning_day=day1
    )

    assert day1_progress.status == "completed"

    print("\nEnrollment Verification: PASSED")

    # ==========================================
    # 2. Adaptation Eligibility
    # ==========================================

    print_section(
        "ADAPTATION ELIGIBILITY"
    )

    eligibility = get_adaptation_eligibility(
        enrollment
    )

    print_json(eligibility)

    if eligibility["already_adapted"]:

        raise RuntimeError(
            "Roadmap has already been adapted "
            "after Day 1. Do not repeat this "
            "initial integration test."
        )

    assert eligibility["eligible"]
    assert eligibility["adaptable_count"] == 5
    assert eligibility["completed_day"] == 1
    assert not eligibility["reasons"]

    print("\nAdaptation Eligibility: PASSED")

    # ==========================================
    # 3. Capture Original Database State
    # ==========================================

    original_roadmap = capture_roadmap(
        enrollment
    )

    protected_records = (
        capture_protected_records(enrollment)
    )

    original_job_count = (
        AIGenerationJob.objects.filter(
            enrollment=enrollment
        ).count()
    )

    job_key = (
        f"roadmap_adaptation_{enrollment.id}_1"
    )

    existing_job = AIGenerationJob.objects.filter(
        idempotency_key=job_key
    ).first()

    original_attempt_count = (
        existing_job.attempt_count
        if existing_job
        else 0
    )

    expected_job_count = (
        original_job_count
        if existing_job
        else original_job_count + 1
    )

    assert len(original_roadmap) == 30

    print(f"Original Learning Days: 30")

    print(
        f"Original AI Jobs: "
        f"{original_job_count}"
    )

    # ==========================================
    # 4. Verify Adaptable Days
    # ==========================================

    print_section(
        "ADAPTABLE DAYS VERIFICATION"
    )

    adaptable_days = get_adaptable_days(
        enrollment
    )

    adaptable_ids = {
        day.id for day in adaptable_days
    }

    adaptable_numbers = [
        day.day_number
        for day in adaptable_days
    ]

    assert adaptable_numbers == [
        2, 3, 4, 5, 6
    ]

    for day in adaptable_days:

        print(
            f"Day {day.day_number}: "
            f"{day.title} | {day.difficulty}"
        )

        assert not day.is_content_generated
        assert is_day_adaptable(day)

    assert not is_day_adaptable(day1)

    print("\nAdaptable Days Verification: PASSED")

    # ==========================================
    # 5. Build Adaptation Context
    # ==========================================

    print_section(
        "ADAPTATION CONTEXT VERIFICATION"
    )

    context = build_adaptation_context(
        enrollment
    )

    assert context["language"] == "python"

    assert context["completed_day"] == 1

    assert context["current_day"] == 2

    assert (
        context["latest_assessment"]["percentage"]
        == 100.0
    )

    assert len(context["upcoming_lessons"]) == 5

    assert len(context["completed_lessons"]) == 1

    mastery_lookup = {
        item["topic"]: item["mastery_score"]
        for item in context["topic_mastery"]
    }

    assert (
        mastery_lookup["Conditional Statements"]
        == 70.0
    )

    assert mastery_lookup["Functions"] == 25.0

    assert (
        mastery_lookup["Object-Oriented Programming"]
        == 0.0
    )

    print_json(context["topic_analysis"])

    print("\nAdaptation Context: PASSED")

    # ==========================================
    # 6. Valid Response Test
    # ==========================================

    print_section(
        "AI RESPONSE VALIDATION TESTS"
    )

    valid_response = build_mock_adaptation(
        context
    )

    validated = validate_adaptation_response(
        valid_response,
        context,
    )

    assert len(validated["adapted_days"]) == 5

    print("Valid Mock Response: PASSED")

    # ==========================================
    # 7. Reject Invalid Language
    # ==========================================

    invalid = copy.deepcopy(valid_response)

    invalid["language"] = "java"

    expect_rejection(
        "Incorrect Programming Language",
        validate_adaptation_response,
        invalid,
        context,
    )

    # ==========================================
    # 8. Reject Missing Learning Day
    # ==========================================

    invalid = copy.deepcopy(valid_response)

    invalid["adapted_days"].pop()

    expect_rejection(
        "Missing Learning Day",
        validate_adaptation_response,
        invalid,
        context,
    )

    # ==========================================
    # 9. Reject Changed Topic
    # ==========================================

    invalid = copy.deepcopy(valid_response)

    invalid["adapted_days"][0]["topic"] = (
        "Machine Learning"
    )

    expect_rejection(
        "Modified Original Topic",
        validate_adaptation_response,
        invalid,
        context,
    )

    # ==========================================
    # 10. Reject Changed Day Sequence
    # ==========================================

    invalid = copy.deepcopy(valid_response)

    invalid["adapted_days"][0]["day_number"] = 10

    expect_rejection(
        "Modified Learning Day Sequence",
        validate_adaptation_response,
        invalid,
        context,
    )

    # ==========================================
    # 11. Reject Excessive Difficulty
    # ==========================================

    invalid = copy.deepcopy(valid_response)

    invalid["adapted_days"][2]["difficulty"] = (
        "advanced"
    )

    expect_rejection(
        "Excessive Difficulty for Weak Topic",
        validate_adaptation_response,
        invalid,
        context,
    )

    # ==========================================
    # 12. Reject Unassessed Topic Difficulty
    # ==========================================

    invalid = copy.deepcopy(valid_response)

    invalid["adapted_days"][3]["difficulty"] = (
        "advanced"
    )

    expect_rejection(
        "Changed Unassessed Topic Difficulty",
        validate_adaptation_response,
        invalid,
        context,
    )

    # ==========================================
    # 13. Reject Invalid Objectives
    # ==========================================

    invalid = copy.deepcopy(valid_response)

    invalid["adapted_days"][0][
        "learning_objectives"
    ] = ["Only one objective"]

    expect_rejection(
        "Insufficient Learning Objectives",
        validate_adaptation_response,
        invalid,
        context,
    )

    # ==========================================
    # 14. Reject Invalid Duration
    # ==========================================

    invalid = copy.deepcopy(valid_response)

    invalid["adapted_days"][0][
        "estimated_minutes"
    ] = 200

    expect_rejection(
        "Invalid Lesson Duration",
        validate_adaptation_response,
        invalid,
        context,
    )

    # ==========================================
    # 15. Reject Duplicate Titles
    # ==========================================

    invalid = copy.deepcopy(valid_response)

    invalid["adapted_days"][1]["title"] = (
        invalid["adapted_days"][0]["title"]
    )

    expect_rejection(
        "Duplicate Lesson Titles",
        validate_adaptation_response,
        invalid,
        context,
    )

    print("\nAI Response Validation Tests: PASSED")

    # ==========================================
    # 16. Simulated AI Failure
    # ==========================================

    print_section(
        "AI FAILURE RECOVERY TEST"
    )

    with patch(
        "learning.services.adaptive_roadmap_service."
        "generate_validated_adaptation",
        side_effect=RoadmapAdaptationError(
            "Simulated AI generation failure."
        ),
    ):

        expect_rejection(
            "Simulated AI Failure",
            adapt_personalized_roadmap,
            enrollment,
        )

    assert (
        capture_roadmap(enrollment)
        == original_roadmap
    )

    assert (
        capture_protected_records(enrollment)
        == protected_records
    )

    failed_job = AIGenerationJob.objects.get(
        idempotency_key=job_key
    )

    assert failed_job.status == "failed"

    assert failed_job.error_message

    assert (
        failed_job.attempt_count
        == original_attempt_count + 1
    )

    print("Original Roadmap Preserved: True")
    print("Existing Learning Records Preserved: True")
    print("Failed Job Recorded: True")

    print("\nAI Failure Recovery: PASSED")

    # ==========================================
    # 17. Transactional Rollback Test
    # ==========================================

    print_section(
        "TRANSACTIONAL ROLLBACK TEST"
    )

    rollback_response = copy.deepcopy(
        valid_response
    )

    # Ensure that the first lesson is modified
    # before simulating failure on the second.

    rollback_response["adapted_days"][0][
        "estimated_minutes"
    ] = (
        60
        if context["upcoming_lessons"][0][
            "estimated_minutes"
        ] != 60
        else 65
    )

    rollback_response = (
        validate_adaptation_response(
            rollback_response,
            context,
        )
    )

    original_save = LearningDay.save

    first_day_id = adaptable_days[0].id
    second_day_id = adaptable_days[1].id

    first_day_saved = []

    # Ensure the second lesson also changes.

    rollback_response["adapted_days"][1][
        "estimated_minutes"
    ] = (
        60
        if context["upcoming_lessons"][1][
            "estimated_minutes"
        ] != 60
        else 65
    )

    def simulated_save(instance, *args, **kwargs):

        if instance.pk == second_day_id:

            raise RoadmapAdaptationError(
                "Simulated database failure "
                "while saving second lesson."
            )

        result = original_save(
            instance,
            *args,
            **kwargs,
        )

        if instance.pk == first_day_id:

            first_day_saved.append(True)

        return result

    with patch(
        "learning.services.adaptive_roadmap_service."
        "generate_validated_adaptation",
        return_value=rollback_response,
    ):

        with patch.object(
            LearningDay,
            "save",
            new=simulated_save,
        ):

            expect_rejection(
                "Simulated Database Failure",
                adapt_personalized_roadmap,
                enrollment,
            )

    assert first_day_saved

    assert (
        capture_roadmap(enrollment)
        == original_roadmap
    )

    assert (
        capture_protected_records(enrollment)
        == protected_records
    )

    failed_job.refresh_from_db()

    assert failed_job.status == "failed"

    assert (
        failed_job.attempt_count
        == original_attempt_count + 2
    )

    print("First Lesson Was Temporarily Updated: True")
    print("Partial Changes Rolled Back: True")
    print("Original Roadmap Preserved: True")

    print("\nTransactional Rollback: PASSED")

    # ==========================================
    # 18. Actual Groq Adaptation
    # ==========================================

    print_section(
        "GENERATE ACTUAL AI ROADMAP ADAPTATION"
    )

    result = adapt_personalized_roadmap(
        enrollment
    )

    print_json(result)

    assert not result["already_adapted"]

    assert result["completed_day"] == 1

    assert result["current_day"] == 2

    assert result["considered_days"] == 5

    assert (
        result["updated_count"]
        + result["unchanged_count"]
        == 5
    )

    # Day 4 must change from intermediate to basic.

    assert result["updated_count"] >= 1

    print("\nActual AI Adaptation: PASSED")

    # ==========================================
    # 19. Verify Roadmap Changes
    # ==========================================

    print_section(
        "ADAPTED ROADMAP VERIFICATION"
    )

    updated_roadmap = capture_roadmap(
        enrollment
    )

    assert len(updated_roadmap) == 30

    assert (
        set(original_roadmap)
        == set(updated_roadmap)
    )

    allowed_fields = {
        "title",
        "difficulty",
        "learning_objectives",
        "estimated_minutes",
        "updated_at",
    }

    changed_days = []

    for day_id, before in original_roadmap.items():

        after = updated_roadmap[day_id]

        if day_id not in adaptable_ids:

            assert before == after, (
                f"Protected Day "
                f"{before['day_number']} was modified."
            )

            continue

        changed_fields = {
            field
            for field in before
            if before[field] != after[field]
        }

        assert changed_fields.issubset(
            allowed_fields
        )

        assert before["topic"] == after["topic"]

        assert (
            before["day_number"]
            == after["day_number"]
        )

        if changed_fields:

            changed_days.append(
                after["day_number"]
            )

        print(
            f"\nDay {after['day_number']}"
        )

        print(f"Topic: {after['topic']}")

        print(f"Before Title: {before['title']}")
        print(f"After Title: {after['title']}")

        print(
            f"Difficulty: "
            f"{before['difficulty']} -> "
            f"{after['difficulty']}"
        )

        print(
            f"Duration: "
            f"{before['estimated_minutes']} -> "
            f"{after['estimated_minutes']} minutes"
        )

    assert (
        len(changed_days)
        == result["updated_count"]
    )

    assert 4 in changed_days

    print("\nRoadmap Structure Preserved: True")

    print("Protected Learning Days Unchanged: True")

    print("\nAdapted Roadmap Verification: PASSED")

    # ==========================================
    # 20. Verify Difficulty Adaptation
    # ==========================================

    print_section(
        "DIFFICULTY ADAPTATION VERIFICATION"
    )

    expected_difficulties = {
        2: ("basic", "intermediate"),
        3: ("basic",),
        4: ("basic",),
        5: ("basic",),
        6: ("basic",),
    }

    for day in LearningDay.objects.filter(
        enrollment=enrollment,
        day_number__range=(2, 6),
    ).order_by("day_number"):

        assert (
            day.difficulty
            in expected_difficulties[day.day_number]
        )

        print(
            f"Day {day.day_number}: "
            f"{day.difficulty}"
        )

    print("\nDifficulty Adaptation: PASSED")

    # ==========================================
    # 21. Verify Learning Progress Protection
    # ==========================================

    print_section(
        "LEARNING PROGRESS PROTECTION"
    )

    enrollment.refresh_from_db()

    assert enrollment.current_day == 2

    assert enrollment.status == "active"

    completed_count = DayProgress.objects.filter(
        learning_day__enrollment=enrollment,
        status="completed",
    ).count()

    unlocked_count = DayProgress.objects.filter(
        learning_day__enrollment=enrollment,
        status="unlocked",
    ).count()

    locked_count = DayProgress.objects.filter(
        learning_day__enrollment=enrollment,
        status="locked",
    ).count()

    assert completed_count == 1
    assert unlocked_count == 1
    assert locked_count == 28

    print(f"Completed Days: {completed_count}")
    print(f"Unlocked Days: {unlocked_count}")
    print(f"Locked Days: {locked_count}")

    print("\nLearning Progress Protection: PASSED")

    # ==========================================
    # 22. Verify Existing Data Preservation
    # ==========================================

    print_section(
        "EXISTING DATA PRESERVATION"
    )

    current_records = (
        capture_protected_records(enrollment)
    )

    for key in protected_records:

        unchanged = (
            protected_records[key]
            == current_records[key]
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
    # 23. Verify Adaptation Job
    # ==========================================

    print_section(
        "ADAPTATION JOB VERIFICATION"
    )

    job = AIGenerationJob.objects.get(
        idempotency_key=job_key
    )

    assert job.status == "completed"

    assert job.job_type == "roadmap_adaptation"

    assert (
        job.attempt_count
        == original_attempt_count + 3
    )

    assert job.completed_at is not None

    assert not job.error_message

    assert job.response_data == result

    print(f"Job ID: {job.id}")
    print(f"Job Type: {job.job_type}")
    print(f"Job Status: {job.status}")
    print(f"Attempt Count: {job.attempt_count}")

    print("\nAdaptation Job Verification: PASSED")

    # ==========================================
    # 24. Duplicate Adaptation Protection
    # ==========================================

    print_section(
        "DUPLICATE ADAPTATION PROTECTION"
    )

    state_before_duplicate = capture_roadmap(
        enrollment
    )

    attempts_before_duplicate = job.attempt_count

    with patch(
        "learning.services.adaptive_roadmap_service."
        "generate_response",
        side_effect=AssertionError(
            "Duplicate adaptation must not call Groq."
        ),
    ) as mocked_groq:

        repeated_result = (
            adapt_personalized_roadmap(
                enrollment
            )
        )

        assert not mocked_groq.called

    assert repeated_result["already_adapted"]

    assert (
        repeated_result["updated_days"]
        == result["updated_days"]
    )

    assert (
        capture_roadmap(enrollment)
        == state_before_duplicate
    )

    job.refresh_from_db()

    assert (
        job.attempt_count
        == attempts_before_duplicate
    )

    assert (
        AIGenerationJob.objects.filter(
            enrollment=enrollment
        ).count()
        == expected_job_count
    )

    print("Existing Adaptation Reused: True")
    print("Additional Groq Calls: 0")
    print("Additional Job Attempts: 0")
    print("Roadmap Modified Again: False")

    print("\nDuplicate Adaptation Protection: PASSED")

    # ==========================================
    # 25. Adaptation History
    # ==========================================

    print_section(
        "ADAPTATION HISTORY VERIFICATION"
    )

    history = get_roadmap_adaptation_history(
        enrollment
    )

    print_json(history)

    matching_history = [
        item
        for item in history
        if item["job_id"] == job.id
    ]

    assert len(matching_history) == 1

    assert (
        matching_history[0]["completed_day"]
        == 1
    )

    assert (
        matching_history[0]["updated_count"]
        == result["updated_count"]
    )

    print("\nAdaptation History: PASSED")

    # ==========================================
    # 26. Final Eligibility Check
    # ==========================================

    print_section(
        "FINAL ADAPTATION ELIGIBILITY"
    )

    final_eligibility = (
        get_adaptation_eligibility(enrollment)
    )

    assert not final_eligibility["eligible"]

    assert final_eligibility["already_adapted"]

    print(
        "Already Adapted: "
        f"{final_eligibility['already_adapted']}"
    )

    print_json(final_eligibility["reasons"])

    print("\nFinal Eligibility Check: PASSED")

    # ==========================================
    # 27. Final Test Summary
    # ==========================================

    print_section(
        "ADAPTIVE ROADMAP TEST PASSED!"
    )

    print(f"Enrollment ID: {enrollment.id}")
    print(f"Language: {enrollment.language}")
    print(f"Current Day: {enrollment.current_day}")

    print("Total Learning Days: 30")

    print(f"Completed Days: {completed_count}")
    print(f"Unlocked Days: {unlocked_count}")
    print(f"Locked Days: {locked_count}")

    print(
        f"\nConsidered Lessons: "
        f"{result['considered_days']}"
    )

    print(
        f"Updated Lessons: "
        f"{result['updated_count']}"
    )

    print(
        f"Unchanged Lessons in Window: "
        f"{result['unchanged_count']}"
    )

    print(f"Changed Days: {changed_days}")

    print("Protected Days: 25")

    print("\nAI Response Validation: PASSED")
    print("AI Failure Recovery: PASSED")
    print("Transactional Rollback: PASSED")
    print("Difficulty Adaptation: PASSED")
    print("Existing Data Preservation: PASSED")
    print("Duplicate Adaptation: PASSED")
    print("Adaptation History: PASSED")

    print(f"\nAI Job Status: {job.status}")
    print(f"AI Job Attempts: {job.attempt_count}")

    print(
        "\nPersonalized roadmap is ready "
        "for the next learning day."
    )


if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print_section(
            "ADAPTIVE ROADMAP TEST FAILED!"
        )

        print(f"Error: {error}")

        print(
            "\nInspect the error before continuing."
        )

        print(
            "If actual adaptation succeeded, "
            "roadmap changes may already "
            "have been committed."
        )

        raise