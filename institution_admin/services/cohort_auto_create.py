# institution_admin/services/cohort_auto_create.py
from datetime import timedelta
import calendar
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

from catalog.models import Program
from institution_admin.models import CohortAutoCreateConfig, ProgramCohort

# try to import Student model conservatively
try:
    from students.models import Student
except Exception:
    Student = None

def _get_program_duration_years(program):
    """
    Infer program duration. Adjust to match your Program model if it has specific fields.
    """
    years = getattr(program, "duration_years", None) or getattr(program, "duration", None) or getattr(program, "length_years", None)
    if years is None:
        years = 2
    try:
        return max(1, int(years))
    except Exception:
        return 2

def _format_suffix_from_dt(dt, mode="YEARLY", custom_template=None):
    """
    Build suffix based on label_mode and datetime dt.
    Supported modes: YEARLY, MONTHLY, DAILY, PRECISE, CUSTOM
    CUSTOM uses custom_template with tokens: {year},{month_num},{month_name},{day},{hour},{minute},{second}
    """
    year = dt.year
    month_num = f"{dt.month:02d}"
    day = f"{dt.day:02d}"
    hour = f"{dt.hour:02d}"
    minute = f"{dt.minute:02d}"
    second = f"{dt.second:02d}"
    month_name = calendar.month_name[dt.month]

    if mode == CohortAutoCreateConfig.LABEL_YEARLY:
        return f"{year}"
    if mode == CohortAutoCreateConfig.LABEL_MONTHLY:
        return f"{month_name}-{year}"
    if mode == CohortAutoCreateConfig.LABEL_DAILY:
        return f"{day}-{month_num}-{year}"
    if mode == CohortAutoCreateConfig.LABEL_PRECISE:
        return f"{hour}-{minute}-{day}-{month_num}-{year}"
    if mode == CohortAutoCreateConfig.LABEL_CUSTOM and custom_template:
        return custom_template.format(
            year=year, month_num=month_num, month_name=month_name, day=day,
            hour=hour, minute=minute, second=second
        )
    # fallback
    return f"{year}"

def _build_cohort_label(program, dt, cfg):
    """
    Build cohort label using the config's label_mode or custom template.
    {dept} and {program} tokens are supported as well as other date tokens.
    """
    dept = getattr(program, "department", None)
    dept_text = getattr(dept, "name", None) or getattr(dept, "code", None) or ""
    program_text = getattr(program, "name", None) or getattr(program, "code", None) or str(program.id)

    mode = getattr(cfg, "label_mode", CohortAutoCreateConfig.LABEL_YEARLY)
    custom_tpl = getattr(cfg, "label_custom_template", "") or None

    suffix = _format_suffix_from_dt(dt, mode=mode, custom_template=custom_tpl)

    # default label template: "{dept} - {program} {suffix}"
    # allow admin to use custom template when label_mode == CUSTOM via label_custom_template
    tpl = "{dept} - {program} {suffix}"
    if mode == CohortAutoCreateConfig.LABEL_CUSTOM and custom_tpl:
        # custom template in label_custom_template can include {dept} and {program} and date tokens
        try:
            label = custom_tpl.format(
                dept=dept_text, program=program_text,
                year=dt.year, month_num=f"{dt.month:02d}", month_name=calendar.month_name[dt.month],
                day=f"{dt.day:02d}", hour=f"{dt.hour:02d}", minute=f"{dt.minute:02d}", second=f"{dt.second:02d}",
                suffix=suffix
            )
            return label
        except Exception:
            logger.exception("Invalid custom label template; falling back to default format.")
            # fallthrough to default

    # default fill
    label = tpl.format(dept=dept_text, program=program_text, suffix=suffix)
    return label

def _auto_enroll_unassigned_students(cohort, cfg):
    """
    Attempt to auto-enroll students into this cohort IF cfg.auto_enroll_students is True.
    Behavior (conservative):
      - Require a Student model with fields 'program' FK and 'cohort' FK (nullable).
      - Enroll only students with program == cohort.program and cohort is NULL (unassigned).
    Adjust this logic to match your student model business rules.
    """
    if not cfg.auto_enroll_students:
        return 0
    if Student is None:
        logger.warning("Student model not found; skipping auto-enroll for cohort %s", cohort.id)
        return 0

    qs = Student.objects.filter(program=cohort.program, cohort__isnull=True)
    count = 0
    for s in qs:
        s.cohort = cohort
        s.save(update_fields=["cohort"])
        count += 1
    logger.info("Auto-enrolled %d students into cohort %s", count, cohort.id)
    return count

@transaction.atomic
def create_due_cohorts(run_at=None, creator=None):
    """
    Create cohorts for configs whose next_creation_at <= now (or next_creation_date if datetime not set).
    Returns a report dict.
    """
    now = run_at or timezone.now()

    due_configs = CohortAutoCreateConfig.objects.filter(active=True).filter(
        Q(next_creation_at__lte=now) | Q(next_creation_at__isnull=True, next_creation_date__lte=now.date())
    )

    report = {"created": 0, "skipped_existing": 0, "configs": []}

    for cfg in due_configs:
        cfg_report = {"config_id": cfg.id, "created": [], "skipped": [], "enrolled": []}
        # decide start_year from next_creation_at or next_creation_date
        dt_for_suffix = cfg.next_creation_at or (timezone.make_aware(timezone.datetime.combine(cfg.next_creation_date, timezone.datetime.min.time())) if cfg.next_creation_date else now)
        start_year = dt_for_suffix.year

        programs = Program.objects.all()
        for prog in programs:
            duration = _get_program_duration_years(prog)
            session_end_year = start_year + duration - 1

            exists = ProgramCohort.objects.filter(
                program=prog,
                session_start_year=start_year,
                session_end_year=session_end_year
            ).exists()

            if exists:
                cfg_report["skipped"].append({"program_id": prog.id, "reason": "exists"})
                report["skipped_existing"] += 1
                continue

            label = _build_cohort_label(prog, dt_for_suffix, cfg)

            try:
                cohort = ProgramCohort.objects.create(
                    program=prog,
                    label=label,
                    session_start_year=start_year,
                    session_end_year=session_end_year,
                    is_auto=True,
                    auto_config=cfg,
                    created_by=creator or cfg.created_by,
                )
                cfg_report["created"].append({"program_id": prog.id, "cohort_id": cohort.id, "label": label})
                report["created"] += 1

                enrolled = _auto_enroll_unassigned_students(cohort, cfg)
                cfg_report["enrolled"].append({"cohort_id": cohort.id, "enrolled": enrolled})

            except IntegrityError:
                cfg_report["skipped"].append({"program_id": prog.id, "reason": "integrity_error"})
                report["skipped_existing"] += 1
            except Exception as e:
                logger.exception("Failed to create cohort for program %s: %s", prog.id, e)
                cfg_report.setdefault("errors", []).append({"program_id": prog.id, "error": str(e)})

        # advance next_creation timestamp
        cfg.last_created_at = timezone.now()
        if cfg.frequency_seconds:
            if cfg.next_creation_at:
                cfg.next_creation_at = cfg.next_creation_at + timedelta(seconds=cfg.frequency_seconds)
            else:
                cfg.next_creation_at = timezone.now() + timedelta(seconds=cfg.frequency_seconds)
            cfg.next_creation_date = cfg.next_creation_at.date()
        else:
            # legacy days behavior
            base_date = cfg.next_creation_date or timezone.localdate()
            cfg.next_creation_date = base_date + timedelta(days=cfg.frequency_days)
            cfg.next_creation_at = timezone.make_aware(timezone.datetime.combine(cfg.next_creation_date, timezone.datetime.min.time()))

        cfg.save(update_fields=["last_created_at", "next_creation_at", "next_creation_date", "updated_at"])
        report["configs"].append(cfg_report)

    return report
