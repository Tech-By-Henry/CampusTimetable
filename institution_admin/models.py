from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from catalog.models import Program, Level, AcademicTerm, Course, Room

# ---------- Cohort & paths ----------

class ProgramCohort(models.Model):
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name="cohorts")
    label = models.CharField(max_length=150)  # e.g., "ND-SE 2025/27"
    session_start_year = models.PositiveSmallIntegerField()
    session_end_year = models.PositiveSmallIntegerField()
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
        return f"{self.label} ({self.program.code})"


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


class CohortStream(models.Model):
    cohort = models.ForeignKey(ProgramCohort, on_delete=models.CASCADE, related_name="streams")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=16)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code", "name"]
        constraints = [
            models.UniqueConstraint(fields=["cohort", "code"], name="uniq_stream_code_per_cohort"),
        ]

    def __str__(self):
        return f"{self.cohort.label} – {self.code}"


# ---------- Offerings ----------

class CourseOffering(models.Model):
    term     = models.ForeignKey(AcademicTerm, on_delete=models.PROTECT, related_name="offerings")
    cohort   = models.ForeignKey("institution_admin.ProgramCohort", on_delete=models.CASCADE, related_name="offerings")
    level    = models.ForeignKey(Level, on_delete=models.PROTECT)
    semester = models.PositiveSmallIntegerField(default=1)

    course   = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="offerings")
    stream   = models.ForeignKey("institution_admin.CohortStream", null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="offerings")

    capacity_need = models.PositiveIntegerField(null=True, blank=True)
    room_features = models.CharField(max_length=200, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cohort_id", "level_id", "semester", "course_id", "stream_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["term", "cohort", "level", "semester", "course", "stream"],
                name="uniq_offering_term_cohort_level_sem_course_stream",
            )
        ]

    def __str__(self):
        sfx = f" [{self.stream.code}]" if self.stream_id else ""
        return f"{self.course.code} {self.cohort.label} {self.level.name} S{self.semester}{sfx}"


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
    # Optional: only block a specific stream; if null, blocks the whole cohort
    stream = models.ForeignKey(CohortStream, null=True, blank=True, on_delete=models.CASCADE, related_name="blackouts")
    reason = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("term", "slot", "cohort", "stream")]
        ordering = ["-created_at"]

    def __str__(self):
        sfx = f"[{self.stream_id}]" if self.stream_id else "[ALL]"
        return f"CohortBlk: {self.cohort_id}{sfx} @ {self.term_id}:{self.slot_id}"


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

from django.conf import settings
from django.db import models

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
    stream_code   = models.CharField(max_length=16, blank=True, default="")  # empty = whole cohort

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["day", "slot_index", "cohort_label", "course_code"]

    def __str__(self):
        return f"PubEntry snap={self.snapshot_id} {self.day}#{self.slot_index} {self.course_code} {self.cohort_label}"
