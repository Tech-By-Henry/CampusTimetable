import datetime as dt
from django.db import transaction, models
from django.http import HttpResponse
from rest_framework import viewsets, mixins, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
import csv

from institution_admin.permissions import IsInstitutionAdmin
from institution_admin.models import (
    TimeGrid, Slot, TimetableEntry, DayOfWeek,
    LecturerBlackout, RoomBlackout, CohortBlackout, GlobalConstraint,
    CourseOffering, TeachingAssignment
)
from institution_admin.serializers.schedule import (
    TimeGridSerializer, SlotSerializer, PlacementSerializer, PrecheckSerializer,
    LecturerBlackoutSerializer, RoomBlackoutSerializer, CohortBlackoutSerializer, GlobalConstraintSerializer
)

# --- helper: materialize all slots for a grid ---

def _add_minutes(t: dt.time, minutes: int) -> dt.time:
    base = dt.datetime.combine(dt.date(2000, 1, 1), t)
    return (base + dt.timedelta(minutes=minutes)).time()

@transaction.atomic
def _materialize_slots(grid: TimeGrid):
    """
    Clears and rebuilds all Slot rows for the grid's term according to the
    grid definition (business_days, slot_length_min, slots_per_day, break_slots).
    """
    Slot.objects.filter(term=grid.term).delete()
    brk = set(grid.break_slots or [])
    for day in grid.business_days or []:
        for i in range(1, int(grid.slots_per_day) + 1):
            start = _add_minutes(grid.first_slot_start, (i - 1) * int(grid.slot_length_min))
            end   = _add_minutes(start, int(grid.slot_length_min))
            Slot.objects.create(
                term=grid.term,
                day=day,
                slot_index=i,
                start_time=start,
                end_time=end,
                is_break=(i in brk),
            )

# --- TimeGrid CRUD (upsert-on-create by term) ---

class TimeGridViewSet(viewsets.ModelViewSet):
    queryset = TimeGrid.objects.select_related("term").all()
    serializer_class = TimeGridSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering = ["-updated_at"]

    def create(self, request, *args, **kwargs):
        term_id = request.data.get("term")
        existing = TimeGrid.objects.filter(term_id=term_id).first()
        if existing:
            ser = self.get_serializer(existing, data=request.data)
            ser.is_valid(raise_exception=True)
            self.perform_update(ser)
            _materialize_slots(existing)
            return Response(ser.data, status=status.HTTP_200_OK)
        response = super().create(request, *args, **kwargs)
        _materialize_slots(TimeGrid.objects.get(pk=response.data["id"]))
        return response

    def update(self, request, *args, **kwargs):
        resp = super().update(request, *args, **kwargs)
        _materialize_slots(self.get_object())
        return resp

    def partial_update(self, request, *args, **kwargs):
        resp = super().partial_update(request, *args, **kwargs)
        _materialize_slots(self.get_object())
        return resp

# --- Slots (read-only) ---

class SlotViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Slot.objects.select_related("term").all()
    serializer_class = SlotSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering = ["day", "slot_index"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params
        if q.get("term"): qs = qs.filter(term_id=q.get("term"))
        if q.get("day"):  qs = qs.filter(day=q.get("day"))
        if q.get("is_break") in ("1", "true", "True"):   qs = qs.filter(is_break=True)
        if q.get("is_break") in ("0", "false", "False"): qs = qs.filter(is_break=False)
        return qs

# --- Timetable placements (CRUD) ---

class TimetableEntryViewSet(viewsets.ModelViewSet):
    queryset = TimetableEntry.objects.select_related(
        "term", "slot",
        "offering__course", "offering__cohort", "offering__level"
    ).all()
    serializer_class = PlacementSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering = ["term_id", "slot_id", "id"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params
        if q.get("term"):     qs = qs.filter(term_id=q["term"])
        if q.get("cohort"):   qs = qs.filter(offering__cohort_id=q["cohort"])
        if q.get("lecturer"): qs = qs.filter(offering__assignments__active=True,
                                             offering__assignments__lecturer_id=q["lecturer"])
        if q.get("level"):    qs = qs.filter(offering__level_id=q["level"])
        if q.get("day"):      qs = qs.filter(slot__day=q["day"])
        return qs

    @action(detail=True, methods=["post"], url_path="reschedule")
    def reschedule(self, request, pk=None):
        """
        POST /api/v1/admin/timetable/{id}/reschedule
        Body: { "slot": <slot_id>, "room": <room_id|null> }
        """
        try:
            tt = self.get_queryset().get(pk=pk)
        except TimetableEntry.DoesNotExist:
            return Response({"detail": "Timetable entry not found"}, status=status.HTTP_404_NOT_FOUND)

        slot_id = request.data.get("slot")
        room_id = request.data.get("room", None)

        if not slot_id:
            return Response({"detail": "slot is required"}, status=status.HTTP_400_BAD_REQUEST)

        pre_ser = PrecheckSerializer(data={
            "term": tt.term_id,
            "offering": tt.offering_id,
            "slot": slot_id,
            "room": room_id,
        })
        pre_ser.is_valid(raise_exception=True)

        pre_resp = ScheduleViewSet()._precheck_internal(pre_ser.validated_data)  # reuse logic
        if not pre_resp["ok"]:
            return Response(pre_resp, status=status.HTTP_400_BAD_REQUEST)

        tt.slot_id = slot_id
        tt.room_id = room_id
        tt.save(update_fields=["slot_id", "room_id"])
        return Response(PlacementSerializer(tt).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="lecturer.csv")
    def lecturer_live_csv(self, request):
        term_id = request.query_params.get("term")
        lec_id  = request.query_params.get("lecturer")
        if not term_id or not lec_id:
            return Response({"detail": "term and lecturer are required"}, status=status.HTTP_400_BAD_REQUEST)

        off_ids = TeachingAssignment.objects.filter(lecturer_id=lec_id, active=True)\
                                            .values_list("offering_id", flat=True)

        qs = (TimetableEntry.objects
                .select_related("slot", "offering__course", "offering__cohort", "offering__level", "room")
                .filter(term_id=term_id, offering_id__in=off_ids)
                .order_by("slot__day", "slot__slot_index", "offering__cohort__label", "offering__course__code"))

        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="live_lecturer_schedule.csv"'
        w = csv.writer(resp)
        w.writerow(["day", "slot_index", "start_time", "end_time", "room_name",
                    "course_code", "course_title", "cohort_label", "level"])
        for t in qs:
            s = t.slot
            off = t.offering
            room_name = t.room.name if t.room_id else ""
            w.writerow([
                s.day, s.slot_index, s.start_time, s.end_time,
                room_name,
                off.course.code if off.course_id else "",
                off.course.title if off.course_id else "",
                off.cohort.label if off.cohort_id else "",
                off.level.name if off.level_id else "",
            ])
        return resp

# --- Schedule utilities (precheck) ---

class ScheduleViewSet(viewsets.ViewSet):
    """
    Stateless validations for a candidate placement (term+offering+slot+room).
    Used by clients and internally by TimetableEntry.reschedule().
    """
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]

    def _precheck_internal(self, vals):
        """
        Shared logic so reschedule() can reuse without an HTTP round-trip.
        vals is the validated_data of PrecheckSerializer.
        """
        term     = vals["term"]
        offering = vals["offering"]
        slot     = vals["slot"]
        room     = vals.get("room")

        violations, warnings = [], []

        # term alignment
        if slot.term_id != term.id:
            violations.append("slot.term != term")
        if offering.term_id != term.id:
            violations.append("offering.term != term")

        # break rule
        if slot.is_break:
            violations.append("slot is a break")

        # cohort clash
        base_q = TimetableEntry.objects.filter(term=term, slot=slot)
        if base_q.filter(offering__cohort_id=offering.cohort_id).exists():
            violations.append("cohort already has a class in this slot")

        # lecturer clash
        lect_ids = list(TeachingAssignment.objects.filter(offering=offering, active=True)
                        .values_list("lecturer_id", flat=True))
        if lect_ids:
            if base_q.filter(offering__assignments__active=True,
                             offering__assignments__lecturer_id__in=lect_ids).exists():
                violations.append("lecturer already teaching in this slot")

        # room clash
        if room is not None:
            if base_q.filter(room=room).exists():
                violations.append("room already in use this slot")

        # blackouts
        if lect_ids and LecturerBlackout.objects.filter(term=term, slot=slot, lecturer_id__in=lect_ids).exists():
            violations.append("lecturer blackout")
        if room is not None and RoomBlackout.objects.filter(term=term, slot=slot, room=room).exists():
            violations.append("room blackout")
        blk_q = CohortBlackout.objects.filter(term=term, slot=slot, cohort=offering.cohort)
        if blk_q.exists():
            violations.append("cohort blackout")

        # capacity
        need = getattr(offering, "capacity_need", None)
        cap  = getattr(room, "capacity", None) if room is not None else None
        if need and cap and need > cap:
            violations.append(f"room capacity ({cap}) < required ({need})")

        # global constraints
        gc = getattr(term, "global_constraints", None)
        if gc:
            day = slot.day

            # cohort daily
            cohort_day_q = TimetableEntry.objects.filter(term=term, slot__day=day)
            cohort_day_q = cohort_day_q.filter(offering__cohort_id=offering.cohort_id)
            if (gc.max_daily_slots_per_cohort or 0) and cohort_day_q.count() + 1 > gc.max_daily_slots_per_cohort:
                violations.append(f"cohort daily limit {gc.max_daily_slots_per_cohort}")

            # lecturer daily
            if lect_ids and (gc.max_daily_slots_per_lecturer or 0):
                lec_day_count = TimetableEntry.objects.filter(
                    term=term, slot__day=day,
                    offering__assignments__active=True,
                    offering__assignments__lecturer_id__in=lect_ids
                ).distinct().count()
                if lec_day_count + 1 > gc.max_daily_slots_per_lecturer:
                    violations.append(f"lecturer daily limit {gc.max_daily_slots_per_lecturer}")

            # consecutive lecturer
            if lect_ids and (gc.max_consecutive_slots_lecturer or 0):
                taken_idx = list(Slot.objects.filter(
                    id__in=TimetableEntry.objects.filter(
                        term=term, slot__day=day,
                        offering__assignments__active=True,
                        offering__assignments__lecturer_id__in=lect_ids
                    ).values_list("slot_id", flat=True)
                ).values_list("slot_index", flat=True))
                idx = slot.slot_index
                if idx not in taken_idx:
                    taken_idx.append(idx)
                taken_idx = sorted(set(taken_idx))
                longest = 0; cur = 0; prev = None
                for s in taken_idx:
                    if prev is None or s == prev + 1:
                        cur += 1
                    else:
                        longest = max(longest, cur)
                        cur = 1
                    prev = s
                longest = max(longest, cur)
                if longest > gc.max_consecutive_slots_lecturer:
                    violations.append(f"lecturer consecutive limit {gc.max_consecutive_slots_lecturer}")

        return {"ok": len(violations) == 0, "violations": violations, "warnings": warnings}

    @action(detail=False, methods=["post"], url_path="precheck")
    def precheck(self, request):
        ser = PrecheckSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = self._precheck_internal(ser.validated_data)
        return Response(result, status=status.HTTP_200_OK)

# ----- Blackouts -----

class LecturerBlackoutViewSet(viewsets.ModelViewSet):
    queryset = LecturerBlackout.objects.select_related("term", "slot", "lecturer").all()
    serializer_class = LecturerBlackoutSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params
        if q.get("term"): qs = qs.filter(term_id=q["term"])
        if q.get("slot"): qs = qs.filter(slot_id=q["slot"])
        if q.get("lecturer"): qs = qs.filter(lecturer_id=q["lecturer"])
        return qs


class RoomBlackoutViewSet(viewsets.ModelViewSet):
    queryset = RoomBlackout.objects.select_related("term", "slot", "room").all()
    serializer_class = RoomBlackoutSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params
        if q.get("term"): qs = qs.filter(term_id=q["term"])
        if q.get("slot"): qs = qs.filter(slot_id=q["slot"])
        if q.get("room"): qs = qs.filter(room_id=q["room"])
        return qs


class CohortBlackoutViewSet(viewsets.ModelViewSet):
    queryset = CohortBlackout.objects.select_related("term", "slot", "cohort").all()
    serializer_class = CohortBlackoutSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params
        if q.get("term"): qs = qs.filter(term_id=q["term"])
        if q.get("slot"): qs = qs.filter(slot_id=q["slot"])
        if q.get("cohort"): qs = qs.filter(cohort_id=q["cohort"])
        return qs


class GlobalConstraintViewSet(viewsets.ModelViewSet):
    queryset = GlobalConstraint.objects.select_related("term").all()
    serializer_class = GlobalConstraintSerializer
    permission_classes = [IsAuthenticated, IsInstitutionAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering = ["-updated_at"]

    def create(self, request, *args, **kwargs):
        term_id = request.data.get("term")
        existing = GlobalConstraint.objects.filter(term_id=term_id).first()
        if existing:
            ser = self.get_serializer(existing, data=request.data, partial=False)
            ser.is_valid(raise_exception=True)
            self.perform_update(ser)
            return Response(ser.data, status=status.HTTP_200_OK)
        return super().create(request, *args, **kwargs)
