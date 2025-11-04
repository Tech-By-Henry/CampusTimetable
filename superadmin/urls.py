# institution_owner/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from institution_owner.views.auth.OTsetup import OTSetupViewSet
from institution_owner.views.auth.login import SuperAdminLoginView
from institution_owner.views.catalog.catalog import (
    FacultyViewSet, DepartmentViewSet, ProgramViewSet, RoomViewSet, AcademicTermViewSet
)

router = DefaultRouter()
# Auth (router-based for setup)
router.register(r"auth/ot-setup", OTSetupViewSet, basename="institution_owner-ot-setup")

# Catalog (router-based)
router.register(r"catalog/faculties",   FacultyViewSet,    basename="sa-faculty")
router.register(r"catalog/departments", DepartmentViewSet, basename="sa-department")
router.register(r"catalog/programs",    ProgramViewSet,    basename="sa-program")
router.register(r"catalog/rooms",       RoomViewSet,       basename="sa-room")
router.register(r"catalog/terms",       AcademicTermViewSet, basename="sa-term")
router.register(r"catalog/academic-terms", AcademicTermViewSet, basename="academic-terms")


urlpatterns = [
    # Login stays a single POST endpoint (not router)
    path("auth/login/", SuperAdminLoginView.as_view(), name="institution_owner-login"),
    # Everything else via router
    path("", include(router.urls)),
]
