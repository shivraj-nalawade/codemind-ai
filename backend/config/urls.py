from django.conf import settings
from django.contrib import admin
from django.urls import path, include


urlpatterns = [

    # General backend APIs
    path(
        "api/",
        include("assistant.urls")
    ),

    # Repository Assistant APIs
    path(
        "api/repositories/",
        include("repositories.urls")
    ),

    # Personalized Learning APIs
    path(
        "api/learning/",
        include("learning.api.urls")
    ),
]


# Enable Django admin only during local development.

if settings.DEBUG:

    urlpatterns.insert(
        0,
        path("admin/", admin.site.urls)
    )