from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

from learning.models import (
    Enrollment,
    LearningDay,
    DayProgress,
    AssessmentAttempt,
    TopicMastery,
    LearningActivity,
    AIGenerationJob,
)


# ==========================================
# Configuration
# ==========================================

TOTAL_LEARNING_DAYS = 30

DEFAULT_TIMEZONE = "Asia/Kolkata"

DAILY_PASS_PERCENTAGE = 80.0


# ==========================================
# Custom Exception
# ==========================================

class DashboardError(Exception):
    pass


# ==========================================
# 1. Resolve Dashboard Timezone
# ==========================================

def get_dashboard_timezone(
    timezone_name=DEFAULT_TIMEZONE,
):

    try:

        return ZoneInfo(timezone_name)

    except (ZoneInfoNotFoundError, ValueError) as error:

        raise DashboardError(
            f"Invalid or unavailable timezone: "
            f"{timezone_name}"
        ) from error


# ==========================================
# 2. Convert Timestamp
# ==========================================

def serialize_datetime(value, local_timezone):

    if value is None:
        return None

    return timezone.localtime(
        value,
        local_timezone,
    ).isoformat()


# ==========================================
# 3. Calculate Percentage
# ==========================================

def calculate_percentage(value, total):

    if total <= 0:
        return 0.0

    return round(
        value / total * 100,
        2,
    )


# ==========================================
# 4. Calculate Average
# ==========================================

def calculate_average(values):

    if not values:
        return None

    return round(
        sum(values) / len(values),
        2,
    )


# ==========================================
# 5. Enrollment Overview
# ==========================================

def get_enrollment_overview(enrollment):

    enrollment.refresh_from_db()

    return {
        "enrollment_id": enrollment.id,
        "language": enrollment.language,
        "language_name": (
            enrollment.get_language_display()
        ),
        "skill_level": enrollment.skill_level,
        "skill_level_display": (
            enrollment.get_skill_level_display()
        ),
        "status": enrollment.status,
        "status_display": (
            enrollment.get_status_display()
        ),
        "current_day": enrollment.current_day,
        "initial_strengths": enrollment.strengths,
        "initial_weaknesses": enrollment.weaknesses,
        "created_at": enrollment.created_at.isoformat(),
        "course_completed": (
            enrollment.status == "completed"
        ),
    }


# ==========================================
# 6. Course Progress Statistics
# ==========================================

def get_course_progress(enrollment):

    days = list(
        LearningDay.objects.filter(
            enrollment=enrollment
        ).order_by("day_number")
    )

    progress_records = list(
        DayProgress.objects.filter(
            learning_day__enrollment=enrollment
        )
    )

    total_days = len(days)

    completed_days = sum(
        record.status == "completed"
        for record in progress_records
    )

    unlocked_days = sum(
        record.status == "unlocked"
        for record in progress_records
    )

    in_progress_days = sum(
        record.status == "in_progress"
        for record in progress_records
    )

    locked_days = sum(
        record.status == "locked"
        for record in progress_records
    )

    completed_lessons = sum(
        record.lesson_completed
        for record in progress_records
    )

    completed_practicals = sum(
        record.practical_completed
        for record in progress_records
    )

    completed_assessments = sum(
        record.assessment_completed
        for record in progress_records
    )

    generated_lessons = sum(
        day.is_content_generated
        for day in days
    )

    completed_scores = [
        record.best_score
        for record in progress_records
        if record.assessment_completed
    ]

    return {
        "planned_days": TOTAL_LEARNING_DAYS,
        "total_days": total_days,
        "completed_days": completed_days,
        "pending_days": total_days - completed_days,
        "unlocked_days": unlocked_days,
        "in_progress_days": in_progress_days,
        "locked_days": locked_days,
        "completed_lessons": completed_lessons,
        "completed_practicals": completed_practicals,
        "completed_assessments": completed_assessments,
        "generated_lessons": generated_lessons,
        "overall_progress_percentage": (
            calculate_percentage(
                completed_days,
                TOTAL_LEARNING_DAYS,
            )
        ),
        "average_completed_day_score": (
            calculate_average(completed_scores)
        ),
        "roadmap_generated": (
            total_days == TOTAL_LEARNING_DAYS
        ),
    }


# ==========================================
# 7. Calculate Streaks From Dates
# ==========================================

def calculate_streaks(completion_dates, today):

    # Remove duplicate and future dates.

    dates = sorted({
        date
        for date in completion_dates
        if date <= today
    })

    if not dates:

        return {
            "current_streak": 0,
            "longest_streak": 0,
            "active_learning_days": 0,
            "completed_today": False,
            "last_learning_date": None,
            "streak_active": False,
        }

    date_set = set(dates)

    # Calculate longest historical streak.

    longest_streak = 1
    running_streak = 1

    for index in range(1, len(dates)):

        difference = (
            dates[index] - dates[index - 1]
        ).days

        if difference == 1:

            running_streak += 1

        else:

            running_streak = 1

        longest_streak = max(
            longest_streak,
            running_streak,
        )

    # Current streak may end today or yesterday.

    current_streak = 0

    if today in date_set:

        cursor = today

    elif today - timedelta(days=1) in date_set:

        cursor = today - timedelta(days=1)

    else:

        cursor = None

    while cursor is not None and cursor in date_set:

        current_streak += 1

        cursor -= timedelta(days=1)

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "active_learning_days": len(dates),
        "completed_today": today in date_set,
        "last_learning_date": dates[-1].isoformat(),
        "streak_active": current_streak > 0,
    }


# ==========================================
# 8. Get Enrollment Streak Statistics
# ==========================================

def get_streak_statistics(
    enrollment,
    timezone_name=DEFAULT_TIMEZONE,
):

    local_timezone = get_dashboard_timezone(
        timezone_name
    )

    today = timezone.localdate(
        timezone=local_timezone
    )

    timestamps = (
        DayProgress.objects.filter(
            learning_day__enrollment=enrollment,
            status="completed",
            completed_at__isnull=False,
        ).values_list(
            "completed_at",
            flat=True,
        )
    )

    completion_dates = [
        timezone.localtime(
            timestamp,
            local_timezone,
        ).date()
        for timestamp in timestamps
    ]

    result = calculate_streaks(
        completion_dates,
        today,
    )

    result["timezone"] = timezone_name

    result["current_date"] = today.isoformat()

    return result


# ==========================================
# 9. Learning Calendar
# ==========================================

def get_learning_calendar(
    enrollment,
    timezone_name=DEFAULT_TIMEZONE,
    number_of_days=30,
):

    if (
        type(number_of_days) is not int
        or not 1 <= number_of_days <= 366
    ):

        raise DashboardError(
            "Calendar duration must be between "
            "1 and 366 days."
        )

    local_timezone = get_dashboard_timezone(
        timezone_name
    )

    today = timezone.localdate(
        timezone=local_timezone
    )

    start_date = today - timedelta(
        days=number_of_days - 1
    )

    completed_records = (
        DayProgress.objects.filter(
            learning_day__enrollment=enrollment,
            status="completed",
            completed_at__isnull=False,
        )
        .select_related("learning_day")
    )

    completion_map = {}

    for record in completed_records:

        date = timezone.localtime(
            record.completed_at,
            local_timezone,
        ).date()

        if not start_date <= date <= today:
            continue

        completion_map.setdefault(
            date,
            [],
        ).append(
            record.learning_day.day_number
        )

    calendar = []

    for offset in range(number_of_days):

        date = start_date + timedelta(
            days=offset
        )

        completed = sorted(
            completion_map.get(date, [])
        )

        calendar.append({
            "date": date.isoformat(),
            "completed_lessons": len(completed),
            "learning_days": completed,
            "is_active": bool(completed),
            "is_today": date == today,
        })

    return calendar


# ==========================================
# 10. Initial Assessment Summary
# ==========================================

def get_initial_assessment_summary(enrollment):

    attempt = (
        AssessmentAttempt.objects.filter(
            assessment__enrollment=enrollment,
            assessment__assessment_type="initial",
            status="evaluated",
        )
        .order_by("-evaluated_at", "-pk")
        .first()
    )

    if attempt is None:
        return None

    return {
        "attempt_id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "percentage": attempt.percentage,
        "obtained_marks": attempt.obtained_marks,
        "total_marks": attempt.total_marks,
        "strengths": attempt.strengths,
        "weaknesses": attempt.weaknesses,
        "recommendations": attempt.recommendations,
        "feedback": attempt.ai_feedback,
        "evaluated_at": (
            attempt.evaluated_at.isoformat()
            if attempt.evaluated_at
            else None
        ),
    }


# ==========================================
# 11. Daily Assessment Performance
# ==========================================

def get_daily_assessment_performance(enrollment):

    attempts = list(
        AssessmentAttempt.objects.filter(
            assessment__enrollment=enrollment,
            assessment__assessment_type="daily",
            status="evaluated",
        )
        .select_related("assessment")
        .order_by(
            "assessment__day_number",
            "attempt_number",
        )
    )

    grouped_attempts = {}

    for attempt in attempts:

        day_number = attempt.assessment.day_number

        grouped_attempts.setdefault(
            day_number,
            [],
        ).append(attempt)

    days = {
        day.day_number: day
        for day in LearningDay.objects.filter(
            enrollment=enrollment
        )
    }

    daily_scores = []

    for day_number, day_attempts in sorted(
        grouped_attempts.items()
    ):

        best_attempt = max(
            day_attempts,
            key=lambda item: item.percentage,
        )

        latest_attempt = day_attempts[-1]

        learning_day = days.get(day_number)

        daily_scores.append({
            "day_number": day_number,
            "title": (
                learning_day.title
                if learning_day
                else f"Day {day_number}"
            ),
            "topic": (
                learning_day.topic
                if learning_day
                else None
            ),
            "best_score": best_attempt.percentage,
            "latest_score": latest_attempt.percentage,
            "attempt_count": len(day_attempts),
            "passed": any(
                attempt.passed
                for attempt in day_attempts
            ),
            "latest_feedback": (
                latest_attempt.ai_feedback
            ),
            "attempts": [
                {
                    "attempt_id": attempt.id,
                    "attempt_number": (
                        attempt.attempt_number
                    ),
                    "percentage": attempt.percentage,
                    "obtained_marks": (
                        attempt.obtained_marks
                    ),
                    "total_marks": attempt.total_marks,
                    "passed": attempt.passed,
                    "evaluated_at": (
                        attempt.evaluated_at.isoformat()
                        if attempt.evaluated_at
                        else None
                    ),
                }
                for attempt in day_attempts
            ],
        })

    all_scores = [
        attempt.percentage
        for attempt in attempts
    ]

    best_scores = [
        day["best_score"]
        for day in daily_scores
    ]

    passed_attempts = sum(
        attempt.passed
        for attempt in attempts
    )

    passed_days = sum(
        day["passed"]
        for day in daily_scores
    )

    latest_attempt = max(
        attempts,
        key=lambda item: (
            item.evaluated_at or item.started_at,
            item.id,
        ),
        default=None,
    )

    return {
        "total_evaluated_attempts": len(attempts),
        "passed_attempts": passed_attempts,
        "unsuccessful_attempts": (
            len(attempts) - passed_attempts
        ),
        "assessed_days": len(daily_scores),
        "passed_days": passed_days,
        "average_attempt_score": (
            calculate_average(all_scores)
        ),
        "average_best_daily_score": (
            calculate_average(best_scores)
        ),
        "highest_score": (
            max(all_scores)
            if all_scores
            else None
        ),
        "lowest_score": (
            min(all_scores)
            if all_scores
            else None
        ),
        "latest_score": (
            latest_attempt.percentage
            if latest_attempt
            else None
        ),
        "attempt_pass_rate": (
            calculate_percentage(
                passed_attempts,
                len(attempts),
            )
            if attempts
            else None
        ),
        "passing_percentage": DAILY_PASS_PERCENTAGE,
        "daily_scores": daily_scores,
    }


# ==========================================
# 12. Topic Mastery Analytics
# ==========================================

def get_topic_mastery_analytics(enrollment):

    records = TopicMastery.objects.filter(
        enrollment=enrollment
    ).order_by(
        "mastery_score",
        "topic",
    )

    # Determine which topics actually appeared
    # in the evaluated initial assessment.

    initial_attempt = (
        AssessmentAttempt.objects.filter(
            assessment__enrollment=enrollment,
            assessment__assessment_type="initial",
            status="evaluated",
        )
        .order_by("-evaluated_at", "-pk")
        .first()
    )

    initial_topics = set()

    if initial_attempt is not None:

        from learning.models import UserAnswer

        initial_topics = {
            topic.casefold()
            for topic in UserAnswer.objects.filter(
                attempt=initial_attempt,
                is_evaluated=True,
            ).values_list(
                "question__topic",
                flat=True,
            )
        }

    topics = []

    for record in records:

        initially_assessed = (
            record.topic.casefold()
            in initial_topics
        )

        initial_score = (
            record.initial_score
            if initially_assessed
            else None
        )

        improvement = (
            round(
                record.mastery_score
                - initial_score,
                2,
            )
            if initial_score is not None
            else None
        )

        if record.mastery_score >= 80:

            classification = "strong"

        elif record.mastery_score >= 50:

            classification = "developing"

        else:

            classification = "weak"

        topics.append({
            "topic": record.topic,
            "initially_assessed": initially_assessed,
            "initial_score": initial_score,
            "current_mastery": record.mastery_score,
            "improvement": improvement,
            "classification": classification,
            "recommended_difficulty": (
                record.recommended_difficulty
            ),
            "total_questions": record.total_questions,
            "correct_answers": record.correct_answers,
            "accuracy": (
                calculate_percentage(
                    record.correct_answers,
                    record.total_questions,
                )
            ),
            "last_practiced_at": (
                record.last_practiced_at.isoformat()
                if record.last_practiced_at
                else None
            ),
        })

    comparable_topics = [
        topic
        for topic in topics
        if topic["initially_assessed"]
    ]

    improved_topics = [
        topic
        for topic in comparable_topics
        if topic["improvement"] > 0
    ]

    improved_topics.sort(
        key=lambda item: item["improvement"],
        reverse=True,
    )

    return {
        "total_topics": len(topics),
        "strong_topics": [
            topic["topic"]
            for topic in topics
            if topic["classification"] == "strong"
        ],
        "developing_topics": [
            topic["topic"]
            for topic in topics
            if topic["classification"] == "developing"
        ],
        "weak_topics": [
            topic["topic"]
            for topic in topics
            if topic["classification"] == "weak"
        ],
        "average_initial_mastery": (
            calculate_average([
                topic["initial_score"]
                for topic in comparable_topics
            ])
        ),
        "average_current_mastery": (
            calculate_average([
                topic["current_mastery"]
                for topic in topics
            ])
        ),
        "average_mastery_improvement": (
            calculate_average([
                topic["improvement"]
                for topic in comparable_topics
            ])
        ),
        "improved_topics_count": len(improved_topics),
        "most_improved_topic": (
            improved_topics[0]
            if improved_topics
            else None
        ),
        "topics": topics,
    }


# ==========================================
# 13. Serialize Roadmap Day
# ==========================================

def serialize_roadmap_day(day, progress):

    return {
        "learning_day_id": day.id,
        "day_number": day.day_number,
        "title": day.title,
        "topic": day.topic,
        "difficulty": day.difficulty,
        "learning_objectives": (
            day.learning_objectives
        ),
        "estimated_minutes": day.estimated_minutes,
        "content_generated": day.is_content_generated,
        "status": (
            progress.status
            if progress
            else "locked"
        ),
        "is_accessible": (
            progress is not None
            and progress.status in (
                "unlocked",
                "in_progress",
                "completed",
            )
        ),
        "lesson_completed": (
            progress.lesson_completed
            if progress
            else False
        ),
        "practical_completed": (
            progress.practical_completed
            if progress
            else False
        ),
        "assessment_completed": (
            progress.assessment_completed
            if progress
            else False
        ),
        "best_score": (
            progress.best_score
            if progress
            else 0.0
        ),
    }


# ==========================================
# 14. Roadmap Overview
# ==========================================

def get_roadmap_overview(enrollment):

    days = LearningDay.objects.filter(
        enrollment=enrollment
    ).order_by("day_number")

    progress_lookup = {
        record.learning_day_id: record
        for record in DayProgress.objects.filter(
            learning_day__enrollment=enrollment
        )
    }

    return [
        serialize_roadmap_day(
            day,
            progress_lookup.get(day.id),
        )
        for day in days
    ]


# ==========================================
# 15. Current Learning Day
# ==========================================

def get_current_learning_day(enrollment):

    enrollment.refresh_from_db()

    if enrollment.status != "active":
        return None

    day = LearningDay.objects.filter(
        enrollment=enrollment,
        day_number=enrollment.current_day,
    ).first()

    if day is None:
        return None

    progress = DayProgress.objects.filter(
        learning_day=day
    ).first()

    result = serialize_roadmap_day(
        day,
        progress,
    )

    if not result["is_accessible"]:

        next_action = "wait_for_unlock"

    elif not result["content_generated"]:

        next_action = "generate_lesson"

    elif not result["lesson_completed"]:

        next_action = "study_lesson"

    elif not result["practical_completed"]:

        next_action = "complete_practical"

    elif not result["assessment_completed"]:

        latest_attempt = (
            AssessmentAttempt.objects.filter(
                assessment__enrollment=enrollment,
                assessment__assessment_type="daily",
                assessment__day_number=day.day_number,
            )
            .order_by("-attempt_number", "-pk")
            .first()
        )

        if latest_attempt is None:

            next_action = "take_assessment"

        elif latest_attempt.status == "in_progress":

            next_action = "resume_assessment"

        elif latest_attempt.status == "submitted":

            next_action = "evaluate_assessment"

        elif latest_attempt.status == "evaluating":

            next_action = "wait_for_evaluation"

        elif latest_attempt.status == "failed":

            next_action = "retry_evaluation"

        elif (
            latest_attempt.status == "evaluated"
            and latest_attempt.passed
        ):

            next_action = "finalize_learning_day"

        else:

            next_action = "retry_assessment"

    else:

        next_action = "review_lesson"

    result["next_action"] = next_action

    return result


# ==========================================
# 16. Upcoming Lessons
# ==========================================

def get_upcoming_lessons(enrollment, limit=5):

    if type(limit) is not int or not 1 <= limit <= 30:

        raise DashboardError(
            "Upcoming lesson limit must be "
            "between 1 and 30."
        )

    enrollment.refresh_from_db()

    if enrollment.status != "active":
        return []

    roadmap = get_roadmap_overview(
        enrollment
    )

    upcoming = [
        day
        for day in roadmap
        if (
            day["day_number"] >= enrollment.current_day
            and day["status"] != "completed"
        )
    ]

    return upcoming[:limit]


# ==========================================
# 17. Estimated Study Time
# ==========================================

def get_study_time_statistics(enrollment):

    roadmap = get_roadmap_overview(
        enrollment
    )

    total_minutes = sum(
        day["estimated_minutes"]
        for day in roadmap
    )

    completed_minutes = sum(
        day["estimated_minutes"]
        for day in roadmap
        if day["status"] == "completed"
    )

    remaining_minutes = (
        total_minutes - completed_minutes
    )

    return {
        "total_estimated_minutes": total_minutes,
        "completed_estimated_minutes": (
            completed_minutes
        ),
        "remaining_estimated_minutes": (
            remaining_minutes
        ),
        "total_estimated_hours": round(
            total_minutes / 60,
            2,
        ),
        "completed_estimated_hours": round(
            completed_minutes / 60,
            2,
        ),
        "remaining_estimated_hours": round(
            remaining_minutes / 60,
            2,
        ),
    }


# ==========================================
# 18. Roadmap Adaptation Statistics
# ==========================================

def get_adaptation_statistics(enrollment):

    jobs = list(
        AIGenerationJob.objects.filter(
            enrollment=enrollment,
            job_type="roadmap_adaptation",
            status="completed",
        ).order_by("-completed_at", "-pk")
    )

    history = []

    unique_adapted_days = set()

    total_updates = 0

    for job in jobs:

        data = job.response_data or {}

        updated_days = data.get(
            "updated_days",
            [],
        )

        total_updates += data.get(
            "updated_count",
            0,
        )

        for day in updated_days:

            day_number = day.get("day_number")

            if day_number is not None:

                unique_adapted_days.add(day_number)

        history.append({
            "job_id": job.id,
            "completed_day": data.get(
                "completed_day"
            ),
            "summary": data.get(
                "adaptation_summary",
                "",
            ),
            "updated_count": data.get(
                "updated_count",
                0,
            ),
            "updated_days": updated_days,
            "completed_at": (
                job.completed_at.isoformat()
                if job.completed_at
                else None
            ),
        })

    return {
        "total_adaptations": len(jobs),
        "total_lesson_updates": total_updates,
        "unique_adapted_lessons": len(
            unique_adapted_days
        ),
        "adapted_day_numbers": sorted(
            unique_adapted_days
        ),
        "latest_adaptation": (
            history[0]
            if history
            else None
        ),
        "history": history,
    }


# ==========================================
# 19. Recent Learning Activities
# ==========================================

def get_recent_learning_activities(
    enrollment,
    limit=10,
    timezone_name=DEFAULT_TIMEZONE,
):

    if type(limit) is not int or not 1 <= limit <= 100:

        raise DashboardError(
            "Activity limit must be between "
            "1 and 100."
        )

    local_timezone = get_dashboard_timezone(
        timezone_name
    )

    events = []

    # Use saved activity records first.

    activities = (
        LearningActivity.objects.filter(
            enrollment=enrollment
        )
        .select_related("learning_day")
        .order_by("-created_at")
    )

    recorded_attempt_ids = set()

    recorded_completed_days = set()

    for activity in activities:

        metadata = activity.metadata or {}

        day_number = (
            activity.learning_day.day_number
            if activity.learning_day
            else metadata.get("day_number")
        )

        if activity.activity_type == "assessment":

            attempt_id = metadata.get("attempt_id")

            if attempt_id is not None:

                recorded_attempt_ids.add(attempt_id)

        if activity.activity_type == "day_completed":

            recorded_completed_days.add(day_number)

        events.append({
            "event_id": f"activity_{activity.id}",
            "activity_type": activity.activity_type,
            "description": activity.description,
            "day_number": day_number,
            "metadata": metadata,
            "timestamp": activity.created_at,
            "source": "learning_activity",
        })

    # Derive missing assessment activities
    # from evaluated attempts.

    attempts = (
        AssessmentAttempt.objects.filter(
            assessment__enrollment=enrollment,
            status="evaluated",
            evaluated_at__isnull=False,
        )
        .select_related("assessment")
    )

    for attempt in attempts:

        if attempt.id in recorded_attempt_ids:
            continue

        is_initial = (
            attempt.assessment.assessment_type
            == "initial"
        )

        day_number = (
            None
            if is_initial
            else attempt.assessment.day_number
        )

        description = (
            "Initial assessment evaluated."
            if is_initial
            else f"Day {day_number} assessment evaluated."
        )

        events.append({
            "event_id": f"assessment_{attempt.id}",
            "activity_type": "assessment",
            "description": description,
            "day_number": day_number,
            "metadata": {
                "attempt_id": attempt.id,
                "percentage": attempt.percentage,
                "passed": attempt.passed,
            },
            "timestamp": attempt.evaluated_at,
            "source": "assessment_attempt",
        })

    # Derive missing day-completion activities.

    completed_days = (
        DayProgress.objects.filter(
            learning_day__enrollment=enrollment,
            status="completed",
            completed_at__isnull=False,
        )
        .select_related("learning_day")
    )

    for progress in completed_days:

        day = progress.learning_day

        if day.day_number in recorded_completed_days:
            continue

        events.append({
            "event_id": f"day_completed_{day.id}",
            "activity_type": "day_completed",
            "description": (
                f"Completed Day {day.day_number}: "
                f"{day.title}"
            ),
            "day_number": day.day_number,
            "metadata": {
                "best_score": progress.best_score,
            },
            "timestamp": progress.completed_at,
            "source": "day_progress",
        })

    # Add completed roadmap adaptations.

    jobs = AIGenerationJob.objects.filter(
        enrollment=enrollment,
        job_type="roadmap_adaptation",
        status="completed",
        completed_at__isnull=False,
    )

    for job in jobs:

        data = job.response_data or {}

        updated_count = data.get(
            "updated_count",
            0,
        )

        events.append({
            "event_id": f"adaptation_{job.id}",
            "activity_type": "roadmap_adaptation",
            "description": (
                f"AI personalized {updated_count} "
                "upcoming lessons."
            ),
            "day_number": data.get("completed_day"),
            "metadata": {
                "job_id": job.id,
                "updated_count": updated_count,
                "summary": data.get(
                    "adaptation_summary",
                    "",
                ),
            },
            "timestamp": job.completed_at,
            "source": "ai_generation_job",
        })

    events.sort(
        key=lambda event: event["timestamp"],
        reverse=True,
    )

    result = []

    for event in events[:limit]:

        result.append({
            **event,
            "timestamp": serialize_datetime(
                event["timestamp"],
                local_timezone,
            ),
        })

    return result


# ==========================================
# 20. Generate Learning Recommendations
# ==========================================

def get_learning_recommendations(
    enrollment,
    mastery_analytics,
    current_day,
):

    recommendations = []

    if enrollment.status == "pending":

        recommendations.append(
            "Complete your initial assessment "
            "to receive a personalized roadmap."
        )

        return recommendations

    if enrollment.status == "completed":

        recommendations.append(
            "You have completed your learning "
            "roadmap. Continue practicing through "
            "independent projects."
        )

        return recommendations

    weak_topics = mastery_analytics["weak_topics"]

    if weak_topics:

        recommendations.append(
            "Prioritize additional practice in: "
            + ", ".join(weak_topics[:3])
            + "."
        )

    if current_day:

        recommendations.append(
            f"Continue Day "
            f"{current_day['day_number']}: "
            f"{current_day['title']}."
        )

    most_improved = mastery_analytics[
        "most_improved_topic"
    ]

    if most_improved:

        recommendations.append(
            f"Your mastery of "
            f"{most_improved['topic']} improved by "
            f"{most_improved['improvement']} "
            "percentage points. Continue reinforcing "
            "this topic through practical exercises."
        )

    recommendations.append(
        "Complete at least one learning day "
        "regularly to maintain your learning streak."
    )

    return recommendations


# ==========================================
# 21. Main Dashboard Function
# ==========================================

def get_learning_dashboard(
    enrollment,
    timezone_name=DEFAULT_TIMEZONE,
):

    enrollment.refresh_from_db()

    get_dashboard_timezone(timezone_name)

    overview = get_enrollment_overview(
        enrollment
    )

    course_progress = get_course_progress(
        enrollment
    )

    streaks = get_streak_statistics(
        enrollment,
        timezone_name,
    )

    initial_assessment = (
        get_initial_assessment_summary(
            enrollment
        )
    )

    daily_performance = (
        get_daily_assessment_performance(
            enrollment
        )
    )

    mastery_analytics = (
        get_topic_mastery_analytics(
            enrollment
        )
    )

    current_day = get_current_learning_day(
        enrollment
    )

    recommendations = (
        get_learning_recommendations(
            enrollment,
            mastery_analytics,
            current_day,
        )
    )

    return {
        "enrollment": overview,

        "course_progress": course_progress,

        "streaks": streaks,

        "initial_assessment": initial_assessment,

        "daily_performance": daily_performance,

        "topic_mastery": mastery_analytics,

        "current_learning_day": current_day,

        "upcoming_lessons": get_upcoming_lessons(
            enrollment,
            limit=5,
        ),

        "roadmap": get_roadmap_overview(
            enrollment
        ),

        "study_time": get_study_time_statistics(
            enrollment
        ),

        "adaptations": get_adaptation_statistics(
            enrollment
        ),

        "learning_calendar": get_learning_calendar(
            enrollment,
            timezone_name=timezone_name,
            number_of_days=30,
        ),

        "recent_activities": (
            get_recent_learning_activities(
                enrollment,
                limit=10,
                timezone_name=timezone_name,
            )
        ),

        "recommendations": recommendations,

        "generated_at": serialize_datetime(
            timezone.now(),
            get_dashboard_timezone(timezone_name),
        ),
    }