import logging

from django.shortcuts import get_object_or_404

from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response

from learning.models import (
    AssessmentAttempt,
    UserAnswer,
)

from learning.services.daily_evaluation_service import (
    DailyEvaluationError,
    start_daily_assessment_attempt,
    save_daily_answers,
    submit_daily_assessment,
    evaluate_daily_assessment,
    get_daily_attempt_summary,
    get_daily_assessment_result,
)

from learning.services.evaluation_service import (
    AssessmentEvaluationError,
)

from learning.services.progression_service import (
    finalize_learning_day,
)

from .permissions import IsLearningAuthenticated

from .lesson_views import (
    get_owned_learning_day,
    success_response,
    error_response,
)


logger = logging.getLogger(__name__)


def get_owned_daily_attempt(request, attempt_id):

    return get_object_or_404(
        AssessmentAttempt,
        id=attempt_id,
        assessment__assessment_type="daily",
        assessment__enrollment__user=request.user,
    )


def serialize_daily_attempt(attempt):

    attempt.refresh_from_db()

    data = get_daily_attempt_summary(attempt)

    data["answers"] = list(
        UserAnswer.objects.filter(
            attempt=attempt
        ).values(
            "question_id",
            "submitted_answer",
        )
    )

    return data


def serialize_safe_daily_result(attempt):

    result = get_daily_assessment_result(attempt)

    # Failed assessments can be attempted again.
    # Avoid revealing answer-specific feedback before a pass.
    if not attempt.passed:

        return {
            "attempt_id": attempt.id,
            "assessment_id": attempt.assessment_id,
            "status": attempt.status,
            "score": result["score"],
            "passed": False,
            "can_retry_assessment": True,
            "message": (
                "Review the lesson and try again. "
                "A minimum score of 80% is required."
            ),
        }

    return result


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def start_daily_attempt_view(request, day_id):

    day = get_owned_learning_day(request, day_id)

    try:
        attempt = start_daily_assessment_attempt(day)

        return success_response(
            serialize_daily_attempt(attempt),
            "Daily assessment started.",
        )

    except (DailyEvaluationError, AssessmentEvaluationError) as exc:
        return error_response(str(exc), 409)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def daily_attempt_detail_view(request, attempt_id):

    attempt = get_owned_daily_attempt(
        request,
        attempt_id,
    )

    return success_response(
        serialize_daily_attempt(attempt)
    )


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def save_daily_answers_view(request, attempt_id):

    attempt = get_owned_daily_attempt(
        request,
        attempt_id,
    )

    answers = request.data.get("answers")

    if not isinstance(answers, list):

        return error_response(
            "Provide a list of answers."
        )

    try:
        save_daily_answers(attempt, answers)

        return success_response(
            serialize_daily_attempt(attempt),
            "Daily answers saved successfully.",
        )

    except (DailyEvaluationError, AssessmentEvaluationError) as exc:
        return error_response(str(exc))


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def submit_daily_attempt_view(request, attempt_id):

    attempt = get_owned_daily_attempt(
        request,
        attempt_id,
    )

    try:
        if attempt.status == "in_progress":
            submit_daily_assessment(attempt)

        return success_response(
            serialize_daily_attempt(attempt),
            "Daily assessment submitted.",
        )

    except (DailyEvaluationError, AssessmentEvaluationError) as exc:
        return error_response(str(exc), 409)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def evaluate_daily_attempt_view(request, attempt_id):

    attempt = get_owned_daily_attempt(
        request,
        attempt_id,
    )

    if attempt.status not in [
        "submitted",
        "failed",
        "evaluated",
    ]:
        return error_response(
            "Assessment is not ready for evaluation.",
            409,
        )

    # Step 1: Evaluate and persist the assessment.
    try:
        evaluate_daily_assessment(attempt)

        attempt.refresh_from_db()

    except Exception:
        logger.exception("Daily evaluation failed.")

        return error_response(
            "Evaluation failed. Your answers are saved. Please retry.",
            503,
        )

    # Step 2: Update mastery and unlock the next day.
    # The evaluated result remains saved if progression fails.
    try:
        progression = finalize_learning_day(attempt)

    except Exception:
        logger.exception("Learning progression failed.")

        return Response({
            "success": False,
            "message": (
                "Assessment evaluated successfully, "
                "but progress could not be updated. "
                "Retry to recover your progress."
            ),
            "data": {
                "result": serialize_safe_daily_result(attempt),
                "progression_pending": True,
            },
        }, status=503)

    return success_response(
        {
            "result": serialize_safe_daily_result(attempt),
            "progression": progression,
            "adaptation_available": (
                attempt.passed
                and progression["day_completed"]
                and not progression["course_completed"]
            ),
        },
        "Daily assessment evaluated successfully.",
    )


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def daily_attempt_result_view(request, attempt_id):

    attempt = get_owned_daily_attempt(
        request,
        attempt_id,
    )

    if attempt.status != "evaluated":
        return error_response(
            "Assessment evaluation is not complete.",
            409,
        )

    return success_response(
        serialize_safe_daily_result(attempt)
    )