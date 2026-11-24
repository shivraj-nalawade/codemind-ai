from django.contrib import admin

from .models import (
    Enrollment,
    Assessment,
    Question,
    LearningDay,
    AssessmentAttempt,
    UserAnswer,
    DayProgress,
    TopicMastery,
    LearningActivity,
    AIGenerationJob,
)


# ==========================================
# 1. Enrollment Admin
# ==========================================

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "language",
        "skill_level",
        "status",
        "current_day",
        "created_at",
    )

    list_filter = (
        "language",
        "skill_level",
        "status",
    )

    search_fields = (
        "user__username",
        "language",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


# ==========================================
# 2. Assessment Admin
# ==========================================

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "title",
        "enrollment",
        "assessment_type",
        "day_number",
        "total_questions",
        "created_at",
    )

    list_filter = (
        "assessment_type",
        "day_number",
    )

    search_fields = (
        "title",
        "enrollment__user__username",
    )


# ==========================================
# 3. Question Admin
# ==========================================

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "assessment",
        "topic",
        "question_type",
        "difficulty",
        "marks",
        "order",
    )

    list_filter = (
        "question_type",
        "difficulty",
        "topic",
    )

    search_fields = (
        "question_text",
        "topic",
    )


# ==========================================
# 4. Learning Day Admin
# ==========================================

@admin.register(LearningDay)
class LearningDayAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "enrollment",
        "day_number",
        "title",
        "difficulty",
        "is_content_generated",
    )

    list_filter = (
        "difficulty",
        "is_content_generated",
        "day_number",
    )

    search_fields = (
        "title",
        "topic",
    )


# ==========================================
# 5. Assessment Attempt Admin
# ==========================================

@admin.register(AssessmentAttempt)
class AssessmentAttemptAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "assessment",
        "attempt_number",
        "status",
        "percentage",
        "passed",
        "submitted_at",
    )

    list_filter = (
        "status",
        "passed",
    )

    search_fields = (
        "assessment__title",
        "assessment__enrollment__user__username",
    )


# ==========================================
# 6. User Answer Admin
# ==========================================

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "attempt",
        "question",
        "is_correct",
        "marks_awarded",
        "is_evaluated",
    )

    list_filter = (
        "is_correct",
        "is_evaluated",
    )

    search_fields = (
        "submitted_answer",
        "question__topic",
    )


# ==========================================
# 7. Day Progress Admin
# ==========================================

@admin.register(DayProgress)
class DayProgressAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "learning_day",
        "status",
        "lesson_completed",
        "practical_completed",
        "assessment_completed",
        "best_score",
    )

    list_filter = (
        "status",
        "lesson_completed",
        "practical_completed",
        "assessment_completed",
    )


# ==========================================
# 8. Topic Mastery Admin
# ==========================================

@admin.register(TopicMastery)
class TopicMasteryAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "enrollment",
        "topic",
        "initial_score",
        "mastery_score",
        "improvement",
        "recommended_difficulty",
    )

    list_filter = (
        "recommended_difficulty",
    )

    search_fields = (
        "topic",
        "enrollment__user__username",
    )


# ==========================================
# 9. Learning Activity Admin
# ==========================================

@admin.register(LearningActivity)
class LearningActivityAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "enrollment",
        "learning_day",
        "activity_type",
        "created_at",
    )

    list_filter = (
        "activity_type",
        "created_at",
    )

    search_fields = (
        "description",
        "enrollment__user__username",
    )


# ==========================================
# 10. AI Generation Job Admin
# ==========================================

@admin.register(AIGenerationJob)
class AIGenerationJobAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "enrollment",
        "job_type",
        "status",
        "attempt_count",
        "created_at",
        "completed_at",
    )

    list_filter = (
        "job_type",
        "status",
    )

    search_fields = (
        "idempotency_key",
        "error_message",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )