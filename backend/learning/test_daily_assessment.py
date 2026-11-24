import os
import json

from collections import Counter

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
    Question,
    AssessmentAttempt,
    TopicMastery,
    AIGenerationJob,
)

from learning.services.daily_assessment_service import (
    DailyAssessmentGenerationError,
    build_daily_assessment_context,
    generate_daily_assessment,
    get_existing_daily_assessment,
    get_daily_assessment_for_learner,
    validate_daily_assessment,
    validate_question_repetition,
)

from learning.services.progress_service import (
    get_daily_progress_summary,
    check_daily_assessment_eligibility,
)


# ==========================================
# Helper: Print Section
# ==========================================

def print_section(title):

    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


# ==========================================
# Helper: Capture Existing Learning Data
# ==========================================

def capture_learning_state(enrollment):

    enrollment.refresh_from_db()

    return {
        "enrollment": (
            Enrollment.objects.filter(
                pk=enrollment.pk
            ).values().get()
        ),

        "learning_days": list(
            LearningDay.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),

        "progress_records": list(
            DayProgress.objects.filter(
                learning_day__enrollment=enrollment
            ).order_by("pk").values()
        ),

        "topic_mastery": list(
            TopicMastery.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),

        "assessment_attempts": list(
            AssessmentAttempt.objects.filter(
                assessment__enrollment=enrollment
            ).order_by("pk").values()
        ),

        "initial_assessments": list(
            Assessment.objects.filter(
                enrollment=enrollment,
                assessment_type="initial",
            ).order_by("pk").values()
        ),

        "initial_questions": list(
            Question.objects.filter(
                assessment__enrollment=enrollment,
                assessment__assessment_type="initial",
            ).order_by("pk").values()
        ),
    }


# ==========================================
# Helper: Verify Rejected Operation
# ==========================================

def expect_rejection(function, learning_day, label):

    try:

        function(learning_day)

    except DailyAssessmentGenerationError as error:

        print(f"{label}: PASSED")
        print(f"Reason: {error}")

        return

    raise AssertionError(
        f"{label}: Operation should have been rejected."
    )


# ==========================================
# Main Test
# ==========================================

def main():

    print_section(
        "CODEMIND AI - DAILY ASSESSMENT GENERATION TEST"
    )

    # ==========================================
    # 1. Retrieve Existing Enrollment
    # ==========================================

    enrollment = Enrollment.objects.select_related(
        "user"
    ).get(
        pk=1,
        language="python",
    )

    print(f"User: {enrollment.user.username}")

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

    assert day1.is_content_generated

    assert progress1.status == "in_progress"

    assert progress1.lesson_completed

    assert progress1.practical_completed

    assert not progress1.assessment_completed

    assert progress2.status == "locked"

    # Preserve existing learning information.
    original_state = capture_learning_state(
        enrollment
    )

    # ==========================================
    # 3. Verify Assessment Eligibility
    # ==========================================

    print_section(
        "ASSESSMENT ELIGIBILITY VERIFICATION"
    )

    eligibility = (
        check_daily_assessment_eligibility(
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

    assert eligibility["reasons"] == []

    print("\nAssessment Eligibility: PASSED")

    # ==========================================
    # 4. Verify Personalized Context
    # ==========================================

    print_section(
        "PERSONALIZED ASSESSMENT CONTEXT"
    )

    context = build_daily_assessment_context(
        day1
    )

    print(f"Day Number: {context['day_number']}")
    print(f"Topic: {context['topic']}")
    print(f"Difficulty: {context['difficulty']}")

    print(
        "Topic Mastery:",
        context["current_topic_mastery"][
            "mastery_score"
        ],
    )

    print(
        "Code Examples:",
        len(context["code_examples"]),
    )

    print(
        "Practical Tasks:",
        len(context["practical_tasks"]),
    )

    print(
        "Previous Questions:",
        len(context["previous_questions"]),
    )

    print("\nLearner Strengths:")

    for strength in context[
        "learner_profile"
    ]["strengths"]:

        print(f"- {strength}")

    print("\nLearner Weaknesses:")

    for weakness in context[
        "learner_profile"
    ]["weaknesses"]:

        print(f"- {weakness}")

    print("\nAssessment Configuration:")

    print(
        json.dumps(
            context["assessment_configuration"],
            indent=4,
        )
    )

    assert context["day_number"] == 1

    assert context["language"] == "python"

    assert context["topic"] == day1.topic

    assert len(context["code_examples"]) == 3

    assert len(context["practical_tasks"]) == 3

    assert len(context["previous_questions"]) == 15

    assert context[
        "assessment_configuration"
    ]["total_questions"] == 5

    print("\nPersonalized Context Test: PASSED")

    # ==========================================
    # 5. Generate Daily Assessment
    # ==========================================

    print_section(
        "GENERATING DAILY ASSESSMENT"
    )

    assessment = generate_daily_assessment(
        day1
    )

    assessment.refresh_from_db()

    print(f"\nAssessment ID: {assessment.id}")
    print(f"Title: {assessment.title}")
    print(f"Type: {assessment.assessment_type}")
    print(f"Day Number: {assessment.day_number}")

    print(
        f"Total Questions: "
        f"{assessment.total_questions}"
    )

    assert assessment.enrollment_id == enrollment.id

    assert assessment.assessment_type == "daily"

    assert assessment.day_number == 1

    assert assessment.total_questions == 5

    # ==========================================
    # 6. Retrieve Generated Questions
    # ==========================================

    questions = list(
        Question.objects.filter(
            assessment=assessment
        ).order_by("order")
    )

    print_section(
        "GENERATED ASSESSMENT QUESTIONS"
    )

    for question in questions:

        print(f"\nQUESTION {question.order}")
        print("-" * 60)

        print(f"Question ID: {question.id}")

        print(
            f"Type: "
            f"{question.get_question_type_display()}"
        )

        print(f"Topic: {question.topic}")
        print(f"Difficulty: {question.difficulty}")
        print(f"Marks: {question.marks}")

        print("\nQuestion:")
        print(question.question_text)

        if question.question_type == "mcq":

            print("\nOptions:")

            for index, option in enumerate(
                question.options
            ):

                option_label = chr(65 + index)

                print(
                    f"{option_label}. {option}"
                )

            print("\nCorrect Answer:")

        else:

            print("\nReference Answer:")

        print(question.correct_answer)

        print("\nAnswer Explanation:")
        print(question.explanation)

        print("-" * 60)

    # ==========================================
    # 7. Verify Question Distribution
    # ==========================================

    print_section(
        "QUESTION DISTRIBUTION TEST"
    )

    question_counts = Counter(
        question.question_type
        for question in questions
    )

    difficulty_counts = Counter(
        question.difficulty
        for question in questions
    )

    total_marks = sum(
        question.marks
        for question in questions
    )

    print(f"Total Questions: {len(questions)}")
    print(f"MCQs: {question_counts['mcq']}")
    print(f"Coding Questions: {question_counts['coding']}")
    print(f"Theory Questions: {question_counts['theory']}")
    print(f"Total Marks: {total_marks}")

    print("\nDifficulty Distribution:")

    for difficulty, count in (
        difficulty_counts.items()
    ):

        print(f"- {difficulty}: {count}")

    assert len(questions) == 5

    assert question_counts["mcq"] == 3

    assert question_counts["coding"] == 1

    assert question_counts["theory"] == 1

    assert total_marks == 9

    assert [
        question.order
        for question in questions
    ] == [1, 2, 3, 4, 5]

    assert [
        question.question_type
        for question in questions
    ] == [
        "mcq",
        "mcq",
        "mcq",
        "coding",
        "theory",
    ]

    for question in questions:

        assert question.topic == day1.topic

        assert question.difficulty in [
            "basic",
            "intermediate",
        ]

        if question.question_type == "mcq":

            assert len(question.options) == 4

            assert (
                question.correct_answer
                in question.options
            )

            assert question.marks == 1

        else:

            assert question.options == []

            assert question.marks == 3

    print("\nQuestion Distribution Test: PASSED")

    # ==========================================
    # 8. Validate Saved Assessment
    # ==========================================

    print_section(
        "SAVED ASSESSMENT VALIDATION"
    )

    saved_data = {
        "language": enrollment.language,
        "day_number": assessment.day_number,
        "questions": [
            {
                "question_type": question.question_type,
                "topic": question.topic,
                "difficulty": question.difficulty,
                "question_text": question.question_text,
                "options": question.options,
                "correct_answer": question.correct_answer,
                "explanation": question.explanation,
                "marks": question.marks,
            }
            for question in questions
        ],
    }

    validate_daily_assessment(
        saved_data,
        day1,
    )

    validate_question_repetition(
        saved_data,
        context,
    )

    saved_assessment = (
        get_existing_daily_assessment(
            day1
        )
    )

    assert saved_assessment is not None

    assert saved_assessment.id == assessment.id

    print("Saved Assessment Structure: Valid")
    print("Question Count: Valid")
    print("Question Order: Valid")
    print("Question Difficulty: Valid")
    print("Marking Scheme: Valid")
    print("Exact Question Repetition Check: Passed")

    print("\nSaved Assessment Validation: PASSED")

    # ==========================================
    # 9. Verify AI Generation Job
    # ==========================================

    print_section(
        "AI GENERATION JOB VERIFICATION"
    )

    job = AIGenerationJob.objects.get(
        idempotency_key=(
            f"daily_assessment_{day1.id}"
        )
    )

    print(f"Job ID: {job.id}")
    print(f"Job Type: {job.job_type}")
    print(f"Job Status: {job.status}")
    print(f"Job Attempts: {job.attempt_count}")
    print(f"Error Message: {job.error_message}")

    assert job.job_type == "daily_assessment"

    assert job.status == "completed"

    assert job.completed_at is not None

    assert not job.error_message

    assert (
        job.response_data["assessment_id"]
        == assessment.id
    )

    print("\nAI Generation Job Test: PASSED")

    # ==========================================
    # 10. Verify Learner-Safe Assessment Data
    # ==========================================

    print_section(
        "ANSWER PROTECTION TEST"
    )

    learner_data = (
        get_daily_assessment_for_learner(
            day1
        )
    )

    print(
        json.dumps(
            learner_data,
            indent=4,
            ensure_ascii=False,
        )
    )

    allowed_top_level_fields = {
        "assessment_id",
        "title",
        "assessment_type",
        "day_number",
        "language",
        "total_questions",
        "total_marks",
        "questions",
    }

    allowed_question_fields = {
        "question_id",
        "order",
        "question_type",
        "topic",
        "difficulty",
        "question_text",
        "options",
        "marks",
    }

    assert set(learner_data.keys()) == (
        allowed_top_level_fields
    )

    assert learner_data["total_questions"] == 5

    assert learner_data["total_marks"] == 9

    assert len(learner_data["questions"]) == 5

    for question in learner_data["questions"]:

        assert set(question.keys()) == (
            allowed_question_fields
        )

        assert "correct_answer" not in question

        assert "explanation" not in question

        assert "reference_answer" not in question

        assert "ai_feedback" not in question

    print("\nCorrect Answer Fields Exposed: False")
    print("Reference Answer Fields Exposed: False")
    print("Answer Explanation Fields Exposed: False")
    print("AI Job Response Exposed: False")

    print("\nAnswer Protection Test: PASSED")

    # ==========================================
    # 11. Duplicate Generation Prevention
    # ==========================================

    print_section(
        "DUPLICATE GENERATION TEST"
    )

    original_attempt_count = job.attempt_count

    original_questions = list(
        Question.objects.filter(
            assessment=assessment
        ).order_by("pk").values()
    )

    repeated_assessment = (
        generate_daily_assessment(
            day1
        )
    )

    job.refresh_from_db()

    repeated_questions = list(
        Question.objects.filter(
            assessment=repeated_assessment
        ).order_by("pk").values()
    )

    same_assessment = (
        repeated_assessment.id == assessment.id
    )

    same_questions = (
        original_questions == repeated_questions
    )

    additional_attempts = (
        job.attempt_count
        - original_attempt_count
    )

    assessment_count = Assessment.objects.filter(
        enrollment=enrollment,
        assessment_type="daily",
        day_number=1,
    ).count()

    print(f"Same Assessment Returned: {same_assessment}")
    print(f"Same Questions Returned: {same_questions}")

    print(
        "Additional Generation Attempts:",
        additional_attempts,
    )

    print(
        "Daily Assessment Records:",
        assessment_count,
    )

    assert same_assessment

    assert same_questions

    assert additional_attempts == 0

    assert assessment_count == 1

    print("\nDuplicate Generation Test: PASSED")

    # ==========================================
    # 12. Locked Day Protection
    # ==========================================

    print_section(
        "LOCKED DAY ASSESSMENT PROTECTION"
    )

    locked_job_key = (
        f"daily_assessment_{day2.id}"
    )

    original_locked_jobs = (
        AIGenerationJob.objects.filter(
            idempotency_key=locked_job_key
        ).count()
    )

    expect_rejection(
        generate_daily_assessment,
        day2,
        "Generate Locked Day Assessment",
    )

    expect_rejection(
        get_daily_assessment_for_learner,
        day2,
        "Retrieve Locked Day Assessment",
    )

    current_locked_jobs = (
        AIGenerationJob.objects.filter(
            idempotency_key=locked_job_key
        ).count()
    )

    locked_assessment_count = (
        Assessment.objects.filter(
            enrollment=enrollment,
            assessment_type="daily",
            day_number=2,
        ).count()
    )

    assert (
        current_locked_jobs
        == original_locked_jobs
    )

    assert locked_assessment_count == 0

    print(
        "\nNew AI Jobs for Locked Day:",
        current_locked_jobs - original_locked_jobs,
    )

    print(
        "Locked Day Assessment Records:",
        locked_assessment_count,
    )

    print("\nLocked Day Protection: PASSED")

    # ==========================================
    # 13. Verify Existing Data Preservation
    # ==========================================

    print_section(
        "EXISTING DATA PRESERVATION TEST"
    )

    current_state = capture_learning_state(
        enrollment
    )

    for key in original_state:

        unchanged = (
            original_state[key]
            == current_state[key]
        )

        print(
            f"{key.replace('_', ' ').title()} "
            f"Unchanged: {unchanged}"
        )

        assert unchanged, (
            f"Existing data was modified: {key}"
        )

    print("\nExisting Data Preservation: PASSED")

    # ==========================================
    # 14. Verify Final Learning Progress
    # ==========================================

    print_section(
        "FINAL LEARNING PROGRESS STATE"
    )

    summary = get_daily_progress_summary(
        day1
    )

    print(
        json.dumps(
            summary,
            indent=4,
        )
    )

    progress2.refresh_from_db()
    enrollment.refresh_from_db()

    assert summary["status"] == "in_progress"

    assert summary["lesson_completed"]

    assert summary["practical_completed"]

    assert not summary["assessment_completed"]

    assert summary["assessment_eligible"]

    assert summary["completion_percentage"] == 66.67

    assert progress2.status == "locked"

    assert enrollment.current_day == 1

    assert enrollment.status == "active"

    print("\nDay 2 Status: locked")

    print(
        "Assessment Generated: True"
    )

    print(
        "Assessment Attempt Started: False"
    )

    print(
        "Daily Completion: 66.67%"
    )

    # ==========================================
    # 15. Final Test Result
    # ==========================================

    print_section(
        "DAILY ASSESSMENT GENERATION TEST PASSED!"
    )

    print("\nAssessment ID:", assessment.id)

    print("Total Questions: 5")
    print("MCQs: 3")
    print("Coding Questions: 1")
    print("Theory Questions: 1")
    print("Total Marks: 9")

    print(
        "\nDaily assessment is ready "
        "for learner submission and evaluation."
    )


if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print_section(
            "DAILY ASSESSMENT GENERATION TEST FAILED!"
        )

        print(f"Error: {error}")

        print(
            "\nInspect the error before continuing."
        )

        print(
            "Successfully committed assessment records "
            "may already exist in the database."
        )

        raise