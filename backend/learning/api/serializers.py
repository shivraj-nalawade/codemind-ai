from django.contrib.auth import (
    get_user_model,
    authenticate,
)

from django.contrib.auth.password_validation import (
    validate_password,
)

from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)

from django.db import IntegrityError, transaction

from rest_framework import serializers


User = get_user_model()


# ==========================================
# 1. User Response Serializer
# ==========================================

class UserSerializer(serializers.ModelSerializer):

    class Meta:

        model = User

        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "date_joined",
        )

        read_only_fields = fields


# ==========================================
# 2. Registration Serializer
# ==========================================

class RegisterSerializer(serializers.Serializer):

    username = serializers.CharField(
        min_length=3,
        max_length=150,
    )

    email = serializers.EmailField(
        max_length=254,
        required=True,
    )

    first_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        default="",
    )

    last_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        default="",
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=128,
        trim_whitespace=False,
        style={"input_type": "password"},
    )

    confirm_password = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
        style={"input_type": "password"},
    )


    # --------------------------------------
    # Validate Username
    # --------------------------------------

    def validate_username(self, value):

        value = value.strip()

        username_field = User._meta.get_field(
            "username"
        )

        try:

            username_field.run_validators(value)

        except DjangoValidationError as error:

            raise serializers.ValidationError(
                error.messages
            )

        if User.objects.filter(
            username__iexact=value
        ).exists():

            raise serializers.ValidationError(
                "This username is already in use."
            )

        return value


    # --------------------------------------
    # Validate Email
    # --------------------------------------

    def validate_email(self, value):

        value = value.strip().lower()

        if User.objects.filter(
            email__iexact=value
        ).exists():

            raise serializers.ValidationError(
                "This email address is already in use."
            )

        return value


    # --------------------------------------
    # Validate Complete Registration Data
    # --------------------------------------

    def validate(self, attrs):

        password = attrs["password"]

        confirm_password = attrs["confirm_password"]

        if password != confirm_password:

            raise serializers.ValidationError({
                "confirm_password": [
                    "Passwords do not match."
                ]
            })

        temporary_user = User(
            username=attrs["username"],
            email=attrs["email"],
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )

        try:

            validate_password(
                password,
                user=temporary_user,
            )

        except DjangoValidationError as error:

            raise serializers.ValidationError({
                "password": error.messages
            })

        return attrs


    # --------------------------------------
    # Create User
    # --------------------------------------

    def create(self, validated_data):

        validated_data.pop(
            "confirm_password",
            None,
        )

        try:

            with transaction.atomic():

                user = User.objects.create_user(
                    username=validated_data["username"],
                    email=validated_data["email"],
                    password=validated_data["password"],
                    first_name=validated_data.get(
                        "first_name",
                        "",
                    ),
                    last_name=validated_data.get(
                        "last_name",
                        "",
                    ),
                )

        except IntegrityError as error:

            raise serializers.ValidationError({
                "username": [
                    "Unable to create account. "
                    "The username may already be in use."
                ]
            }) from error

        return user


# ==========================================
# 3. Login Serializer
# ==========================================

class LoginSerializer(serializers.Serializer):

    username = serializers.CharField(
        max_length=150,
    )

    password = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
        style={"input_type": "password"},
    )


    def validate(self, attrs):

        username = attrs["username"]

        password = attrs["password"]

        request = self.context.get("request")

        user = authenticate(
            request=request,
            username=username,
            password=password,
        )

        if user is None or not user.is_active:

            raise serializers.ValidationError({
                "non_field_errors": [
                    "Invalid username or password."
                ]
            })

        attrs["user"] = user

        return attrs