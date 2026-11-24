import logging

from django.db import transaction
from django.utils import timezone

from learning.models import (
    Enrollment,
    LearningDay,
    DayProgress,
    LearningActivity,
)


logger = logging.getLogger(__name__)

DAILY_PASS_PERCENTAGE = 80.0
TOTAL_LEARNING_DAYS = 30


class LearningProgressError(Exception):
    pass


# ==========================================
# 1. Retrieve Daily Progress
# ==========================================

def get_day_progress(learning_day):

    try:

        progress = (
            DayProgress.objects
            .select_related(
                "learning_day",
                "learning_day__enrollment",
            )
            .get(learning_day=learning_day)
        )

    except DayProgress.DoesNotExist:

        raise LearningProgressError(
            "Learning day progress record not found."
        )

    return progress


# ==========================================
# 2. Retrieve Locked Progress Record
# ==========================================

def get_locked_progress_record(learning_day):

    try:

        progress = (
            DayProgress.objects
            .select_for_update()
            .get(learning_day=learning_day)
        )

    except DayProgress.DoesNotExist:

        raise LearningProgressError(
            "Learning day progress record not found."
        )

    return progress


# ==========================================
# 3. Validate Learning Day Accessibility
# ==========================================

def validate_day_access(progress):

    if progress.status == "locked":

        raise LearningProgressError(
            f"Day {progress.learning_day.day_number} "
            "is locked. Complete the previous "
            "learning day first."
        )

    if progress.status not in [
        "unlocked",
        "in_progress",
        "completed",
    ]:

        raise LearningProgressError(
            "Invalid learning day status."
        )

    return True


# ==========================================
# 4. Validate Generated Lesson Content
# ==========================================

def validate_lesson_content(learning_day):

    if not learning_day.is_content_generated:

        raise LearningProgressError(
            "Lesson content has not been generated yet."
        )

    if not learning_day.explanation.strip():

        raise LearningProgressError(
            "Lesson explanation is missing."
        )

    if (
        not isinstance(
            learning_day.code_examples,
            list,
        )
        or not learning_day.code_examples
    ):

        raise LearningProgressError(
            "Lesson code examples are missing."
        )

    if (
        not isinstance(
            learning_day.practical_tasks,
            list,
        )
        or not learning_day.practical_tasks
    ):

        raise LearningProgressError(
            "Lesson practical tasks are missing."
        )

    return True


# ==========================================
# 5. Validate Enrollment Status
# ==========================================

def validate_enrollment(enrollment):

    if enrollment.status == "pending":

        raise LearningProgressError(
            "Complete the initial assessment and "
            "generate the personalized roadmap first."
        )

    if enrollment.status not in [
        "active",
        "completed",
    ]:

        raise LearningProgressError(
            "Invalid enrollment status."
        )

    return True


# ==========================================
# 6. Retrieve Learning Records for Update
# ==========================================

def get_learning_records_for_update(learning_day):

    # Maintain a consistent database lock order.
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

    progress = get_locked_progress_record(
        learning_day
    )

    validate_enrollment(enrollment)

    validate_day_access(progress)

    return enrollment, learning_day, progress


# ==========================================
# 7. Record Learning Activity
# ==========================================

def record_learning_activity(
    enrollment,
    activity_type,
    description,
    metadata=None,
):

    valid_activity_types = {
        value
        for value, label in (
            LearningActivity._meta
            .get_field("activity_type")
            .flatchoices
        )
    }

    if activity_type not in valid_activity_types:

        raise LearningProgressError(
            f"Invalid activity type: {activity_type}"
        )

    activity = LearningActivity.objects.create(
        enrollment=enrollment,
        activity_type=activity_type,
        description=description,
        metadata=metadata or {},
    )

    return activity


# ==========================================
# 8. Start Learning Day
# ==========================================

@transaction.atomic
def start_learning_day(learning_day):

    enrollment, learning_day, progress = (
        get_learning_records_for_update(
            learning_day
        )
    )

    validate_lesson_content(
        learning_day
    )

    # Prevent duplicate status changes.
    if progress.status in [
        "in_progress",
        "completed",
    ]:

        return progress

    if enrollment.status != "active":

        raise LearningProgressError(
            "Enrollment is not active."
        )

    if learning_day.day_number != enrollment.current_day:

        raise LearningProgressError(
            "Only the current learning day "
            "can be started."
        )

    progress.status = "in_progress"

    if progress.unlocked_at is None:

        progress.unlocked_at = timezone.now()

    progress.save(update_fields=[
        "status",
        "unlocked_at",
        "updated_at",
    ])

    logger.info(
        "Learning day %s started "
        "for enrollment %s.",
        learning_day.day_number,
        enrollment.id,
    )

    return progress


# ==========================================
# 9. Mark Lesson as Completed
# ==========================================

@transaction.atomic
def mark_lesson_completed(learning_day):

    enrollment, learning_day, progress = (
        get_learning_records_for_update(
            learning_day
        )
    )

    validate_lesson_content(
        learning_day
    )

    # Prevent duplicate completion.
    if progress.lesson_completed:

        return progress

    if enrollment.status != "active":

        raise LearningProgressError(
            "Enrollment is not active."
        )

    if learning_day.day_number != enrollment.current_day:

        raise LearningProgressError(
            "Only the current lesson "
            "can be completed."
        )

    if progress.status != "in_progress":

        raise LearningProgressError(
            "Start the learning day before "
            "marking the lesson as completed."
        )

    progress.lesson_completed = True

    progress.save(update_fields=[
        "lesson_completed",
        "updated_at",
    ])

    logger.info(
        "Lesson completed for enrollment %s, "
        "day %s.",
        enrollment.id,
        learning_day.day_number,
    )

    return progress


# ==========================================
# 10. Mark Practical Tasks as Completed
# ==========================================

@transaction.atomic
def mark_practical_completed(learning_day):

    enrollment, learning_day, progress = (
        get_learning_records_for_update(
            learning_day
        )
    )

    validate_lesson_content(
        learning_day
    )

    # Prevent duplicate completion.
    if progress.practical_completed:

        return progress

    if enrollment.status != "active":

        raise LearningProgressError(
            "Enrollment is not active."
        )

    if learning_day.day_number != enrollment.current_day:

        raise LearningProgressError(
            "Only the current day's practical "
            "tasks can be completed."
        )

    if progress.status != "in_progress":

        raise LearningProgressError(
            "Start the learning day first."
        )

    if not progress.lesson_completed:

        raise LearningProgressError(
            "Complete the lesson before "
            "completing practical tasks."
        )

    progress.practical_completed = True

    progress.save(update_fields=[
        "practical_completed",
        "updated_at",
    ])

    logger.info(
        "Practical tasks completed "
        "for enrollment %s, day %s.",
        enrollment.id,
        learning_day.day_number,
    )

    return progress


# ==========================================
# 11. Check Daily Assessment Eligibility
# ==========================================

def check_daily_assessment_eligibility(
    learning_day,
):

    learning_day.refresh_from_db()

    progress = get_day_progress(
        learning_day
    )

    enrollment = learning_day.enrollment

    reasons = []

    if enrollment.status != "active":

        reasons.append(
            "Enrollment is not active."
        )

    if progress.status == "locked":

        reasons.append(
            "Learning day is locked."
        )

    elif progress.status != "in_progress":

        reasons.append(
            "Learning day must be in progress."
        )

    if learning_day.day_number != enrollment.current_day:

        reasons.append(
            "Assessment is not for the "
            "current learning day."
        )

    if not learning_day.is_content_generated:

        reasons.append(
            "Lesson content has not been generated."
        )

    else:

        try:

            validate_lesson_content(
                learning_day
            )

        except LearningProgressError as error:

            reasons.append(str(error))

    if not progress.lesson_completed:

        reasons.append(
            "Complete the lesson first."
        )

    if not progress.practical_completed:

        reasons.append(
            "Complete the practical tasks first."
        )

    if progress.assessment_completed:

        reasons.append(
            "Daily assessment is already completed."
        )

    return {
        "eligible": len(reasons) == 0,
        "day_number": learning_day.day_number,
        "status": progress.status,
        "lesson_completed": (
            progress.lesson_completed
        ),
        "practical_completed": (
            progress.practical_completed
        ),
        "assessment_completed": (
            progress.assessment_completed
        ),
        "reasons": reasons,
    }


# ==========================================
# 12. Enforce Daily Assessment Eligibility
# ==========================================

def require_daily_assessment_eligibility(
    learning_day,
):

    eligibility = (
        check_daily_assessment_eligibility(
            learning_day
        )
    )

    if not eligibility["eligible"]:

        error_message = " ".join(
            eligibility["reasons"]
        )

        raise LearningProgressError(
            error_message
        )

    return eligibility


# ==========================================
# 13. Calculate Daily Activity Completion
# ==========================================

def calculate_daily_completion_percentage(
    progress,
):

    activities = [
        progress.lesson_completed,
        progress.practical_completed,
        progress.assessment_completed,
    ]

    completed_activities = sum(
        bool(activity)
        for activity in activities
    )

    total_activities = len(activities)

    percentage = (
        completed_activities
        / total_activities
    ) * 100

    return round(percentage, 2)


# ==========================================
# 14. Retrieve Daily Progress Summary
# ==========================================

def get_daily_progress_summary(
    learning_day,
):

    learning_day.refresh_from_db()

    progress = get_day_progress(
        learning_day
    )

    eligibility = (
        check_daily_assessment_eligibility(
            learning_day
        )
    )

    # Do not expose lesson content for locked days.
    is_accessible = (
        progress.status != "locked"
    )

    return {
        "learning_day_id": learning_day.id,
        "day_number": learning_day.day_number,
        "title": learning_day.title,
        "topic": learning_day.topic,
        "difficulty": learning_day.difficulty,
        "estimated_minutes": (
            learning_day.estimated_minutes
        ),
        "status": progress.status,
        "is_accessible": is_accessible,
        "content_generated": (
            learning_day.is_content_generated
        ),
        "lesson_completed": (
            progress.lesson_completed
        ),
        "practical_completed": (
            progress.practical_completed
        ),
        "assessment_completed": (
            progress.assessment_completed
        ),
        "assessment_eligible": (
            eligibility["eligible"]
        ),
        "assessment_blocking_reasons": (
            eligibility["reasons"]
        ),
        "completion_percentage": (
            calculate_daily_completion_percentage(
                progress
            )
        ),
        "best_score": progress.best_score,
        "unlocked_at": (
            progress.unlocked_at.isoformat()
            if progress.unlocked_at
            else None
        ),
        "completed_at": (
            progress.completed_at.isoformat()
            if progress.completed_at
            else None
        ),
    }


# ==========================================
# 15. Retrieve Overall Learning Progress
# ==========================================

def get_enrollment_progress_summary(
    enrollment,
):

    enrollment.refresh_from_db()

    progress_records = list(
        DayProgress.objects.filter(
            learning_day__enrollment=enrollment
        ).select_related(
            "learning_day"
        ).order_by(
            "learning_day__day_number"
        )
    )

    total_days = len(progress_records)

    completed_days = sum(
        progress.status == "completed"
        for progress in progress_records
    )

    unlocked_days = sum(
        progress.status == "unlocked"
        for progress in progress_records
    )

    in_progress_days = sum(
        progress.status == "in_progress"
        for progress in progress_records
    )

    locked_days = sum(
        progress.status == "locked"
        for progress in progress_records
    )

    generated_lessons = sum(
        progress.learning_day.is_content_generated
        for progress in progress_records
    )

    completed_lessons = sum(
        progress.lesson_completed
        for progress in progress_records
    )

    completed_practicals = sum(
        progress.practical_completed
        for progress in progress_records
    )

    completed_assessments = sum(
        progress.assessment_completed
        for progress in progress_records
    )

    assessment_scores = [
        progress.best_score
        for progress in progress_records
        if progress.assessment_completed
    ]

    average_score = (
        round(
            sum(assessment_scores)
            / len(assessment_scores),
            2,
        )
        if assessment_scores
        else None
    )

    overall_percentage = (
        round(
            (completed_days / total_days) * 100,
            2,
        )
        if total_days
        else 0.0
    )

    current_learning_day = next(
        (
            progress.learning_day
            for progress in progress_records
            if progress.learning_day.day_number
            == enrollment.current_day
        ),
        None,
    )

    current_day_summary = (
        get_daily_progress_summary(
            current_learning_day
        )
        if current_learning_day
        else None
    )

    return {
        "enrollment_id": enrollment.id,
        "language": enrollment.language,
        "language_name": (
            enrollment.get_language_display()
        ),
        "skill_level": enrollment.skill_level,
        "enrollment_status": enrollment.status,
        "current_day": enrollment.current_day,
        "total_days": total_days,
        "completed_days": completed_days,
        "pending_days": (
            total_days - completed_days
        ),
        "unlocked_days": unlocked_days,
        "in_progress_days": in_progress_days,
        "locked_days": locked_days,
        "generated_lessons": generated_lessons,
        "completed_lessons": completed_lessons,
        "completed_practicals": completed_practicals,
        "completed_assessments": completed_assessments,
        "overall_progress_percentage": (
            overall_percentage
        ),
        "average_assessment_score": (
            average_score
        ),
        "current_day_progress": (
            current_day_summary
        ),
    }