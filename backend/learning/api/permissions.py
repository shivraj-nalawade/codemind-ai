from rest_framework.permissions import BasePermission


class IsLearningAuthenticated(BasePermission):
    """
    Allow access only to authenticated, active users.
    """

    message = "Authentication is required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
        )


class IsEnrollmentOwner(IsLearningAuthenticated):
    """
    Allow users to access only their own learning records.
    """

    message = "You do not have permission to access this learning record."

    def has_object_permission(self, request, view, obj):

        if not self.has_permission(request, view):
            return False

        # Enrollment
        if hasattr(obj, "user_id"):
            return obj.user_id == request.user.id

        # LearningDay, Assessment, TopicMastery,
        # LearningActivity, AIGenerationJob
        if hasattr(obj, "enrollment"):
            return obj.enrollment.user_id == request.user.id

        # DayProgress
        if hasattr(obj, "learning_day"):
            return (
                obj.learning_day.enrollment.user_id
                == request.user.id
            )

        # AssessmentAttempt, Question
        if hasattr(obj, "assessment"):
            return (
                obj.assessment.enrollment.user_id
                == request.user.id
            )

        # UserAnswer
        if hasattr(obj, "attempt"):
            return (
                obj.attempt.assessment.enrollment.user_id
                == request.user.id
            )

        return False