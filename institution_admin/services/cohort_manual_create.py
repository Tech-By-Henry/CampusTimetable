# institution_admin/services/cohort_manual_create.py

from django.db import transaction
from django.db import IntegrityError

from catalog.models import Program
from institution_admin.models import ProgramCohort

def build_default_label(program, start_year, session_end_year):
    dept = getattr(program, "department", None)
    dept_text = getattr(dept, "name", None) or getattr(dept, "code", None) or ""
    program_text = getattr(program, "name", None) or getattr(program, "code", None) or str(program.id)
    end_short = str(session_end_year)[-2:]
    if dept_text:
        return f"{dept_text} - {program_text} {start_year}/{end_short}"
    return f"{program_text} {start_year}/{end_short}"

@transaction.atomic
def create_manual_cohort(program_id, start_year, session_end_year=None, label=None, created_by=None, is_auto=False, auto_config=None):
    """
    Safely create a single ProgramCohort as a manual creation API. Does not touch auto-configs.
    Returns the created ProgramCohort instance.
    Raises ValueError on invalid program.
    """
    program = Program.objects.filter(id=program_id).first()
    if not program:
        raise ValueError("Unknown program")

    if session_end_year is None:
        # if program has duration use it else assume 2 years
        duration = getattr(program, "duration_years", None) or getattr(program, "duration", None) or 2
        try:
            duration = int(duration)
        except Exception:
            duration = 2
        session_end_year = start_year + max(1, duration) - 1

    if not label:
        label = build_default_label(program, start_year, session_end_year)

    # check uniqueness
    exists = ProgramCohort.objects.filter(program=program, session_start_year=start_year, session_end_year=session_end_year).exists()
    if exists:
        raise IntegrityError("Cohort for this program and session already exists")

    cohort = ProgramCohort.objects.create(
        program=program,
        label=label,
        session_start_year=start_year,
        session_end_year=session_end_year,
        is_auto=is_auto,
        auto_config=auto_config,
        created_by=created_by,
    )

    return cohort
