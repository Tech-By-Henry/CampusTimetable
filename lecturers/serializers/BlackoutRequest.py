# lecturers/serializers/BlackoutRequest.py
from rest_framework import serializers
from django.db.models import Q
from onboarding.models import IntakeSubmission, IntakeLink
from catalog.models import AcademicTerm
from institution_admin.models import Slot, TimetableEntry, TeachingAssignment
from django.contrib.auth import get_user_model

from ..models import LecturerBlackoutRequest

User = get_user_model()


class LecturerBlackoutRequestSerializer(serializers.ModelSerializer):
    lecturer_name = serializers.SerializerMethodField(read_only=True)
    lecturer_email = serializers.EmailField(source="lecturer.email", read_only=True)
    has_conflict = serializers.SerializerMethodField(read_only=True)  # true if lecturer has live class in that slot

    class Meta:
        model = LecturerBlackoutRequest
        fields = [
            "id", "lecturer", "lecturer_name", "lecturer_email",
            "term", "slot", "reason", "lecturer_note",
            "reschedule_entry",
            "status", "admin_note", "reviewed_by",
            "has_conflict",
            "created_at", "updated_at",
        ]
        read_only_fields = ["status", "admin_note", "reviewed_by", "created_at", "updated_at", "lecturer", "lecturer_email", "lecturer_name", "has_conflict"]

    def get_lecturer_name(self, obj):
        u = obj.lecturer
        return f"{u.first_name} {u.last_name}".strip() or u.get_username()

    def get_has_conflict(self, obj):
        # determine if lecturer has a live timetable entry at (term, slot)
        # A "live class" is a TimetableEntry where the offering has an active assignment for this lecturer.
        if not obj or not obj.lecturer_id:
            return False
        return TimetableEntry.objects.filter(
            term_id=obj.term_id,
            slot_id=obj.slot_id,
            offering__assignments__active=True,
            offering__assignments__lecturer_id=obj.lecturer_id
        ).exists()

    def validate(self, data):
        """
        Basic sanity:
          - slot.term must match term
          - reschedule_entry (if provided) must be an entry in the same term (and belongs to the lecturer)
        """
        term = data.get("term")
        slot = data.get("slot")
        reschedule_entry = data.get("reschedule_entry", None)

        # Ensure slot/term alignment
        if slot and term and slot.term_id != term.id:
            raise serializers.ValidationError("slot.term and term must match.")

        # If reschedule_entry provided, ensure it's in the same term and is indeed a TimetableEntry
        if reschedule_entry:
            if reschedule_entry.term_id != term.id:
                raise serializers.ValidationError("reschedule_entry.term and term must match.")
            # ensure the lecturer is assigned to that entry (active assignment)
            lect_ids = list(TeachingAssignment.objects.filter(
                offering_id=reschedule_entry.offering_id, active=True
            ).values_list("lecturer_id", flat=True))
            req_lecturer_id = getattr(self.context["request"].user, "id", None)
            if req_lecturer_id not in lect_ids:
                raise serializers.ValidationError("reschedule_entry is not a class taught by this lecturer (or not assigned).")

        return data

    def create(self, validated_data):
        # lecturer will be set in viewset (we still guard if not present)
        request = self.context.get("request")
        if request and not validated_data.get("lecturer"):
            validated_data["lecturer"] = request.user
        return super().create(validated_data)
