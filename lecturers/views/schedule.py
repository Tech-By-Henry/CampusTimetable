from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from institution_admin.models import (
    TimetableEntry, PublishedEntry, PublishedTimetable,
    TeachingAssignment
)

from lecturers.serializers.schedule import LecturerEventSerializer


class LecturerScheduleViewSet(viewsets.ViewSet):
    """
    GET /api/v1/lecturer/me/schedule/?term=<id>&scope=live|published&day=MON
    - term: REQUIRED (int)
    - scope: default 'live' (or 'published')
    - day: optional (e.g., MON,TUE,...)
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        user = request.user
        term_param = request.query_params.get("term")
        scope = (request.query_params.get("scope") or "live").lower()
        day = (request.query_params.get("day") or "").upper().strip()

        if not term_param or not term_param.isdigit():
            return Response({"detail": "Query param 'term' is required and must be an integer."},
                            status=status.HTTP_400_BAD_REQUEST)
        term_id = int(term_param)

        offering_ids = list(
            TeachingAssignment.objects.filter(lecturer_id=user.id, active=True)
            .values_list("offering_id", flat=True)
        )
        if not offering_ids:
            return Response([], status=status.HTTP_200_OK)

        events = []
        if scope == "published":
            snap = (
                PublishedTimetable.objects
                .filter(term_id=term_id, is_current=True)
                .order_by("-created_at")
                .first()
            )
            if not snap:
                return Response([], status=status.HTTP_200_OK)

            qs = (
                PublishedEntry.objects
                .filter(snapshot_id=snap.id, offering_id__in=offering_ids)
                .order_by("day", "slot_index")
            )
            if day:
                qs = qs.filter(day=day)

            for pe in qs:
                events.append({
                    "origin": "published",
                    "day": pe.day,
                    "slot_index": pe.slot_index,
                    "start_time": pe.start_time.strftime("%H:%M") if pe.start_time else "",
                    "end_time": pe.end_time.strftime("%H:%M") if pe.end_time else "",
                    "room_name": getattr(pe, "room_name", "") or "",
                    "course_code": getattr(pe, "course_code", "") or "",
                    "course_title": getattr(pe, "course_title", "") or "",
                    "cohort_label": getattr(pe, "cohort_label", "") or "",
                    "level_name": getattr(pe, "level_name", "") or "",
                    "published_entry_id": pe.id,
                })

        else:
            qs = (
                TimetableEntry.objects
                .select_related("slot", "offering__course", "offering__cohort", "offering__level", "room")
                .filter(term_id=term_id, offering_id__in=offering_ids)
                .order_by("slot__day", "slot__slot_index")
            )
            if day:
                qs = qs.filter(slot__day=day)

            for te in qs:
                slot = te.slot
                off = te.offering
                room_name = te.room.name if getattr(te, "room", None) else ""

                course_code = getattr(getattr(off, "course", None), "code", "") or ""
                course_title = getattr(getattr(off, "course", None), "title", "") or ""
                cohort_label = getattr(getattr(off, "cohort", None), "label", "") or ""
                level_name = getattr(getattr(off, "level", None), "name", "") or ""

                events.append({
                    "origin": "live",
                    "day": slot.day,
                    "slot_index": slot.slot_index,
                    "start_time": slot.start_time.strftime("%H:%M") if slot.start_time else "",
                    "end_time": slot.end_time.strftime("%H:%M") if slot.end_time else "",
                    "room_name": room_name,
                    "course_code": course_code,
                    "course_title": course_title,
                    "cohort_label": cohort_label,
                    "level_name": level_name,
                    "timetable_entry_id": te.id,
                })

        ser = LecturerEventSerializer(events, many=True)
        return Response(ser.data, status=status.HTTP_200_OK)
