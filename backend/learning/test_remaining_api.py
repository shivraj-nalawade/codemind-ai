from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from learning.models import (
    Enrollment,
    LearningDay,
    DayProgress,
)


User = get_user_model()


class RemainingAPITests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="daily_learner",
            password="TestPassword123!",
        )

        self.client = APIClient()
        self.client.force_login(self.user)

        self.enrollment = Enrollment.objects.create(
            user=self.user,
            language="python",
            skill_level="intermediate",
            status="active",
            current_day=1,
        )

        for number in range(1, 31):

            day = LearningDay.objects.create(
                enrollment=self.enrollment,
                day_number=number,
                title=f"Python Lesson {number}",
                topic="Conditional Statements",
                difficulty="basic",
                learning_objectives=[
                    "Understand conditions",
                    "Write if statements",
                    "Solve exercises",
                ],
                estimated_minutes=45,
                is_content_generated=(number == 1),
                explanation=(
                    "Python conditional statements."
                    if number == 1 else ""
                ),
                code_examples=[
                    {"code": "if True: print('Hello')"}
                ] if number == 1 else [],
                practical_tasks=[
                    {"title": "Write a condition"}
                ] if number == 1 else [],
            )

            DayProgress.objects.create(
                learning_day=day,
                status="unlocked" if number == 1 else "locked",
            )

        self.day1 = LearningDay.objects.get(
            enrollment=self.enrollment,
            day_number=1,
        )

        self.day2 = LearningDay.objects.get(
            enrollment=self.enrollment,
            day_number=2,
        )

    def post(self, name, object_id):

        return self.client.post(
            reverse(
                f"learning:{name}",
                args=[object_id],
            ),
            {},
            format="json",
        )

    def test_lesson_access(self):

        response = self.client.get(
            reverse(
                "learning:lesson_detail",
                args=[self.day1.id],
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_locked_day(self):

        response = self.post(
            "generate_lesson",
            self.day2.id,
        )

        self.assertEqual(response.status_code, 409)

        response = self.post(
            "start_day",
            self.day2.id,
        )

        self.assertEqual(response.status_code, 409)

    def test_learning_progress_workflow(self):

        response = self.post(
            "start_day",
            self.day1.id,
        )

        self.assertEqual(response.status_code, 200)

        response = self.post(
            "complete_lesson",
            self.day1.id,
        )

        self.assertEqual(response.status_code, 200)

        response = self.post(
            "complete_practical",
            self.day1.id,
        )

        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            response.json()["data"]["assessment_eligible"]
        )

    def test_assessment_before_lesson_completion(self):

        response = self.post(
            "generate_daily_assessment",
            self.day1.id,
        )

        self.assertEqual(response.status_code, 409)

    def test_dashboard(self):

        response = self.client.get(
            reverse(
                "learning:dashboard",
                args=[self.enrollment.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()["data"]

        self.assertIn("course_progress", data)
        self.assertIn("topic_mastery", data)
        self.assertIn("streaks", data)
        self.assertIn("roadmap", data)

        self.assertEqual(len(data["roadmap"]), 30)

    def test_job_status(self):

        response = self.client.get(
            reverse(
                "learning:ai_jobs",
                args=[self.enrollment.id],
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_other_user_cannot_access_lesson(self):

        other_user = User.objects.create_user(
            username="unauthorized_learner",
            password="OtherPassword123!",
        )

        self.client.force_login(other_user)

        response = self.client.get(
            reverse(
                "learning:lesson_detail",
                args=[self.day1.id],
            )
        )

        self.assertEqual(response.status_code, 404)

        response = self.client.get(
            reverse(
                "learning:dashboard",
                args=[self.enrollment.id],
            )
        )

        self.assertEqual(response.status_code, 404)