from django.db import models

# Create your models here.
from django.db import models

class Faculty(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=16, unique=True)  # e.g., ENG

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Department(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name="departments")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=16, unique=True)  # e.g., CSC

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Program(models.Model):
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="programs")
    name = models.CharField(max_length=150)              # e.g., BSc Computer Science
    code = models.CharField(max_length=16, unique=True)  # e.g., BSCS
    duration_years = models.PositiveSmallIntegerField(default=4)  # quick default

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Room(models.Model):
    name = models.CharField(max_length=150)              # e.g., LT1
    code = models.CharField(max_length=16, unique=True)  # e.g., LT1
    capacity = models.PositiveIntegerField(default=0)
    features = models.JSONField(default=list, blank=True)  # e.g., ["projector","lab"]

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class AcademicTerm(models.Model):
    """Minimal term so Admin can pin timetables to a session/semester."""
    name = models.CharField(max_length=150)             # e.g., 2025/2026 - First Semester
    code = models.CharField(max_length=24, unique=True) # e.g., 25-26-1
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} ({self.code})"
