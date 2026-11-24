from django.shortcuts import get_object_or_404

from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response

from learning.models import Enrollment
from learning.services.assessment_service import (
    LANGUAGE_TOPICS,
    generate_initial_assessment,
)
from learning.services.roadmap_service import (
    generate_personalized_roadmap,
)
from learning.services.dashboard_service import (
    get_roadmap_overview,
)

from .permissions import IsLearningAuthenticated

import logging

logger = logging.getLogger(__name__)


def serialize_enrollment(enrollment):
    return {
        "id": enrollment.id,
        "language": enrollment.language,
        "language_name": enrollment.get_language_display(),
        "skill_level": enrollment.skill_level,
        "status": enrollment.status,
        "current_day": enrollment.current_day,
        "strengths": enrollment.strengths,
        "weaknesses": enrollment.weaknesses,
        "created_at": enrollment.created_at.isoformat(),
    }


def get_owned_enrollment(request, enrollment_id):
    return get_object_or_404(
        Enrollment,
        id=enrollment_id,
        user=request.user,
    )


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def languages_view(request):

    languages = [
        {"id": "cpp", "name": "C++"},
        {"id": "python", "name": "Python"},
        {"id": "javascript", "name": "JavaScript"},
        {"id": "java", "name": "Java"},
        {"id": "sql", "name": "SQL"},
    ]

    for language in languages:
        language["topics"] = LANGUAGE_TOPICS[language["id"]]
        language["duration_days"] = 30

    return Response({
        "success": True,
        "data": languages,
    })


@api_view(["GET", "POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def enrollments_view(request):

    if request.method == "GET":

        enrollments = Enrollment.objects.filter(
            user=request.user
        ).order_by("-created_at")

        return Response({
            "success": True,
            "data": [
                serialize_enrollment(enrollment)
                for enrollment in enrollments
            ],
        })

    language = request.data.get("language")

    if (
        not isinstance(language, str)
        or language not in LANGUAGE_TOPICS
    ):
        return Response({
            "success": False,
            "message": "Select a supported programming language.",
        }, status=400)

    enrollment, created = Enrollment.objects.get_or_create(
        user=request.user,
        language=language,
    )

    return Response({
        "success": True,
        "message": (
            "Enrollment created successfully."
            if created
            else "Existing enrollment retrieved."
        ),
        "data": serialize_enrollment(enrollment),
    }, status=201 if created else 200)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def enrollment_detail_view(request, enrollment_id):

    enrollment = get_owned_enrollment(
        request,
        enrollment_id,
    )

    return Response({
        "success": True,
        "data": serialize_enrollment(enrollment),
    })


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def generate_initial_assessment_view(request, enrollment_id):

    enrollment = get_owned_enrollment(
        request,
        enrollment_id,
    )

    try:
        assessment = generate_initial_assessment(enrollment)

        return Response({
            "success": True,
            "message": "Initial assessment is ready.",
            "data": {
                "assessment_id": assessment.id,
                "total_questions": assessment.total_questions,
            },
        })

    except Exception:
        logger.exception("Initial assessment generation failed.")

        return Response({
            "success": False,
            "message": (
                "Unable to generate assessment. "
                "Please retry."
            ),
        }, status=503)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def generate_roadmap_view(request, enrollment_id):

    enrollment = get_owned_enrollment(
        request,
        enrollment_id,
    )

    if enrollment.skill_level == "unassessed":
        return Response({
            "success": False,
            "message": "Complete your initial assessment first.",
        }, status=409)

    try:
        generate_personalized_roadmap(enrollment)

        enrollment.refresh_from_db()

        return Response({
            "success": True,
            "message": "Personalized roadmap is ready.",
            "data": {
                "enrollment": serialize_enrollment(enrollment),
                "roadmap": get_roadmap_overview(enrollment),
            },
        })

    except Exception:
        logger.exception("Roadmap generation failed.")

        return Response({
            "success": False,
            "message": (
                "Unable to generate roadmap. "
                "Your assessment results are saved. Please retry."
            ),
        }, status=503)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def roadmap_view(request, enrollment_id):

    enrollment = get_owned_enrollment(
        request,
        enrollment_id,
    )

    return Response({
        "success": True,
        "data": get_roadmap_overview(enrollment),
    })