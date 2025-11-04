from rest_framework.routers import DefaultRouter
from .views.auth import LecturerAuthViewSet
from .views.schedule import LecturerScheduleViewSet
from .views.assignments import LecturerAssignmentsViewSet
from .views.placements import LecturerPlacementsViewSet
from .views.BlackoutRequest import LecturerBlackoutRequestViewSet

router = DefaultRouter()
router.register(r"auth", LecturerAuthViewSet, basename="lecturer-auth")
router.register(r"me/schedule", LecturerScheduleViewSet, basename="lecturer-schedule")
router.register(r"me/assignments", LecturerAssignmentsViewSet, basename="lecturer-assignments")
router.register(r"me/placements", LecturerPlacementsViewSet, basename="lecturer-placements")
router.register(r"me/blackout-requests", LecturerBlackoutRequestViewSet, basename="lecturer-blackouts")


urlpatterns = router.urls
