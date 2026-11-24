import logging

from django.shortcuts import get_object_or_404

from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response

from learning.models import LearningDay

from learning.services.lesson_service import (
    generate_daily_lesson,
    LessonGenerationError,
)

from learning.services.progress_service import (
    start_learning_day,
    mark_lesson_completed,
    mark_practical_completed,
    get_daily_progress_summary,
    LearningProgressError,
)

from learning.services.daily_assessment_service import (
    generate_daily_assessment,
    get_daily_assessment_for_learner,
    DailyAssessmentGenerationError,
)

from .permissions import IsLearningAuthenticated


logger = logging.getLogger(__name__)


def get_owned_learning_day(request, day_id):

    return get_object_or_404(
        LearningDay,
        id=day_id,
        enrollment__user=request.user,
    )


def serialize_lesson(day):

    day.refresh_from_db()

    return {
        "learning_day_id": day.id,
        "day_number": day.day_number,
        "title": day.title,
        "topic": day.topic,
        "difficulty": day.difficulty,
        "learning_objectives": day.learning_objectives,
        "explanation": day.explanation,
        "code_examples": day.code_examples,
        "practical_tasks": day.practical_tasks,
        "estimated_minutes": day.estimated_minutes,
        "content_generated": day.is_content_generated,
        "progress": get_daily_progress_summary(day),
    }


def error_response(message, status=400):

    return Response({
        "success": False,
        "message": message,
    }, status=status)


def success_response(data, message="Request successful."):

    return Response({
        "success": True,
        "message": message,
        "data": data,
    })


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def lesson_detail_view(request, day_id):

    day = get_owned_learning_day(request, day_id)

    progress = get_daily_progress_summary(day)

    if not progress["is_accessible"]:
        return error_response(
            "This learning day is locked.",
            409,
        )

    return success_response(
        serialize_lesson(day)
    )


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def generate_lesson_view(request, day_id):

    day = get_owned_learning_day(request, day_id)

    if not get_daily_progress_summary(day)["is_accessible"]:
        return error_response(
            "This learning day is locked.",
            409,
        )

    try:
        generate_daily_lesson(day)

        return success_response(
            serialize_lesson(day),
            "Lesson generated successfully.",
        )

    except Exception:
        logger.exception("Daily lesson generation failed.")

        return error_response(
            "Unable to generate lesson. Please retry.",
            503,
        )


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def start_day_view(request, day_id):

    day = get_owned_learning_day(request, day_id)

    try:
        start_learning_day(day)

        return success_response(
            get_daily_progress_summary(day),
            "Learning day started.",
        )

    except LearningProgressError as exc:
        return error_response(str(exc), 409)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def complete_lesson_view(request, day_id):

    day = get_owned_learning_day(request, day_id)

    try:
        mark_lesson_completed(day)

        return success_response(
            get_daily_progress_summary(day),
            "Lesson marked as completed.",
        )

    except LearningProgressError as exc:
        return error_response(str(exc), 409)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def complete_practical_view(request, day_id):

    day = get_owned_learning_day(request, day_id)

    try:
        mark_practical_completed(day)

        return success_response(
            get_daily_progress_summary(day),
            "Practical tasks marked as completed.",
        )

    except LearningProgressError as exc:
        return error_response(str(exc), 409)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def generate_daily_assessment_view(request, day_id):

    day = get_owned_learning_day(request, day_id)

    progress = get_daily_progress_summary(day)

    if not progress["assessment_eligible"]:
        return Response({
            "success": False,
            "message": "Daily assessment is not available.",
            "reasons": progress["assessment_blocking_reasons"],
        }, status=409)

    try:
        generate_daily_assessment(day)

        return success_response(
            get_daily_assessment_for_learner(day),
            "Daily assessment generated successfully.",
        )

    except Exception:
        logger.exception("Daily assessment generation failed.")

        return error_response(
            "Unable to generate assessment. Please retry.",
            503,
        )


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def daily_assessment_view(request, day_id):

    day = get_owned_learning_day(request, day_id)

    try:
        return success_response(
            get_daily_assessment_for_learner(day)
        )

    except DailyAssessmentGenerationError:
        return error_response(
            "Daily assessment is not available yet.",
            409,
        )