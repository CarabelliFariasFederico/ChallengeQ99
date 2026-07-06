from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.api.views import (
    CredentialViewSet,
    FileContentView,
    FilesView,
    LoginView,
    MeView,
    OAuthCallbackView,
    OAuthInitiateView,
    TeamViewSet,
    UserViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register("admin/teams", TeamViewSet, basename="admin-teams")
router.register("admin/users", UserViewSet, basename="admin-users")
router.register("admin/credentials", CredentialViewSet, basename="admin-credentials")

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="auth-refresh"),
    path(
        "admin/credentials/oauth/initiate",
        OAuthInitiateView.as_view(),
        name="oauth-initiate",
    ),
    path(
        "admin/credentials/oauth/callback",
        OAuthCallbackView.as_view(),
        name="oauth-callback",
    ),
    path("me", MeView.as_view(), name="me"),
    path("files", FilesView.as_view(), name="files"),
    path("files/<str:file_id>/content", FileContentView.as_view(), name="file-content"),
    *router.urls,
]
