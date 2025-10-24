# superadmin/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from superadmin.views.auth.OTsetup import OTSetupView
from superadmin.views.auth.login import SuperAdminLoginView
from superadmin.views.catalog.catalog import (
    FacultyViewSet, DepartmentViewSet, ProgramViewSet, RoomViewSet, AcademicTermViewSet
)

router = DefaultRouter()
router.register(r"catalog/faculties", FacultyViewSet, basename="sa-faculty")
router.register(r"catalog/departments", DepartmentViewSet, basename="sa-department")
router.register(r"catalog/programs", ProgramViewSet, basename="sa-program")
router.register(r"catalog/rooms", RoomViewSet, basename="sa-room")
router.register(r"catalog/terms", AcademicTermViewSet, basename="sa-term")

urlpatterns = [
    path("auth/ot-setup/", OTSetupView.as_view(), name="superadmin-ot-setup"),
    path("auth/login/", SuperAdminLoginView.as_view(), name="superadmin-login"),
    path("", include(router.urls)),  # <-- CRUD endpoints live here
]
