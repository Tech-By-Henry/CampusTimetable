# lecturers/models.py
from django.conf import settings
from django.db import models
from catalog.models import AcademicTerm
from institution_admin.models import Slot, TimetableEntry


class LecturerBlackoutRequest(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    lecturer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blackout_requests")
    term = models.ForeignKey(AcademicTerm, on_delete=models.PROTECT, related_name="lecturer_blackout_requests")
    slot = models.ForeignKey(Slot, on_delete=models.PROTECT, related_name="lecturer_blackout_requests")
    reason = models.CharField(max_length=300, blank=True, default="")  # short reason provided by lecturer
    lecturer_note = models.CharField(max_length=300, blank=True, default="")
    # optional: if lecturer wants to propose a reschedule for an existing TimetableEntry
    reschedule_entry = models.ForeignKey(
        TimetableEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="blackout_requests"
    )

    # admin decision fields (populated by admin)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_note = models.CharField(max_length=300, blank=True, default="")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="reviewed_blackout_requests")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lecturer", "term", "slot", "status"]),
        ]

    def __str__(self):
        return f"BlackoutRequest({self.id}) {self.lecturer_id} @ term={self.term_id} slot={self.slot_id} status={self.status}"
