from django.contrib.auth import get_user_model
from rest_framework import serializers

from catalog.models import AcademicTerm
from institution_admin.models import PublishedTimetable, PublishedEntry

User = get_user_model()

class PublishRequestSerializer(serializers.Serializer):
    term = serializers.PrimaryKeyRelatedField(queryset=AcademicTerm.objects.all())
    note = serializers.CharField(max_length=200, allow_blank=True, required=False)
    # If false, we create a snapshot but don't activate it (rare; default True)
    activate = serializers.BooleanField(required=False, default=True)
    # Alias accepted on input:
    label = serializers.CharField(max_length=200, allow_blank=True, required=False)

    def validate(self, attrs):
        # Map "label" -> "note" if label was provided
        label = attrs.pop("label", None)
        if label is not None and "note" not in attrs:
            attrs["note"] = label
        return super().validate(attrs)

class PublishedTimetableSerializer(serializers.ModelSerializer):
    term_label = serializers.SerializerMethodField()
    entries_count = serializers.IntegerField(read_only=True)
    # For UI parity (write still uses PublishRequestSerializer)
    label = serializers.SerializerMethodField()

    class Meta:
        model = PublishedTimetable
        fields = [
            "id", "term", "term_label", "version", "is_current",
            "note", "label", "created_by", "created_at", "entries_count",
        ]
        read_only_fields = ["version", "is_current", "created_by", "created_at", "entries_count", "label"]

    def get_term_label(self, obj):
        return getattr(obj.term, "name", f"Term {obj.term_id}")

    def get_label(self, obj):
        return obj.note

class PublishedEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = PublishedEntry
        fields = [
            "id", "snapshot",
            "offering", "slot", "room",
            "day", "slot_index", "start_time", "end_time", "room_name",
            "course_code", "course_title",
            "cohort_label", "level_name",
            "created_at",
        ]
        read_only_fields = fields
