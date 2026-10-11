import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from cv_service.models.schemas import PipelineExecutionRequest
from cv_service.processors.image_processor import execute_cv_pipeline

router = APIRouter()
logger = logging.getLogger(__name__)
MEDIA_ROOT = (Path(__file__).resolve().parents[2] / 'media').resolve()


def _resolve_media_path(path, *, require_file=False, missing_status=400):
    if not path:
        raise HTTPException(status_code=400, detail='A media path is required.')
    try:
        resolved = Path(path).expanduser().resolve(strict=False)
        if os.path.commonpath((str(MEDIA_ROOT), str(resolved))) != str(MEDIA_ROOT):
            raise HTTPException(status_code=400, detail='Input media must be inside the configured media directory.')
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail='The media path is not a readable file or directory.') from exc
    if require_file:
        if not resolved.exists():
            raise HTTPException(status_code=missing_status, detail='The input media path is not a readable file.')
        if not resolved.is_file():
            raise HTTPException(status_code=missing_status, detail='The input media path is not a readable file.')
    return str(resolved)


def resolve_media_file(path, *, missing_status=400):
    return _resolve_media_path(path, require_file=True, missing_status=missing_status)


def _resolve_input_path(input_file_path):
    return resolve_media_file(input_file_path)

@router.post("/pipeline/execute")
def execute_pipeline_route(req: PipelineExecutionRequest):
    try:
        input_path = _resolve_input_path(req.input_file_path)
        result = execute_cv_pipeline(
            pipeline_graph=req.pipeline,
            input_file_path=input_path
        )
        return result
    except HTTPException:
        raise
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception('Unexpected pipeline execution failure')
        raise HTTPException(status_code=500, detail='The CV service could not complete this pipeline.') from exc
