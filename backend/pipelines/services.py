import os
import time

import requests
from django.conf import settings
from django.core.files import File
from django.utils import timezone

from backend.processing.models import ProcessingResult


def execute_processing_job(job):
    job.status = 'PROCESSING'
    job.start_time = job.start_time or timezone.now()
    job.error_message = ''
    job.save(update_fields=('status', 'start_time', 'error_message'))
    input_path = job.input_file.file.path if job.input_file and job.input_file.file else None
    payload = {
        'job_id': job.id,
        'pipeline_id': job.pipeline_id,
        'pipeline': job.pipeline_graph or job.pipeline.graph_data,
        'input_file_path': input_path,
    }
    started = time.monotonic()
    service_url = getattr(settings, 'CV_SERVICE_URL', 'http://127.0.0.1:8001').rstrip('/')

    try:
        response = requests.post(
            f'{service_url}/pipeline/execute',
            json=payload,
            timeout=getattr(settings, 'CV_SERVICE_TIMEOUT', 600),
        )
    except requests.RequestException as exc:
        _fail_job(job, f'Could not reach the CV service: {exc}', time.monotonic() - started)
        return False

    elapsed = time.monotonic() - started
    if not response.ok:
        try:
            detail = response.json().get('detail', response.text)
        except ValueError:
            detail = response.text
        _fail_job(job, f'CV service returned HTTP {response.status_code}: {detail}', elapsed)
        return False

    try:
        data = response.json()
    except ValueError:
        _fail_job(job, 'CV service returned an invalid JSON response.', elapsed)
        return False

    if not isinstance(data, dict) or data.get('status') != 'success':
        _fail_job(job, 'CV service returned an invalid or unsuccessful result payload.', elapsed)
        return False

    result_path = data.get('result_file_path')
    if not isinstance(result_path, str) or not os.path.isfile(result_path):
        _fail_job(job, 'CV service completed without a readable result file.', elapsed)
        return False

    result = ProcessingResult.objects.create(
        job=job,
        metrics=data.get('metrics', {}),
        detected_objects=data.get('objects_detected', []),
        logs=data.get('logs', []),
    )
    try:
        with open(result_path, 'rb') as result_file:
            result.output_file.save(os.path.basename(result_path), File(result_file), save=True)
    except OSError as exc:
        result.delete()
        _fail_job(job, f'Could not store the CV result: {exc}', elapsed)
        return False

    job.status = 'COMPLETED'
    job.processing_time = round(float(data.get('processing_time', elapsed)), 3)
    job.end_time = timezone.now()
    job.progress = 100
    job.save(update_fields=('status', 'processing_time', 'end_time', 'progress'))
    return True


def _fail_job(job, message, elapsed):
    job.status = 'FAILED'
    job.error_message = str(message)
    job.end_time = timezone.now()
    job.processing_time = round(elapsed, 3)
    job.save(update_fields=('status', 'error_message', 'end_time', 'processing_time'))
