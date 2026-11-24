
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from learning.models import Enrollment
from learning.api.permissions import IsEnrollmentOwner

from types import SimpleNamespace


User = get_user_model()


class LearningAuthenticationTests(TestCase):

    def setUp(self):

        self.client = Client(enforce_csrf_checks=True)

        self.registration_data = {
            "username": "learning_test_user",
            "email": "learning_test@example.com",
            "first_name": "Test",
            "last_name": "Learner",
            "password": "V9!qL2#zR8@p",
            "confirm_password": "V9!qL2#zR8@p",
        }

        self.login_data = {
            "username": "learning_test_user",
            "password": "V9!qL2#zR8@p",
        }

    def get_csrf_token(self):

        response = self.client.get(
            reverse("learning:csrf")
        )

        self.assertEqual(response.status_code, 200)

        return response.json()["data"]["csrf_token"]

    def post_json(self, endpoint, data, token=None):

        headers = {}

        if token:
            headers["HTTP_X_CSRFTOKEN"] = token

        return self.client.post(
            reverse(endpoint),
            data=data,
            content_type="application/json",
            **headers,
        )

    def register_user(self):

        token = self.get_csrf_token()

        response = self.post_json(
            "learning:register",
            self.registration_data,
            token,
        )

        self.assertEqual(response.status_code, 201)

        return token

    def test_complete_authentication_workflow(self):

        # Anonymous access must be rejected.
        response = self.client.get(
            reverse("learning:current_user")
        )

        self.assertEqual(response.status_code, 401)

        # Registration without CSRF must fail.
        response = self.post_json(
            "learning:register",
            self.registration_data,
        )

        self.assertEqual(response.status_code, 403)

        # Register successfully.
        token = self.register_user()

        user = User.objects.get(
            username="learning_test_user"
        )

        # Password must be hashed.
        self.assertNotEqual(
            user.password,
            self.registration_data["password"],
        )

        self.assertTrue(
            user.check_password(
                self.registration_data["password"]
            )
        )

        # Registration must not automatically log in.
        response = self.client.get(
            reverse("learning:current_user")
        )

        self.assertEqual(response.status_code, 401)

        # Duplicate registration must fail.
        response = self.post_json(
            "learning:register",
            self.registration_data,
            token,
        )

        self.assertEqual(response.status_code, 400)

        # Incorrect password must fail.
        response = self.post_json(
            "learning:login",
            {
                "username": "learning_test_user",
                "password": "IncorrectPassword",
            },
            token,
        )

        self.assertEqual(response.status_code, 400)

        # Login without CSRF must fail.
        response = self.post_json(
            "learning:login",
            self.login_data,
        )

        self.assertEqual(response.status_code, 403)

        # Correct login must succeed.
        response = self.post_json(
            "learning:login",
            self.login_data,
            token,
        )

        self.assertEqual(response.status_code, 200)

        login_data = response.json()["data"]

        self.assertTrue(
            login_data["is_authenticated"]
        )

        new_token = login_data["csrf_token"]

        # Session must remain authenticated.
        response = self.client.get(
            reverse("learning:current_user")
        )

        self.assertEqual(response.status_code, 200)

        user_data = response.json()["data"]["user"]

        self.assertEqual(
            user_data["username"],
            "learning_test_user",
        )

        # Sensitive fields must not be exposed.
        for field in [
            "password",
            "is_superuser",
            "is_staff",
            "user_permissions",
            "groups",
        ]:
            self.assertNotIn(field, user_data)

        # Old CSRF token must fail after login.
        response = self.post_json(
            "learning:logout",
            {},
            token,
        )

        self.assertEqual(response.status_code, 403)

        # Logout with the new token.
        response = self.post_json(
            "learning:logout",
            {},
            new_token,
        )

        self.assertEqual(response.status_code, 200)

        # Session must be terminated.
        response = self.client.get(
            reverse("learning:current_user")
        )

        self.assertEqual(response.status_code, 401)

    def test_invalid_registration(self):

        token = self.get_csrf_token()

        data = self.registration_data.copy()

        data["confirm_password"] = "DifferentPassword"

        response = self.post_json(
            "learning:register",
            data,
            token,
        )

        self.assertEqual(response.status_code, 400)

        self.assertFalse(
            User.objects.filter(
                username=data["username"]
            ).exists()
        )

    def test_invalid_json(self):

        token = self.get_csrf_token()

        response = self.client.post(
            reverse("learning:register"),
            data="{invalid json",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 400)

    def test_http_method_restrictions(self):

        response = self.client.get(
            reverse("learning:register")
        )

        self.assertEqual(response.status_code, 405)

        response = self.client.get(
            reverse("learning:login")
        )

        self.assertEqual(response.status_code, 405)

        response = self.client.get(
            reverse("learning:logout")
        )

        self.assertEqual(response.status_code, 405)

    def test_enrollment_ownership(self):

        owner = User.objects.create_user(
            username="owner",
            password="OwnerTestPassword123!",
        )

        other_user = User.objects.create_user(
            username="other_user",
            password="OtherTestPassword123!",
        )

        enrollment = Enrollment.objects.create(
            user=owner,
            language="python",
        )

        permission = IsEnrollmentOwner()

        owner_request = SimpleNamespace(
            user=owner
        )

        other_request = SimpleNamespace(
            user=other_user
        )

        self.assertTrue(
            permission.has_object_permission(
                owner_request,
                None,
                enrollment,
            )
        )

        self.assertFalse(
            permission.has_object_permission(
                other_request,
                None,
                enrollment,
            )
        )
