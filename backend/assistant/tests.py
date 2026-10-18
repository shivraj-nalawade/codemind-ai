from django.test import TestCase
from django.urls import reverse


class HealthAPITest(TestCase):

    def test_home_endpoint(self):
        response = self.client.get("/api/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "running")

    def test_health_endpoint(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")