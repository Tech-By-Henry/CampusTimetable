# lecturers/serializers/schedule.py
from rest_framework import serializers

class LecturerEventSerializer(serializers.Serializer):
    origin = serializers.ChoiceField(choices=["live", "published"])
    day = serializers.CharField()              # e.g., "MON"
    slot_index = serializers.IntegerField()
    start_time = serializers.CharField()       # "HH:MM"
    end_time = serializers.CharField()         # "HH:MM"
    room_name = serializers.CharField(allow_blank=True, required=False)

    course_code = serializers.CharField(allow_blank=True, required=False)
    course_title = serializers.CharField(allow_blank=True, required=False)
    cohort_label = serializers.CharField(allow_blank=True, required=False)
    level_name = serializers.CharField(allow_blank=True, required=False)

    timetable_entry_id = serializers.IntegerField(required=False)
    published_entry_id = serializers.IntegerField(required=False)
