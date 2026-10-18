from django.shortcuts import render

# Create your views here.
from django.http import JsonResponse
from django.utils import timezone


def home(request):
    return JsonResponse({
        "message": "Welcome to CodeMind AI",
        "status": "running",
    })


def health_check(request):
    return JsonResponse({
        "status": "healthy",
        "service": "codemind-ai-backend",
        "timestamp": timezone.now().isoformat(),
    })