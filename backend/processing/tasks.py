import logging
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

from django.db import close_old_connections
from django.utils import timezone

from backend.processing.models import ProcessingJob
from backend.pipelines.services import execute_processing_job

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='visionforge-job')
_submission_slots = BoundedSemaphore(34)


def submit_processing_job(job_id):
    if not _submission_slots.acquire(blocking=False):
        ProcessingJob.objects.filter(pk=job_id, status='QUEUED').update(
            status='FAILED',
            error_message='The local processing queue is full. Try again shortly.',
            end_time=timezone.now(),
        )
        logger.warning('Rejected job %s because the local processing queue is full', job_id)
        return False
    try:
        _executor.submit(_run_and_release, job_id)
    except RuntimeError:
        _submission_slots.release()
        ProcessingJob.objects.filter(pk=job_id, status='QUEUED').update(
            status='FAILED',
            error_message='The local processing worker is unavailable. Try again shortly.',
            end_time=timezone.now(),
        )
        logger.exception('Could not submit processing job %s', job_id)
        return False
    return True


def _run_and_release(job_id):
    try:
        process_processing_job(job_id)
    except Exception:
        logger.exception('Background worker failed while handling job %s', job_id)
    finally:
        _submission_slots.release()


def process_processing_job(job_id):
    close_old_connections()
    try:
        claimed = ProcessingJob.objects.filter(pk=job_id, status='QUEUED').update(
            status='PROCESSING',
            start_time=timezone.now(),
            error_message='',
        )
        if not claimed:
            return
        job = ProcessingJob.objects.select_related(
            'pipeline', 'input_file', 'pipeline_version'
        ).get(pk=job_id)
        try:
            execute_processing_job(job)
        except Exception:
            logger.exception('Unexpected error while processing job %s', job_id)
            job.refresh_from_db()
            job.status = 'FAILED'
            job.error_message = 'An unexpected processing error occurred. Check the server logs.'
            job.end_time = timezone.now()
            job.save(update_fields=('status', 'error_message', 'end_time'))
    except ProcessingJob.DoesNotExist:
        logger.warning('Queued processing job %s no longer exists', job_id)
    except Exception:
        logger.exception('Could not start processing job %s', job_id)
    finally:
        close_old_connections()
