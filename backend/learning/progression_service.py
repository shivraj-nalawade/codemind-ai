import logging
import math

from django.db import transaction
from django.utils import timezone

from learning.models import (
    Enrollment,
    LearningDay,
    DayProgress,
    AssessmentAttempt,
    TopicMastery,
)

from .daily_evaluation_service import (
    DailyEvaluationError,
    calculate_daily_assessment_score,
)

from .evaluation_service import (
    calculate_topic_performance,
)

from .progress_service import (
    DAILY_PASS_PERCENTAGE,
    get_daily_progress_summary,
    get_enrollment_progress_summary,
)


logger = logging.getLogger(__name__)


# ==========================================
# Configuration
# ==========================================

TOTAL_LEARNING_DAYS = 30

PREVIOUS_MASTERY_WEIGHT = 0.40

LATEST_PERFORMANCE_WEIGHT = 0.60


class ProgressionError(Exception):
    pass


# ==========================================
# 1. Calculate Updated Topic Mastery
# ==========================================

def calculate_updated_mastery(
    previous_mastery,
    latest_score,
):

    try:

        previous_mastery = float(
            previous_mastery
        )

        latest_score = float(
            latest_score
        )

    except (TypeError, ValueError) as error:

        raise ProgressionError(
            "Mastery scores must be numeric."
        ) from error

    if not math.isfinite(previous_mastery):

        raise ProgressionError(
            "Invalid previous mastery score."
        )

    if not math.isfinite(latest_score):

        raise ProgressionError(
            "Invalid latest assessment score."
        )

    if not 0 <= previous_mastery <= 100:

        raise ProgressionError(
            "Previous mastery must be "
            "between 0 and 100."
        )

    if not 0 <= latest_score <= 100:

        raise ProgressionError(
            "Latest score must be "
            "between 0 and 100."
        )

    updated_mastery = (
        previous_mastery
        * PREVIOUS_MASTERY_WEIGHT
        +
        latest_score
        * LATEST_PERFORMANCE_WEIGHT
    )

    return round(
        updated_mastery,
        2,
    )


# ==========================================
# 2. Determine Recommended Difficulty
# ==========================================

def get_recommended_difficulty(
    mastery_score,
):

    if mastery_score >= 80:

        return "advanced"

    if mastery_score >= 50:

        return "intermediate"

    return "basic"


# ==========================================
# 3. Validate Evaluated Daily Attempt
# ==========================================

def validate_progression_attempt(attempt):

    assessment = attempt.assessment

    if assessment.assessment_type != "daily":

        raise ProgressionError(
            "Only daily assessments can "
            "finalize a learning day."
        )

    if attempt.status != "evaluated":

        raise ProgressionError(
            "Assessment evaluation must "
            "be completed first."
        )

    if attempt.evaluated_at is None:

        raise ProgressionError(
            "Assessment evaluation timestamp "
            "is missing."
        )

    if not (
        1 <= assessment.day_number
        <= TOTAL_LEARNING_DAYS
    ):

        raise ProgressionError(
            "Invalid learning day number."
        )

    try:

        score = (
            calculate_daily_assessment_score(
                attempt
            )
        )

    except DailyEvaluationError as error:

        raise ProgressionError(
            str(error)
        ) from error

    if not math.isclose(
        attempt.obtained_marks,
        score["obtained_marks"],
        abs_tol=0.001,
    ):

        raise ProgressionError(
            "Stored marks do not match "
            "evaluated answer marks."
        )

    if not math.isclose(
        attempt.percentage,
        score["percentage"],
        abs_tol=0.001,
    ):

        raise ProgressionError(
            "Stored percentage does not "
            "match calculated percentage."
        )

    if attempt.total_marks != score["total_marks"]:

        raise ProgressionError(
            "Stored total marks are invalid."
        )

    if attempt.passed != score["passed"]:

        raise ProgressionError(
            "Stored passing status does not "
            "match calculated result."
        )

    return score


# ==========================================
# 4. Retrieve Learning Day
# ==========================================

def get_progression_learning_day(attempt):

    assessment = attempt.assessment

    try:

        return LearningDay.objects.get(
            enrollment_id=(
                assessment.enrollment_id
            ),
            day_number=assessment.day_number,
        )

    except LearningDay.DoesNotExist as error:

        raise ProgressionError(
            "Learning day associated with "
            "this assessment was not found."
        ) from error


# ==========================================
# 5. Validate Day Completion Requirements
# ==========================================

def validate_day_completion_requirements(
    enrollment,
    learning_day,
    progress,
):

    if enrollment.status != "active":

        raise ProgressionError(
            "Enrollment is not active."
        )

    if (
        enrollment.current_day
        != learning_day.day_number
    ):

        raise ProgressionError(
            "Only the current learning day "
            "can be finalized."
        )

    if progress.status != "in_progress":

        raise ProgressionError(
            "Learning day must be in progress."
        )

    if not learning_day.is_content_generated:

        raise ProgressionError(
            "Lesson content has not been generated."
        )

    if not progress.lesson_completed:

        raise ProgressionError(
            "Complete the lesson first."
        )

    if not progress.practical_completed:

        raise ProgressionError(
            "Complete the practical tasks first."
        )

    if progress.assessment_completed:

        raise ProgressionError(
            "Inconsistent assessment completion "
            "state detected."
        )

    if progress.completed_at is not None:

        raise ProgressionError(
            "Inconsistent day completion "
            "timestamp detected."
        )

    if progress.unlocked_at is None:

        raise ProgressionError(
            "Learning day has not been unlocked."
        )

    return True


# ==========================================
# 6. Update Topic Mastery
# ==========================================

@transaction.atomic
def _update_daily_topic_mastery(
    enrollment,
    attempt,
):

    topic_results = calculate_topic_performance(
        attempt
    )

    if not topic_results:

        raise ProgressionError(
            "No evaluated topic performance "
            "was found."
        )

    mastery_updates = []

    for result in topic_results:

        topic = result["topic"]

        latest_score = float(
            result["percentage"]
        )

        questions_tested = int(
            result["total_questions"]
        )

        correct_answers = int(
            result["correct_answers"]
        )

        if not topic.strip():

            raise ProgressionError(
                "Invalid topic name."
            )

        if not math.isfinite(latest_score):

            raise ProgressionError(
                "Invalid topic performance score."
            )

        if not 0 <= latest_score <= 100:

            raise ProgressionError(
                "Topic performance score "
                "is outside the permitted range."
            )

        if questions_tested <= 0:

            raise ProgressionError(
                "Invalid number of tested questions."
            )

        if not (
            0 <= correct_answers
            <= questions_tested
        ):

            raise ProgressionError(
                "Invalid number of correct answers."
            )

        mastery = (
            TopicMastery.objects
            .select_for_update()
            .filter(
                enrollment=enrollment,
                topic__iexact=topic,
            )
            .first()
        )

        is_new_topic = mastery is None

        if is_new_topic:

            previous_mastery = None

            updated_mastery = round(
                latest_score,
                2,
            )

            recommended_difficulty = (
                get_recommended_difficulty(
                    updated_mastery
                )
            )

            mastery = TopicMastery.objects.create(
                enrollment=enrollment,
                topic=topic,
                initial_score=0,
                mastery_score=updated_mastery,
                total_questions=questions_tested,
                correct_answers=correct_answers,
                recommended_difficulty=(
                    recommended_difficulty
                ),
                last_practiced_at=timezone.now(),
            )

        else:

            previous_mastery = (
                mastery.mastery_score
            )

            updated_mastery = (
                calculate_updated_mastery(
                    previous_mastery,
                    latest_score,
                )
            )

            recommended_difficulty = (
                get_recommended_difficulty(
                    updated_mastery
                )
            )

            mastery.mastery_score = (
                updated_mastery
            )

            mastery.total_questions += (
                questions_tested
            )

            mastery.correct_answers += (
                correct_answers
            )

            mastery.recommended_difficulty = (
                recommended_difficulty
            )

            mastery.last_practiced_at = (
                timezone.now()
            )

            mastery.save(update_fields=[
                "mastery_score",
                "total_questions",
                "correct_answers",
                "recommended_difficulty",
                "last_practiced_at",
                "updated_at",
            ])

        improvement = (
            round(
                updated_mastery
                - previous_mastery,
                2,
            )
            if previous_mastery is not None
            else None
        )

        mastery_updates.append({
            "topic": mastery.topic,
            "is_new_topic": is_new_topic,
            "initial_score": mastery.initial_score,
            "previous_mastery": previous_mastery,
            "latest_assessment_score": latest_score,
            "updated_mastery": updated_mastery,
            "improvement": improvement,
            "questions_tested": questions_tested,
            "correct_answers": correct_answers,
            "recommended_difficulty": (
                recommended_difficulty
            ),
        })

    return mastery_updates


# ==========================================
# 7. Retrieve Existing Best Assessment Score
# ==========================================

def get_best_daily_score(learning_day):

    best_attempt = (
        AssessmentAttempt.objects.filter(
            assessment__enrollment_id=(
                learning_day.enrollment_id
            ),
            assessment__assessment_type="daily",
            assessment__day_number=(
                learning_day.day_number
            ),
            status="evaluated",
        )
        .order_by(
            "-percentage",
            "-evaluated_at",
        )
        .first()
    )

    if best_attempt is None:

        return 0.0

    return round(
        float(best_attempt.percentage),
        2,
    )


# ==========================================
# 8. Record Below-Threshold Assessment
# ==========================================

def _record_unsuccessful_assessment(
    progress,
    score,
):

    updated_best_score = max(
        progress.best_score,
        score["percentage"],
    )

    if (
        updated_best_score
        != progress.best_score
    ):

        progress.best_score = (
            updated_best_score
        )

        progress.save(update_fields=[
            "best_score",
            "updated_at",
        ])

    return progress


# ==========================================
# 9. Unlock Next Learning Day
# ==========================================

def _unlock_next_learning_day(
    enrollment,
    current_day,
):

    next_day_number = (
        current_day.day_number + 1
    )

    if next_day_number > TOTAL_LEARNING_DAYS:

        return None

    try:

        next_day = (
            LearningDay.objects
            .select_for_update()
            .get(
                enrollment=enrollment,
                day_number=next_day_number,
            )
        )

        next_progress = (
            DayProgress.objects
            .select_for_update()
            .get(
                learning_day=next_day
            )
        )

    except (
        LearningDay.DoesNotExist,
        DayProgress.DoesNotExist,
    ) as error:

        raise ProgressionError(
            "Next learning day or its "
            "progress record is missing."
        ) from error

    if next_progress.status != "locked":

        raise ProgressionError(
            "Next learning day is not locked. "
            "Inconsistent roadmap state detected."
        )

    if any([
        next_progress.lesson_completed,
        next_progress.practical_completed,
        next_progress.assessment_completed,
        next_progress.completed_at is not None,
        next_progress.unlocked_at is not None,
    ]):

        raise ProgressionError(
            "Next learning day contains "
            "unexpected progress."
        )

    next_progress.status = "unlocked"

    next_progress.unlocked_at = (
        timezone.now()
    )

    next_progress.save(update_fields=[
        "status",
        "unlocked_at",
        "updated_at",
    ])

    return next_day


# ==========================================
# 10. Complete Enrollment
# ==========================================

def _complete_enrollment(enrollment):

    total_days = LearningDay.objects.filter(
        enrollment=enrollment
    ).count()

    completed_days = DayProgress.objects.filter(
        learning_day__enrollment=enrollment,
        status="completed",
        lesson_completed=True,
        practical_completed=True,
        assessment_completed=True,
        completed_at__isnull=False,
    ).count()

    if total_days != TOTAL_LEARNING_DAYS:

        raise ProgressionError(
            "Enrollment does not contain "
            "exactly 30 learning days."
        )

    if completed_days != TOTAL_LEARNING_DAYS:

        raise ProgressionError(
            "All 30 learning days must "
            "be completed first."
        )

    enrollment.status = "completed"

    enrollment.current_day = (
        TOTAL_LEARNING_DAYS
    )

    enrollment.save(update_fields=[
        "status",
        "current_day",
        "updated_at",
    ])

    return enrollment


# ==========================================
# 11. Build Progression Result
# ==========================================

def build_progression_result(
    enrollment,
    learning_day,
    attempt,
    score,
    mastery_updates=None,
    next_day=None,
    already_finalized=False,
):

    enrollment.refresh_from_db()

    progress = DayProgress.objects.get(
        learning_day=learning_day
    )

    completed_days = DayProgress.objects.filter(
        learning_day__enrollment=enrollment,
        status="completed",
    ).count()

    locked_days = DayProgress.objects.filter(
        learning_day__enrollment=enrollment,
        status="locked",
    ).count()

    course_completed = (
        enrollment.status == "completed"
    )

    next_day_data = None

    if next_day is not None:

        next_progress = DayProgress.objects.get(
            learning_day=next_day
        )

        next_day_data = {
            "learning_day_id": next_day.id,
            "day_number": next_day.day_number,
            "title": next_day.title,
            "topic": next_day.topic,
            "difficulty": next_day.difficulty,
            "status": next_progress.status,
            "content_generated": (
                next_day.is_content_generated
            ),
            "unlocked_at": (
                next_progress.unlocked_at.isoformat()
                if next_progress.unlocked_at
                else None
            ),
        }

    if already_finalized:

        message = (
            "Learning day has already "
            "been finalized."
        )

    elif not score["passed"]:

        message = (
            "Assessment score is below the "
            "passing threshold. Revise the "
            "topic and try again."
        )

    elif course_completed:

        message = (
            "Congratulations! All 30 learning "
            "days have been completed."
        )

    else:

        message = (
            f"Day {learning_day.day_number} "
            f"completed successfully. "
            f"Day {enrollment.current_day} "
            f"is now unlocked."
        )

    return {
        "enrollment_id": enrollment.id,
        "language": enrollment.language,
        "assessment_id": attempt.assessment_id,
        "attempt_id": attempt.id,
        "day_number": learning_day.day_number,
        "assessment_score": score["percentage"],
        "passing_percentage": (
            DAILY_PASS_PERCENTAGE
        ),
        "passed": score["passed"],
        "day_completed": (
            progress.status == "completed"
        ),
        "already_finalized": already_finalized,
        "best_score": progress.best_score,
        "day_status": progress.status,
        "assessment_completed": (
            progress.assessment_completed
        ),
        "current_day": enrollment.current_day,
        "completed_days": completed_days,
        "total_days": TOTAL_LEARNING_DAYS,
        "locked_days": locked_days,
        "overall_progress_percentage": round(
            completed_days
            / TOTAL_LEARNING_DAYS
            * 100,
            2,
        ),
        "enrollment_status": enrollment.status,
        "course_completed": course_completed,
        "mastery_updates": mastery_updates or [],
        "next_day": next_day_data,
        "can_retry_assessment": (
            not score["passed"]
            and progress.status == "in_progress"
        ),
        "completed_at": (
            progress.completed_at.isoformat()
            if progress.completed_at
            else None
        ),
        "message": message,
    }


# ==========================================
# 12. Main Transactional Progression Service
# ==========================================

@transaction.atomic
def finalize_learning_day(attempt):

    # Read identifiers before acquiring locks.

    attempt = (
        AssessmentAttempt.objects
        .select_related("assessment")
        .get(pk=attempt.pk)
    )

    assessment = attempt.assessment

    if assessment.assessment_type != "daily":

        raise ProgressionError(
            "Only daily assessments can "
            "finalize learning progress."
        )

    # --------------------------------------
    # Lock Enrollment
    # --------------------------------------

    enrollment = (
        Enrollment.objects
        .select_for_update()
        .get(
            pk=assessment.enrollment_id
        )
    )

    # --------------------------------------
    # Lock Learning Day
    # --------------------------------------

    try:

        learning_day = (
            LearningDay.objects
            .select_for_update()
            .get(
                enrollment=enrollment,
                day_number=assessment.day_number,
            )
        )

        progress = (
            DayProgress.objects
            .select_for_update()
            .get(
                learning_day=learning_day
            )
        )

    except (
        LearningDay.DoesNotExist,
        DayProgress.DoesNotExist,
    ) as error:

        raise ProgressionError(
            "Learning day or progress "
            "record is missing."
        ) from error

    # --------------------------------------
    # Lock Assessment Attempt
    # --------------------------------------

    attempt = (
        AssessmentAttempt.objects
        .select_for_update()
        .get(pk=attempt.pk)
    )

    # --------------------------------------
    # Validate Persisted Assessment
    # --------------------------------------

    score = validate_progression_attempt(
        attempt
    )

    # --------------------------------------
    # Duplicate Finalization Protection
    # --------------------------------------

    if progress.status == "completed":

        if not all([
            progress.lesson_completed,
            progress.practical_completed,
            progress.assessment_completed,
            progress.completed_at is not None,
        ]):

            raise ProgressionError(
                "Completed day contains "
                "inconsistent progress."
            )

        next_day = None

        if (
            learning_day.day_number
            < TOTAL_LEARNING_DAYS
        ):

            next_day = LearningDay.objects.filter(
                enrollment=enrollment,
                day_number=(
                    learning_day.day_number + 1
                ),
            ).first()

        return build_progression_result(
            enrollment=enrollment,
            learning_day=learning_day,
            attempt=attempt,
            score=score,
            mastery_updates=[],
            next_day=next_day,
            already_finalized=True,
        )

    # --------------------------------------
    # Validate Learning Requirements
    # --------------------------------------

    validate_day_completion_requirements(
        enrollment,
        learning_day,
        progress,
    )

    # --------------------------------------
    # Below-Threshold Assessment
    # --------------------------------------

    if not score["passed"]:

        _record_unsuccessful_assessment(
            progress,
            score,
        )

        return build_progression_result(
            enrollment=enrollment,
            learning_day=learning_day,
            attempt=attempt,
            score=score,
            mastery_updates=[],
        )

    # --------------------------------------
    # Successful Assessment
    # --------------------------------------

    mastery_updates = (
        _update_daily_topic_mastery(
            enrollment,
            attempt,
        )
    )

    # --------------------------------------
    # Complete Current Day
    # --------------------------------------

    progress.best_score = max(
        progress.best_score,
        get_best_daily_score(learning_day),
    )

    progress.assessment_completed = True

    progress.status = "completed"

    progress.completed_at = timezone.now()

    progress.save(update_fields=[
        "best_score",
        "assessment_completed",
        "status",
        "completed_at",
        "updated_at",
    ])

    # --------------------------------------
    # Unlock Next Day or Complete Course
    # --------------------------------------

    next_day = None

    if (
        learning_day.day_number
        == TOTAL_LEARNING_DAYS
    ):

        _complete_enrollment(
            enrollment
        )

    else:

        next_day = (
            _unlock_next_learning_day(
                enrollment,
                learning_day,
            )
        )

        enrollment.current_day = (
            next_day.day_number
        )

        enrollment.save(update_fields=[
            "current_day",
            "updated_at",
        ])

    logger.info(
        "Learning day %s finalized for "
        "enrollment %s. Assessment score: %s%%.",
        learning_day.day_number,
        enrollment.id,
        score["percentage"],
    )

    return build_progression_result(
        enrollment=enrollment,
        learning_day=learning_day,
        attempt=attempt,
        score=score,
        mastery_updates=mastery_updates,
        next_day=next_day,
    )


# ==========================================
# 13. Retrieve Finalization Eligibility
# ==========================================

def get_day_finalization_eligibility(
    learning_day,
):

    learning_day.refresh_from_db()

    enrollment = learning_day.enrollment

    progress = DayProgress.objects.get(
        learning_day=learning_day
    )

    passed_attempt = (
        AssessmentAttempt.objects.filter(
            assessment__enrollment=enrollment,
            assessment__assessment_type="daily",
            assessment__day_number=(
                learning_day.day_number
            ),
            status="evaluated",
            passed=True,
        )
        .order_by(
            "-percentage",
            "-evaluated_at",
        )
        .first()
    )

    reasons = []

    if enrollment.status != "active":

        reasons.append(
            "Enrollment is not active."
        )

    if (
        enrollment.current_day
        != learning_day.day_number
    ):

        reasons.append(
            "This is not the current learning day."
        )

    if progress.status == "completed":

        reasons.append(
            "Learning day is already completed."
        )

    elif progress.status != "in_progress":

        reasons.append(
            "Learning day must be in progress."
        )

    if not learning_day.is_content_generated:

        reasons.append(
            "Lesson content has not been generated."
        )

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
            "Assessment is already finalized."
        )

    if passed_attempt is None:

        reasons.append(
            f"Pass the daily assessment with "
            f"at least {DAILY_PASS_PERCENTAGE}%."
        )

    else:

        try:

            validate_progression_attempt(
                passed_attempt
            )

        except ProgressionError as error:

            reasons.append(
                str(error)
            )

    return {
        "eligible": len(reasons) == 0,
        "learning_day_id": learning_day.id,
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
        "passed_attempt_id": (
            passed_attempt.id
            if passed_attempt
            else None
        ),
        "assessment_score": (
            passed_attempt.percentage
            if passed_attempt
            else None
        ),
        "reasons": reasons,
    }


# ==========================================
# 14. Finalize Using Best Passed Attempt
# ==========================================

def finalize_day_from_best_attempt(
    learning_day,
):

    passed_attempt = (
        AssessmentAttempt.objects.filter(
            assessment__enrollment_id=(
                learning_day.enrollment_id
            ),
            assessment__assessment_type="daily",
            assessment__day_number=(
                learning_day.day_number
            ),
            status="evaluated",
            passed=True,
        )
        .order_by(
            "-percentage",
            "-evaluated_at",
        )
        .first()
    )

    if passed_attempt is None:

        raise ProgressionError(
            "No successfully passed assessment "
            "attempt was found."
        )

    return finalize_learning_day(
        passed_attempt
    )


# ==========================================
# 15. Retrieve Progression Summary
# ==========================================

def get_progression_summary(enrollment):

    enrollment.refresh_from_db()

    current_day = LearningDay.objects.filter(
        enrollment=enrollment,
        day_number=enrollment.current_day,
    ).first()

    topic_mastery = list(
        TopicMastery.objects.filter(
            enrollment=enrollment
        ).order_by(
            "mastery_score",
            "topic",
        ).values(
            "topic",
            "initial_score",
            "mastery_score",
            "total_questions",
            "correct_answers",
            "recommended_difficulty",
        )
    )

    current_day_progress = None

    finalization_eligibility = None

    if current_day is not None:

        current_day_progress = (
            get_daily_progress_summary(
                current_day
            )
        )

        finalization_eligibility = (
            get_day_finalization_eligibility(
                current_day
            )
        )

    return {
        "enrollment_progress": (
            get_enrollment_progress_summary(
                enrollment
            )
        ),
        "current_day_progress": (
            current_day_progress
        ),
        "finalization_eligibility": (
            finalization_eligibility
        ),
        "topic_mastery": topic_mastery,
        "course_completed": (
            enrollment.status == "completed"
        ),
    }