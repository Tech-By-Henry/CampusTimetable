from rest_framework import serializers

class PlacementItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    day = serializers.CharField()
    slot_index = serializers.IntegerField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    room_name = serializers.CharField(allow_blank=True)


class LecturerPlacementSerializer(serializers.Serializer):
    """
    Returns one object per TeachingAssignment (scoped to the requesting lecturer).
    The `placements` list contains live TimetableEntry rows (if any) for the offering.
    """
    assignment_id = serializers.IntegerField(source="id")
    offering = serializers.IntegerField(source="offering.id", read_only=True)
    course_code = serializers.CharField(source="offering.course.code", read_only=True)
    course_title = serializers.CharField(source="offering.course.title", read_only=True)
    cohort_label = serializers.CharField(source="offering.cohort.label", read_only=True)
    role = serializers.CharField()
    position = serializers.IntegerField()
    active = serializers.BooleanField()
    placed = serializers.SerializerMethodField()
    placements = serializers.SerializerMethodField()

    def _iter_prefetched(self, obj):
        """
        Helper: prefer a to_attr name set by the view's Prefetch; fall back to normal related manager.
        """
        off = getattr(obj, "offering", None)
        if not off:
            return []
        items = getattr(off, "prefetched_placements", None)
        if items is not None:
            return items
        return list(getattr(off, "placements").all())

    def get_placements(self, obj):
        rows = []
        for t in self._iter_prefetched(obj):
            rows.append({
                "id": t.id,
                "day": t.slot.day if getattr(t, "slot", None) else "",
                "slot_index": t.slot.slot_index if getattr(t, "slot", None) else None,
                "start_time": t.slot.start_time if getattr(t, "slot", None) else None,
                "end_time": t.slot.end_time if getattr(t, "slot", None) else None,
                "room_name": t.room.name if getattr(t, "room", None) else "",
            })
        return PlacementItemSerializer(rows, many=True).data

    def get_placed(self, obj):
        return bool(self._iter_prefetched(obj))
