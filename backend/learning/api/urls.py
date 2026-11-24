from django.urls import path

from .auth_views import (
    csrf_view,
    register_view,
    login_view,
    logout_view,
    current_user_view,
)

from .enrollment_views import (
    languages_view,
    enrollments_view,
    enrollment_detail_view,
    generate_initial_assessment_view,
    generate_roadmap_view,
    roadmap_view,
)

from .assessment_views import (
    initial_assessment_view,
    start_assessment_view,
    save_answers_view,
    submit_assessment_view,
    evaluate_assessment_view,
    assessment_result_view,
)

from .lesson_views import (
    lesson_detail_view,
    generate_lesson_view,
    start_day_view,
    complete_lesson_view,
    complete_practical_view,
    generate_daily_assessment_view,
    daily_assessment_view,
)

from .daily_assessment_views import (
    start_daily_attempt_view,
    daily_attempt_detail_view,
    save_daily_answers_view,
    submit_daily_attempt_view,
    evaluate_daily_attempt_view,
    daily_attempt_result_view,
)

from .dashboard_views import (
    dashboard_view,
    adapt_roadmap_view,
    adaptation_status_view,
    ai_jobs_view,
    ai_job_detail_view,
)


app_name = "learning"


urlpatterns = [

    # =====================================================
    # AUTHENTICATION
    # =====================================================

    path("auth/csrf/", csrf_view, name="csrf"),
    path("auth/register/", register_view, name="register"),
    path("auth/login/", login_view, name="login"),
    path("auth/logout/", logout_view, name="logout"),
    path("auth/me/", current_user_view, name="current_user"),

    # =====================================================
    # LANGUAGES AND ENROLLMENTS
    # =====================================================

    path(
        "languages/",
        languages_view,
        name="languages",
    ),

    path(
        "enrollments/",
        enrollments_view,
        name="enrollments",
    ),

    path(
        "enrollments/<int:enrollment_id>/",
        enrollment_detail_view,
        name="enrollment_detail",
    ),

    # =====================================================
    # INITIAL ASSESSMENT
    # =====================================================

    path(
        "enrollments/<int:enrollment_id>/assessment/generate/",
        generate_initial_assessment_view,
        name="generate_initial_assessment",
    ),

    path(
        "enrollments/<int:enrollment_id>/assessment/",
        initial_assessment_view,
        name="initial_assessment",
    ),

    path(
        "assessments/<int:assessment_id>/start/",
        start_assessment_view,
        name="start_assessment",
    ),

    path(
        "attempts/<int:attempt_id>/answers/",
        save_answers_view,
        name="save_answers",
    ),

    path(
        "attempts/<int:attempt_id>/submit/",
        submit_assessment_view,
        name="submit_assessment",
    ),

    path(
        "attempts/<int:attempt_id>/evaluate/",
        evaluate_assessment_view,
        name="evaluate_assessment",
    ),

    path(
        "attempts/<int:attempt_id>/result/",
        assessment_result_view,
        name="assessment_result",
    ),

    # =====================================================
    # PERSONALIZED ROADMAP
    # =====================================================

    path(
        "enrollments/<int:enrollment_id>/roadmap/generate/",
        generate_roadmap_view,
        name="generate_roadmap",
    ),

    path(
        "enrollments/<int:enrollment_id>/roadmap/",
        roadmap_view,
        name="roadmap",
    ),

    # =====================================================
    # DAILY LESSONS
    # =====================================================

    path(
        "days/<int:day_id>/",
        lesson_detail_view,
        name="lesson_detail",
    ),

    path(
        "days/<int:day_id>/lesson/generate/",
        generate_lesson_view,
        name="generate_lesson",
    ),

    path(
        "days/<int:day_id>/start/",
        start_day_view,
        name="start_day",
    ),

    path(
        "days/<int:day_id>/lesson/complete/",
        complete_lesson_view,
        name="complete_lesson",
    ),

    path(
        "days/<int:day_id>/practical/complete/",
        complete_practical_view,
        name="complete_practical",
    ),

    # =====================================================
    # DAILY ASSESSMENTS
    # =====================================================

    path(
        "days/<int:day_id>/assessment/generate/",
        generate_daily_assessment_view,
        name="generate_daily_assessment",
    ),

    path(
        "days/<int:day_id>/assessment/",
        daily_assessment_view,
        name="daily_assessment",
    ),

    path(
        "days/<int:day_id>/assessment/start/",
        start_daily_attempt_view,
        name="start_daily_attempt",
    ),

    path(
        "daily-attempts/<int:attempt_id>/",
        daily_attempt_detail_view,
        name="daily_attempt_detail",
    ),

    path(
        "daily-attempts/<int:attempt_id>/answers/",
        save_daily_answers_view,
        name="save_daily_answers",
    ),

    path(
        "daily-attempts/<int:attempt_id>/submit/",
        submit_daily_attempt_view,
        name="submit_daily_attempt",
    ),

    path(
        "daily-attempts/<int:attempt_id>/evaluate/",
        evaluate_daily_attempt_view,
        name="evaluate_daily_attempt",
    ),

    path(
        "daily-attempts/<int:attempt_id>/result/",
        daily_attempt_result_view,
        name="daily_attempt_result",
    ),

    # =====================================================
    # DASHBOARD
    # =====================================================

    path(
        "enrollments/<int:enrollment_id>/dashboard/",
        dashboard_view,
        name="dashboard",
    ),

    # =====================================================
    # ADAPTIVE ROADMAP
    # =====================================================

    path(
        "enrollments/<int:enrollment_id>/roadmap/adapt/",
        adapt_roadmap_view,
        name="adapt_roadmap",
    ),

    path(
        "enrollments/<int:enrollment_id>/roadmap/adaptation/",
        adaptation_status_view,
        name="adaptation_status",
    ),

    # =====================================================
    # AI GENERATION JOBS
    # =====================================================

    path(
        "enrollments/<int:enrollment_id>/jobs/",
        ai_jobs_view,
        name="ai_jobs",
    ),

    path(
        "jobs/<int:job_id>/",
        ai_job_detail_view,
        name="ai_job_detail",
    ),

]