# VisioFlow

VisioFlow is a web application for organizing image/video projects, designing computer-vision pipelines, running OpenCV processing jobs, and reviewing results. The interface is plain HTML, CSS, and Vanilla JavaScript; Django and Django REST Framework provide the authenticated API and MySQL persistence; a separate FastAPI service executes OpenCV pipelines.

## What works

- Session-based registration, login, logout, and authenticated pages.
- Owner-scoped projects and media management, including metadata, previews, deletion, and uploads up to 100 MB.
- A visual pipeline editor with node creation, parameter editing, graph connections, templates, and Python/OpenCV code export.
- Immutable pipeline versions created for meaningful saves, selectable versions for execution, version restoration, and version snapshots on jobs.
- Asynchronous job submission and status polling (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`), including actual retry execution.
- Incremental video processing with OpenCV `VideoCapture`/`VideoWriter`: supported image operations are applied to each frame, then FFmpeg encodes browser-compatible H.264 MP4 (and AAC audio when present). Dimensions, FPS, frame count, and output size are validated and reported. Video output requires FFmpeg on PATH with `libx264`, `libopenh264`, or Windows Media Foundation H.264 encoding available.
- Image/video result previews, processing metrics, logs, history, owner-scoped reports, dashboard counts, and analytics.
- Deterministic, rule-based natural-language pipeline generation. It does not call an external language model.

Only supported, validated graph node types and parameters are executed. The Python exporter generates source text; VisionForge does not run arbitrary user-provided Python.

## Architecture

```text
Browser (HTML/CSS/Vanilla JavaScript)
        │ same-origin REST requests and protected media downloads
        ▼
Django + Django REST Framework ───────► MySQL 8.0
        │ authenticated CV request
        ▼
FastAPI + OpenCV
```

- **Django/DRF** owns authentication, projects, uploaded media, pipelines and versions, jobs, reports, and analytics.
- **MySQL 8.0** is the only supported application database.
- **FastAPI/OpenCV** processes image and video inputs. Input paths are restricted to the application media directory.
- **Vanilla JavaScript** drives the static pages served by Django in development. User media and job results are streamed through authenticated API endpoints; do not expose the media directory directly from a web server.

The local background executor uses two threads and a bounded in-process queue; it needs no Celery or Redis. If `SECRET_KEY` is omitted in debug mode, Django stores a generated development key in `~/.visionforge/development_secret_key`, outside the repository, so local sessions survive restarts. Queued work is not durable across a Django process restart. For multi-process or restart-resilient production deployments, replace it with a persistent task queue before relying on background work operationally.

## Requirements

- Python 3.10 or later
- MySQL Server 8.0
- OpenCV video codecs enabled in the installed OpenCV build for the input formats and intermediate MJPG output
- FFmpeg on PATH with `libx264`, `libopenh264`, or Windows Media Foundation H.264 encoding for browser-compatible video output

## Setup

Install dependencies from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `SECRET_KEY` in `.env` to a stable, random value. For example, generate one with:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Set the database name, user, password, host, and port in `.env`, then create the MySQL database/user with privileges for that database. The relevant settings are:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Stable Django signing/session secret; required in production |
| `DEBUG` | Django debug mode; set to `False` in production |
| `ALLOWED_HOSTS` | Comma-separated Django host names |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | MySQL 8.0 connection |
| `CV_SERVICE_URL` | FastAPI base URL; defaults to `http://127.0.0.1:8001` |
| `CV_SERVICE_TIMEOUT` | Maximum wait in seconds for a CV service request; defaults to `600` |
| `FFmpeg` | Install separately and add `ffmpeg.exe` to PATH with a supported H.264 encoder for MP4 video results; the application does not install system software |

Apply database migrations (including the additive job snapshot and default template migrations):

```powershell
python backend/manage.py migrate
```

## Run the application

Open two terminals from the repository root.

Terminal 1 — FastAPI/OpenCV:

```powershell
python -m uvicorn cv_service.main:app --host 127.0.0.1 --port 8001
```

Terminal 2 — Django, API, and development frontend:

```powershell
python backend/manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/>. Keep the FastAPI service on a trusted local interface; Django communicates with it using local file paths under `media/`.

## Tests and checks

Run from the repository root:

```powershell
python backend/manage.py check
python backend/manage.py test --verbosity 2
python -m unittest cv_service.tests.test_api -v
node --check frontend\js\api.js
node --check frontend\js\pipeline-builder.js
node --check frontend\js\dashboard.js
node --check frontend\js\projects.js
node --check frontend\js\project-detail.js
node --check frontend\js\result.js
```

The tests cover authenticated ownership, project/file validation, job queue transitions and retries, pipeline graph validation and versions, Django-to-FastAPI image processing, and streamed video frame processing.

## Repository layout

```text
backend/       Django project, REST APIs, models, migrations, and tests
cv_service/    FastAPI routes, OpenCV processors, and service tests
frontend/      HTML pages, CSS, and Vanilla JavaScript
media/         Private uploaded inputs and persisted processing outputs
requirements.txt
```
