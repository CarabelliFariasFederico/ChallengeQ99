from django.contrib import admin
from django.urls import include, path

from config import views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("healthz", views.healthz),
    path("readyz", views.readyz),
    path("api/", include("apps.api.urls")),
]
