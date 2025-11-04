from rest_framework.routers import DefaultRouter

from .views.auth import AdminAuthViewSet
from .views.levels import LevelViewSet
from .views.cohorts import ProgramCohortViewSet
from .views.courses import CourseViewSet
from .views.offerings import CourseOfferingViewSet
from .views.assignments import TeachingAssignmentViewSet
from .views.lecturers import AdminLecturersViewSet
from .views.cohort_auto import CohortAutoCreateConfigViewSet
from .views.cohort_manual import CohortManualCreateViewSet
from .views.schedule import (
    TimeGridViewSet, SlotViewSet, TimetableEntryViewSet, ScheduleViewSet,
    LecturerBlackoutViewSet, RoomBlackoutViewSet, CohortBlackoutViewSet, GlobalConstraintViewSet
)
# NEW
from .views.publish import PublishedTimetableViewSet
# existing router.register(... cohorts ... ) remains


router = DefaultRouter()
router.register(r"auth",        AdminAuthViewSet,          basename="admin-auth")
router.register(r"levels",      LevelViewSet,              basename="admin-levels")
router.register(r"cohorts",     ProgramCohortViewSet,      basename="admin-cohorts")
router.register(r"cohort-auto-config", CohortAutoCreateConfigViewSet, basename="admin-cohort-auto")
router.register(r"cohorts-manual", CohortManualCreateViewSet, basename="admin-cohort-manual")



router.register(r"courses",     CourseViewSet,             basename="admin-courses")
router.register(r"offerings",   CourseOfferingViewSet,     basename="admin-offerings")
router.register(r"assignments", TeachingAssignmentViewSet, basename="admin-assignments")
router.register(r"lecturers",   AdminLecturersViewSet,     basename="admin-lecturers")

router.register(r"timegrid",              TimeGridViewSet,         basename="admin-timegrid")
router.register(r"slots",                 SlotViewSet,             basename="admin-slots")
router.register(r"timetable",             TimetableEntryViewSet,   basename="admin-timetable")
router.register(r"schedule",              ScheduleViewSet,         basename="admin-schedule")
router.register(r"blackouts/lecturer",    LecturerBlackoutViewSet, basename="admin-blackouts-lecturer")
router.register(r"blackouts/room",        RoomBlackoutViewSet,     basename="admin-blackouts-room")
router.register(r"blackouts/cohort",      CohortBlackoutViewSet,   basename="admin-blackouts-cohort")
router.register(r"constraints/global",    GlobalConstraintViewSet, basename="admin-constraints-global")

router.register(r"publish",               PublishedTimetableViewSet, basename="admin-publish")

urlpatterns = router.urls


