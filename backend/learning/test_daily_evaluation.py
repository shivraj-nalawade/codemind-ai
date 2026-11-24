import os
import json
import math

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

from learning.services.daily_evaluation_service import (
    DailyEvaluationError,
    start_daily_assessment_attempt,
    save_daily_answer,
    save_daily_answers,
    submit_daily_assessment,
    evaluate_daily_assessment,
    get_daily_attempt_summary,
    get_daily_assessment_result,
    calculate_daily_assessment_score,
)

from learning.services.progress_service import (
    get_daily_progress_summary,
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

def expect_rejection(label, function, *args, **kwargs):

    try:

        function(*args, **kwargs)

    except DailyEvaluationError as error:

        print(f"{label}: PASSED")
        print(f"Reason: {error}")

        return

    raise AssertionError(
        f"{label}: Operation should have been rejected."
    )


# ==========================================
# Helper: Capture Existing Learning State
# ==========================================

def capture_learning_state(enrollment):

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

        "initial_assessment_attempts": list(
            AssessmentAttempt.objects.filter(
                assessment__enrollment=enrollment,
                assessment__assessment_type="initial",
            ).order_by("pk").values()
        ),

        "initial_answers": list(
            UserAnswer.objects.filter(
                attempt__assessment__enrollment=enrollment,
                attempt__assessment__assessment_type="initial",
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

        "existing_generation_jobs": list(
            AIGenerationJob.objects.filter(
                enrollment=enrollment
            ).exclude(
                idempotency_key__startswith=(
                    "daily_assessment_evaluation_"
                )
            ).order_by("pk").values()
        ),
    }


# ==========================================
# Main Test
# ==========================================

def main():

    print_section(
        "CODEMIND AI - DAILY ASSESSMENT EVALUATION TEST"
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

    assert progress1.status == "in_progress"
    assert progress1.lesson_completed
    assert progress1.practical_completed
    assert not progress1.assessment_completed
    assert progress2.status == "locked"

    original_state = capture_learning_state(
        enrollment
    )

    # ==========================================
    # 3. Retrieve Daily Assessment
    # ==========================================

    print_section(
        "DAILY ASSESSMENT VERIFICATION"
    )

    assessment = Assessment.objects.get(
        enrollment=enrollment,
        assessment_type="daily",
        day_number=1,
    )

    questions = list(
        Question.objects.filter(
            assessment=assessment
        ).order_by("order")
    )

    print(f"Assessment ID: {assessment.id}")
    print(f"Title: {assessment.title}")
    print(f"Questions: {len(questions)}")

    total_marks = sum(
        question.marks
        for question in questions
    )

    print(f"Total Marks: {total_marks}")

    assert len(questions) == 5
    assert total_marks == 9

    assert sum(
        question.question_type == "mcq"
        for question in questions
    ) == 3

    assert sum(
        question.question_type == "coding"
        for question in questions
    ) == 1

    assert sum(
        question.question_type == "theory"
        for question in questions
    ) == 1

    print("\nAssessment Verification: PASSED")

    # ==========================================
    # 4. Locked Day Protection
    # ==========================================

    print_section(
        "LOCKED DAY PROTECTION TEST"
    )

    expect_rejection(
        "Start Locked Day Assessment",
        start_daily_assessment_attempt,
        day2,
    )

    print("\nLocked Day Protection: PASSED")

    # ==========================================
    # 5. Start or Resume Assessment Attempt
    # ==========================================

    print_section(
        "START DAILY ASSESSMENT ATTEMPT"
    )

    existing_attempt = (
        AssessmentAttempt.objects.filter(
            assessment=assessment
        ).order_by("-attempt_number").first()
    )

    fresh_attempt = existing_attempt is None

    if existing_attempt is None:

        attempt = start_daily_assessment_attempt(
            day1
        )

    else:

        attempt = existing_attempt

        print(
            "Existing assessment attempt found. "
            "Resuming test."
        )

    print(f"Attempt ID: {attempt.id}")
    print(f"Attempt Number: {attempt.attempt_number}")
    print(f"Status: {attempt.status}")
    print(f"Total Marks: {attempt.total_marks}")

    assert attempt.assessment_id == assessment.id
    assert attempt.total_marks == 9

    if attempt.status == "evaluating":

        raise RuntimeError(
            "Attempt is already evaluating. "
            "Inspect the existing AI job before retrying."
        )

    print("\nStart or Resume Attempt: PASSED")

    # ==========================================
    # 6. Duplicate Attempt Protection
    # ==========================================

    if attempt.status == "in_progress":

        print_section(
            "DUPLICATE ATTEMPT PROTECTION"
        )

        original_attempt_count = (
            AssessmentAttempt.objects.filter(
                assessment=assessment
            ).count()
        )

        repeated_attempt = (
            start_daily_assessment_attempt(day1)
        )

        current_attempt_count = (
            AssessmentAttempt.objects.filter(
                assessment=assessment
            ).count()
        )

        print(
            "Same Attempt Returned:",
            repeated_attempt.id == attempt.id,
        )

        print(
            "Additional Attempts:",
            current_attempt_count
            - original_attempt_count,
        )

        assert repeated_attempt.id == attempt.id

        assert (
            original_attempt_count
            == current_attempt_count
        )

        print("\nDuplicate Attempt Test: PASSED")

    # ==========================================
    # 7. Initial Attempt Summary
    # ==========================================

    print_section(
        "INITIAL ATTEMPT SUMMARY"
    )

    initial_summary = get_daily_attempt_summary(
        attempt
    )

    print_json(initial_summary)

    if fresh_attempt:

        assert initial_summary[
            "answered_questions"
        ] == 0

        assert initial_summary[
            "can_edit_answers"
        ]

        assert not initial_summary[
            "can_submit"
        ]

    # ==========================================
    # 8. Result Protection Before Evaluation
    # ==========================================

    if attempt.status != "evaluated":

        print_section(
            "PRE-EVALUATION RESULT PROTECTION"
        )

        expect_rejection(
            "Retrieve Unevaluated Result",
            get_daily_assessment_result,
            attempt,
        )

    # ==========================================
    # 9. Answer Submission Tests
    # ==========================================

    if attempt.status == "in_progress":

        print_section(
            "INCOMPLETE SUBMISSION PROTECTION"
        )

        if initial_summary["answered_questions"] < 5:

            expect_rejection(
                "Submit Incomplete Assessment",
                submit_daily_assessment,
                attempt,
            )

        else:

            print(
                "Skipped: All answers were "
                "already saved during an earlier run."
            )

        # --------------------------------------
        # Invalid Question Protection
        # --------------------------------------

        print_section(
            "INVALID QUESTION PROTECTION"
        )

        initial_question = Question.objects.filter(
            assessment__enrollment=enrollment,
            assessment__assessment_type="initial",
        ).first()

        assert initial_question is not None

        expect_rejection(
            "Save Answer From Another Assessment",
            save_daily_answer,
            attempt,
            initial_question.id,
            "Invalid cross-assessment answer",
        )

        # --------------------------------------
        # Invalid MCQ Option Protection
        # --------------------------------------

        print_section(
            "INVALID MCQ OPTION PROTECTION"
        )

        mcq_question = next(
            question
            for question in questions
            if question.question_type == "mcq"
        )

        invalid_option = "__INVALID_TEST_OPTION__"

        assert invalid_option not in (
            mcq_question.options
        )

        expect_rejection(
            "Save Invalid MCQ Option",
            save_daily_answer,
            attempt,
            mcq_question.id,
            invalid_option,
        )

        # --------------------------------------
        # Save Individual Answer
        # --------------------------------------

        print_section(
            "INDIVIDUAL ANSWER SAVING TEST"
        )

        first_question = questions[0]

        saved_answer = save_daily_answer(
            attempt=attempt,
            question_id=first_question.id,
            submitted_answer=(
                first_question.correct_answer
            ),
        )

        print(f"Answer ID: {saved_answer.id}")
        print(f"Question ID: {saved_answer.question_id}")

        print(
            "Submitted Answer:",
            saved_answer.submitted_answer,
        )

        print(
            "Is Evaluated:",
            saved_answer.is_evaluated,
        )

        assert (
            saved_answer.submitted_answer
            == first_question.correct_answer
        )

        assert not saved_answer.is_evaluated

        print("\nIndividual Answer Saving: PASSED")

        # --------------------------------------
        # Duplicate Answer Protection
        # --------------------------------------

        print_section(
            "DUPLICATE ANSWER PROTECTION"
        )

        repeated_answer = save_daily_answer(
            attempt=attempt,
            question_id=first_question.id,
            submitted_answer=(
                first_question.correct_answer
            ),
        )

        answer_count = UserAnswer.objects.filter(
            attempt=attempt,
            question=first_question,
        ).count()

        print(
            "Same Answer Record:",
            repeated_answer.id == saved_answer.id,
        )

        print(
            "Answer Records for Question:",
            answer_count,
        )

        assert repeated_answer.id == saved_answer.id
        assert answer_count == 1

        print("\nDuplicate Answer Test: PASSED")

        # --------------------------------------
        # Atomic Bulk Answer Protection
        # --------------------------------------

        print_section(
            "ATOMIC BULK ANSWER PROTECTION"
        )

        answers_before = list(
            UserAnswer.objects.filter(
                attempt=attempt
            ).order_by("pk").values()
        )

        invalid_bulk_answers = [
            {
                "question_id": first_question.id,
                "submitted_answer": (
                    first_question.correct_answer
                ),
            },
            {
                "question_id": first_question.id,
                "submitted_answer": (
                    first_question.correct_answer
                ),
            },
        ]

        expect_rejection(
            "Reject Duplicate Question IDs",
            save_daily_answers,
            attempt,
            invalid_bulk_answers,
        )

        answers_after = list(
            UserAnswer.objects.filter(
                attempt=attempt
            ).order_by("pk").values()
        )

        assert answers_before == answers_after

        print("Existing Answers Preserved: True")

        print("\nAtomic Bulk Protection: PASSED")

        # ==========================================
        # 10. Prepare Simulated Learner Answers
        # ==========================================

        print_section(
            "PREPARING SIMULATED LEARNER ANSWERS"
        )

        submitted_answers = []

        for question in questions:

            submitted_answer = question.correct_answer

            assert isinstance(submitted_answer, str)
            assert submitted_answer.strip()

            submitted_answers.append({
                "question_id": question.id,
                "submitted_answer": submitted_answer,
            })

            print(f"\nQuestion {question.order}")
            print(f"Type: {question.question_type}")

            print("Question:")
            print(question.question_text)

            print("\nSimulated Learner Answer:")
            print(submitted_answer)

        # ==========================================
        # 11. Save All Five Answers
        # ==========================================

        print_section(
            "BULK ANSWER SAVING TEST"
        )

        saved_answers = save_daily_answers(
            attempt,
            submitted_answers,
        )

        total_saved_answers = (
            UserAnswer.objects.filter(
                attempt=attempt
            ).count()
        )

        print(
            "Answers Returned:",
            len(saved_answers),
        )

        print(
            "Answers Saved in Database:",
            total_saved_answers,
        )

        assert len(saved_answers) == 5
        assert total_saved_answers == 5

        summary = get_daily_attempt_summary(
            attempt
        )

        print_json(summary)

        assert summary["answered_questions"] == 5

        assert summary[
            "answer_completion_percentage"
        ] == 100.0

        assert summary["can_submit"]

        print("\nBulk Answer Saving: PASSED")

        # ==========================================
        # 12. Submit Daily Assessment
        # ==========================================

        print_section(
            "DAILY ASSESSMENT SUBMISSION"
        )

        attempt = submit_daily_assessment(
            attempt
        )

        attempt.refresh_from_db()

        print(f"Attempt Status: {attempt.status}")
        print(f"Submitted At: {attempt.submitted_at}")

        assert attempt.status == "submitted"
        assert attempt.submitted_at is not None

        print("\nAssessment Submission: PASSED")

    # ==========================================
    # 13. Duplicate Submission Protection
    # ==========================================

    print_section(
        "DUPLICATE SUBMISSION PROTECTION"
    )

    original_submitted_at = attempt.submitted_at

    repeated_submission = (
        submit_daily_assessment(attempt)
    )

    repeated_submission.refresh_from_db()

    assert repeated_submission.id == attempt.id

    assert (
        repeated_submission.submitted_at
        == original_submitted_at
    )

    print("Same Attempt Returned: True")
    print("Submission Timestamp Preserved: True")

    print("\nDuplicate Submission Test: PASSED")

    # ==========================================
    # 14. Post-Submission Answer Protection
    # ==========================================

    print_section(
        "POST-SUBMISSION ANSWER PROTECTION"
    )

    expect_rejection(
        "Modify Submitted Answer",
        save_daily_answer,
        attempt,
        questions[0].id,
        questions[0].correct_answer,
    )

    print("\nPost-Submission Protection: PASSED")

    # ==========================================
    # 15. Preserve Submitted Answers
    # ==========================================

    original_submitted_answers = list(
        UserAnswer.objects.filter(
            attempt=attempt
        ).order_by("question_id").values_list(
            "question_id",
            "submitted_answer",
        )
    )

    assert len(original_submitted_answers) == 5

    # ==========================================
    # 16. Evaluate Daily Assessment
    # ==========================================

    print_section(
        "AI DAILY ASSESSMENT EVALUATION"
    )

    if attempt.status == "evaluated":

        print(
            "Assessment is already evaluated. "
            "Reusing saved results."
        )

    else:

        print(
            "Evaluating MCQs and written answers..."
        )

        attempt = evaluate_daily_assessment(
            attempt
        )

    attempt.refresh_from_db()

    print(f"\nAttempt ID: {attempt.id}")
    print(f"Status: {attempt.status}")
    print(f"Obtained Marks: {attempt.obtained_marks}")
    print(f"Total Marks: {attempt.total_marks}")
    print(f"Percentage: {attempt.percentage}%")
    print(f"Passed: {attempt.passed}")

    assert attempt.status == "evaluated"
    assert attempt.evaluated_at is not None

    assert 0 <= attempt.obtained_marks <= 9

    assert 0 <= attempt.percentage <= 100

    print("\nDaily Assessment Evaluation: PASSED")

    # ==========================================
    # 17. Verify Individual Question Evaluation
    # ==========================================

    print_section(
        "INDIVIDUAL QUESTION EVALUATION"
    )

    evaluated_answers = list(
        UserAnswer.objects.filter(
            attempt=attempt
        ).select_related(
            "question"
        ).order_by(
            "question__order"
        )
    )

    assert len(evaluated_answers) == 5

    for answer in evaluated_answers:

        question = answer.question

        print(f"\nQUESTION {question.order}")
        print("-" * 60)

        print(f"Type: {question.question_type}")
        print(f"Topic: {question.topic}")

        print("\nQuestion:")
        print(question.question_text)

        print("\nSubmitted Answer:")
        print(answer.submitted_answer)

        print(
            f"\nMarks Awarded: "
            f"{answer.marks_awarded}/{question.marks}"
        )

        print(f"Is Correct: {answer.is_correct}")

        print(
            f"Is Evaluated: "
            f"{answer.is_evaluated}"
        )

        print("\nEvaluation Feedback:")
        print(answer.ai_feedback)

        assert answer.is_evaluated

        assert math.isfinite(
            answer.marks_awarded
        )

        assert (
            0 <= answer.marks_awarded
            <= question.marks
        )

        if question.question_type == "mcq":

            expected_marks = (
                question.marks
                if answer.submitted_answer
                == question.correct_answer
                else 0
            )

            assert (
                answer.marks_awarded
                == expected_marks
            )

        assert answer.ai_feedback.strip()

    print("\nIndividual Evaluation Test: PASSED")

    # ==========================================
    # 18. Verify Score Calculation
    # ==========================================

    print_section(
        "SCORE CALCULATION TEST"
    )

    score = calculate_daily_assessment_score(
        attempt
    )

    print_json(score)

    expected_marks = round(
        sum(
            answer.marks_awarded
            for answer in evaluated_answers
        ),
        2,
    )

    expected_percentage = round(
        expected_marks / 9 * 100,
        2,
    )

    expected_passed = expected_marks >= 7.2

    assert score["total_marks"] == 9

    assert math.isclose(
        score["obtained_marks"],
        expected_marks,
    )

    assert math.isclose(
        attempt.obtained_marks,
        expected_marks,
    )

    assert math.isclose(
        attempt.percentage,
        expected_percentage,
    )

    assert score["passing_percentage"] == 80

    assert math.isclose(
        score["minimum_passing_marks"],
        7.2,
    )

    assert score["passed"] == expected_passed

    assert attempt.passed == expected_passed

    assert score["evaluated_questions"] == 5

    if fresh_attempt:

        assert score["mcq_marks"] == 3

    print("\nScore Calculation Test: PASSED")

    # ==========================================
    # 19. Verify Personalized Feedback
    # ==========================================

    print_section(
        "PERSONALIZED FEEDBACK VERIFICATION"
    )

    print("Strengths:")

    for strength in attempt.strengths:

        print(f"- {strength}")

    print("\nWeaknesses:")

    for weakness in attempt.weaknesses:

        print(f"- {weakness}")

    print("\nRecommendations:")

    for recommendation in attempt.recommendations:

        print(f"- {recommendation}")

    print("\nOverall AI Feedback:")
    print(attempt.ai_feedback)

    assert isinstance(attempt.strengths, list)

    assert isinstance(attempt.weaknesses, list)

    assert isinstance(
        attempt.recommendations,
        list,
    )

    assert 1 <= len(
        attempt.recommendations
    ) <= 5

    assert attempt.ai_feedback.strip()

    print("\nPersonalized Feedback Test: PASSED")

    # ==========================================
    # 20. Verify Evaluation Job
    # ==========================================

    print_section(
        "AI EVALUATION JOB VERIFICATION"
    )

    job = AIGenerationJob.objects.get(
        idempotency_key=(
            f"daily_assessment_evaluation_{attempt.id}"
        )
    )

    print(f"Job ID: {job.id}")
    print(f"Job Type: {job.job_type}")
    print(f"Job Status: {job.status}")
    print(f"Job Attempts: {job.attempt_count}")
    print(f"Error Message: {job.error_message}")

    assert job.job_type == "assessment_evaluation"
    assert job.status == "completed"
    assert job.completed_at is not None
    assert not job.error_message

    assert (
        job.response_data["attempt_id"]
        == attempt.id
    )

    assert (
        job.response_data["score"]["passed"]
        == attempt.passed
    )

    print("\nAI Evaluation Job Test: PASSED")

    # ==========================================
    # 21. Duplicate Evaluation Prevention
    # ==========================================

    print_section(
        "DUPLICATE EVALUATION PREVENTION"
    )

    original_job_attempts = job.attempt_count

    original_evaluated_at = attempt.evaluated_at

    original_evaluated_answers = list(
        UserAnswer.objects.filter(
            attempt=attempt
        ).order_by("pk").values()
    )

    repeated_evaluation = (
        evaluate_daily_assessment(attempt)
    )

    job.refresh_from_db()

    repeated_evaluation.refresh_from_db()

    current_evaluated_answers = list(
        UserAnswer.objects.filter(
            attempt=attempt
        ).order_by("pk").values()
    )

    assert repeated_evaluation.id == attempt.id

    assert (
        repeated_evaluation.evaluated_at
        == original_evaluated_at
    )

    assert (
        job.attempt_count
        == original_job_attempts
    )

    assert (
        original_evaluated_answers
        == current_evaluated_answers
    )

    print("Same Evaluation Returned: True")
    print("Evaluation Timestamp Preserved: True")
    print("Additional Generation Attempts: 0")
    print("Evaluated Answers Unchanged: True")

    print("\nDuplicate Evaluation Test: PASSED")

    # ==========================================
    # 22. Retrieve Final Learner Result
    # ==========================================

    print_section(
        "FINAL LEARNER ASSESSMENT RESULT"
    )

    result = get_daily_assessment_result(
        attempt
    )

    print_json(result)

    assert result["status"] == "evaluated"

    assert len(result["question_results"]) == 5

    assert result["passed"] == attempt.passed

    assert (
        result["eligible_for_day_completion"]
        == attempt.passed
    )

    assert (
        result["can_retry_assessment"]
        == (not attempt.passed)
    )

    for question_result in result[
        "question_results"
    ]:

        assert "correct_answer" not in question_result

        assert (
            "reference_answer"
            not in question_result
        )

    print("\nLearner Result Retrieval: PASSED")

    # ==========================================
    # 23. Passed Attempt Protection
    # ==========================================

    print_section(
        "PASSED ASSESSMENT PROTECTION"
    )

    if attempt.passed:

        expect_rejection(
            "Start New Attempt After Passing",
            start_daily_assessment_attempt,
            day1,
        )

        print(
            "\nPassed Assessment Protection: PASSED"
        )

    else:

        print(
            "Learner did not reach the passing "
            "threshold."
        )

        print(
            "Another assessment attempt is allowed."
        )

        print(
            "New attempt creation is not performed "
            "in this test."
        )

    # ==========================================
    # 24. Submitted Answer Preservation
    # ==========================================

    print_section(
        "SUBMITTED ANSWER PRESERVATION"
    )

    current_submitted_answers = list(
        UserAnswer.objects.filter(
            attempt=attempt
        ).order_by("question_id").values_list(
            "question_id",
            "submitted_answer",
        )
    )

    assert (
        original_submitted_answers
        == current_submitted_answers
    )

    print("All Submitted Answers Preserved: True")

    print("\nAnswer Preservation Test: PASSED")

    # ==========================================
    # 25. Existing Data Preservation
    # ==========================================

    print_section(
        "EXISTING LEARNING DATA PRESERVATION"
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
            f"Existing data modified: {key}"
        )

    print("\nExisting Data Preservation: PASSED")

    # ==========================================
    # 26. Verify Learning Progress
    # ==========================================

    print_section(
        "FINAL LEARNING PROGRESS VERIFICATION"
    )

    enrollment.refresh_from_db()
    progress1.refresh_from_db()
    progress2.refresh_from_db()

    progress_summary = (
        get_daily_progress_summary(day1)
    )

    print_json(progress_summary)

    assert enrollment.current_day == 1
    assert enrollment.status == "active"

    assert progress1.status == "in_progress"

    assert progress1.lesson_completed
    assert progress1.practical_completed

    assert not progress1.assessment_completed

    assert progress2.status == "locked"

    assert (
        progress_summary["completion_percentage"]
        == 66.67
    )

    print("\nDay 1 Status:", progress1.status)
    print("Day 2 Status:", progress2.status)

    print(
        "Assessment Passed:",
        attempt.passed,
    )

    print(
        "Eligible for Day Completion:",
        attempt.passed,
    )

    print(
        "Automatic Unlocking Performed: False"
    )

    print("\nLearning Progress Verification: PASSED")

    # ==========================================
    # 27. Final Test Summary
    # ==========================================

    print_section(
        "DAILY ASSESSMENT EVALUATION TEST PASSED!"
    )

    print(f"\nAssessment ID: {assessment.id}")
    print(f"Attempt ID: {attempt.id}")
    print(f"Attempt Number: {attempt.attempt_number}")

    print(f"MCQ Marks: {score['mcq_marks']}/3")
    print(f"Coding Marks: {score['coding_marks']}/3")
    print(f"Theory Marks: {score['theory_marks']}/3")

    print(
        f"Total Marks: "
        f"{score['obtained_marks']}/9"
    )

    print(f"Percentage: {score['percentage']}%")
    print(f"Passing Threshold: 80%")
    print(f"Assessment Passed: {attempt.passed}")

    print("\nAll five answers evaluated successfully.")
    print("Evaluation results saved successfully.")
    print("Existing learning progress preserved.")

    if attempt.passed:

        print(
            "\nDay 1 is ready for "
            "transactional progress finalization."
        )

    else:

        print(
            "\nRevision and another assessment "
            "attempt are required."
        )


if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print_section(
            "DAILY ASSESSMENT EVALUATION TEST FAILED!"
        )

        print(f"Error: {error}")

        print(
            "\nInspect the error before continuing."
        )

        print(
            "Previously committed answers and "
            "evaluation results may already "
            "exist in the database."
        )

        raise