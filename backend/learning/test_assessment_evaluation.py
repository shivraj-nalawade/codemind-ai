import os

import django

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

django.setup()

from django.contrib.auth import get_user_model

from learning.models import (
    Enrollment,
    Assessment,
    AssessmentAttempt,
    Question,
    TopicMastery,
    AIGenerationJob,
)

from learning.services.evaluation_service import (
    start_assessment_attempt,
    save_user_answer,
    submit_assessment,
    evaluate_initial_assessment,
    AssessmentEvaluationError,
)


def main():

    print("\n" + "=" * 60)
    print("CODEMIND AI - ASSESSMENT EVALUATION TEST")
    print("=" * 60)

    # ==========================================
    # 1. Retrieve Existing Enrollment
    # ==========================================

    User = get_user_model()

    user = User.objects.filter(
        is_superuser=True
    ).first()

    if not user:
        print("No superuser found.")
        return

    enrollment = Enrollment.objects.filter(
        user=user,
        language="python"
    ).first()

    if not enrollment:
        print("Python enrollment not found.")
        return

    print("\nUser:", user.username)
    print("Language:", enrollment.get_language_display())

    # ==========================================
    # 2. Retrieve Initial Assessment
    # ==========================================

    assessment = Assessment.objects.filter(
        enrollment=enrollment,
        assessment_type="initial",
        day_number=0,
    ).first()

    if not assessment:
        print("Initial assessment not found.")
        return

    questions = list(
        assessment.questions.all()
    )

    print("Assessment:", assessment.title)
    print("Total Questions:", len(questions))

    # ==========================================
    # 3. Create or Resume Assessment Attempt
    # ==========================================

    existing_attempt = assessment.attempts.order_by(
        "-attempt_number"
    ).first()

    if existing_attempt:

        attempt = existing_attempt

        print("\nExisting attempt found.")

    else:

        attempt = start_assessment_attempt(
            assessment
        )

        print("\nNew attempt created.")

    print("Attempt ID:", attempt.id)
    print("Attempt Number:", attempt.attempt_number)
    print("Total Marks:", attempt.total_marks)
    print("Status:", attempt.status)

    # ==========================================
    # 4. Simulate Learner Answers
    # ==========================================

    if attempt.status == AssessmentAttempt.Status.IN_PROGRESS:

        print("\nSaving sample learner answers...")

        mcq_number = 0
        written_number = 0

        for question in questions:

            if question.question_type == Question.QuestionType.MCQ:

                mcq_number += 1

                # Simulate 8 correct and 4 incorrect MCQs
                if mcq_number <= 8:

                    submitted_answer = (
                        question.correct_answer
                    )

                else:

                    submitted_answer = next(
                        option
                        for option in question.options
                        if option != question.correct_answer
                    )

            else:

                written_number += 1

                if written_number == 1:

                    # Simulate a correct written answer
                    submitted_answer = (
                        question.correct_answer
                    )

                elif written_number == 2:

                    # Simulate an uncertain learner
                    submitted_answer = (
                        "I understand the basic concept, "
                        "but I am unable to explain "
                        "the complete solution."
                    )

                else:

                    # Simulate an incorrect answer
                    submitted_answer = (
                        "I do not know how to solve "
                        "this question."
                    )

            save_user_answer(
                attempt=attempt,
                question_id=question.id,
                submitted_answer=submitted_answer,
            )

            print(
                f"Q{question.order}: "
                f"{question.question_type.upper()} "
                f"- Answer saved"
            )

        # ==========================================
        # 5. Submit Assessment
        # ==========================================

        attempt = submit_assessment(attempt)

        print("\nAssessment submitted successfully.")
        print("Saved Answers:", attempt.answers.count())

    # ==========================================
    # 6. Evaluate Complete Assessment
    # ==========================================

    if attempt.status == AssessmentAttempt.Status.EVALUATED:

        result = attempt

        print("\nUsing existing evaluation result.")

    else:

        print("\nStarting assessment evaluation...")
        print("Evaluating MCQs and written answers.")
        print("Please wait for Groq AI responses...")

        result = evaluate_initial_assessment(
            attempt
        )

    # ==========================================
    # 7. Display Final Result
    # ==========================================

    enrollment.refresh_from_db()

    print("\n" + "=" * 60)
    print("FINAL ASSESSMENT RESULT")
    print("=" * 60)

    print("Status:", result.status)
    print("Total Marks:", result.total_marks)
    print("Obtained Marks:", result.obtained_marks)
    print("Percentage:", result.percentage)
    print("Skill Level:", enrollment.skill_level)

    # ==========================================
    # 8. Display Individual Answer Evaluation
    # ==========================================

    print("\n" + "=" * 60)
    print("INDIVIDUAL QUESTION RESULTS")
    print("=" * 60)

    answers = result.answers.select_related(
        "question"
    ).order_by("question__order")

    for answer in answers:

        question = answer.question

        print(f"\nQuestion {question.order}")
        print("Topic:", question.topic)
        print("Type:", question.question_type)

        print(
            "Marks:",
            f"{answer.marks_awarded}/{question.marks}"
        )

        print("Evaluated:", answer.is_evaluated)
        print("Feedback:", answer.ai_feedback)

    # ==========================================
    # 9. Display Strengths and Weaknesses
    # ==========================================

    print("\n" + "=" * 60)
    print("LEARNER PROFILE")
    print("=" * 60)

    print("\nStrengths:")

    for topic in result.strengths:
        print("-", topic)

    print("\nWeaknesses:")

    for topic in result.weaknesses:
        print("-", topic)

    print("\nAI Feedback:")
    print(result.ai_feedback)

    print("\nRecommendations:")

    for recommendation in result.recommendations:
        print("-", recommendation)

    # ==========================================
    # 10. Display Topic Mastery
    # ==========================================

    print("\n" + "=" * 60)
    print("TOPIC MASTERY")
    print("=" * 60)

    masteries = TopicMastery.objects.filter(
        enrollment=enrollment
    ).order_by("-mastery_score")

    for mastery in masteries:

        print(
            f"{mastery.topic}: "
            f"{mastery.mastery_score}% "
            f"| Recommended difficulty: "
            f"{mastery.recommended_difficulty}"
        )

    # ==========================================
    # 11. Verify AI Generation Job
    # ==========================================

    job = AIGenerationJob.objects.filter(
        idempotency_key=(
            f"assessment_evaluation_{result.id}"
        )
    ).first()

    if job:

        print("\nAI Evaluation Job Status:", job.status)
        print("Job Attempts:", job.attempt_count)

    # ==========================================
    # 12. Validate Final Results
    # ==========================================

    assert result.status == "evaluated"
    assert result.answers.count() == 15
    assert result.answers.filter(
        is_evaluated=False
    ).count() == 0
    assert result.total_marks == 21
    assert 0 <= result.obtained_marks <= 21
    assert 0 <= result.percentage <= 100
    assert enrollment.skill_level != "unassessed"
    assert masteries.exists()
    assert job is not None
    assert job.status == "completed"

    print("\n" + "=" * 60)
    print("ASSESSMENT EVALUATION TEST PASSED!")
    print("=" * 60)


if __name__ == "__main__":

    try:

        main()

    except AssessmentEvaluationError as error:

        print("\nEvaluation Error:", error)
        print("Saved learner answers are preserved.")
        print("Run the test again if evaluation failed.")

        raise SystemExit(1)