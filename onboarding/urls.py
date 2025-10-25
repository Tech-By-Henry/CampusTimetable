# onboarding/urls.py
from rest_framework.routers import DefaultRouter
from .views import OnboardingViewSet

router = DefaultRouter()
# Register a single ViewSet; all endpoints are custom actions to keep your URL shapes.
router.register(r"", OnboardingViewSet, basename="onboarding")

urlpatterns = router.urls
