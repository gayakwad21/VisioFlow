import cv2
from fastapi import APIRouter, HTTPException
from cv_service.models.schemas import ImageAnalysisRequest
from cv_service.processors.image_processor import calculate_image_metrics
from cv_service.routes.pipeline import resolve_media_file

router = APIRouter()

@router.post("/analyze/image")
def analyze_image_route(req: ImageAnalysisRequest):
    try:
        image_path = resolve_media_file(req.image_path, missing_status=404)
    except HTTPException:
        raise

    img = cv2.imread(image_path)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid or corrupt image file")

    metrics = calculate_image_metrics(img)
    return {
        "status": "success",
        "image_path": image_path,
        "metrics": metrics
    }
