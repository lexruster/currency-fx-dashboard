"""URL configuration for currency_project."""

from django.urls import include, path

urlpatterns = [
    path("", include("dashboard.urls")),
]
