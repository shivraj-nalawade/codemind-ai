import os
import sys

import django

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

django.setup()

from django.contrib.auth import get_user_model

from learning.models import (
    Enrollment,
    LearningDay,
    DayProgress,
    AIGenerationJob,
)

from learning.services.lesson_service import (
    generate_daily_lesson,
    build_lesson_context,
    validate_lesson,
    LessonGenerationError,
)


User = get_user_model()


def main():

    print("\n" + "=" * 60)
    print("CODEMIND AI - DAILY LESSON GENERATION TEST")
    print("=" * 60)

    # ==========================================
    # 1. Retrieve Existing User
    # ==========================================

    user = User.objects.filter(
        is_superuser=True
    ).first()

    if not user:

        print("No superuser found.")
        sys.exit(1)

    # ==========================================
    # 2. Retrieve Python Enrollment
    # ==========================================

    enrollment = Enrollment.objects.filter(
        user=user,
        language="python",
    ).first()

    if not enrollment:

        print("Python enrollment not found.")
        sys.exit(1)

    print(f"\nUser: {user.username}")
    print(f"Language: {enrollment.get_language_display()}")
    print(f"Skill Level: {enrollment.skill_level}")
    print(f"Enrollment Status: {enrollment.status}")
    print(f"Current Day: {enrollment.current_day}")

    assert enrollment.status == "active", (
        "Enrollment must be active."
    )

    # ==========================================
    # 3. Retrieve Day 1
    # ==========================================

    learning_day = LearningDay.objects.filter(
        enrollment=enrollment,
        day_number=1,
    ).first()

    if not learning_day:

        print("Day 1 not found.")
        sys.exit(1)

    progress = DayProgress.objects.get(
        learning_day=learning_day
    )

    print("\n" + "=" * 60)
    print("LEARNING DAY DETAILS")
    print("=" * 60)

    print(f"Day Number: {learning_day.day_number}")
    print(f"Title: {learning_day.title}")
    print(f"Topic: {learning_day.topic}")
    print(f"Difficulty: {learning_day.difficulty}")
    print(f"Estimated Time: {learning_day.estimated_minutes} minutes")
    print(f"Progress Status: {progress.status}")
    print(f"Content Generated: {learning_day.is_content_generated}")

    print("\nLearning Objectives:")

    for objective in learning_day.learning_objectives:

        print(f"- {objective}")

    # Preserve original progress state
    original_progress = {
        "status": progress.status,
        "lesson_completed": progress.lesson_completed,
        "practical_completed": progress.practical_completed,
        "assessment_completed": progress.assessment_completed,
        "best_score": progress.best_score,
    }

    original_current_day = enrollment.current_day

    # ==========================================
    # 4. Verify Personalized Lesson Context
    # ==========================================

    context = build_lesson_context(
        learning_day
    )

    mastery = context["current_topic_mastery"]

    print("\n" + "=" * 60)
    print("PERSONALIZATION CONTEXT")
    print("=" * 60)

    print(f"Topic: {mastery['topic']}")
    print(f"Initial Score: {mastery['initial_score']}")
    print(f"Mastery Score: {mastery['mastery_score']}")

    print(
        "Recommended Difficulty:",
        mastery["recommended_difficulty"],
    )

    print(
        "Previously Assessed:",
        mastery["previously_assessed"],
    )

    print("\nLearner Strengths:")

    for strength in context["learner_profile"]["strengths"]:

        print(f"- {strength}")

    print("\nLearner Weaknesses:")

    for weakness in context["learner_profile"]["weaknesses"]:

        print(f"- {weakness}")

    print(
        "\nPrevious Completed Days:",
        len(context["previous_performance"]),
    )

    print(
        "Previous Assessment Feedback:",
        len(context["recent_assessment_feedback"]),
    )

    # ==========================================
    # 5. Generate Daily Lesson
    # ==========================================

    print("\n" + "=" * 60)
    print("GENERATING PERSONALIZED LESSON")
    print("=" * 60)

    try:

        lesson = generate_daily_lesson(
            learning_day
        )

    except LessonGenerationError as error:

        print(f"\nLesson Generation Error: {error}")

        print(
            "Existing roadmap and learning "
            "progress are preserved."
        )

        job = AIGenerationJob.objects.filter(
            idempotency_key=(
                f"daily_lesson_{learning_day.id}"
            )
        ).first()

        if job:

            print(f"Job Status: {job.status}")
            print(f"Job Attempts: {job.attempt_count}")
            print(f"Job Error: {job.error_message}")

        sys.exit(1)

    lesson.refresh_from_db()

    # ==========================================
    # 6. Display Generated Explanation
    # ==========================================

    print("\n" + "=" * 60)
    print("GENERATED LESSON EXPLANATION")
    print("=" * 60)

    print(f"\nDay: {lesson.day_number}")
    print(f"Title: {lesson.title}")
    print(f"Topic: {lesson.topic}")
    print(f"Difficulty: {lesson.difficulty}")

    print("\n" + lesson.explanation)

    # ==========================================
    # 7. Display Generated Code Examples
    # ==========================================

    print("\n" + "=" * 60)
    print("GENERATED CODE EXAMPLES")
    print("=" * 60)

    for index, example in enumerate(
        lesson.code_examples,
        start=1,
    ):

        print(f"\nEXAMPLE {index}")
        print("-" * 60)

        print(f"Title: {example['title']}")

        print(
            f"Description: "
            f"{example['description']}"
        )

        print(f"Language: {example['language']}")

        print("\nCode:")
        print(example["code"])

        print("\nExpected Output:")
        print(example["expected_output"])

        print("\nExplanation:")
        print(example["explanation"])

        print("-" * 60)

    # ==========================================
    # 8. Display Generated Practical Tasks
    # ==========================================

    print("\n" + "=" * 60)
    print("GENERATED PRACTICAL TASKS")
    print("=" * 60)

    for index, task in enumerate(
        lesson.practical_tasks,
        start=1,
    ):

        print(f"\nPRACTICAL TASK {index}")
        print("-" * 60)

        print(f"Title: {task['title']}")
        print(f"Difficulty: {task['difficulty']}")

        print("\nDescription:")
        print(task["description"])

        print("\nRequirements:")

        for requirement in task["requirements"]:

            print(f"- {requirement}")

        print("\nSample Input:")
        print(task["sample_input"])

        print("\nExpected Output:")
        print(task["expected_output"])

        print("\nHints:")

        for hint in task["hints"]:

            print(f"- {hint}")

        print("-" * 60)

    # ==========================================
    # 9. Verify Database Storage
    # ==========================================

    saved_lesson = LearningDay.objects.get(
        pk=lesson.pk
    )

    job = AIGenerationJob.objects.get(
        idempotency_key=(
            f"daily_lesson_{lesson.id}"
        )
    )

    explanation_words = len(
        saved_lesson.explanation.split()
    )

    print("\n" + "=" * 60)
    print("LESSON DATABASE STATISTICS")
    print("=" * 60)

    print(
        "Content Generated:",
        saved_lesson.is_content_generated,
    )

    print(
        "Explanation Word Count:",
        explanation_words,
    )

    print(
        "Code Examples:",
        len(saved_lesson.code_examples),
    )

    print(
        "Practical Tasks:",
        len(saved_lesson.practical_tasks),
    )

    print(f"AI Job Type: {job.job_type}")
    print(f"AI Job Status: {job.status}")
    print(f"Job Attempts: {job.attempt_count}")

    # Validate saved content again
    saved_data = {
        "language": enrollment.language,
        "day_number": saved_lesson.day_number,
        "title": saved_lesson.title,
        "explanation": saved_lesson.explanation,
        "code_examples": saved_lesson.code_examples,
        "practical_tasks": saved_lesson.practical_tasks,
    }

    validate_lesson(
        saved_data,
        saved_lesson,
    )

    print("Saved Lesson Validation: Passed")

    # ==========================================
    # 10. Test Duplicate Generation Prevention
    # ==========================================

    print("\n" + "=" * 60)
    print("DUPLICATE GENERATION TEST")
    print("=" * 60)

    original_attempt_count = job.attempt_count

    original_explanation = saved_lesson.explanation
    original_examples = saved_lesson.code_examples
    original_tasks = saved_lesson.practical_tasks

    repeated_lesson = generate_daily_lesson(
        saved_lesson
    )

    job.refresh_from_db()

    same_lesson = (
        repeated_lesson.id == saved_lesson.id
        and repeated_lesson.explanation == original_explanation
        and repeated_lesson.code_examples == original_examples
        and repeated_lesson.practical_tasks == original_tasks
    )

    additional_attempts = (
        job.attempt_count - original_attempt_count
    )

    print(f"Same Lesson Returned: {same_lesson}")

    print(
        "Additional Generation Attempts:",
        additional_attempts,
    )

    # ==========================================
    # 11. Test Locked Day Protection
    # ==========================================

    print("\n" + "=" * 60)
    print("LOCKED DAY ACCESS TEST")
    print("=" * 60)

    locked_day = LearningDay.objects.filter(
        enrollment=enrollment,
        day_number=2,
    ).first()

    assert locked_day is not None, (
        "Day 2 does not exist."
    )

    locked_progress = DayProgress.objects.get(
        learning_day=locked_day
    )

    print(f"Day Number: {locked_day.day_number}")
    print(f"Title: {locked_day.title}")
    print(f"Status: {locked_progress.status}")

    assert locked_progress.status == "locked", (
        "This test requires Day 2 to remain locked."
    )

    locked_job_count_before = (
        AIGenerationJob.objects.filter(
            idempotency_key=(
                f"daily_lesson_{locked_day.id}"
            )
        ).count()
    )

    locked_day_rejected = False

    try:

        generate_daily_lesson(
            locked_day
        )

        print("ERROR: Locked day generation was allowed.")

    except LessonGenerationError as error:

        locked_day_rejected = True

        print(f"Access Rejected: {error}")

    locked_day.refresh_from_db()

    locked_job_count_after = (
        AIGenerationJob.objects.filter(
            idempotency_key=(
                f"daily_lesson_{locked_day.id}"
            )
        ).count()
    )

    print(
        "Locked Day Protection:",
        locked_day_rejected,
    )

    print(
        "Locked Day Content Generated:",
        locked_day.is_content_generated,
    )

    print(
        "New AI Jobs for Locked Day:",
        locked_job_count_after - locked_job_count_before,
    )

    # ==========================================
    # 12. Verify Learning Progress Preservation
    # ==========================================

    print("\n" + "=" * 60)
    print("LEARNING PROGRESS VERIFICATION")
    print("=" * 60)

    progress.refresh_from_db()
    enrollment.refresh_from_db()

    current_progress = {
        "status": progress.status,
        "lesson_completed": progress.lesson_completed,
        "practical_completed": progress.practical_completed,
        "assessment_completed": progress.assessment_completed,
        "best_score": progress.best_score,
    }

    progress_preserved = (
        original_progress == current_progress
    )

    print(f"Day 1 Status: {progress.status}")

    print(
        "Lesson Completed:",
        progress.lesson_completed,
    )

    print(
        "Practical Completed:",
        progress.practical_completed,
    )

    print(
        "Assessment Completed:",
        progress.assessment_completed,
    )

    print(f"Current Day: {enrollment.current_day}")

    print(
        "Learning Progress Preserved:",
        progress_preserved,
    )

    total_days = LearningDay.objects.filter(
        enrollment=enrollment
    ).count()

    total_progress = DayProgress.objects.filter(
        learning_day__enrollment=enrollment
    ).count()

    generated_lessons = LearningDay.objects.filter(
        enrollment=enrollment,
        is_content_generated=True,
    ).count()

    unlocked_days = DayProgress.objects.filter(
        learning_day__enrollment=enrollment,
        status="unlocked",
    ).count()

    locked_days = DayProgress.objects.filter(
        learning_day__enrollment=enrollment,
        status="locked",
    ).count()

    print(f"Total Learning Days: {total_days}")
    print(f"Total Progress Records: {total_progress}")
    print(f"Generated Lessons: {generated_lessons}")
    print(f"Unlocked Days: {unlocked_days}")
    print(f"Locked Days: {locked_days}")

    # ==========================================
    # 13. Final Test Assertions
    # ==========================================

    assert saved_lesson.is_content_generated, (
        "Lesson content was not generated."
    )

    assert explanation_words >= 150, (
        "Lesson explanation is too short."
    )

    assert len(saved_lesson.code_examples) == 3, (
        "Expected exactly 3 code examples."
    )

    assert len(saved_lesson.practical_tasks) == 3, (
        "Expected exactly 3 practical tasks."
    )

    assert job.status == "completed", (
        "AI generation job was not completed."
    )

    assert job.job_type == "daily_lesson", (
        "Incorrect AI generation job type."
    )

    assert same_lesson, (
        "Duplicate generation prevention failed."
    )

    assert additional_attempts == 0, (
        "An unnecessary generation attempt occurred."
    )

    assert locked_day_rejected, (
        "Locked day protection failed."
    )

    assert not locked_day.is_content_generated, (
        "Content was generated for a locked day."
    )

    assert (
        locked_job_count_after == locked_job_count_before
    ), (
        "An AI job was created for a locked day."
    )

    assert progress_preserved, (
        "Lesson generation modified learning progress."
    )

    assert enrollment.current_day == original_current_day, (
        "Current learning day changed unexpectedly."
    )

    assert total_days == 30, (
        "Roadmap learning days were modified."
    )

    assert total_progress == 30, (
        "Roadmap progress records were modified."
    )

    assert generated_lessons == 1, (
        "Expected exactly one generated lesson."
    )

    assert unlocked_days == 1, (
        "Expected exactly one unlocked day."
    )

    assert locked_days == 29, (
        "Expected exactly 29 locked days."
    )

    print("\n" + "=" * 60)
    print("DAILY LESSON GENERATION TEST PASSED!")
    print("=" * 60)


if __name__ == "__main__":

    main()