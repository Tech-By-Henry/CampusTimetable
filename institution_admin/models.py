# institution_admin/models.py
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from catalog.models import Program, Level, AcademicTerm, Course, Room

# ---------- Auto-create config ----------

class CohortAutoCreateConfig(models.Model):
    """
    Admin-configured schedule for automatically creating cohorts.

    Fields:
     - frequency_days: legacy days-based schedule (default 365)
     - frequency_seconds: optional higher-precision schedule (seconds)
     - next_creation_at: precise datetime when next creation should run
     - next_creation_date: legacy date field (kept for compatibility)
     - label_mode: how suffix/path should be produced (YEARLY, MONTHLY, DAILY, PRECISE, CUSTOM)
     - label_custom_template: used when label_mode == CUSTOM (supports tokens like {year},{month_num},{day},{hour},{minute},{second})
     - auto_enroll_students: if True, attempt to auto-enroll eligible students into the new cohorts.
     - active: enable/disable the config.
    """
    FREQUENCY_LEGACY_DEFAULT = 365

    LABEL_YEARLY = "YEARLY"
    LABEL_MONTHLY = "MONTHLY"
    LABEL_DAILY = "DAILY"
    LABEL_PRECISE = "PRECISE"
    LABEL_CUSTOM = "CUSTOM"

    LABEL_MODE_CHOICES = [
        (LABEL_YEARLY, "Yearly (year)"),
        (LABEL_MONTHLY, "Monthly (month-year)"),
        (LABEL_DAILY, "Daily (date-month-year)"),
        (LABEL_PRECISE, "Precise (hour-minute-date-month-year)"),
        (LABEL_CUSTOM, "Custom (use template)"),
    ]

    frequency_days = models.PositiveIntegerField(default=FREQUENCY_LEGACY_DEFAULT)
    frequency_seconds = models.PositiveIntegerField(null=True, blank=True)
    next_creation_at = models.DateTimeField(null=True, blank=True)
    next_creation_date = models.DateField(null=True, blank=True)

    label_mode = models.CharField(max_length=12, choices=LABEL_MODE_CHOICES, default=LABEL_YEARLY)
    label_custom_template = models.CharField(max_length=200, blank=True, default="", help_text="Used when label_mode=CUSTOM. Use tokens: {year},{month_num},{month_name},{day},{hour},{minute},{second},{dept},{program},{suffix}")

    auto_enroll_students = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    last_created_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-next_creation_at", "-next_creation_date"]

    def __str__(self):
        freq = f"{self.frequency_seconds}s" if self.frequency_seconds else f"{self.frequency_days}d"
        nextt = self.next_creation_at or self.next_creation_date
        return f"AutoCreate(next={nextt}, freq={freq}, mode={self.label_mode}, auto_enroll={self.auto_enroll_students})"


# ---------- Cohort & paths ----------

class ProgramCohort(models.Model):
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="cohorts")
    label = models.CharField(max_length=150)  # e.g., "ND-SE 2025/27" or with suffix
    session_start_year = models.PositiveSmallIntegerField()
    session_end_year = models.PositiveSmallIntegerField()

    # Distinguish auto-created cohorts vs manual
    is_auto = models.BooleanField(default=False, db_index=True)
    auto_config = models.ForeignKey("institution_admin.CohortAutoCreateConfig", null=True, blank=True, on_delete=models.SET_NULL)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-session_start_year", "program__name", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["program", "session_start_year", "session_end_year"],
                name="uniq_program_session"
            )
        ]

    def __str__(self):
        try:
            prog_code = self.program.code
        except Exception:
            prog_code = str(self.program_id)
        return f"{self.label} ({prog_code})"


class CohortLevel(models.Model):
    cohort = models.ForeignKey(ProgramCohort, on_delete=models.CASCADE, related_name="levels")
    level = models.ForeignKey(Level, on_delete=models.PROTECT)
    position = models.PositiveSmallIntegerField()  # 1..N
    semesters = models.PositiveSmallIntegerField(default=2)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["cohort", "position"], name="uniq_cohort_position"),
            models.UniqueConstraint(fields=["cohort", "level"], name="uniq_cohort_level"),
        ]

    def __str__(self):
        return f"{self.cohort.label}: {self.position} → {self.level.name} ({self.semesters} sems)"


# ---------- Offerings (unchanged) ----------
class CourseOffering(models.Model):
    term     = models.ForeignKey(AcademicTerm, on_delete=models.PROTECT, related_name="offerings")
    cohort   = models.ForeignKey("institution_admin.ProgramCohort", on_delete=models.CASCADE, related_name="offerings")
    level    = models.ForeignKey(Level, on_delete=models.PROTECT)
    semester = models.PositiveSmallIntegerField(default=1)
    course   = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="offerings")
    capacity_need = models.PositiveIntegerField(null=True, blank=True)
    room_features = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cohort_id", "level_id", "semester", "course_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["term", "cohort", "level", "semester", "course"],
                name="uniq_offering_term_cohort_level_sem_course",
            )
        ]

    def __str__(self):
        return f"{self.course.code} {self.cohort.label} {self.level.name} S{self.semester}"


# (rest of file continues unchanged: TeachingAssignment, TimeGrid, Slot, TimetableEntry, Blackouts, GlobalConstraint, PublishedTimetable, PublishedEntry, etc.)
# If you already have these in your file, keep them below unchanged.


# ---------- Teaching assignments (free-text roles) ----------

class TeachingAssignment(models.Model):
    offering   = models.ForeignKey("institution_admin.CourseOffering", on_delete=models.CASCADE, related_name="assignments")
    lecturer   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="teaching_assignments")
    role       = models.CharField(max_length=64)  # arbitrary admin-provided label
    position   = models.PositiveSmallIntegerField(default=1)  # ordering among same-role peers
    load_share = models.PositiveSmallIntegerField(null=True, blank=True)  # 1..100 optional
    notes      = models.CharField(max_length=300, blank=True, default="")
    active     = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["offering_id", "role", "position", "-active", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["offering", "role", "position"],
                name="uniq_role_position_per_offering",
            ),
        ]

    def __str__(self):
        return f"{self.offering} — {self.role} pos{self.position}"


# ---------- Scheduling (MVP) ----------

class DayOfWeek(models.TextChoices):
    MON = "MON", "Monday"
    TUE = "TUE", "Tuesday"
    WED = "WED", "Wednesday"
    THU = "THU", "Thursday"
    FRI = "FRI", "Friday"
    SAT = "SAT", "Saturday"
    SUN = "SUN", "Sunday"


class TimeGrid(models.Model):
    """
    One grid per term. Creating or updating this (re)materializes Slots.
    """
    term = models.OneToOneField(AcademicTerm, on_delete=models.PROTECT, related_name="timegrid")
    business_days = models.JSONField(default=list)  # e.g. ["MON","TUE","WED","THU","FRI"]
    first_slot_start = models.TimeField()          # e.g. 08:00
    slot_length_min = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(30), MaxValueValidator(180)]
    )
    slots_per_day   = models.PositiveSmallIntegerField(
        default=6, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    break_slots     = models.JSONField(default=list)  # indexes like [3]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-term_id"]

    def __str__(self):
        return f"Grid for {self.term_id}"


class Slot(models.Model):
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE, related_name="slots")
    day  = models.CharField(max_length=3, choices=DayOfWeek.choices)
    slot_index = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time   = models.TimeField()
    is_break   = models.BooleanField(default=False)

    class Meta:
        unique_together = [("term", "day", "slot_index")]
        ordering = ["day", "slot_index"]

    def __str__(self):
        return f"{self.term_id} {self.day} #{self.slot_index}"


class TimetableEntry(models.Model):
    """
    A single class meeting (time+optional room) for a CourseOffering.
    """
    term     = models.ForeignKey(AcademicTerm, on_delete=models.PROTECT, related_name="placements")
    offering = models.ForeignKey("institution_admin.CourseOffering", on_delete=models.CASCADE, related_name="placements")
    slot     = models.ForeignKey(Slot, on_delete=models.PROTECT, related_name="placements")
    room     = models.ForeignKey(Room, null=True, blank=True, on_delete=models.SET_NULL, related_name="placements")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["term_id", "slot_id", "id"]
        constraints = [
            models.UniqueConstraint(fields=["offering", "slot"], name="uniq_offering_slot"),
        ]

    def __str__(self):
        return f"{self.offering_id} -> {self.slot_id}"


# ---------- Blackouts & Global Constraints (MVP+) ----------

class LecturerBlackout(models.Model):
    term   = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE, related_name="lecturer_blackouts")
    slot   = models.ForeignKey(Slot, on_delete=models.CASCADE, related_name="lecturer_blackouts")
    lecturer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="teaching_blackouts")
    reason = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("term", "slot", "lecturer")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"LectBlk: {self.lecturer_id} @ {self.term_id}:{self.slot_id}"


class RoomBlackout(models.Model):
    term   = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE, related_name="room_blackouts")
    slot   = models.ForeignKey(Slot, on_delete=models.CASCADE, related_name="room_blackouts")
    room   = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="blackouts")
    reason = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("term", "slot", "room")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"RoomBlk: {self.room_id} @ {self.term_id}:{self.slot_id}"


class CohortBlackout(models.Model):
    term   = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE, related_name="cohort_blackouts")
    slot   = models.ForeignKey(Slot, on_delete=models.CASCADE, related_name="cohort_blackouts")
    cohort = models.ForeignKey(ProgramCohort, on_delete=models.CASCADE, related_name="blackouts")
    reason = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("term", "slot", "cohort")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"CohortBlk: {self.cohort_id} @ {self.term_id}:{self.slot_id}"


class GlobalConstraint(models.Model):
    """
    One row per term. All fields are optional; only enforced when >0.
    """
    term = models.OneToOneField(AcademicTerm, on_delete=models.CASCADE, related_name="global_constraints")

    # caps
    max_daily_slots_per_cohort      = models.PositiveSmallIntegerField(null=True, blank=True)
    max_daily_slots_per_lecturer    = models.PositiveSmallIntegerField(null=True, blank=True)
    max_consecutive_slots_lecturer  = models.PositiveSmallIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"GlobalConstraints(term={self.term_id})"


# --- PUBLISHING (MVP) ---

class PublishedTimetable(models.Model):
    """
    A versioned, read-only snapshot of timetable rows for a term.
    Exactly one snapshot per term should be marked is_current=True.
    """
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE, related_name="published_snapshots")
    version = models.PositiveSmallIntegerField(default=1)
    is_current = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["term", "version"], name="uniq_term_version_snapshot"),
        ]

    def __str__(self):
        flag = " (current)" if self.is_current else ""
        return f"Snapshot term={self.term_id} v{self.version}{flag}"


class PublishedEntry(models.Model):
    """
    Frozen entry copied from TimetableEntry at publish time, with denormalized labels
    for fast, stable reads (no joins needed for public views).
    """
    snapshot = models.ForeignKey(PublishedTimetable, on_delete=models.CASCADE, related_name="entries")

    # Keep original fks (not strictly required, but useful for admin inspection)
    offering = models.ForeignKey("institution_admin.CourseOffering", on_delete=models.SET_NULL, null=True, blank=True)
    slot     = models.ForeignKey(Slot, on_delete=models.SET_NULL, null=True, blank=True)
    room     = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)

    # Denormalized fields (frozen at publish time)
    day         = models.CharField(max_length=3, choices=DayOfWeek.choices)
    slot_index  = models.PositiveSmallIntegerField()
    start_time  = models.TimeField()
    end_time    = models.TimeField()
    room_name   = models.CharField(max_length=120, blank=True, default="")

    course_code   = models.CharField(max_length=32, blank=True, default="")
    course_title  = models.CharField(max_length=200, blank=True, default="")
    cohort_label  = models.CharField(max_length=150, blank=True, default="")
    level_name    = models.CharField(max_length=50, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["day", "slot_index", "cohort_label", "course_code"]

    def __str__(self):
        return f"PubEntry snap={self.snapshot_id} {self.day}#{self.slot_index} {self.course_code} {self.cohort_label}"
