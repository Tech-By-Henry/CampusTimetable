# institution_admin/tasks.py
from celery import shared_task
from institution_admin.services.cohort_auto_create import create_due_cohorts
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def create_auto_cohorts_task(self):
    try:
        report = create_due_cohorts()
        logger.info("create_auto_cohorts_task report: %s", report)
        return {"created": report.get("created", 0), "skipped": report.get("skipped_existing", 0)}
    except Exception as e:
        logger.exception("create_auto_cohorts_task failed: %s", e)
        raise
