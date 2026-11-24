import logging

from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response

from learning.models import (
    Assessment,
    AssessmentAttempt,
    Question,
    UserAnswer,
)

from learning.services.evaluation_service import (
    AssessmentEvaluationError,
    start_assessment_attempt,
    save_user_answer,
    submit_assessment,
    evaluate_initial_assessment,
)

from .permissions import IsLearningAuthenticated
from .enrollment_views import get_owned_enrollment


logger = logging.getLogger(__name__)


def serialize_assessment(assessment):

    questions = Question.objects.filter(
        assessment=assessment
    ).order_by("order")

    return {
        "assessment_id": assessment.id,
        "title": assessment.title,
        "assessment_type": assessment.assessment_type,
        "day_number": assessment.day_number,
        "total_questions": assessment.total_questions,
        "total_marks": sum(q.marks for q in questions),
        "questions": [
            {
                "question_id": question.id,
                "order": question.order,
                "question_type": question.question_type,
                "topic": question.topic,
                "difficulty": question.difficulty,
                "question_text": question.question_text,
                "options": question.options,
                "marks": question.marks,
            }
            for question in questions
        ],
    }


def serialize_attempt(attempt):

    return {
        "attempt_id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "attempt_number": attempt.attempt_number,
        "status": attempt.status,
        "total_marks": attempt.total_marks,
        "answers": [
            {
                "question_id": answer.question_id,
                "submitted_answer": answer.submitted_answer,
            }
            for answer in UserAnswer.objects.filter(
                attempt=attempt
            )
        ],
    }


def serialize_result(attempt):

    return {
        "attempt_id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "status": attempt.status,
        "obtained_marks": attempt.obtained_marks,
        "total_marks": attempt.total_marks,
        "percentage": attempt.percentage,
        "passed": attempt.passed,
        "skill_level": attempt.assessment.enrollment.skill_level,
        "strengths": attempt.strengths,
        "weaknesses": attempt.weaknesses,
        "recommendations": attempt.recommendations,
        "ai_feedback": attempt.ai_feedback,
        "question_results": [
            {
                "question_id": answer.question_id,
                "question_text": answer.question.question_text,
                "question_type": answer.question.question_type,
                "submitted_answer": answer.submitted_answer,
                "is_correct": answer.is_correct,
                "marks_awarded": answer.marks_awarded,
                "maximum_marks": answer.question.marks,
                "feedback": answer.ai_feedback,
            }
            for answer in UserAnswer.objects.filter(
                attempt=attempt
            ).select_related("question").order_by(
                "question__order"
            )
        ],
    }


def get_owned_assessment(request, assessment_id):

    return get_object_or_404(
        Assessment,
        id=assessment_id,
        enrollment__user=request.user,
        assessment_type="initial",
    )


def get_owned_attempt(request, attempt_id):

    return get_object_or_404(
        AssessmentAttempt,
        id=attempt_id,
        assessment__enrollment__user=request.user,
        assessment__assessment_type="initial",
    )


def service_error(exc):

    return Response({
        "success": False,
        "message": str(exc),
    }, status=400)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def initial_assessment_view(request, enrollment_id):

    enrollment = get_owned_enrollment(
        request,
        enrollment_id,
    )

    assessment = get_object_or_404(
        Assessment,
        enrollment=enrollment,
        assessment_type="initial",
        day_number=0,
    )

    return Response({
        "success": True,
        "data": serialize_assessment(assessment),
    })


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def start_assessment_view(request, assessment_id):

    assessment = get_owned_assessment(
        request,
        assessment_id,
    )

    try:
        with transaction.atomic():

            assessment = Assessment.objects.select_for_update().get(
                pk=assessment.pk
            )

            existing = AssessmentAttempt.objects.filter(
                assessment=assessment
            ).order_by("-attempt_number").first()

            if existing:
                attempt = existing
            else:
                attempt = start_assessment_attempt(assessment)

        return Response({
            "success": True,
            "data": serialize_attempt(attempt),
        })

    except AssessmentEvaluationError as exc:
        return service_error(exc)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def save_answers_view(request, attempt_id):

    attempt = get_owned_attempt(
        request,
        attempt_id,
    )

    answers = request.data.get("answers")

    if (
        not isinstance(answers, list)
        or not 1 <= len(answers) <= 15
    ):
        return Response({
            "success": False,
            "message": "Provide between 1 and 15 answers.",
        }, status=400)

    question_ids = set()

    for answer in answers:

        if not isinstance(answer, dict):
            return Response({
                "success": False,
                "message": "Invalid answer format.",
            }, status=400)

        question_id = answer.get("question_id")
        submitted_answer = answer.get("submitted_answer")

        if (
            type(question_id) is not int
            or question_id <= 0
            or not isinstance(submitted_answer, str)
            or len(submitted_answer) > 20000
            or question_id in question_ids
        ):
            return Response({
                "success": False,
                "message": "Invalid or duplicate answer.",
            }, status=400)

        question_ids.add(question_id)

    try:
        with transaction.atomic():

            for answer in answers:

                save_user_answer(
                    attempt,
                    answer["question_id"],
                    answer["submitted_answer"],
                )

        attempt.refresh_from_db()

        return Response({
            "success": True,
            "message": "Answers saved successfully.",
            "data": serialize_attempt(attempt),
        })

    except AssessmentEvaluationError as exc:
        return service_error(exc)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def submit_assessment_view(request, attempt_id):

    attempt = get_owned_attempt(
        request,
        attempt_id,
    )

    try:
        if attempt.status == "in_progress":
            submit_assessment(attempt)

        attempt.refresh_from_db()

        return Response({
            "success": True,
            "message": "Assessment submitted successfully.",
            "data": serialize_attempt(attempt),
        })

    except AssessmentEvaluationError as exc:
        return service_error(exc)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def evaluate_assessment_view(request, attempt_id):

    attempt = get_owned_attempt(
        request,
        attempt_id,
    )

    if attempt.status not in [
        "submitted",
        "failed",
        "evaluated",
    ]:
        return Response({
            "success": False,
            "message": "Assessment is not ready for evaluation.",
        }, status=409)

    try:
        evaluate_initial_assessment(attempt)

        attempt.refresh_from_db()

        return Response({
            "success": True,
            "message": "Assessment evaluated successfully.",
            "data": serialize_result(attempt),
        })

    except Exception:
        logger.exception("Initial assessment evaluation failed.")

        return Response({
            "success": False,
            "message": (
                "Evaluation could not be completed. "
                "Your answers are saved. Please retry."
            ),
        }, status=503)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def assessment_result_view(request, attempt_id):

    attempt = get_owned_attempt(
        request,
        attempt_id,
    )

    if attempt.status != "evaluated":
        return Response({
            "success": False,
            "message": "Assessment evaluation is not complete.",
        }, status=409)

    return Response({
        "success": True,
        "data": serialize_result(attempt),
    })