import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from cv_service.models.schemas import ImageComparisonRequest
from cv_service.routes.pipeline import resolve_media_file

router = APIRouter()

@router.post("/compare/images")
def compare_images_route(req: ImageComparisonRequest):
    try:
        image_a_path = resolve_media_file(req.image_a_path, missing_status=404)
        image_b_path = resolve_media_file(req.image_b_path, missing_status=404)
    except HTTPException:
        raise

    img_a = cv2.imread(image_a_path)
    img_b = cv2.imread(image_b_path)

    if img_a is None or img_b is None:
        raise HTTPException(status_code=400, detail="Failed to decode images")

    # Resize image B to match image A dimensions if different
    if img_a.shape != img_b.shape:
        img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))

    gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY) if len(img_a.shape) == 3 else img_a
    gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY) if len(img_b.shape) == 3 else img_b

    diff = cv2.absdiff(gray_a, gray_b)
    non_zero = np.count_nonzero(diff > 30)
    total_pixels = diff.shape[0] * diff.shape[1]
    diff_percent = round(float((non_zero / total_pixels) * 100), 2)

    return {
        "status": "success",
        "difference_percentage": diff_percent,
        "changed_pixels": non_zero,
        "total_pixels": total_pixels
    }
