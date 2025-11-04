# server/api_urls.py
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # App routers
    path("v1/superadmin/", include("superadmin.urls")),       # -> /api/v1/superadmin/...
    path("v1/onboarding/", include("onboarding.urls")),       # -> /api/v1/onboarding/...
    path("v1/admin/", include("institution_admin.urls")),     # -> /api/v1/admin/...
    path("v1/lecturer/", include("lecturers.urls")),          # -> /api/v1/lecturer/...

    # JWT endpoints
    path("v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("v1/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # OpenAPI schema + Swagger / Redoc
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
