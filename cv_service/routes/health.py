from fastapi import APIRouter
import time

router = APIRouter()

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "VisionForge FastAPI CV Engine",
        "timestamp": time.time()
    }
