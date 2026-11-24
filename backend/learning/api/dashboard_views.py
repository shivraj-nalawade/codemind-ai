import logging

from django.shortcuts import get_object_or_404

from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.authentication import SessionAuthentication

from learning.models import AIGenerationJob

from learning.services.dashboard_service import (
    get_learning_dashboard,
    DashboardError,
)

from learning.services.adaptive_roadmap_service import (
    adapt_personalized_roadmap,
    get_adaptation_eligibility,
    get_roadmap_adaptation_history,
)

from .permissions import IsLearningAuthenticated

from .enrollment_views import get_owned_enrollment

from .lesson_views import (
    success_response,
    error_response,
)


logger = logging.getLogger(__name__)


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def dashboard_view(request, enrollment_id):

    enrollment = get_owned_enrollment(
        request,
        enrollment_id,
    )

    timezone_name = request.query_params.get(
        "timezone",
        "Asia/Kolkata",
    )

    try:
        dashboard = get_learning_dashboard(
            enrollment,
            timezone_name=timezone_name,
        )

        return success_response(dashboard)

    except DashboardError as exc:
        return error_response(str(exc))


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def adapt_roadmap_view(request, enrollment_id):

    enrollment = get_owned_enrollment(
        request,
        enrollment_id,
    )

    try:
        result = adapt_personalized_roadmap(enrollment)

        return success_response(
            result,
            "Roadmap adaptation processed successfully.",
        )

    except Exception:
        logger.exception("Roadmap adaptation failed.")

        return error_response(
            "Adaptation failed. Your learning progress is safe. Please retry.",
            503,
        )


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def adaptation_status_view(request, enrollment_id):

    enrollment = get_owned_enrollment(
        request,
        enrollment_id,
    )

    return success_response({
        "eligibility": get_adaptation_eligibility(enrollment),
        "history": get_roadmap_adaptation_history(enrollment),
    })


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def ai_jobs_view(request, enrollment_id):

    enrollment = get_owned_enrollment(
        request,
        enrollment_id,
    )

    jobs = AIGenerationJob.objects.filter(
        enrollment=enrollment
    ).order_by("-created_at")[:50]

    return success_response([
        {
            "job_id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "attempt_count": job.attempt_count,
            "created_at": job.created_at.isoformat(),
            "completed_at": (
                job.completed_at.isoformat()
                if job.completed_at else None
            ),
            "can_retry": job.status == "failed",
        }
        for job in jobs
    ])


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsLearningAuthenticated])
def ai_job_detail_view(request, job_id):

    job = get_object_or_404(
        AIGenerationJob,
        id=job_id,
        enrollment__user=request.user,
    )

    return success_response({
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "attempt_count": job.attempt_count,
        "can_retry": job.status == "failed",
    })