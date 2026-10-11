import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure cv_service root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from cv_service.routes import health, pipeline, analyze, compare, detect

app = FastAPI(
    title="VisionForge Computer Vision & AI Microservice",
    description="High-performance FastAPI service executing Python OpenCV operations, image metrics calculation, object detection, and visual graph pipelines.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in os.environ.get("CV_CORS_ALLOWED_ORIGINS", "").split(',')
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(pipeline.router)
app.include_router(analyze.router)
app.include_router(compare.router)
app.include_router(detect.router)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("cv_service.main:app", host="127.0.0.1", port=8001, reload=True)
