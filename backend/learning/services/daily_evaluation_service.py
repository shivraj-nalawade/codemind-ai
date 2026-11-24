import logging
import math

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from learning.models import (
    Enrollment,
    LearningDay,
    DayProgress,
    Assessment,
    AssessmentAttempt,
    Question,
    UserAnswer,
    AIGenerationJob,
)

from .evaluation_service import (
    AssessmentEvaluationError,
    start_assessment_attempt,
    save_user_answer,
    submit_assessment,
    evaluate_mcq_answers,
    evaluate_written_answers,
    calculate_topic_performance,
    identify_topic_strengths,
    generate_assessment_feedback,
)

from .daily_assessment_service import (
    DailyAssessmentGenerationError,
    get_existing_daily_assessment,
    DAILY_TOTAL_QUESTIONS,
    DAILY_TOTAL_MARKS,
)

from .progress_service import (
    LearningProgressError,
    require_daily_assessment_eligibility,
    DAILY_PASS_PERCENTAGE,
)


logger = logging.getLogger(__name__)


class DailyEvaluationError(Exception):
    pass


# ==========================================
# 1. Retrieve Daily Assessment
# ==========================================

def get_daily_assessment(learning_day):

    try:

        assessment = get_existing_daily_assessment(
            learning_day
        )

    except DailyAssessmentGenerationError as error:

        raise DailyEvaluationError(
            str(error)
        ) from error

    if assessment is None:

        raise DailyEvaluationError(
            "Daily assessment has not been generated."
        )

    return assessment


# ==========================================
# 2. Validate Assessment Attempt Type
# ==========================================

def validate_daily_attempt(attempt):

    assessment = attempt.assessment

    if assessment.assessment_type != "daily":

        raise DailyEvaluationError(
            "This service only supports "
            "daily assessment attempts."
        )

    if not 1 <= assessment.day_number <= 30:

        raise DailyEvaluationError(
            "Invalid daily assessment day number."
        )

    if (
        assessment.total_questions
        != DAILY_TOTAL_QUESTIONS
    ):

        raise DailyEvaluationError(
            "Invalid daily assessment question count."
        )

    return assessment


# ==========================================
# 3. Retrieve Learning Day from Attempt
# ==========================================

def get_attempt_learning_day(attempt):

    assessment = validate_daily_attempt(
        attempt
    )

    try:

        learning_day = LearningDay.objects.get(
            enrollment=assessment.enrollment,
            day_number=assessment.day_number,
        )

    except LearningDay.DoesNotExist as error:

        raise DailyEvaluationError(
            "Learning day associated with "
            "this assessment was not found."
        ) from error

    return learning_day


# ==========================================
# 4. Validate Assessment Eligibility
# ==========================================

def validate_daily_evaluation_access(
    learning_day,
):

    try:

        return require_daily_assessment_eligibility(
            learning_day
        )

    except LearningProgressError as error:

        raise DailyEvaluationError(
            str(error)
        ) from error


# ==========================================
# 5. Prevent New Attempts After Passing
# ==========================================

def check_existing_passed_attempt(assessment):

    return AssessmentAttempt.objects.filter(
        assessment=assessment,
        status="evaluated",
        passed=True,
    ).order_by(
        "-evaluated_at"
    ).first()


# ==========================================
# 6. Start Daily Assessment Attempt
# ==========================================

@transaction.atomic
def start_daily_assessment_attempt(
    learning_day,
):

    enrollment = (
        Enrollment.objects
        .select_for_update()
        .get(pk=learning_day.enrollment_id)
    )

    learning_day = (
        LearningDay.objects
        .select_for_update()
        .get(
            pk=learning_day.pk,
            enrollment=enrollment,
        )
    )

    DayProgress.objects.select_for_update().get(
        learning_day=learning_day
    )

    validate_daily_evaluation_access(
        learning_day
    )

    assessment = get_daily_assessment(
        learning_day
    )

    assessment = (
        Assessment.objects
        .select_for_update()
        .get(pk=assessment.pk)
    )

    passed_attempt = (
        check_existing_passed_attempt(
            assessment
        )
    )

    if passed_attempt is not None:

        raise DailyEvaluationError(
            "This daily assessment has "
            "already been passed."
        )

    try:

        attempt = start_assessment_attempt(
            assessment
        )

    except AssessmentEvaluationError as error:

        raise DailyEvaluationError(
            str(error)
        ) from error

    logger.info(
        "Daily assessment attempt %s started "
        "or retrieved for day %s.",
        attempt.id,
        learning_day.day_number,
    )

    return attempt


# ==========================================
# 7. Save Individual Daily Answer
# ==========================================

@transaction.atomic
def save_daily_answer(
    attempt,
    question_id,
    submitted_answer,
):

    attempt.refresh_from_db()

    learning_day = get_attempt_learning_day(
        attempt
    )

    validate_daily_evaluation_access(
        learning_day
    )

    if attempt.status != "in_progress":

        raise DailyEvaluationError(
            "Answers can only be modified "
            "while the attempt is in progress."
        )

    try:

        answer = save_user_answer(
            attempt,
            question_id,
            submitted_answer,
        )

    except AssessmentEvaluationError as error:

        raise DailyEvaluationError(
            str(error)
        ) from error

    return answer


# ==========================================
# 8. Save Multiple Daily Answers
# ==========================================

@transaction.atomic
def save_daily_answers(attempt, answers):

    if not isinstance(answers, list):

        raise DailyEvaluationError(
            "Answers must be provided as a list."
        )

    if not 1 <= len(answers) <= DAILY_TOTAL_QUESTIONS:

        raise DailyEvaluationError(
            "Provide between one and five answers."
        )

    seen_question_ids = set()

    saved_answers = []

    for index, answer_data in enumerate(
        answers,
        start=1,
    ):

        if not isinstance(answer_data, dict):

            raise DailyEvaluationError(
                f"Answer {index} must be an object."
            )

        question_id = answer_data.get(
            "question_id"
        )

        submitted_answer = answer_data.get(
            "submitted_answer"
        )

        if (
            type(question_id) is not int
            or question_id <= 0
        ):

            raise DailyEvaluationError(
                f"Answer {index} has an "
                "invalid question ID."
            )

        if question_id in seen_question_ids:

            raise DailyEvaluationError(
                "Duplicate question IDs detected."
            )

        if not isinstance(
            submitted_answer,
            str,
        ):

            raise DailyEvaluationError(
                f"Answer {index} must contain text."
            )

        seen_question_ids.add(
            question_id
        )

        saved_answer = save_daily_answer(
            attempt=attempt,
            question_id=question_id,
            submitted_answer=submitted_answer,
        )

        saved_answers.append(
            saved_answer
        )

    return saved_answers


# ==========================================
# 9. Submit Daily Assessment
# ==========================================

@transaction.atomic
def submit_daily_assessment(attempt):

    attempt.refresh_from_db()

    learning_day = get_attempt_learning_day(
        attempt
    )

    validate_daily_evaluation_access(
        learning_day
    )

    # Duplicate submission protection.
    if attempt.status in [
        "submitted",
        "evaluating",
        "evaluated",
        "failed",
    ]:

        return attempt

    if attempt.status != "in_progress":

        raise DailyEvaluationError(
            "Invalid assessment attempt status."
        )

    try:

        submit_assessment(
            attempt
        )

    except AssessmentEvaluationError as error:

        raise DailyEvaluationError(
            str(error)
        ) from error

    attempt.refresh_from_db()

    logger.info(
        "Daily assessment attempt %s submitted.",
        attempt.id,
    )

    return attempt


# ==========================================
# 10. Retrieve Attempt Answers
# ==========================================

def get_daily_attempt_answers(attempt):

    validate_daily_attempt(
        attempt
    )

    answers = list(
        UserAnswer.objects.filter(
            attempt=attempt
        ).select_related(
            "question"
        ).order_by(
            "question__order"
        )
    )

    expected_question_ids = set(
        Question.objects.filter(
            assessment=attempt.assessment
        ).values_list(
            "id",
            flat=True,
        )
    )

    actual_question_ids = {
        answer.question_id
        for answer in answers
    }

    if len(expected_question_ids) != DAILY_TOTAL_QUESTIONS:

        raise DailyEvaluationError(
            "Assessment contains an invalid "
            "number of questions."
        )

    if len(answers) != DAILY_TOTAL_QUESTIONS:

        raise DailyEvaluationError(
            "All five questions must be answered."
        )

    if actual_question_ids != expected_question_ids:

        raise DailyEvaluationError(
            "Submitted answers do not match "
            "the assessment questions."
        )

    for answer in answers:

        if not answer.submitted_answer.strip():

            raise DailyEvaluationError(
                "Empty answers cannot be evaluated."
            )

    return answers


# ==========================================
# 11. Calculate Daily Assessment Score
# ==========================================

def calculate_daily_assessment_score(attempt):

    answers = get_daily_attempt_answers(
        attempt
    )

    if not all(
        answer.is_evaluated
        for answer in answers
    ):

        raise DailyEvaluationError(
            "All answers must be evaluated "
            "before calculating the final score."
        )

    mcq_marks = 0.0

    coding_marks = 0.0

    theory_marks = 0.0

    total_marks = 0.0

    for answer in answers:

        question = answer.question

        awarded_marks = float(
            answer.marks_awarded
        )

        maximum_marks = float(
            question.marks
        )

        if not math.isfinite(awarded_marks):

            raise DailyEvaluationError(
                "Non-finite marks detected."
            )

        if not 0 <= awarded_marks <= maximum_marks:

            raise DailyEvaluationError(
                "Awarded marks are outside "
                "the permitted range."
            )

        total_marks += maximum_marks

        if question.question_type == "mcq":

            mcq_marks += awarded_marks

        elif question.question_type == "coding":

            coding_marks += awarded_marks

        elif question.question_type == "theory":

            theory_marks += awarded_marks

        else:

            raise DailyEvaluationError(
                "Unknown question type detected."
            )

    if total_marks != DAILY_TOTAL_MARKS:

        raise DailyEvaluationError(
            "Daily assessment must contain "
            "exactly nine marks."
        )

    obtained_marks = round(
        mcq_marks + coding_marks + theory_marks,
        2,
    )

    percentage = round(
        (obtained_marks / total_marks) * 100,
        2,
    )

    minimum_passing_marks = (
        total_marks
        * DAILY_PASS_PERCENTAGE
        / 100
    )

    passed = (
        obtained_marks >= minimum_passing_marks
    )

    return {
        "mcq_marks": round(mcq_marks, 2),
        "mcq_total": 3,
        "coding_marks": round(coding_marks, 2),
        "coding_total": 3,
        "theory_marks": round(theory_marks, 2),
        "theory_total": 3,
        "obtained_marks": obtained_marks,
        "total_marks": total_marks,
        "percentage": percentage,
        "passing_percentage": DAILY_PASS_PERCENTAGE,
        "minimum_passing_marks": (
            minimum_passing_marks
        ),
        "passed": passed,
        "evaluated_questions": len(answers),
    }


# ==========================================
# 12. Finalize Daily Assessment
# ==========================================

def finalize_daily_assessment(attempt):

    attempt.refresh_from_db()

    learning_day = get_attempt_learning_day(
        attempt
    )

    if attempt.status == "evaluated":

        return attempt

    if attempt.status != "evaluating":

        raise DailyEvaluationError(
            "Assessment must be in evaluating "
            "status before finalization."
        )

    validate_daily_evaluation_access(
        learning_day
    )

    score = calculate_daily_assessment_score(
        attempt
    )

    topic_results = calculate_topic_performance(
        attempt
    )

    topic_analysis = identify_topic_strengths(
        topic_results
    )

    # AI feedback generation happens outside
    # the database transaction.
    feedback_data = generate_assessment_feedback(
        attempt,
        score["percentage"],
        topic_results,
        topic_analysis,
    )

    with transaction.atomic():

        attempt = (
            AssessmentAttempt.objects
            .select_for_update()
            .get(pk=attempt.pk)
        )

        if attempt.status == "evaluated":

            return attempt

        if attempt.status != "evaluating":

            raise DailyEvaluationError(
                "Assessment status changed "
                "during finalization."
            )

        # Recalculate persisted scores.
        score = calculate_daily_assessment_score(
            attempt
        )

        attempt.total_marks = score[
            "total_marks"
        ]

        attempt.obtained_marks = score[
            "obtained_marks"
        ]

        attempt.percentage = score[
            "percentage"
        ]

        attempt.passed = score[
            "passed"
        ]

        attempt.strengths = topic_analysis.get(
            "strengths",
            [],
        )

        attempt.weaknesses = topic_analysis.get(
            "weaknesses",
            [],
        )

        attempt.recommendations = (
            feedback_data.get(
                "recommendations",
                [],
            )
        )

        attempt.ai_feedback = feedback_data.get(
            "feedback",
            "",
        )

        attempt.status = "evaluated"

        attempt.evaluated_at = timezone.now()

        attempt.save(update_fields=[
            "total_marks",
            "obtained_marks",
            "percentage",
            "passed",
            "strengths",
            "weaknesses",
            "recommendations",
            "ai_feedback",
            "status",
            "evaluated_at",
        ])

    logger.info(
        "Daily assessment attempt %s evaluated. "
        "Score: %s%%. Passed: %s.",
        attempt.id,
        score["percentage"],
        score["passed"],
    )

    return attempt


# ==========================================
# 13. Main Daily Assessment Evaluation
# ==========================================

def evaluate_daily_assessment(attempt):

    attempt.refresh_from_db()

    learning_day = get_attempt_learning_day(
        attempt
    )

    # Return previously evaluated results.
    if attempt.status == "evaluated":

        return attempt

    validate_daily_evaluation_access(
        learning_day
    )

    if attempt.status not in [
        "submitted",
        "failed",
    ]:

        raise DailyEvaluationError(
            "Only submitted or failed attempts "
            "can be evaluated."
        )

    get_daily_attempt_answers(
        attempt
    )

    enrollment = (
        attempt.assessment.enrollment
    )

    job_key = (
        f"daily_assessment_evaluation_{attempt.id}"
    )

    request_data = {
        "assessment_id": attempt.assessment_id,
        "attempt_id": attempt.id,
        "day_number": learning_day.day_number,
        "language": enrollment.language,
    }

    # Claim the attempt and job atomically.
    with transaction.atomic():

        attempt = (
            AssessmentAttempt.objects
            .select_for_update()
            .get(pk=attempt.pk)
        )

        if attempt.status == "evaluated":

            return attempt

        if attempt.status not in [
            "submitted",
            "failed",
        ]:

            raise DailyEvaluationError(
                "Assessment evaluation is "
                "already in progress."
            )

        job, _ = AIGenerationJob.objects.get_or_create(
            idempotency_key=job_key,
            defaults={
                "enrollment": enrollment,
                "job_type": "assessment_evaluation",
                "request_data": request_data,
            },
        )

        claimed = AIGenerationJob.objects.filter(
            pk=job.pk,
            status__in=[
                "pending",
                "failed",
            ],
        ).update(
            status="processing",
            started_at=timezone.now(),
            completed_at=None,
            updated_at=timezone.now(),
            error_message="",
            attempt_count=F("attempt_count") + 1,
            request_data=request_data,
            response_data={},
        )

        if not claimed:

            raise DailyEvaluationError(
                "Evaluation job is already "
                "processing or requires recovery."
            )

        attempt.status = "evaluating"

        attempt.save(
            update_fields=["status"]
        )

    try:

        job.refresh_from_db()

        print(
            f"\nEvaluating Day "
            f"{learning_day.day_number} assessment...",
            flush=True,
        )

        # ----------------------------------
        # Evaluate MCQs
        # ----------------------------------

        print(
            "Evaluating 3 MCQs...",
            flush=True,
        )

        evaluate_mcq_answers(
            attempt
        )

        # ----------------------------------
        # Evaluate Written Questions
        # ----------------------------------

        print(
            "Evaluating 2 written questions "
            "using GPT-OSS-120B...",
            flush=True,
        )

        written_result = (
            evaluate_written_answers(
                attempt
            )
        )

        if not written_result.get(
            "evaluation_complete",
            False,
        ):

            raise DailyEvaluationError(
                "One or more written answers "
                "could not be evaluated. "
                "Saved answers and completed "
                "evaluations are preserved."
            )

        # Verify all answers are evaluated.
        answers = get_daily_attempt_answers(
            attempt
        )

        if not all(
            answer.is_evaluated
            for answer in answers
        ):

            raise DailyEvaluationError(
                "Assessment evaluation is incomplete."
            )

        # ----------------------------------
        # Finalize Results
        # ----------------------------------

        print(
            "Calculating final score "
            "and personalized feedback...",
            flush=True,
        )

        attempt = finalize_daily_assessment(
            attempt
        )

        score = calculate_daily_assessment_score(
            attempt
        )

        # ----------------------------------
        # Complete AI Generation Job
        # ----------------------------------

        AIGenerationJob.objects.filter(
            pk=job.pk,
            status="processing",
        ).update(
            status="completed",
            response_data={
                "assessment_id": (
                    attempt.assessment_id
                ),
                "attempt_id": attempt.id,
                "day_number": (
                    learning_day.day_number
                ),
                "score": score,
                "strengths": attempt.strengths,
                "weaknesses": attempt.weaknesses,
                "recommendations": (
                    attempt.recommendations
                ),
                "ai_feedback": attempt.ai_feedback,
            },
            completed_at=timezone.now(),
            updated_at=timezone.now(),
            error_message="",
        )

        print(
            "\nDaily assessment evaluation "
            "completed successfully.",
            flush=True,
        )

        print(
            f"MCQ Marks: "
            f"{score['mcq_marks']}/3",
            flush=True,
        )

        print(
            f"Coding Marks: "
            f"{score['coding_marks']}/3",
            flush=True,
        )

        print(
            f"Theory Marks: "
            f"{score['theory_marks']}/3",
            flush=True,
        )

        print(
            f"Total Marks: "
            f"{score['obtained_marks']}/9",
            flush=True,
        )

        print(
            f"Percentage: "
            f"{score['percentage']}%",
            flush=True,
        )

        print(
            f"Passed: {score['passed']}",
            flush=True,
        )

        return attempt

    except Exception as error:

        logger.exception(
            "Daily assessment evaluation "
            "failed for attempt %s.",
            attempt.id,
        )

        error_message = (
            str(error)
            if isinstance(
                error,
                (
                    DailyEvaluationError,
                    AssessmentEvaluationError,
                ),
            )
            else "Unexpected daily evaluation error."
        )

        with transaction.atomic():

            current_attempt = (
                AssessmentAttempt.objects
                .select_for_update()
                .get(pk=attempt.pk)
            )

            # Recover a finalized result if
            # only the job completion failed.
            if current_attempt.status == "evaluated":

                score = (
                    calculate_daily_assessment_score(
                        current_attempt
                    )
                )

                AIGenerationJob.objects.filter(
                    pk=job.pk
                ).update(
                    status="completed",
                    response_data={
                        "assessment_id": (
                            current_attempt.assessment_id
                        ),
                        "attempt_id": (
                            current_attempt.id
                        ),
                        "day_number": (
                            learning_day.day_number
                        ),
                        "score": score,
                        "strengths": (
                            current_attempt.strengths
                        ),
                        "weaknesses": (
                            current_attempt.weaknesses
                        ),
                        "recommendations": (
                            current_attempt.recommendations
                        ),
                        "ai_feedback": (
                            current_attempt.ai_feedback
                        ),
                    },
                    completed_at=timezone.now(),
                    updated_at=timezone.now(),
                    error_message="",
                )

                return current_attempt

            AssessmentAttempt.objects.filter(
                pk=attempt.pk,
                status="evaluating",
            ).update(
                status="failed"
            )

            AIGenerationJob.objects.filter(
                pk=job.pk,
                status="processing",
            ).update(
                status="failed",
                error_message=error_message,
                completed_at=timezone.now(),
                updated_at=timezone.now(),
            )

        if isinstance(
            error,
            DailyEvaluationError,
        ):

            raise

        raise DailyEvaluationError(
            "Unable to complete daily assessment "
            "evaluation. Submitted answers and "
            "completed evaluations are preserved. "
            "Please retry."
        ) from error


# ==========================================
# 14. Retrieve Daily Attempt Progress
# ==========================================

def get_daily_attempt_summary(attempt):

    attempt.refresh_from_db()

    assessment = validate_daily_attempt(
        attempt
    )

    answers = list(
        UserAnswer.objects.filter(
            attempt=attempt
        )
    )

    answered_questions = sum(
        bool(answer.submitted_answer.strip())
        for answer in answers
    )

    evaluated_questions = sum(
        answer.is_evaluated
        for answer in answers
    )

    return {
        "attempt_id": attempt.id,
        "assessment_id": assessment.id,
        "day_number": assessment.day_number,
        "attempt_number": attempt.attempt_number,
        "status": attempt.status,
        "total_questions": DAILY_TOTAL_QUESTIONS,
        "answered_questions": answered_questions,
        "evaluated_questions": evaluated_questions,
        "answer_completion_percentage": round(
            (
                answered_questions
                / DAILY_TOTAL_QUESTIONS
            ) * 100,
            2,
        ),
        "can_edit_answers": (
            attempt.status == "in_progress"
        ),
        "can_submit": (
            attempt.status == "in_progress"
            and answered_questions
            == DAILY_TOTAL_QUESTIONS
        ),
        "can_retry_evaluation": (
            attempt.status == "failed"
        ),
        "submitted_at": (
            attempt.submitted_at.isoformat()
            if attempt.submitted_at
            else None
        ),
        "evaluated_at": (
            attempt.evaluated_at.isoformat()
            if attempt.evaluated_at
            else None
        ),
    }


# ==========================================
# 15. Retrieve Evaluated Daily Result
# ==========================================

def get_daily_assessment_result(attempt):

    attempt.refresh_from_db()

    assessment = validate_daily_attempt(
        attempt
    )

    if attempt.status != "evaluated":

        raise DailyEvaluationError(
            "Assessment results are not "
            "available until evaluation "
            "is completed."
        )

    score = calculate_daily_assessment_score(
        attempt
    )

    answers = get_daily_attempt_answers(
        attempt
    )

    question_results = []

    for answer in answers:

        question = answer.question

        question_results.append({
            "question_id": question.id,
            "order": question.order,
            "question_type": (
                question.question_type
            ),
            "topic": question.topic,
            "difficulty": question.difficulty,
            "question_text": (
                question.question_text
            ),
            "submitted_answer": (
                answer.submitted_answer
            ),
            "is_correct": answer.is_correct,
            "marks_awarded": (
                answer.marks_awarded
            ),
            "maximum_marks": question.marks,
            "feedback": answer.ai_feedback,
        })

    return {
        "attempt_id": attempt.id,
        "assessment_id": assessment.id,
        "assessment_title": assessment.title,
        "day_number": assessment.day_number,
        "attempt_number": attempt.attempt_number,
        "status": attempt.status,
        "score": score,
        "passed": attempt.passed,
        "strengths": attempt.strengths,
        "weaknesses": attempt.weaknesses,
        "recommendations": (
            attempt.recommendations
        ),
        "ai_feedback": attempt.ai_feedback,
        "question_results": question_results,
        "can_retry_assessment": (
            not attempt.passed
        ),
        "eligible_for_day_completion": (
            attempt.passed
        ),
        "evaluated_at": (
            attempt.evaluated_at.isoformat()
            if attempt.evaluated_at
            else None
        ),
    }