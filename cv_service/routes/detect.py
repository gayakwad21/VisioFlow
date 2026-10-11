import os
import cv2
from fastapi import APIRouter, HTTPException
from cv_service.models.schemas import ObjectDetectionRequest
from cv_service.routes.pipeline import resolve_media_file

router = APIRouter()

@router.post("/detect/objects")
def detect_objects_route(req: ObjectDetectionRequest):
    try:
        image_path = resolve_media_file(req.image_path, missing_status=404)
    except HTTPException:
        raise

    img = cv2.imread(image_path)
    if img is None:
        raise HTTPException(status_code=400, detail="Failed to decode image")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    detected_objects = []

    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    if os.path.exists(cascade_path):
        cascade = cv2.CascadeClassifier(cascade_path)
        objects = cascade.detectMultiScale(gray, 1.1, 4)
        for (x, y, w, h) in objects:
            detected_objects.append({
                "label": "Face/Feature",
                "confidence": 0.90,
                "bbox": [int(x), int(y), int(w), int(h)]
            })

    return {
        "status": "success",
        "objects_count": len(detected_objects),
        "detected_objects": detected_objects
    }
