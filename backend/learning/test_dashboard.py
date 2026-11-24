import os
import json

from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

import django

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

django.setup()

from django.utils import timezone

from learning.models import (
    Enrollment,
    LearningDay,
    DayProgress,
    Assessment,
    AssessmentAttempt,
    Question,
    UserAnswer,
    TopicMastery,
    LearningActivity,
    AIGenerationJob,
)

from learning.services.dashboard_service import (
    DashboardError,
    calculate_streaks,
    calculate_average,
    calculate_percentage,
    get_dashboard_timezone,
    serialize_datetime,
    get_course_progress,
    get_streak_statistics,
    get_learning_calendar,
    get_initial_assessment_summary,
    get_daily_assessment_performance,
    get_topic_mastery_analytics,
    get_current_learning_day,
    get_upcoming_lessons,
    get_roadmap_overview,
    get_study_time_statistics,
    get_adaptation_statistics,
    get_recent_learning_activities,
    get_learning_dashboard,
)


# ==========================================
# Helper Functions
# ==========================================

def print_section(title):

    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def print_json(data):

    print(
        json.dumps(
            data,
            indent=4,
            ensure_ascii=False,
            default=str,
        )
    )


def expect_rejection(label, function, *args, **kwargs):

    try:

        function(*args, **kwargs)

    except DashboardError as error:

        print(f"{label}: PASSED")
        print(f"Reason: {error}")

        return

    raise AssertionError(
        f"{label}: Invalid input was accepted."
    )


# ==========================================
# Capture Database State
# ==========================================

def capture_database_state(enrollment):

    return {
        "enrollment": list(
            Enrollment.objects.filter(
                pk=enrollment.pk
            ).values()
        ),

        "learning_days": list(
            LearningDay.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),

        "day_progress": list(
            DayProgress.objects.filter(
                learning_day__enrollment=enrollment
            ).order_by("pk").values()
        ),

        "assessments": list(
            Assessment.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),

        "questions": list(
            Question.objects.filter(
                assessment__enrollment=enrollment
            ).order_by("pk").values()
        ),

        "attempts": list(
            AssessmentAttempt.objects.filter(
                assessment__enrollment=enrollment
            ).order_by("pk").values()
        ),

        "answers": list(
            UserAnswer.objects.filter(
                attempt__assessment__enrollment=enrollment
            ).order_by("pk").values()
        ),

        "topic_mastery": list(
            TopicMastery.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),

        "activities": list(
            LearningActivity.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),

        "ai_jobs": list(
            AIGenerationJob.objects.filter(
                enrollment=enrollment
            ).order_by("pk").values()
        ),
    }


# ==========================================
# 1. Mathematical Helper Tests
# ==========================================

def test_mathematical_helpers():

    print_section("MATHEMATICAL HELPER TESTS")

    assert calculate_percentage(1, 30) == 3.33

    assert calculate_percentage(0, 30) == 0.0

    assert calculate_percentage(1, 0) == 0.0

    assert calculate_average([]) is None

    assert calculate_average([100]) == 100.0

    assert calculate_average([60, 80, 100]) == 80.0

    print("Percentage Calculation: PASSED")
    print("Average Calculation: PASSED")
    print("Empty Data Handling: PASSED")


# ==========================================
# 2. Controlled Streak Tests
# ==========================================

def test_streak_calculation():

    print_section("CONTROLLED STREAK TESTS")

    today = date(2026, 11, 24)

    yesterday = today - timedelta(days=1)

    two_days_ago = today - timedelta(days=2)

    three_days_ago = today - timedelta(days=3)

    five_days_ago = today - timedelta(days=5)

    tomorrow = today + timedelta(days=1)

    # No completed dates.

    result = calculate_streaks([], today)

    assert result["current_streak"] == 0
    assert result["longest_streak"] == 0

    print("Empty Learning History: PASSED")

    # One completed date.

    result = calculate_streaks([today], today)

    assert result["current_streak"] == 1
    assert result["longest_streak"] == 1
    assert result["completed_today"]

    print("Single Completed Day: PASSED")

    # Multiple completions on the same date.

    result = calculate_streaks(
        [today, today, today],
        today,
    )

    assert result["current_streak"] == 1
    assert result["active_learning_days"] == 1

    print("Duplicate Completion Dates: PASSED")

    # Three consecutive calendar dates.

    result = calculate_streaks(
        [today, yesterday, two_days_ago],
        today,
    )

    assert result["current_streak"] == 3
    assert result["longest_streak"] == 3

    print("Consecutive Learning Dates: PASSED")

    # Last completion yesterday.

    result = calculate_streaks(
        [yesterday, two_days_ago],
        today,
    )

    assert result["current_streak"] == 2
    assert result["streak_active"]
    assert not result["completed_today"]

    print("Yesterday Streak Preservation: PASSED")

    # Missed learning date.

    result = calculate_streaks(
        [two_days_ago, three_days_ago],
        today,
    )

    assert result["current_streak"] == 0
    assert result["longest_streak"] == 2
    assert not result["streak_active"]

    print("Broken Streak Detection: PASSED")

    # Restart after a missed day.

    result = calculate_streaks(
        [
            today,
            two_days_ago,
            three_days_ago,
        ],
        today,
    )

    assert result["current_streak"] == 1
    assert result["longest_streak"] == 2

    print("Streak Restart: PASSED")

    # Unsorted completion history.

    result = calculate_streaks(
        [
            today,
            five_days_ago,
            yesterday,
            two_days_ago,
        ],
        today,
    )

    assert result["current_streak"] == 3
    assert result["longest_streak"] == 3

    print("Unsorted Completion Dates: PASSED")

    # Future dates must be ignored.

    result = calculate_streaks(
        [today, tomorrow],
        today,
    )

    assert result["current_streak"] == 1
    assert result["active_learning_days"] == 1

    print("Future Date Protection: PASSED")


# ==========================================
# 3. Timezone Tests
# ==========================================

def test_timezone_handling():

    print_section("TIMEZONE HANDLING TESTS")

    india_timezone = get_dashboard_timezone(
        "Asia/Kolkata"
    )

    utc_timezone = get_dashboard_timezone(
        "UTC"
    )

    timestamp = datetime(
        2026, 11, 24, 20, 0,
        tzinfo=dt_timezone.utc,
    )

    india_time = serialize_datetime(
        timestamp,
        india_timezone,
    )

    utc_time = serialize_datetime(
        timestamp,
        utc_timezone,
    )

    print(f"UTC Timestamp: {utc_time}")
    print(f"India Timestamp: {india_time}")

    assert utc_time.startswith(
        "2026-11-24T20:00"
    )

    assert india_time.startswith(
        "2026-11-25T01:30"
    )

    assert india_time.endswith("+05:30")

    assert serialize_datetime(
        None,
        india_timezone,
    ) is None

    expect_rejection(
        "Invalid Timezone",
        get_dashboard_timezone,
        "Invalid/Timezone",
    )

    print("Timezone Conversion: PASSED")
    print("Midnight Boundary: PASSED")


# ==========================================
# 4. Course Progress Tests
# ==========================================

def test_course_progress(enrollment):

    print_section("COURSE PROGRESS TEST")

    progress = get_course_progress(
        enrollment
    )

    print_json(progress)

    assert progress["planned_days"] == 30

    assert progress["total_days"] == 30

    assert progress["completed_days"] == 1

    assert progress["pending_days"] == 29

    assert progress["unlocked_days"] == 1

    assert progress["in_progress_days"] == 0

    assert progress["locked_days"] == 28

    assert progress["completed_lessons"] == 1

    assert progress["completed_practicals"] == 1

    assert progress["completed_assessments"] == 1

    assert progress["generated_lessons"] == 1

    assert (
        progress["overall_progress_percentage"]
        == 3.33
    )

    assert (
        progress["average_completed_day_score"]
        == 100.0
    )

    assert progress["roadmap_generated"]

    print("\nCourse Progress: PASSED")


# ==========================================
# 5. Actual Streak and Calendar Tests
# ==========================================

def test_learning_calendar(enrollment):

    print_section("DATABASE STREAK AND CALENDAR TEST")

    completion = DayProgress.objects.get(
        learning_day__enrollment=enrollment,
        learning_day__day_number=1,
    )

    assert completion.completed_at is not None

    # Freeze time at the recorded completion.
    # This makes the test independent of today's date.

    with patch(
        "django.utils.timezone.now",
        return_value=completion.completed_at,
    ):

        streaks = get_streak_statistics(
            enrollment
        )

        calendar = get_learning_calendar(
            enrollment,
            number_of_days=30,
        )

    print_json(streaks)

    assert streaks["current_streak"] == 1

    assert streaks["longest_streak"] == 1

    assert streaks["active_learning_days"] == 1

    assert streaks["completed_today"]

    assert len(calendar) == 30

    active_dates = [
        item
        for item in calendar
        if item["is_active"]
    ]

    assert len(active_dates) == 1

    assert active_dates[0]["completed_lessons"] == 1

    assert active_dates[0]["learning_days"] == [1]

    assert calendar[-1]["is_today"]

    print("\nActive Calendar Date:")

    print_json(active_dates[0])

    expect_rejection(
        "Invalid Calendar Duration",
        get_learning_calendar,
        enrollment,
        number_of_days=0,
    )

    expect_rejection(
        "Excessive Calendar Duration",
        get_learning_calendar,
        enrollment,
        number_of_days=367,
    )

    print("\nDatabase Streak Calculation: PASSED")
    print("Learning Calendar: PASSED")


# ==========================================
# 6. Initial Assessment Tests
# ==========================================

def test_initial_assessment(enrollment):

    print_section("INITIAL ASSESSMENT ANALYTICS")

    result = get_initial_assessment_summary(
        enrollment
    )

    assert result is not None

    assert result["percentage"] == 52.38

    assert result["obtained_marks"] == 11

    assert result["total_marks"] == 21

    assert len(result["strengths"]) == 3

    assert len(result["weaknesses"]) == 3

    print_json(result)

    print("\nInitial Assessment Analytics: PASSED")


# ==========================================
# 7. Daily Assessment Analytics
# ==========================================

def test_daily_performance(enrollment):

    print_section("DAILY ASSESSMENT ANALYTICS")

    performance = get_daily_assessment_performance(
        enrollment
    )

    print_json(performance)

    assert performance["total_evaluated_attempts"] == 1

    assert performance["passed_attempts"] == 1

    assert performance["unsuccessful_attempts"] == 0

    assert performance["assessed_days"] == 1

    assert performance["passed_days"] == 1

    assert performance["average_attempt_score"] == 100.0

    assert (
        performance["average_best_daily_score"]
        == 100.0
    )

    assert performance["highest_score"] == 100.0

    assert performance["lowest_score"] == 100.0

    assert performance["latest_score"] == 100.0

    assert performance["attempt_pass_rate"] == 100.0

    assert performance["passing_percentage"] == 80.0

    daily_scores = performance["daily_scores"]

    assert len(daily_scores) == 1

    assert daily_scores[0]["day_number"] == 1

    assert daily_scores[0]["best_score"] == 100.0

    assert daily_scores[0]["passed"]

    assert daily_scores[0]["attempt_count"] == 1

    print("\nDaily Assessment Analytics: PASSED")


# ==========================================
# 8. Topic Mastery Analytics
# ==========================================

def test_topic_mastery(enrollment):

    print_section("TOPIC MASTERY ANALYTICS")

    analytics = get_topic_mastery_analytics(
        enrollment
    )

    assert analytics["total_topics"] == 9

    assert len(analytics["strong_topics"]) == 3

    assert len(analytics["developing_topics"]) == 4

    assert len(analytics["weak_topics"]) == 2

    assert analytics["improved_topics_count"] == 1

    assert analytics["average_initial_mastery"] == 55.56

    assert analytics["average_current_mastery"] == 60.56

    assert analytics["average_mastery_improvement"] == 5.0

    most_improved = analytics["most_improved_topic"]

    assert (
        most_improved["topic"]
        == "Conditional Statements"
    )

    assert most_improved["initial_score"] == 25.0

    assert most_improved["current_mastery"] == 70.0

    assert most_improved["improvement"] == 45.0

    print("\nTopic Mastery Comparison:")

    for topic in analytics["topics"]:

        print(
            f"{topic['topic']} | "
            f"Initial: {topic['initial_score']} | "
            f"Current: {topic['current_mastery']} | "
            f"Improvement: {topic['improvement']}"
        )

    print("\nMost Improved Topic:")

    print_json(most_improved)

    print("\nTopic Mastery Analytics: PASSED")


# ==========================================
# 9. Roadmap and Upcoming Lessons
# ==========================================

def test_roadmap(enrollment):

    print_section("ROADMAP AND UPCOMING LESSONS")

    roadmap = get_roadmap_overview(
        enrollment
    )

    assert len(roadmap) == 30

    assert [
        day["day_number"]
        for day in roadmap
    ] == list(range(1, 31))

    assert roadmap[0]["status"] == "completed"

    assert roadmap[1]["status"] == "unlocked"

    assert all(
        day["status"] == "locked"
        for day in roadmap[2:]
    )

    current_day = get_current_learning_day(
        enrollment
    )

    assert current_day["day_number"] == 2

    assert current_day["is_accessible"]

    assert not current_day["content_generated"]

    assert (
        current_day["next_action"]
        == "generate_lesson"
    )

    print("\nCurrent Learning Day:")

    print_json(current_day)

    upcoming = get_upcoming_lessons(
        enrollment,
        limit=5,
    )

    assert len(upcoming) == 5

    assert [
        day["day_number"]
        for day in upcoming
    ] == [2, 3, 4, 5, 6]

    print("\nUpcoming Lessons:")

    for day in upcoming:

        print(
            f"Day {day['day_number']} | "
            f"{day['title']} | "
            f"{day['difficulty']} | "
            f"{day['status']}"
        )

    expect_rejection(
        "Invalid Upcoming Lesson Limit",
        get_upcoming_lessons,
        enrollment,
        limit=0,
    )

    print("\nRoadmap Overview: PASSED")
    print("Current Learning Day: PASSED")
    print("Upcoming Lessons: PASSED")


# ==========================================
# 10. Study Time Statistics
# ==========================================

def test_study_time(enrollment):

    print_section("ESTIMATED STUDY TIME")

    result = get_study_time_statistics(
        enrollment
    )

    print_json(result)

    expected_total = sum(
        LearningDay.objects.filter(
            enrollment=enrollment
        ).values_list(
            "estimated_minutes",
            flat=True,
        )
    )

    assert (
        result["total_estimated_minutes"]
        == expected_total
    )

    assert result["completed_estimated_minutes"] == 45

    assert (
        result["remaining_estimated_minutes"]
        == expected_total - 45
    )

    assert (
        result["total_estimated_hours"]
        == round(expected_total / 60, 2)
    )

    print("\nEstimated Study Time: PASSED")


# ==========================================
# 11. Adaptation Analytics
# ==========================================

def test_adaptation_analytics(enrollment):

    print_section("ROADMAP ADAPTATION ANALYTICS")

    result = get_adaptation_statistics(
        enrollment
    )

    assert result["total_adaptations"] == 1

    assert result["total_lesson_updates"] == 5

    assert result["unique_adapted_lessons"] == 5

    assert result["adapted_day_numbers"] == [
        2, 3, 4, 5, 6
    ]

    assert len(result["history"]) == 1

    assert (
        result["latest_adaptation"]["completed_day"]
        == 1
    )

    print(f"Total Adaptations: {result['total_adaptations']}")

    print(
        f"Unique Adapted Lessons: "
        f"{result['unique_adapted_lessons']}"
    )

    print(
        f"Adapted Days: "
        f"{result['adapted_day_numbers']}"
    )

    print("\nRoadmap Adaptation Analytics: PASSED")


# ==========================================
# 12. Recent Activity Tests
# ==========================================

def test_recent_activities(enrollment):

    print_section("RECENT LEARNING ACTIVITIES")

    activities = get_recent_learning_activities(
        enrollment,
        limit=10,
    )

    print_json(activities)

    assert len(activities) == 4

    event_ids = [
        event["event_id"]
        for event in activities
    ]

    assert len(event_ids) == len(set(event_ids))

    activity_types = [
        event["activity_type"]
        for event in activities
    ]

    assert activity_types.count("assessment") == 2

    assert activity_types.count("day_completed") == 1

    assert activity_types.count("roadmap_adaptation") == 1

    timestamps = [
        datetime.fromisoformat(
            event["timestamp"]
        )
        for event in activities
    ]

    assert timestamps == sorted(
        timestamps,
        reverse=True,
    )

    assert len(
        get_recent_learning_activities(
            enrollment,
            limit=2,
        )
    ) == 2

    expect_rejection(
        "Invalid Activity Limit",
        get_recent_learning_activities,
        enrollment,
        limit=0,
    )

    print("\nActivity Ordering: PASSED")
    print("Duplicate Activity Protection: PASSED")
    print("Activity Limit Validation: PASSED")


# ==========================================
# 13. Complete Dashboard Test
# ==========================================

def test_complete_dashboard(enrollment):

    print_section("COMPLETE DASHBOARD RESPONSE")

    dashboard = get_learning_dashboard(
        enrollment
    )

    required_keys = {
        "enrollment",
        "course_progress",
        "streaks",
        "initial_assessment",
        "daily_performance",
        "topic_mastery",
        "current_learning_day",
        "upcoming_lessons",
        "roadmap",
        "study_time",
        "adaptations",
        "learning_calendar",
        "recent_activities",
        "recommendations",
        "generated_at",
    }

    assert required_keys.issubset(
        dashboard.keys()
    )

    # Verify that the response can be sent
    # directly as JSON without custom conversion.

    serialized = json.dumps(
        dashboard,
        ensure_ascii=False,
        allow_nan=False,
    )

    restored = json.loads(serialized)

    assert restored == dashboard

    assert (
        dashboard["enrollment"]["current_day"]
        == 2
    )

    assert (
        dashboard["course_progress"]["completed_days"]
        == 1
    )

    assert len(dashboard["roadmap"]) == 30

    assert len(dashboard["upcoming_lessons"]) == 5

    assert len(dashboard["learning_calendar"]) == 30

    assert dashboard["recommendations"]

    print("All Required Dashboard Fields: PASSED")

    print("JSON Serialization: PASSED")

    print(
        f"Dashboard Response Size: "
        f"{len(serialized.encode('utf-8'))} bytes"
    )

    print("\nLearning Recommendations:")

    for recommendation in dashboard["recommendations"]:

        print(f"- {recommendation}")

    return dashboard


# ==========================================
# Main Integration Test
# ==========================================

def main():

    print_section(
        "CODEMIND AI - DASHBOARD INTEGRATION TEST"
    )

    enrollment = Enrollment.objects.get(
        pk=1,
        language="python",
    )

    assert enrollment.status == "active"

    assert enrollment.current_day == 2

    print(f"Enrollment ID: {enrollment.id}")
    print(f"Language: {enrollment.language}")
    print(f"Current Day: {enrollment.current_day}")

    # Capture all existing learning records.

    original_state = capture_database_state(
        enrollment
    )

    original_job_count = (
        AIGenerationJob.objects.filter(
            enrollment=enrollment
        ).count()
    )

    # Execute all dashboard tests.

    test_mathematical_helpers()

    test_streak_calculation()

    test_timezone_handling()

    test_course_progress(enrollment)

    test_learning_calendar(enrollment)

    test_initial_assessment(enrollment)

    test_daily_performance(enrollment)

    test_topic_mastery(enrollment)

    test_roadmap(enrollment)

    test_study_time(enrollment)

    test_adaptation_analytics(enrollment)

    test_recent_activities(enrollment)

    # Prevent accidental Groq calls while
    # generating the complete dashboard.

    with patch(
        "learning.services.groq_service.generate_response",
        side_effect=AssertionError(
            "Dashboard must not call Groq."
        ),
    ) as mocked_groq:

        dashboard = test_complete_dashboard(
            enrollment
        )

        assert not mocked_groq.called

    # ==========================================
    # Database Preservation
    # ==========================================

    print_section("DATABASE PRESERVATION TEST")

    current_state = capture_database_state(
        enrollment
    )

    for key in original_state:

        unchanged = (
            original_state[key]
            == current_state[key]
        )

        print(
            f"{key.replace('_', ' ').title()} "
            f"Unchanged: {unchanged}"
        )

        assert unchanged, (
            f"Database records modified: {key}"
        )

    final_job_count = (
        AIGenerationJob.objects.filter(
            enrollment=enrollment
        ).count()
    )

    assert final_job_count == original_job_count

    print("\nDatabase Preservation: PASSED")

    # ==========================================
    # Final Summary
    # ==========================================

    print_section(
        "DASHBOARD INTEGRATION TEST PASSED!"
    )

    progress = dashboard["course_progress"]

    mastery = dashboard["topic_mastery"]

    streaks = dashboard["streaks"]

    print(f"Enrollment ID: {enrollment.id}")

    print(f"Language: {enrollment.language}")

    print(f"Current Day: {enrollment.current_day}")

    print(
        f"Completed Days: "
        f"{progress['completed_days']}/30"
    )

    print(
        f"Overall Progress: "
        f"{progress['overall_progress_percentage']}%"
    )

    print(
        f"Current Streak: "
        f"{streaks['current_streak']} day(s)"
    )

    print(
        f"Longest Streak: "
        f"{streaks['longest_streak']} day(s)"
    )

    print(
        f"Average Daily Score: "
        f"{dashboard['daily_performance']['average_attempt_score']}%"
    )

    print(
        f"Most Improved Topic: "
        f"{mastery['most_improved_topic']['topic']}"
    )

    print(
        f"Topic Improvement: "
        f"+{mastery['most_improved_topic']['improvement']} "
        "percentage points"
    )

    print(
        f"Adapted Lessons: "
        f"{dashboard['adaptations']['unique_adapted_lessons']}"
    )

    print("\nStreak Calculation: PASSED")
    print("Timezone Handling: PASSED")
    print("Assessment Analytics: PASSED")
    print("Topic Mastery Analytics: PASSED")
    print("Roadmap Overview: PASSED")
    print("Study Time Statistics: PASSED")
    print("Adaptation Analytics: PASSED")
    print("Recent Activities: PASSED")
    print("JSON Serialization: PASSED")
    print("Database Preservation: PASSED")

    print("\nAdditional AI Jobs: 0")
    print("Database Records Modified: 0")

    print(
        "\nDashboard service is ready "
        "for REST API integration."
    )


if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print_section(
            "DASHBOARD INTEGRATION TEST FAILED!"
        )

        print(f"Error: {error}")

        raise