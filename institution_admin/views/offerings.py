from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.models import CourseOffering
from institution_admin.serializers.offerings import CourseOfferingSerializer

class CourseOfferingViewSet(viewsets.ModelViewSet):
    queryset = CourseOffering.objects.select_related(
        "term", "cohort", "level", "course", "stream"
    ).all()
    serializer_class = CourseOfferingSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["course__code", "course__title", "cohort__label", "level__name", "stream__code"]
    ordering_fields = ["term__start_date", "cohort__label", "level__order", "semester", "course__code", "id"]
    ordering = ["cohort__label", "level__order", "semester", "course__code"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params
        if q.get("cohort"):   qs = qs.filter(cohort_id=q["cohort"])
        if q.get("term"):     qs = qs.filter(term_id=q["term"])
        if q.get("level"):    qs = qs.filter(level_id=q["level"])
        if q.get("stream"):   qs = qs.filter(stream_id=q["stream"])
        if q.get("semester"): qs = qs.filter(semester=int(q["semester"]))
        return qs
