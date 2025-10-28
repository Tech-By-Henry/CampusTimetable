from django.db.models import Q
from rest_framework import serializers
from catalog.models import AcademicTerm, Room
from institution_admin.models import (
    TimeGrid, Slot, TimetableEntry, DayOfWeek,
    CourseOffering, TeachingAssignment,
    LecturerBlackout, RoomBlackout, CohortBlackout, GlobalConstraint
)

# ---------- TimeGrid & Slots ----------

class TimeGridSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeGrid
        fields = [
            "id", "term", "business_days", "first_slot_start",
            "slot_length_min", "slots_per_day", "break_slots",
            "created_at", "updated_at"
        ]

    def validate_business_days(self, days):
        allowed = {d.value for d in DayOfWeek}
        bad = [d for d in (days or []) if d not in allowed]
        if bad:
            raise serializers.ValidationError(f"invalid day codes: {bad}")
        return days


class SlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slot
        fields = ["id", "term", "day", "slot_index", "start_time", "end_time", "is_break"]


# ---------- Blackouts & Constraints ----------

class LecturerBlackoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = LecturerBlackout
        fields = ["id", "term", "slot", "lecturer", "reason", "created_at"]


class RoomBlackoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomBlackout
        fields = ["id", "term", "slot", "room", "reason", "created_at"]


class CohortBlackoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = CohortBlackout
        fields = ["id", "term", "slot", "cohort", "stream", "reason", "created_at"]


class GlobalConstraintSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalConstraint
        fields = [
            "id", "term",
            "max_daily_slots_per_cohort",
            "max_daily_slots_per_lecturer",
            "max_consecutive_slots_lecturer",
            "created_at", "updated_at"
        ]


# ---------- Timetable (placements) ----------

class PlacementSerializer(serializers.ModelSerializer):
    course_code  = serializers.CharField(source="offering.course.code", read_only=True)
    course_title = serializers.CharField(source="offering.course.title", read_only=True)
    cohort_label = serializers.CharField(source="offering.cohort.label", read_only=True)
    level_name   = serializers.CharField(source="offering.level.name", read_only=True)

    class Meta:
        model = TimetableEntry
        fields = [
            "id", "term", "offering", "slot", "room",
            "course_code", "course_title", "cohort_label", "level_name",
            "created_at"
        ]

    def validate(self, attrs):
        inst     = self.instance
        term     = attrs.get("term")     or (inst and inst.term)
        slot     = attrs.get("slot")     or (inst and inst.slot)
        offering = attrs.get("offering") or (inst and inst.offering)
        room     = attrs.get("room")     if "room" in attrs else (inst and inst.room)

        if slot.term_id != term.id:
            raise serializers.ValidationError("slot.term and term must match.")
        if offering.term_id != term.id:
            raise serializers.ValidationError("offering.term and term must match.")
        if slot.is_break:
            raise serializers.ValidationError("Cannot place a class on a break slot.")

        # ----- STREAM-AWARE COHORT CLASH -----
        base_q = TimetableEntry.objects.filter(term=term, slot=slot).exclude(id=getattr(inst, "id", None))
        if offering.stream_id:
            cohort_conflict = base_q.filter(
                Q(offering__cohort_id=offering.cohort_id) &
                (Q(offering__stream__isnull=True) | Q(offering__stream_id=offering.stream_id))
            ).exists()
        else:
            cohort_conflict = base_q.filter(offering__cohort_id=offering.cohort_id).exists()
        if cohort_conflict:
            raise serializers.ValidationError("Cohort/stream already has a class in this slot.")

        # ----- LECTURER CLASH -----
        lect_ids = list(TeachingAssignment.objects.filter(offering=offering, active=True)
                        .values_list("lecturer_id", flat=True))
        if lect_ids:
            lecturer_busy = base_q.filter(offering__assignments__active=True,
                                          offering__assignments__lecturer_id__in=lect_ids).exists()
            if lecturer_busy:
                raise serializers.ValidationError("A lecturer on this offering is already teaching in this slot.")

        # ----- ROOM (HALL) CLASH -----
        if room is not None:
            room_busy = base_q.filter(room=room).exists()
            if room_busy:
                raise serializers.ValidationError("Room already in use for this slot.")

        # ----- BLACKOUTS -----
        if lect_ids and LecturerBlackout.objects.filter(term=term, slot=slot, lecturer_id__in=lect_ids).exists():
            raise serializers.ValidationError("Lecturer blackout prevents this slot.")
        if room is not None and RoomBlackout.objects.filter(term=term, slot=slot, room=room).exists():
            raise serializers.ValidationError("Room blackout prevents this slot.")
        blk_q = CohortBlackout.objects.filter(term=term, slot=slot, cohort=offering.cohort)
        if offering.stream_id:
            blk_q = blk_q.filter(Q(stream__isnull=True) | Q(stream_id=offering.stream_id))
        if blk_q.exists():
            raise serializers.ValidationError("Cohort blackout prevents this slot.")

        # ----- CAPACITY (optional) -----
        need = getattr(offering, "capacity_need", None)
        cap  = getattr(room, "capacity", None) if room is not None else None
        if need and cap and need > cap:
            raise serializers.ValidationError(f"Room capacity ({cap}) < required ({need}).")

        # ----- GLOBAL CONSTRAINTS -----
        gc = getattr(term, "global_constraints", None)
        if gc:
            day = slot.day

            # Max daily per cohort
            cohort_day_q = TimetableEntry.objects.filter(term=term, slot__day=day) \
                               .exclude(id=getattr(inst, "id", None))
            if offering.stream_id:
                cohort_day_q = cohort_day_q.filter(
                    offering__cohort_id=offering.cohort_id
                ).filter(
                    Q(offering__stream__isnull=True) | Q(offering__stream_id=offering.stream_id)
                )
            else:
                cohort_day_q = cohort_day_q.filter(offering__cohort_id=offering.cohort_id)
            limit = gc.max_daily_slots_per_cohort or 0
            if limit and cohort_day_q.count() + 1 > limit:
                raise serializers.ValidationError(f"Max daily load for cohort would exceed {limit} slots.")

            # Max daily per lecturer
            if lect_ids and (gc.max_daily_slots_per_lecturer or 0):
                lec_day_count = TimetableEntry.objects.filter(
                    term=term, slot__day=day,
                    offering__assignments__active=True,
                    offering__assignments__lecturer_id__in=lect_ids
                ).exclude(id=getattr(inst, "id", None)).distinct().count()
                if lec_day_count + 1 > gc.max_daily_slots_per_lecturer:
                    raise serializers.ValidationError(
                        f"Max daily load for lecturer would exceed {gc.max_daily_slots_per_lecturer} slots."
                    )

            # Max consecutive slots per lecturer
            if lect_ids and (gc.max_consecutive_slots_lecturer or 0):
                # collect occupied slot indexes that day, include candidate
                existing_idx = list(Slot.objects.filter(
                    id__in=TimetableEntry.objects.filter(
                        term=term, slot__day=day,
                        offering__assignments__active=True,
                        offering__assignments__lecturer_id__in=lect_ids
                    ).exclude(id=getattr(inst, "id", None)).values_list("slot_id", flat=True)
                ).values_list("slot_index", flat=True))
                idx = slot.slot_index
                if idx not in existing_idx:
                    existing_idx.append(idx)
                existing_idx = sorted(set(existing_idx))
                # longest consecutive run
                longest = 0; cur = 0; prev = None
                for s in existing_idx:
                    if prev is None or s == prev + 1:
                        cur += 1
                    else:
                        longest = max(longest, cur)
                        cur = 1
                    prev = s
                longest = max(longest, cur)
                if longest > gc.max_consecutive_slots_lecturer:
                    raise serializers.ValidationError(
                        f"Max consecutive slots for lecturer would exceed {gc.max_consecutive_slots_lecturer}."
                    )

        return attrs


# ---------- Precheck ----------

class PrecheckSerializer(serializers.Serializer):
    term     = serializers.PrimaryKeyRelatedField(queryset=AcademicTerm.objects.all())
    offering = serializers.PrimaryKeyRelatedField(queryset=CourseOffering.objects.all())
    slot     = serializers.PrimaryKeyRelatedField(queryset=Slot.objects.all())
    room     = serializers.PrimaryKeyRelatedField(queryset=Room.objects.all(), required=False, allow_null=True)
