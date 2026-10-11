from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class NodeConfig(BaseModel):
    id: str
    type: str
    position: Optional[Dict[str, float]] = None
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ConnectionConfig(BaseModel):
    id: Optional[str] = None
    source: str
    target: str

class PipelineGraph(BaseModel):
    nodes: List[NodeConfig]
    edges: List[ConnectionConfig]

class PipelineExecutionRequest(BaseModel):
    job_id: int
    pipeline_id: int
    pipeline: PipelineGraph
    input_file_path: Optional[str] = None

class ImageAnalysisRequest(BaseModel):
    image_path: str

class ImageComparisonRequest(BaseModel):
    image_a_path: str
    image_b_path: str

class ObjectDetectionRequest(BaseModel):
    image_path: str
    confidence_threshold: float = 0.5
