from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
import csv

from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.models import (
    TimetableEntry, PublishedTimetable, PublishedEntry, TeachingAssignment
)
from institution_admin.serializers.publish import (
    PublishRequestSerializer, PublishedTimetableSerializer, PublishedEntrySerializer,
)


class PublishedTimetableViewSet(viewsets.ViewSet):
    """
    Admin endpoints:
      - POST   /api/v1/admin/publish/                     (create snapshot from live timetable)
      - GET    /api/v1/admin/publish/?term=1              (list snapshots; filter by term)
      - GET    /api/v1/admin/publish/{id}/                (snapshot metadata)
      - POST   /api/v1/admin/publish/{id}/activate        (make this snapshot current)
      - GET    /api/v1/admin/publish/{id}/entries         (list frozen entries)
      - GET    /api/v1/admin/publish/{id}/entries.csv     (CSV of entries, optional ?cohort=<label>)
      - GET    /api/v1/admin/publish/{id}/lecturer.csv    (CSV of entries filtered by lecturer=<user_id>)
    """
    permission_classes = [permissions.IsAuthenticated, IsInstitutionAdmin]

    # -------- list / retrieve --------

    def list(self, request):
        qs = PublishedTimetable.objects.all()
        term = request.query_params.get("term")
        if term:
            qs = qs.filter(term_id=term)
        qs = qs.annotate(entries_count=Count("entries")).order_by("-is_current", "-version", "-id")
        data = PublishedTimetableSerializer(qs, many=True).data
        return Response({"count": len(data), "results": data}, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        snap = PublishedTimetable.objects.annotate(entries_count=Count("entries")).get(pk=pk)
        return Response(PublishedTimetableSerializer(snap).data, status=status.HTTP_200_OK)

    # -------- create / activate --------

    def create(self, request):
        """
        Build a new snapshot from current TimetableEntry rows of the given term.
        If 'activate' is true (default), mark it the current snapshot for that term.
        """
        ser = PublishRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        term = ser.validated_data["term"]
        note = ser.validated_data.get("note", "")
        activate = ser.validated_data.get("activate", True)

        if note and PublishedTimetable.objects.filter(term=term, note=note).exists():
            return Response(
                {"detail": "A snapshot with this label already exists for the term."},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            last = PublishedTimetable.objects.filter(term=term).order_by("-version").first()
            next_version = (last.version + 1) if last else 1

            snap = PublishedTimetable.objects.create(
                term=term,
                version=next_version,
                is_current=False,
                note=note,
                created_by=getattr(request, "user", None),
            )

            rows = (
                TimetableEntry.objects
                .select_related("offering__course", "offering__cohort", "offering__level",
                                "slot", "room")
                .filter(term=term)
            )

            bulk = []
            for t in rows:
                off = t.offering
                slot = t.slot
                room = t.room
                bulk.append(PublishedEntry(
                    snapshot=snap,
                    offering=off, slot=slot, room=room,
                    day=slot.day, slot_index=slot.slot_index,
                    start_time=slot.start_time, end_time=slot.end_time,
                    room_name=(room.name if room else ""),
                    course_code=(off.course.code if off and off.course_id else ""),
                    course_title=(off.course.title if off and off.course_id else ""),
                    cohort_label=(off.cohort.label if off and off.cohort_id else ""),
                    level_name=(off.level.name if off and off.level_id else ""),
                ))
            PublishedEntry.objects.bulk_create(bulk, batch_size=1000)

            if activate:
                PublishedTimetable.objects.filter(term=term, is_current=True).exclude(id=snap.id).update(is_current=False)
                snap.is_current = True
                snap.save(update_fields=["is_current"])

        out = PublishedTimetable.objects.annotate(entries_count=Count("entries")).get(pk=snap.id)
        return Response(PublishedTimetableSerializer(out).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        snap = PublishedTimetable.objects.select_related("term").get(pk=pk)
        with transaction.atomic():
            PublishedTimetable.objects.filter(term=snap.term, is_current=True).exclude(id=snap.id).update(is_current=False)
            snap.is_current = True
            snap.save(update_fields=["is_current"])
        out = PublishedTimetable.objects.annotate(entries_count=Count("entries")).get(pk=snap.id)
        return Response(PublishedTimetableSerializer(out).data, status=status.HTTP_200_OK)

    # -------- entries / CSV exports --------

    @action(detail=True, methods=["get"], url_path="entries")
    def entries(self, request, pk=None):
        snap = PublishedTimetable.objects.get(pk=pk)
        qs = snap.entries.all().order_by("day", "slot_index", "cohort_label", "course_code")
        data = PublishedEntrySerializer(qs, many=True).data
        return Response({"count": len(data), "results": data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="entries.csv")
    def entries_csv(self, request, pk=None):
        cohort = request.query_params.get("cohort")
        qs = PublishedEntry.objects.filter(snapshot_id=pk)
        if cohort:
            qs = qs.filter(cohort_label=cohort)

        rows = qs.values_list(
            "day", "slot_index", "start_time", "end_time",
            "room_name", "course_code", "course_title", "cohort_label"
        ).order_by("day", "slot_index", "cohort_label", "course_code")

        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="snapshot_entries.csv"'
        w = csv.writer(resp)
        w.writerow(["day", "slot_index", "start_time", "end_time", "room_name", "course_code", "course_title", "cohort_label"])
        for r in rows:
            w.writerow(r)
        return resp

    @action(detail=True, methods=["get"], url_path="lecturer.csv")
    def lecturer_csv(self, request, pk=None):
        lec_id = request.query_params.get("lecturer")
        if not lec_id:
            return Response({"detail": "lecturer is required"}, status=status.HTTP_400_BAD_REQUEST)

        off_ids = TeachingAssignment.objects.filter(lecturer_id=lec_id, active=True)\
                                            .values_list("offering_id", flat=True)
        qs = PublishedEntry.objects.filter(snapshot_id=pk, offering_id__in=off_ids)

        rows = qs.values_list(
            "day", "slot_index", "start_time", "end_time",
            "room_name", "course_code", "course_title", "cohort_label", "level_name"
        ).order_by("day", "slot_index", "cohort_label", "course_code")

        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="lecturer_schedule.csv"'
        w = csv.writer(resp)
        w.writerow(["day", "slot_index", "start_time", "end_time", "room_name",
                    "course_code", "course_title", "cohort_label", "level"])
        for r in rows:
            w.writerow(r)
        return resp
