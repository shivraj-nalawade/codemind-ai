from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from learning.models import (
    Enrollment,
    Assessment,
    Question,
)


User = get_user_model()


class EnrollmentAPITests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="learner",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="other_learner",
            password="OtherPassword123!",
        )

        self.client = APIClient()
        self.client.force_login(self.user)

        self.enrollment = Enrollment.objects.create(
            user=self.user,
            language="python",
        )

        self.other_enrollment = Enrollment.objects.create(
            user=self.other_user,
            language="java",
        )

        self.assessment = Assessment.objects.create(
            enrollment=self.enrollment,
            assessment_type="initial",
            day_number=0,
            title="Python Initial Assessment",
            total_questions=15,
        )

        for number in range(1, 16):

            question_type = (
                "mcq" if number <= 12
                else "coding" if number <= 14
                else "theory"
            )

            Question.objects.create(
                assessment=self.assessment,
                question_type=question_type,
                topic="Variables and Data Types",
                difficulty="basic",
                question_text=f"Test question {number}",
                options=["A", "B", "C", "D"]
                if question_type == "mcq" else [],
                correct_answer="A",
                explanation="Test reference explanation.",
                marks=1 if question_type == "mcq" else 3,
                order=number,
            )

    def test_languages(self):

        response = self.client.get(
            reverse("learning:languages")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 5)

    def test_enrollment_creation_and_duplicate(self):

        url = reverse("learning:enrollments")

        response = self.client.post(
            url,
            {"language": "sql"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        response = self.client.post(
            url,
            {"language": "sql"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            Enrollment.objects.filter(
                user=self.user,
                language="sql",
            ).count(),
            1,
        )

    def test_invalid_language(self):

        response = self.client.post(
            reverse("learning:enrollments"),
            {"language": "invalid"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_ownership(self):

        response = self.client.get(
            reverse(
                "learning:enrollment_detail",
                args=[self.other_enrollment.id],
            )
        )

        self.assertEqual(response.status_code, 404)

        response = self.client.get(
            reverse("learning:enrollments")
        )

        ids = [
            item["id"]
            for item in response.json()["data"]
        ]

        self.assertNotIn(
            self.other_enrollment.id,
            ids,
        )

    def test_anonymous_access(self):

        self.client.logout()

        response = self.client.get(
            reverse("learning:enrollments")
        )

        self.assertIn(response.status_code, [401, 403])

    def test_assessment_answer_protection(self):

        response = self.client.get(
            reverse(
                "learning:initial_assessment",
                args=[self.enrollment.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        questions = response.json()["data"]["questions"]

        self.assertEqual(len(questions), 15)

        for question in questions:

            self.assertNotIn("correct_answer", question)
            self.assertNotIn("explanation", question)

    @patch(
        "learning.api.enrollment_views.generate_initial_assessment"
    )
    def test_assessment_generation(self, mock_generate):

        mock_generate.return_value = self.assessment

        response = self.client.post(
            reverse(
                "learning:generate_initial_assessment",
                args=[self.enrollment.id],
            ),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        mock_generate.assert_called_once()

    def test_attempt_and_answer_submission(self):

        response = self.client.post(
            reverse(
                "learning:start_assessment",
                args=[self.assessment.id],
            ),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        attempt_id = response.json()["data"]["attempt_id"]

        questions = Question.objects.filter(
            assessment=self.assessment
        )

        answers = [
            {
                "question_id": question.id,
                "submitted_answer": "A",
            }
            for question in questions
        ]

        response = self.client.post(
            reverse(
                "learning:save_answers",
                args=[attempt_id],
            ),
            {"answers": answers},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            len(response.json()["data"]["answers"]),
            15,
        )

        response = self.client.post(
            reverse(
                "learning:submit_assessment",
                args=[attempt_id],
            ),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.json()["data"]["status"],
            "submitted",
        )

        response = self.client.get(
            reverse(
                "learning:assessment_result",
                args=[attempt_id],
            )
        )

        self.assertEqual(response.status_code, 409)

    def test_roadmap_requires_assessment(self):

        response = self.client.post(
            reverse(
                "learning:generate_roadmap",
                args=[self.enrollment.id],
            ),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 409)

    def test_csrf_protection(self):

        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)

        response = client.post(
            reverse("learning:enrollments"),
            {"language": "sql"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)