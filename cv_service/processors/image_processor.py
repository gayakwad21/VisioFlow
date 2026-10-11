import logging
import math
import os
import shutil
import subprocess
import time
import uuid
from types import SimpleNamespace
import cv2
import numpy as np

SUPPORTED_NODE_TYPES = {
    'imageSource', 'output', 'grayscale', 'blur', 'gaussianBlur', 'medianBlur',
    'canny', 'threshold', 'adaptiveThreshold', 'morphological', 'rotate',
    'resize', 'crop', 'brightness', 'sharpen', 'findContours', 'histogram',
    'imageStatistics', 'objectDetection',
}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
logger = logging.getLogger(__name__)


def _ordered_nodes(pipeline_graph):
    if isinstance(pipeline_graph, dict):
        nodes = [
            SimpleNamespace(id=node['id'], type=node.get('type'), data=node.get('data') or {})
            for node in pipeline_graph.get('nodes', [])
        ]
        edges = [
            SimpleNamespace(source=edge['source'], target=edge['target'])
            for edge in pipeline_graph.get('edges', [])
        ]
    else:
        nodes = list(pipeline_graph.nodes)
        edges = list(pipeline_graph.edges)
    if not edges:
        return nodes

    node_ids = {node.id for node in nodes}
    order_index = {node.id: index for index, node in enumerate(nodes)}
    incoming = {node.id: 0 for node in nodes}
    outgoing = {node.id: [] for node in nodes}
    for edge in edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            raise ValueError("Pipeline connection references a node that does not exist.")
        outgoing[edge.source].append(edge.target)
        incoming[edge.target] += 1

    ready = sorted((node_id for node_id, count in incoming.items() if count == 0),
                   key=order_index.get)
    result = []
    while ready:
        node_id = ready.pop(0)
        result.append(node_id)
        for target in outgoing[node_id]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort(key=order_index.get)

    if len(result) != len(nodes):
        raise ValueError("Pipeline connections contain a cycle.")
    by_id = {node.id: node for node in nodes}
    return [by_id[node_id] for node_id in result]


def validate_pipeline_graph(pipeline_graph):
    if not isinstance(pipeline_graph, dict):
        raise ValueError('Pipeline graph must be an object.')
    nodes = pipeline_graph.get('nodes')
    edges = pipeline_graph.get('edges')
    if not isinstance(nodes, list) or not nodes:
        raise ValueError('Pipeline must contain at least one node.')
    if not isinstance(edges, list):
        raise ValueError('Pipeline edges must be a list.')

    ids = []
    node_types = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get('id'), str) or not node['id'].strip():
            raise ValueError('Every pipeline node must have a non-empty string ID.')
        if node['id'] in node_types:
            raise ValueError(f"Pipeline contains duplicate node ID '{node['id']}'.")
        node_type = node.get('type')
        if node_type not in SUPPORTED_NODE_TYPES:
            raise ValueError(f"Unsupported pipeline operation '{node_type}'.")
        data = node.get('data', {})
        if not isinstance(data, dict):
            raise ValueError(f"Parameters for node '{node['id']}' must be an object.")
        _validate_node_parameters(node_type, data, node['id'])
        ids.append(node['id'])
        node_types[node['id']] = node_type

    sources = [node_id for node_id, kind in node_types.items() if kind == 'imageSource']
    outputs = [node_id for node_id, kind in node_types.items() if kind == 'output']
    if len(sources) != 1 or len(outputs) != 1:
        raise ValueError('Pipeline must have exactly one Image Source and one Output node.')

    known_ids = set(ids)
    outgoing = {node_id: [] for node_id in ids}
    incoming = {node_id: 0 for node_id in ids}
    seen_edges = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError('Every pipeline connection must be an object.')
        source, target = edge.get('source'), edge.get('target')
        if source not in known_ids or target not in known_ids:
            raise ValueError('Pipeline connection references a node that does not exist.')
        if source == target or (source, target) in seen_edges:
            raise ValueError('Pipeline contains a self-connection or duplicate connection.')
        seen_edges.add((source, target))
        outgoing[source].append(target)
        incoming[target] += 1
    if len(nodes) > 1 and not edges:
        raise ValueError('Pipeline nodes must be connected from Image Source to Output.')
    if incoming[sources[0]] or outgoing[outputs[0]]:
        raise ValueError('Image Source cannot have inputs and Output cannot have outgoing connections.')

    reachable = set()
    stack = [sources[0]]
    while stack:
        node_id = stack.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        stack.extend(outgoing[node_id])
    if outputs[0] not in reachable or reachable != known_ids:
        raise ValueError('Every pipeline node must be connected from Image Source to Output.')
    _ordered_nodes(
        type('Graph', (), {
            'nodes': [type('Node', (), {'id': node_id})() for node_id in ids],
            'edges': [type('Edge', (), {'source': source, 'target': target})()
                      for source, target in seen_edges],
        })()
    )


def _validate_node_parameters(node_type, data, node_id):
    limits = {
        'blur': {'strength': (1, 63), 'kernelSize': (1, 63)},
        'gaussianBlur': {'kernelSize': (1, 63), 'sigma': (0, 100)},
        'medianBlur': {'kernelSize': (3, 63)},
        'canny': {'threshold1': (0, 255), 'threshold2': (0, 255)},
        'threshold': {'threshold': (0, 255)},
        'adaptiveThreshold': {'blockSize': (3, 99), 'constant': (-255, 255)},
        'morphological': {'iterations': (1, 20), 'kernelSize': (1, 31)},
        'resize': {'width': (1, 8192), 'height': (1, 8192)},
        'crop': {'x': (0, 8192), 'y': (0, 8192), 'width': (1, 8192), 'height': (1, 8192)},
        'brightness': {'contrast': (0, 5), 'brightness': (-255, 255)},
        'sharpen': {'amount': (0, 5)},
        'objectDetection': {'confidence': (0, 1)},
        'rotate': {'angle': (-360, 360)},
    }
    for field, (minimum, maximum) in limits.get(node_type, {}).items():
        if field not in data:
            continue
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(
                f"Parameter '{field}' on node '{node_id}' must be between {minimum} and {maximum}."
            )
        if field in ('strength', 'kernelSize', 'threshold1', 'threshold2', 'threshold',
                     'blockSize', 'iterations', 'width', 'height', 'x', 'y', 'angle'):
            if not isinstance(value, int):
                raise ValueError(f"Parameter '{field}' on node '{node_id}' must be an integer.")
    for field in ('strength', 'kernelSize', 'blockSize'):
        if field in data and data[field] % 2 == 0:
            raise ValueError(f"Parameter '{field}' on node '{node_id}' must be odd.")
    if node_type == 'blur' and data.get('blurType', 'gaussian') not in ('gaussian', 'median', 'box'):
        raise ValueError(f"Node '{node_id}' has an unsupported blur type.")
    if node_type == 'morphological' and data.get('operation', 'erode') not in ('erode', 'dilate', 'open', 'close'):
        raise ValueError(f"Node '{node_id}' has an unsupported morphology operation.")
    if node_type == 'threshold' and data.get('mode', 'binary') not in ('binary', 'adaptive', 'otsu'):
        raise ValueError(f"Node '{node_id}' has an unsupported threshold mode.")
    if node_type == 'adaptiveThreshold' and data.get('mode', 'adaptive') != 'adaptive':
        raise ValueError(f"Node '{node_id}' has an unsupported adaptive threshold mode.")
    if node_type == 'findContours' and 'fill' in data and not isinstance(data['fill'], bool):
        raise ValueError(f"Parameter 'fill' on node '{node_id}' must be a boolean.")


def execute_cv_pipeline(
    pipeline_graph, input_file_path=None, output_dir=None, _input_frame=None, _write_output=True
):
    validate_pipeline_graph(pipeline_graph.model_dump() if hasattr(pipeline_graph, 'model_dump') else pipeline_graph)
    logs = []
    start_time = time.time()
    logs.append(f"[{time.strftime('%H:%M:%S')}] Execution started.")

    if _input_frame is not None:
        img = _input_frame
    else:
        if not input_file_path:
            raise ValueError('An input image or video is required.')
        if not os.path.isfile(input_file_path):
            raise ValueError('The input media file does not exist or is not readable.')
        if os.path.splitext(input_file_path)[1].lower() in VIDEO_EXTENSIONS:
            return _execute_video_pipeline(pipeline_graph, input_file_path, output_dir, start_time)
        img = cv2.imread(input_file_path)
        if img is None:
            raise ValueError(f"Could not decode the input image file '{os.path.basename(input_file_path)}'.")

    logs.append(f"[{time.strftime('%H:%M:%S')}] Image loaded successfully ({img.shape[1]}x{img.shape[0]} px).")

    current = img.copy()
    nodes = _ordered_nodes(pipeline_graph)
    detected_objects = []

    for idx, node in enumerate(nodes):
        ntype = node.type
        data = node.data or {}
        nid = node.id

        if ntype == 'imageSource':
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (ImageSource) initialized.")

        elif ntype in ('output',):
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Output) completed.")

        elif ntype == 'grayscale':
            if len(current.shape) == 3:
                current = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Grayscale) completed.")

        elif ntype == 'blur':
            ksize = max(1, min(63, int(data.get('strength', data.get('kernelSize', 5)))))
            btype = data.get('blurType', 'gaussian')
            if ksize % 2 == 0:
                ksize += 1
            if btype == 'median':
                ksize = max(3, ksize)
            if btype == 'gaussian':
                current = cv2.GaussianBlur(current, (ksize, ksize), 0)
            elif btype == 'median':
                if len(current.shape) == 2 or current.shape[2] in [1, 3, 4]:
                    current = cv2.medianBlur(current, ksize)
            else:
                current = cv2.blur(current, (ksize, ksize))
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Blur - {btype}, kernel={ksize}) completed.")

        elif ntype == 'gaussianBlur':
            ksize = max(1, min(63, int(data.get('kernelSize', 5))))
            if ksize % 2 == 0:
                ksize += 1
            current = cv2.GaussianBlur(current, (ksize, ksize), float(data.get('sigma', 0)))
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Gaussian Blur - kernel={ksize}) completed.")

        elif ntype == 'medianBlur':
            ksize = max(3, min(63, int(data.get('kernelSize', 5))))
            if ksize % 2 == 0:
                ksize += 1
            current = cv2.medianBlur(current, ksize)
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Median Blur - kernel={ksize}) completed.")

        elif ntype == 'canny':
            t1 = int(data.get('threshold1', 75))
            t2 = int(data.get('threshold2', 200))
            gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY) if len(current.shape) == 3 else current
            current = cv2.Canny(gray, t1, t2)
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Canny Edge Detection {t1}/{t2}) completed.")

        elif ntype in ('threshold', 'adaptiveThreshold'):
            thresh_val = int(data.get('threshold', 127))
            mode = data.get('mode', 'adaptive' if ntype == 'adaptiveThreshold' else 'binary')
            gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY) if len(current.shape) == 3 else current
            if mode == 'adaptive':
                block_size = max(3, min(99, int(data.get('blockSize', 11))))
                if block_size % 2 == 0:
                    block_size += 1
                current = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
                    block_size, float(data.get('constant', 2))
                )
            elif mode == 'otsu':
                _, current = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            else:
                _, current = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Threshold - {mode}) completed.")

        elif ntype == 'morphological':
            op_name = str(data.get('operation', 'erode')).lower()
            iters = max(1, min(20, int(data.get('iterations', 1))))
            size = max(1, min(31, int(data.get('kernelSize', 3))))
            kernel = np.ones((size, size), np.uint8)
            op_map = {
                'erode': cv2.MORPH_ERODE,
                'dilate': cv2.MORPH_DILATE,
                'open': cv2.MORPH_OPEN,
                'close': cv2.MORPH_CLOSE
            }
            cv_op = op_map.get(op_name, cv2.MORPH_ERODE)
            current = cv2.morphologyEx(current, cv_op, kernel, iterations=iters)
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Morphological - {op_name}) completed.")

        elif ntype == 'rotate':
            angle = int(data.get('angle', 90)) % 360
            if angle == 90:
                current = cv2.rotate(current, cv2.ROTATE_90_CLOCKWISE)
            elif angle == 180:
                current = cv2.rotate(current, cv2.ROTATE_180)
            elif angle == 270:
                current = cv2.rotate(current, cv2.ROTATE_90_COUNTERCLOCKWISE)
            elif angle:
                height, width = current.shape[:2]
                matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
                current = cv2.warpAffine(current, matrix, (width, height))
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Rotate - {angle} deg) completed.")

        elif ntype == 'resize':
            width = max(1, min(8192, int(data.get('width', 640))))
            height = max(1, min(8192, int(data.get('height', 480))))
            current = cv2.resize(current, (width, height), interpolation=cv2.INTER_AREA)
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Resize - {width}x{height}) completed.")

        elif ntype == 'crop':
            image_height, image_width = current.shape[:2]
            x = int(data.get('x', 0))
            y = int(data.get('y', 0))
            width = int(data.get('width', image_width - x))
            height = int(data.get('height', image_height - y))
            if x + width > image_width or y + height > image_height:
                raise ValueError(f"Crop node '{nid}' exceeds the current frame dimensions.")
            current = current[y:y + height, x:x + width].copy()
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Crop) completed.")

        elif ntype == 'brightness':
            alpha = max(0.0, min(5.0, float(data.get('contrast', 1.2))))
            beta = max(-255, min(255, int(data.get('brightness', 20))))
            current = cv2.convertScaleAbs(current, alpha=alpha, beta=beta)
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Brightness/Contrast) completed.")

        elif ntype == 'sharpen':
            amount = max(0.0, min(5.0, float(data.get('amount', 1.0))))
            blurred = cv2.GaussianBlur(current, (0, 0), 3)
            current = cv2.addWeighted(current, 1.0 + amount, blurred, -amount, 0)
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Sharpen) completed.")

        elif ntype == 'findContours':
            fill = bool(data.get('fill', False))
            gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY) if len(current.shape) == 3 else current
            contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) if len(gray.shape) == 2 else gray.copy()
            thickness = -1 if fill else 2
            cv2.drawContours(vis, contours, -1, (0, 255, 0), thickness)
            current = vis
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Find Contours - found {len(contours)}) completed.")

        elif ntype in ('histogram', 'imageStatistics'):
            gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY) if len(current.shape) == 3 else current
            if ntype == 'histogram':
                histogram = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
                detected_objects.append({
                    'type': 'histogram',
                    'bins': [int(value) for value in histogram.tolist()]
                })
            else:
                detected_objects.append({
                    'type': 'image_statistics',
                    'mean': round(float(np.mean(gray)), 3),
                    'stddev': round(float(np.std(gray)), 3),
                    'min': int(np.min(gray)),
                    'max': int(np.max(gray)),
                })
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' ({ntype}) completed.")

        elif ntype == 'objectDetection':
            # Haar Cascade / OpenCV built-in object detection
            gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY) if len(current.shape) == 3 else current
            vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) if len(gray.shape) == 2 else current.copy()

            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            if os.path.exists(cascade_path):
                face_cascade = cv2.CascadeClassifier(cascade_path)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                for (x, y, w, h) in faces:
                    cv2.rectangle(vis, (x, y), (x+w, y+h), (255, 0, 0), 2)
                    cv2.putText(vis, "Object", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                    detected_objects.append({'label': 'Object/Face', 'confidence': 0.88, 'bbox': [int(x), int(y), int(w), int(h)]})

            current = vis
            logs.append(f"[{time.strftime('%H:%M:%S')}] Node '{nid}' (Object Detection - detected {len(detected_objects)}) completed.")

    # Output file handling
    if not _write_output:
        return {'processed_frame': current, 'objects_detected': detected_objects}

    if not output_dir:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'media', 'results')
    os.makedirs(output_dir, exist_ok=True)
    
    result_filename = f"result_{uuid.uuid4().hex}.png"
    result_file_path = os.path.join(output_dir, result_filename)
    if not cv2.imwrite(result_file_path, current):
        raise OSError("Could not write the processed image.")

    # Compute metrics
    metrics = calculate_image_metrics(current)
    elapsed_time = round(time.time() - start_time, 3)
    logs.append(f"[{time.strftime('%H:%M:%S')}] Pipeline execution finished in {elapsed_time}s.")

    return {
        "status": "success",
        "processing_time": elapsed_time,
        "result_file_path": result_file_path,
        "objects_detected": detected_objects,
        "metrics": metrics,
        "logs": logs
    }


def _execute_video_pipeline(pipeline_graph, input_file_path, output_dir, start_time):
    output_dir = output_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'media', 'results'
    )
    os.makedirs(output_dir, exist_ok=True)

    capture = cv2.VideoCapture(input_file_path)
    if not capture.isOpened():
        capture.release()
        raise ValueError('Could not open the input video; it may be corrupt or use an unsupported codec.')
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if width <= 0 or height <= 0:
        capture.release()
        raise ValueError('The input video does not report valid frame dimensions.')
    if not math.isfinite(fps) or fps <= 0 or fps > 240:
        fps = 25.0
        fps_was_defaulted = True
    else:
        fps_was_defaulted = False
    if width % 2 or height % 2:
        capture.release()
        raise ValueError('H.264 MP4 output requires even frame width and height; the input dimensions cannot be preserved.')

    result_path = os.path.join(output_dir, f'result_{uuid.uuid4().hex}.mp4')
    intermediate_path = os.path.join(output_dir, f'intermediate_{uuid.uuid4().hex}.avi')
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        capture.release()
        raise ValueError(
            'FFmpeg is required to create browser-compatible H.264 MP4 video. '
            'Install FFmpeg with an H.264 encoder such as libx264, add ffmpeg.exe to PATH, '
            'and restart the CV service.'
        )

    try:
        encoder = _available_h264_encoder(ffmpeg_path)
    except Exception:
        capture.release()
        raise
    try:
        writer = cv2.VideoWriter(
            intermediate_path, cv2.VideoWriter_fourcc(*'MJPG'), fps, (width, height)
        )
    except cv2.error as exc:
        capture.release()
        raise ValueError('Could not create the intermediate video with the OpenCV MJPG writer.') from exc
    if not writer.isOpened():
        capture.release()
        writer.release()
        if os.path.exists(intermediate_path):
            os.remove(intermediate_path)
        raise ValueError('Could not create the intermediate video; the OpenCV MJPG writer is unavailable.')

    frame_count = 0
    metrics = {}
    logs = [f"[{time.strftime('%H:%M:%S')}] Video processing started ({width}x{height} at {fps:.3f} FPS)."]
    if fps_was_defaulted:
        logs.append(
            f"[{time.strftime('%H:%M:%S')}] Input FPS was invalid; using the safe fallback of {fps:.3f} FPS."
        )
    try:
        while True:
            read_ok, frame = capture.read()
            if not read_ok:
                break
            processed = execute_cv_pipeline(
                pipeline_graph,
                output_dir=output_dir,
                _input_frame=frame,
                _write_output=False,
            )['processed_frame']
            if processed.shape[:2] != (height, width):
                processed = cv2.resize(processed, (width, height), interpolation=cv2.INTER_AREA)
            if len(processed.shape) == 2:
                processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
            elif processed.shape[2] == 4:
                processed = cv2.cvtColor(processed, cv2.COLOR_BGRA2BGR)
            writer.write(processed)
            metrics = calculate_image_metrics(processed)
            frame_count += 1
    except Exception as exc:
        capture.release()
        writer.release()
        if os.path.exists(intermediate_path):
            os.remove(intermediate_path)
        if isinstance(exc, (cv2.error, ValueError, OSError)):
            raise ValueError(f'Video frame processing failed: {exc}') from exc
        raise
    finally:
        capture.release()
        writer.release()

    try:
        if not frame_count or not os.path.isfile(intermediate_path) or os.path.getsize(intermediate_path) == 0:
            raise ValueError('The video contained no readable frames or the intermediate output is empty.')

        duration = frame_count / fps
        command = [
            ffmpeg_path,
            '-hide_banner',
            '-loglevel', 'error',
            '-y',
            '-i', input_file_path,
            '-i', intermediate_path,
            '-map', '1:v:0',
            '-map', '0:a?',
            '-c:v', encoder,
            '-b:v', '5M',
            '-pix_fmt', 'yuv420p',
            '-tag:v', 'avc1',
            '-r', f'{fps:.8f}',
            '-frames:v', str(frame_count),
            '-c:a', 'aac',
            '-t', f'{duration:.8f}',
            '-movflags', '+faststart',
            result_path,
        ]
        try:
            conversion = subprocess.run(
                command, capture_output=True, text=True, timeout=600, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.exception('FFmpeg could not encode the processed video')
            raise ValueError(
                'FFmpeg could not finish creating the browser-compatible MP4. '
                'Check the FFmpeg installation and H.264 encoder, then try again.'
            ) from exc
        if conversion.returncode:
            logger.error('FFmpeg video conversion failed: %s', conversion.stderr.strip())
            raise ValueError(
                'FFmpeg could not encode the processed video as browser-compatible H.264 MP4. '
                'Check that the installed FFmpeg build includes the selected H.264 encoder.'
            )

        if not os.path.isfile(result_path) or os.path.getsize(result_path) <= 0:
            raise ValueError('FFmpeg completed without producing a non-empty MP4 result.')
        verification = cv2.VideoCapture(result_path)
        try:
            if not verification.isOpened():
                raise ValueError('The encoded MP4 could not be opened for verification.')
            output_fps = float(verification.get(cv2.CAP_PROP_FPS))
            output_width = int(verification.get(cv2.CAP_PROP_FRAME_WIDTH))
            output_height = int(verification.get(cv2.CAP_PROP_FRAME_HEIGHT))
            output_frame_count = int(verification.get(cv2.CAP_PROP_FRAME_COUNT))
            has_output_frame, output_frame = verification.read()
        finally:
            verification.release()
        if not has_output_frame or output_frame is None or output_frame.size == 0:
            raise ValueError('The encoded MP4 contains no readable frames.')
        if (output_width, output_height) != (width, height) or output_frame.shape[:2] != (height, width):
            raise ValueError('The encoded MP4 dimensions do not match the processed video frames.')
        if not math.isfinite(output_fps) or abs(output_fps - fps) > max(0.1, fps * 0.01):
            raise ValueError('The encoded MP4 FPS does not match the processed video FPS.')
        if output_frame_count <= 0 or output_frame_count != frame_count:
            raise ValueError('The encoded MP4 frame count does not match the processed video.')

        duration = round(frame_count / fps, 3)
        metrics.update({
            'fps': round(fps, 3),
            'frame_count': frame_count,
            'duration': duration,
            'output_format': 'MP4 (H.264)',
            'output_size_bytes': os.path.getsize(result_path),
        })
        elapsed = round(time.time() - start_time, 3)
        logs.append(f"[{time.strftime('%H:%M:%S')}] Processed {frame_count} frames ({duration}s).")
        logs.append(f"[{time.strftime('%H:%M:%S')}] Encoded browser-compatible H.264 MP4 ({encoder}).")
        logs.append(f"[{time.strftime('%H:%M:%S')}] Video pipeline completed in {elapsed}s.")
        return {
            'status': 'success',
            'processing_time': elapsed,
            'result_file_path': result_path,
            'objects_detected': [],
            'metrics': metrics,
            'logs': logs,
        }
    except Exception:
        if os.path.exists(result_path):
            os.remove(result_path)
        raise
    finally:
        if os.path.exists(intermediate_path):
            os.remove(intermediate_path)


def _available_h264_encoder(ffmpeg_path):
    try:
        result = subprocess.run(
            [ffmpeg_path, '-hide_banner', '-encoders'],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.exception('Could not inspect FFmpeg video encoders')
        raise ValueError(
            'FFmpeg was found but its available encoders could not be checked. '
            'Verify the FFmpeg installation and restart the CV service.'
        ) from exc
    if result.returncode:
        logger.error('Could not list FFmpeg encoders: %s', result.stderr.strip())
        raise ValueError('FFmpeg was found but could not list its video encoders.')

    available = set()
    for line in result.stdout.splitlines():
        columns = line.split(maxsplit=2)
        if len(columns) >= 2 and columns[0].startswith('V'):
            available.add(columns[1])
    for encoder in ('libx264', 'libopenh264', 'h264_mf'):
        if encoder in available:
            return encoder
    raise ValueError(
        'FFmpeg is installed but no supported H.264 encoder was detected. '
        'Install an FFmpeg build with libx264, libopenh264, or the Windows Media Foundation H.264 encoder.'
    )

def calculate_image_metrics(img):
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w, c = img.shape
    else:
        gray = img
        h, w = img.shape
        c = 1

    brightness = round(float(np.mean(gray)), 2)
    contrast = round(float(np.std(gray)), 2)
    sharpness = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2)
    edges = cv2.Canny(gray, 100, 200)
    edge_density = round(float(np.count_nonzero(edges) / (h * w)), 4)

    return {
        "width": w,
        "height": h,
        "channels": c,
        "brightness": brightness,
        "contrast": contrast,
        "sharpness": sharpness,
        "edge_density": edge_density
    }
