import os
import django

from collections import Counter

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

django.setup()

from django.contrib.auth import get_user_model

from learning.models import (
    Enrollment,
    LearningDay,
    DayProgress,
    AIGenerationJob,
)

from learning.services.roadmap_service import (
    get_learner_profile,
    generate_personalized_roadmap,
    RoadmapGenerationError,
)


def main():

    print("\n" + "=" * 60)
    print("CODEMIND AI - PERSONALIZED ROADMAP TEST")
    print("=" * 60)

    # ==========================================
    # 1. Retrieve Existing Enrollment
    # ==========================================

    User = get_user_model()

    user = User.objects.filter(
        is_superuser=True
    ).first()

    if not user:
        raise RuntimeError("No superuser found.")

    enrollment = Enrollment.objects.filter(
        user=user,
        language="python",
    ).first()

    if not enrollment:
        raise RuntimeError("Python enrollment not found.")

    print("\nUser:", user.username)
    print("Language:", enrollment.get_language_display())
    print("Skill Level:", enrollment.skill_level)
    print("Current Status:", enrollment.status)

    # ==========================================
    # 2. Retrieve Learner Profile
    # ==========================================

    profile = get_learner_profile(enrollment)

    print("\nAssessment Score:",
          profile["assessment_percentage"])

    print("\nStrengths:")

    for topic in profile["strengths"]:
        print("-", topic)

    print("\nWeaknesses:")

    for topic in profile["weaknesses"]:
        print("-", topic)

    print("\nTopic Performance:")

    for topic in profile["topic_performance"]:

        print(
            f"- {topic['topic']}: "
            f"{topic['mastery_score']}%"
        )

    # ==========================================
    # 3. Generate Personalized Roadmap
    # ==========================================

    print("\nGenerating personalized 30-day roadmap...")
    print("Please wait for GPT-OSS-120B response...")

    roadmap = generate_personalized_roadmap(
        enrollment
    )

    print("\nRoadmap retrieved successfully!")
    print("Total Learning Days:", len(roadmap))

    # ==========================================
    # 4. Display All Learning Days
    # ==========================================

    print("\n" + "=" * 60)
    print("PERSONALIZED 30-DAY ROADMAP")
    print("=" * 60)

    for day in roadmap:

        progress = DayProgress.objects.get(
            learning_day=day
        )

        print(f"\nDAY {day.day_number}")
        print("Title:", day.title)
        print("Topic:", day.topic)
        print("Difficulty:", day.difficulty)
        print("Estimated Time:", day.estimated_minutes,
              "minutes")
        print("Status:", progress.status)

        print("Learning Objectives:")

        for objective in day.learning_objectives:
            print("-", objective)

        print("-" * 60)

    # ==========================================
    # 5. Verify Roadmap Statistics
    # ==========================================

    learning_days = LearningDay.objects.filter(
        enrollment=enrollment
    )

    progress_records = DayProgress.objects.filter(
        learning_day__enrollment=enrollment
    )

    difficulty_distribution = Counter(
        learning_days.values_list(
            "difficulty",
            flat=True,
        )
    )

    topic_distribution = Counter(
        learning_days.values_list(
            "topic",
            flat=True,
        )
    )

    print("\n" + "=" * 60)
    print("ROADMAP STATISTICS")
    print("=" * 60)

    print("Total Learning Days:", learning_days.count())
    print("Progress Records:", progress_records.count())

    print(
        "Unlocked Days:",
        progress_records.filter(
            status="unlocked"
        ).count()
    )

    print(
        "Locked Days:",
        progress_records.filter(
            status="locked"
        ).count()
    )

    print(
        "Generated Lesson Content:",
        learning_days.filter(
            is_content_generated=True
        ).count()
    )

    print(
        "Total Estimated Learning Hours:",
        round(
            sum(
                day.estimated_minutes
                for day in learning_days
            ) / 60,
            2,
        )
    )

    print("\nDifficulty Distribution:")

    for difficulty, count in difficulty_distribution.items():
        print(f"- {difficulty}: {count} days")

    print("\nTopic Distribution:")

    for topic, count in topic_distribution.most_common():
        print(f"- {topic}: {count} days")

    # ==========================================
    # 6. Verify Enrollment Activation
    # ==========================================

    enrollment.refresh_from_db()

    print("\n" + "=" * 60)
    print("ENROLLMENT STATUS")
    print("=" * 60)

    print("Language:", enrollment.get_language_display())
    print("Skill Level:", enrollment.skill_level)
    print("Status:", enrollment.status)
    print("Current Day:", enrollment.current_day)

    # ==========================================
    # 7. Verify AI Generation Job
    # ==========================================

    job = AIGenerationJob.objects.get(
        idempotency_key=f"roadmap_{enrollment.id}"
    )

    print("\nAI Job Type:", job.job_type)
    print("AI Job Status:", job.status)
    print("Job Attempts:", job.attempt_count)

    print("\nRoadmap Summary:")
    print(job.response_data.get("summary", ""))

    # ==========================================
    # 8. Test Duplicate Generation Prevention
    # ==========================================

    print("\nTesting duplicate roadmap prevention...")

    previous_attempt_count = job.attempt_count

    second_roadmap = generate_personalized_roadmap(
        enrollment
    )

    original_ids = [day.id for day in roadmap]

    second_ids = [
        day.id for day in second_roadmap
    ]

    same_roadmap = original_ids == second_ids

    job.refresh_from_db()

    print("Same Roadmap Returned:", same_roadmap)

    print(
        "Additional Generation Attempts:",
        job.attempt_count - previous_attempt_count
    )

    # ==========================================
    # 9. Validate Final Results
    # ==========================================

    assert len(roadmap) == 30

    assert learning_days.count() == 30

    assert progress_records.count() == 30

    assert [
        day.day_number for day in roadmap
    ] == list(range(1, 31))

    assert progress_records.filter(
        status="unlocked"
    ).count() == 1

    assert progress_records.filter(
        status="locked"
    ).count() == 29

    assert progress_records.get(
        learning_day__day_number=1
    ).status == "unlocked"

    assert learning_days.filter(
        is_content_generated=True
    ).count() == 0

    assert enrollment.status == "active"

    assert enrollment.current_day == 1

    assert job.status == "completed"

    assert same_roadmap is True

    assert job.attempt_count == previous_attempt_count

    print("\n" + "=" * 60)
    print("PERSONALIZED ROADMAP TEST PASSED!")
    print("=" * 60)


if __name__ == "__main__":

    try:

        main()

    except RoadmapGenerationError as error:

        print("\nRoadmap Generation Error:", error)

        print(
            "Existing assessment results are preserved."
        )

        print(
            "Check the AI generation job before retrying."
        )

        raise SystemExit(1)