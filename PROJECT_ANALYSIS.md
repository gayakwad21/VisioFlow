# VisionForge - Project Architecture & Implementation Notes

## 1. Current Architecture Overview
The active full-stack application in this repository uses:
- **Frontend**: HTML5, CSS3, and Vanilla JavaScript with a DOM/SVG node editor.
- **Application backend**: Django and Django REST Framework.
- **Database**: MySQL 8.0 only.
- **Computer vision service**: FastAPI with Python, OpenCV, NumPy, and Pillow.
- **Tests**: Django tests and FastAPI unittest/TestClient tests.

### Key Existing Components & Modules
- **`frontend/js/pipeline-builder.js`**: Vanilla JavaScript node graph editor for adding, moving, connecting, configuring, and deleting nodes.
- **`backend/`**: Django apps for accounts, projects/files, pipelines, processing jobs, reports, and analytics.
- **`cv_service/`**: FastAPI endpoints and OpenCV processors for image analysis and pipeline execution.
- **`frontend/`**: Dashboard, project workspace, file manager, pipeline editor, history, analytics, reports, and API playground.

---

## 2. Identified Gaps & Refactoring Requirements
To transition from a client-only demo to a production-grade **Full Stack Computer Vision & AI Analysis Platform**:

1. **Frontend Architecture**:
   - *Requirement*: Shift from React/ReactFlow to a high-performance, modular **Vanilla JavaScript (HTML5 + CSS3 + JS)** frontend architecture without React.
   - *Action*: Build an intuitive, zero-dependency node graph visual editor in Vanilla JS (DOM/SVG canvas), preserving all graph features (dragging, connecting inputs/outputs, parameter tweaking, deleting, zooming, preset loading).

2. **Backend Services & Persistence**:
   - *Requirement*: Full Django + Django REST Framework (DRF) backend with MySQL 8.0.
   - *Action*: Implement Django models for Users, Projects, Files, Pipelines, Nodes, Connections, Versions, Jobs, Results, Experiments, Reports, Templates, and Activity Logs.

3. **Dedicated Computer Vision Microservice**:
   - *Requirement*: FastAPI processing engine powered by Python + OpenCV.
   - *Action*: Offload heavy image/video processing, object detection, SSIM comparison, and analysis to FastAPI endpoints using OpenCV and Pydantic validation.

4. **AI & Intelligence Features**:
   - *Requirement*: AI pipeline generation from natural language prompt, pipeline node explanations, and Python code generation.
   - *Action*: Implement AI pipeline synthesis service with structured JSON output (with LLM API integration and rule-based fallback).

5. **Analytics, Reporting & History**:
   - *Requirement*: Performance metrics, processing history, side-by-side experiment comparisons, downloadable reports, and interactive API playground.

---

## 3. Reusable Assets & Preserved Functionality
- **Python OpenCV Code Generator Algorithm**: Preserve and expand `pipelineCodeGenerator.js` logic to translate full visual node graphs into clean, standard Python `cv2` scripts.
- **Workflow Presets**: Retain all 12 existing preset workflows (Edge Detection, Contour Analysis, Drone Aerial, Architecture Floor Plan) and convert them to reusable database templates.
- **OpenCV Parameter Schemas**: Reuse exact processing parameter ranges (Canny thresholds, Gaussian kernel sizes, morphological operations, color space conversions).

---

## 4. Target Architecture

```
                       +----------------------------------+
                       |      Browser (Vanilla JS)        |
                       |  HTML5 / CSS3 / ES6 Modules UI   |
                       +----------------------------------+
                                        |
                                        v  REST / JSON
                       +----------------------------------+
                       |   Django + DRF Application Hub   |
                       | - Authentication & Permissions   |
                       | - Project & Pipeline Management  |
                       | - ProcessingJob Workflow State   |
                       | - Analytics & Audit Logs         |
                       +----------------------------------+
                             |                      |
                 Django ORM  |                      | REST API
                             v                      v
                +--------------------+    +--------------------+
                |      MySQL 8.0     |    |  FastAPI CV Engine |
                |      Database      |    |  Python + OpenCV   |
                +--------------------+    +--------------------+
```

---

## 5. Incremental Implementation Phases

- **Phase 1**: Architecture & Directory Restructuring (Django backend, FastAPI service, Vanilla JS frontend).
- **Phase 2**: Django Core, MySQL Schema & Auth (Session Authentication, Projects, Models, Migrations).
- **Phase 3**: DRF API Layer (Projects, Pipelines, Files, Templates, Jobs, Reports endpoints).
- **Phase 4**: Modular Vanilla JS Frontend (Dashboard, Projects, Node Pipeline Graph Builder, Canvas UI).
- **Phase 5**: FastAPI Microservice (OpenCV image/video execution, image analysis, object detection, comparison).
- **Phase 6**: Pipeline Execution Lifecycle & Integration (Django <-> FastAPI communication, job polling).
- **Phase 7**: AI Services & Code Generator (NL to Pipeline, AI Explanation, Python Code Exporter).
- **Phase 8**: Experiments, Analytics, Reports & History (Comparison dashboard, Chart.js metrics, PDF/HTML reports).
- **Phase 9**: API Playground, Documentation & Verification (Swagger UI, DRF Playground, End-to-End Testing).
