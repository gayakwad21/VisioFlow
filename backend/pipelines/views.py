import re

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .models import Pipeline, PipelineVersion, PipelineTemplate
from .serializers import PipelineSerializer, PipelineVersionSerializer, PipelineTemplateSerializer
from backend.processing.models import ProcessingJob
from backend.processing.serializers import ProcessingJobSerializer
from backend.analytics.models import ActivityLog
from backend.processing.tasks import submit_processing_job
from cv_service.processors.image_processor import validate_pipeline_graph


def create_pipeline_version(pipeline, user):
    with transaction.atomic():
        Pipeline.objects.select_for_update().get(pk=pipeline.pk)
        latest = pipeline.versions.first()
        if latest and (
            latest.name == pipeline.name
            and latest.description == pipeline.description
            and latest.graph_data == pipeline.graph_data
        ):
            return latest, False
        version = PipelineVersion.objects.create(
            pipeline=pipeline,
            version_number=(latest.version_number + 1) if latest else 1,
            name=pipeline.name,
            description=pipeline.description,
            graph_data=pipeline.graph_data,
            created_by=user,
        )
        return version, True

class PipelineViewSet(viewsets.ModelViewSet):
    serializer_class = PipelineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Pipeline.objects.filter(owner=self.request.user)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        pipeline = serializer.save(owner=self.request.user)
        create_pipeline_version(pipeline, self.request.user)
        ActivityLog.objects.create(
            user=self.request.user,
            action='PIPELINE_CREATED',
            details={'pipeline_id': pipeline.id, 'name': pipeline.name}
        )

    def perform_update(self, serializer):
        before = self.get_object()
        previous = (before.name, before.description, before.graph_data)
        pipeline = serializer.save()
        if previous != (pipeline.name, pipeline.description, pipeline.graph_data):
            create_pipeline_version(pipeline, self.request.user)

    @action(detail=True, methods=['post'], url_path='run')
    def run_pipeline(self, request, pk=None):
        pipeline = self.get_object()
        file_id = request.data.get('input_file_id')
        if not file_id:
            return Response(
                {'input_file_id': ['Choose an image or video from this pipeline project.']},
                status=status.HTTP_400_BAD_REQUEST
            )

        version_id = request.data.get('version_id')
        version = None
        if version_id:
            version = get_object_or_404(pipeline.versions, pk=version_id)
            graph_data = version.graph_data
        else:
            graph_data = pipeline.graph_data
        try:
            validate_pipeline_graph(graph_data)
        except ValueError as exc:
            raise ValidationError({'graph_data': [str(exc)]}) from exc
        if not version:
            version, _ = create_pipeline_version(pipeline, request.user)
            graph_data = version.graph_data

        file_id = request.data.get('input_file_id')
        from backend.projects.models import UploadedFile
        input_file = UploadedFile.objects.filter(id=file_id, user=request.user).first()
        if not input_file or input_file.project_id != pipeline.project_id:
            return Response(
                {'input_file_id': ['Choose an input file from this pipeline project.']},
                status=status.HTTP_400_BAD_REQUEST
            )

        job = ProcessingJob.objects.create(
            project=pipeline.project,
            pipeline=pipeline,
            pipeline_version=version,
            pipeline_graph=graph_data,
            user=request.user,
            input_file=input_file,
            status='QUEUED',
        )

        ActivityLog.objects.create(
            user=request.user,
            action='PIPELINE_EXECUTED',
            details={'pipeline_id': pipeline.id, 'job_id': job.id}
        )

        transaction.on_commit(lambda: submit_processing_job(job.pk))
        return Response(
            {'status': 'queued', 'job': ProcessingJobSerializer(job, context={'request': request}).data},
            status=status.HTTP_202_ACCEPTED
        )

    @action(detail=True, methods=['post'], url_path='save-version')
    def save_version(self, request, pk=None):
        pipeline = self.get_object()
        version, created = create_pipeline_version(pipeline, request.user)
        return Response(
            PipelineVersionSerializer(version).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'], url_path='versions')
    def list_versions(self, request, pk=None):
        pipeline = self.get_object()
        return Response(PipelineVersionSerializer(pipeline.versions.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='restore-version')
    def restore_version(self, request, pk=None):
        pipeline = self.get_object()
        version = get_object_or_404(pipeline.versions, pk=request.data.get('version_id'))
        pipeline.name = version.name
        pipeline.description = version.description
        pipeline.graph_data = version.graph_data
        pipeline.save(update_fields=('name', 'description', 'graph_data', 'updated_at'))
        restored, _ = create_pipeline_version(pipeline, request.user)
        return Response({
            'pipeline': PipelineSerializer(pipeline, context={'request': request}).data,
            'version': PipelineVersionSerializer(restored).data,
        })

    @action(detail=True, methods=['get'], url_path='export-python')
    def export_python(self, request, pk=None):
        pipeline = self.get_object()
        version_id = request.query_params.get('version_id')
        graph_data = pipeline.graph_data
        if version_id:
            graph_data = get_object_or_404(pipeline.versions, pk=version_id).graph_data
        python_code = generate_python_code_from_graph(graph_data, pipeline.name)
        return Response({'pipeline_id': pipeline.id, 'python_code': python_code})

class PipelineTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PipelineTemplate.objects.all()
    serializer_class = PipelineTemplateSerializer
    permission_classes = [permissions.AllowAny]

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_ai_pipeline(request):
    prompt = request.data.get('prompt', '')
    if not isinstance(prompt, str) or not prompt.strip():
        return Response({'prompt': ['A non-empty text prompt is required.']}, status=status.HTTP_400_BAD_REQUEST)
    if len(prompt) > 2000:
        return Response({'prompt': ['Prompt must be 2000 characters or fewer.']}, status=status.HTTP_400_BAD_REQUEST)

    prompt_lower = prompt.strip().lower()
    nodes = []
    connections = []
    explanations = []

    def add_node(node_type, data=None):
        node_number = len(nodes) + 1
        node = {
            'id': f'node-{node_number}',
            'type': node_type,
            'position': {'x': 80 + (node_number - 1) * 210, 'y': 200},
            'data': data or {},
        }
        nodes.append(node)
        explanations.append(f'{node_number}. Added {node_type} node.')

    add_node('imageSource', {'imageName': 'input.jpg'})

    if any(term in prompt_lower for term in ('resize', 'scale')):
        add_node('resize', {'width': 640, 'height': 480})
    if 'crop' in prompt_lower:
        add_node('crop', {'x': 0, 'y': 0, 'width': 320, 'height': 240})
    if 'rotate' in prompt_lower or 'rotation' in prompt_lower:
        add_node('rotate', {'angle': 90})
    if any(term in prompt_lower for term in ('sharpen', 'sharpening')):
        add_node('sharpen', {'amount': 1.0})
    if any(term in prompt_lower for term in ('brightness', 'contrast', 'brighten', 'darken')):
        add_node('brightness', {'brightness': 20, 'contrast': 1.2})

    noise_removal = any(term in prompt_lower for term in ('denoise', 'de-noise', 'noise', 'smooth'))
    blur_requested = 'blur' in prompt_lower or 'gaussian' in prompt_lower or noise_removal
    if blur_requested:
        blur_type = 'median' if 'median' in prompt_lower else 'gaussian'
        add_node('blur', {'strength': 5, 'blurType': blur_type})

    needs_grayscale = any(term in prompt_lower for term in (
        'gray', 'grayscale', 'grey', 'canny', 'edge', 'threshold', 'contour', 'histogram', 'statistics'
    ))
    if needs_grayscale:
        add_node('grayscale')
    if 'adaptive threshold' in prompt_lower:
        add_node('adaptiveThreshold', {'blockSize': 11, 'constant': 2})
    elif 'threshold' in prompt_lower:
        add_node('threshold', {'threshold': 127, 'mode': 'binary'})
    if any(term in prompt_lower for term in ('canny', 'edge', 'edges', 'outline', 'boundary')):
        add_node('canny', {'threshold1': 75, 'threshold2': 200})
    if any(term in prompt_lower for term in ('contour', 'segment', 'shape', 'count objects')):
        add_node('findContours', {'fill': False})
    if 'histogram' in prompt_lower:
        add_node('histogram')
    if 'statistic' in prompt_lower or 'image stats' in prompt_lower:
        add_node('imageStatistics')
    if any(term in prompt_lower for term in ('object detection', 'detect object', 'identify object', 'yolo')):
        add_node('objectDetection', {'confidence': 0.5})

    add_node('output')
    for index in range(1, len(nodes)):
        connections.append({
            'id': f'edge-{index}',
            'source': nodes[index - 1]['id'],
            'target': nodes[index]['id']
        })

    graph_data = {'nodes': nodes, 'edges': connections}
    explanation_text = "\n".join(explanations)

    return Response({
        'prompt': prompt,
        'graph_data': graph_data,
        'explanation': explanation_text
    })

def generate_python_code_from_graph(graph_data, pipeline_name="VisioForge Pipeline"):
    nodes = graph_data.get('nodes', [])
    edges = graph_data.get('edges', [])
    by_id = {str(node.get('id')): node for node in nodes}
    incoming = {node_id: 0 for node_id in by_id}
    outgoing = {node_id: [] for node_id in by_id}
    for edge in edges:
        source, target = str(edge.get('source')), str(edge.get('target'))
        if source in by_id and target in by_id:
            outgoing[source].append(target)
            incoming[target] += 1
    order = {str(node.get('id')): index for index, node in enumerate(nodes)}
    ready = sorted((node_id for node_id, count in incoming.items() if count == 0), key=order.get)
    ordered_ids = []
    while ready:
        node_id = ready.pop(0)
        ordered_ids.append(node_id)
        for target in outgoing[node_id]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort(key=order.get)
    if len(ordered_ids) != len(nodes):
        raise ValueError('Cannot generate code for a pipeline containing a cycle.')
    nodes = [by_id[node_id] for node_id in ordered_ids]
    safe_pipeline_name = str(pipeline_name).replace('\r', ' ').replace('\n', ' ')

    lines = [
        "import cv2",
        "import numpy as np",
        "import os",
        "",
        f"# {safe_pipeline_name} - Generated by VisionForge Platform",
        "",
        "def run_pipeline(input_image_path):",
        "    if not os.path.exists(input_image_path):",
        "        raise FileNotFoundError(f'Input image not found: {input_image_path}')",
        "",
        "    img = cv2.imread(input_image_path)",
        "    if img is None:",
        "        raise ValueError(f'Failed to decode image from {input_image_path}')",
        "    current = img",
        ""
    ]

    for node in nodes:
        ntype = node.get('type')
        data = node.get('data', {})
        nid = re.sub(r'[^A-Za-z0-9_]', '_', str(node.get('id', 'node')))

        if ntype in ('imageSource', 'output'):
            continue
        elif ntype == 'grayscale':
            lines.append(f"    # Node {nid}: Grayscale")
            lines.append("    if len(current.shape) == 3:")
            lines.append("        current = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)")
            lines.append("")
        elif ntype == 'blur':
            ksize = max(1, min(63, int(data.get('strength', 5))))
            if ksize % 2 == 0:
                ksize += 1
            btype = data.get('blurType', 'gaussian')
            if btype not in ('gaussian', 'median', 'box'):
                btype = 'gaussian'
            lines.append(f"    # Node {nid}: Blur ({btype})")
            if btype == 'gaussian':
                lines.append(f"    current = cv2.GaussianBlur(current, ({ksize}, {ksize}), 0)")
            elif btype == 'median':
                lines.append(f"    current = cv2.medianBlur(current, {ksize})")
            else:
                lines.append(f"    current = cv2.blur(current, ({ksize}, {ksize}))")
            lines.append("")
        elif ntype == 'gaussianBlur':
            ksize = max(1, min(63, int(data.get('kernelSize', 5))))
            ksize += 1 if ksize % 2 == 0 else 0
            sigma = max(0.0, min(100.0, float(data.get('sigma', 0))))
            lines.append(f"    current = cv2.GaussianBlur(current, ({ksize}, {ksize}), {sigma})")
        elif ntype == 'medianBlur':
            ksize = max(3, min(63, int(data.get('kernelSize', 5))))
            ksize += 1 if ksize % 2 == 0 else 0
            lines.append(f"    current = cv2.medianBlur(current, {ksize})")
        elif ntype == 'canny':
            t1 = max(0, min(255, int(data.get('threshold1', 75))))
            t2 = max(0, min(255, int(data.get('threshold2', 200))))
            lines.append(f"    # Node {nid}: Canny Edge Detection")
            lines.append("    _gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY) if len(current.shape) == 3 else current")
            lines.append(f"    current = cv2.Canny(_gray, {t1}, {t2})")
            lines.append("")
        elif ntype in ('threshold', 'adaptiveThreshold'):
            thresh = max(0, min(255, int(data.get('threshold', 127))))
            lines.append(f"    # Node {nid}: Threshold")
            lines.append("    _gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY) if len(current.shape) == 3 else current")
            mode = 'adaptive' if ntype == 'adaptiveThreshold' else data.get('mode', 'binary')
            if mode == 'adaptive':
                block = max(3, min(99, int(data.get('blockSize', 11))))
                block += 1 if block % 2 == 0 else 0
                constant = float(data.get('constant', 2))
                lines.append(f"    current = cv2.adaptiveThreshold(_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, {block}, {constant})")
            elif mode == 'otsu':
                lines.append("    _, current = cv2.threshold(_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)")
            else:
                lines.append(f"    _, current = cv2.threshold(_gray, {thresh}, 255, cv2.THRESH_BINARY)")
            lines.append("")
        elif ntype == 'morphological':
            op = str(data.get('operation', 'erode')).lower()
            iters = max(1, min(20, int(data.get('iterations', 1))))
            kernel_size = max(1, min(31, int(data.get('kernelSize', 3))))
            operations = {'erode': 'MORPH_ERODE', 'dilate': 'MORPH_DILATE', 'open': 'MORPH_OPEN', 'close': 'MORPH_CLOSE'}
            cv_operation = operations.get(op, 'MORPH_ERODE')
            lines.append(f"    # Node {nid}: Morphological {op}")
            lines.append(f"    _kernel = np.ones(({kernel_size}, {kernel_size}), np.uint8)")
            lines.append(f"    current = cv2.morphologyEx(current, cv2.{cv_operation}, _kernel, iterations={iters})")
            lines.append("")
        elif ntype == 'rotate':
            angle = int(data.get('angle', 90)) % 360
            lines.append(f"    # Node {nid}: Rotate ({angle} deg)")
            if angle == 90:
                lines.append("    current = cv2.rotate(current, cv2.ROTATE_90_CLOCKWISE)")
            elif angle == 180:
                lines.append("    current = cv2.rotate(current, cv2.ROTATE_180)")
            elif angle == 270:
                lines.append("    current = cv2.rotate(current, cv2.ROTATE_90_COUNTERCLOCKWISE)")
            elif angle:
                lines.append(f"    _height, _width = current.shape[:2]")
                lines.append(f"    _matrix = cv2.getRotationMatrix2D((_width / 2, _height / 2), {angle}, 1.0)")
                lines.append("    current = cv2.warpAffine(current, _matrix, (_width, _height))")
            lines.append("")
        elif ntype == 'resize':
            width = max(1, min(8192, int(data.get('width', 640))))
            height = max(1, min(8192, int(data.get('height', 480))))
            lines.append(f"    current = cv2.resize(current, ({width}, {height}), interpolation=cv2.INTER_AREA)")
        elif ntype == 'crop':
            x = max(0, int(data.get('x', 0)))
            y = max(0, int(data.get('y', 0)))
            width = max(1, int(data.get('width', 320)))
            height = max(1, int(data.get('height', 240)))
            lines.append(f"    current = current[{y}:{y + height}, {x}:{x + width}].copy()")
        elif ntype == 'brightness':
            alpha = max(0.0, min(5.0, float(data.get('contrast', 1.2))))
            beta = max(-255, min(255, int(data.get('brightness', 20))))
            lines.append(f"    # Node {nid}: Brightness/Contrast")
            lines.append(f"    current = cv2.convertScaleAbs(current, alpha={alpha}, beta={beta})")
            lines.append("")
        elif ntype == 'sharpen':
            amount = max(0.0, min(5.0, float(data.get('amount', 1))))
            lines.append("    _blurred = cv2.GaussianBlur(current, (0, 0), 3)")
            lines.append(f"    current = cv2.addWeighted(current, {1.0 + amount}, _blurred, {-amount}, 0)")
        elif ntype == 'histogram':
            lines.append("    _gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY) if len(current.shape) == 3 else current")
            lines.append("    histogram = cv2.calcHist([_gray], [0], None, [256], [0, 256]).flatten()")
        elif ntype == 'imageStatistics':
            lines.append("    _gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY) if len(current.shape) == 3 else current")
            lines.append("    image_statistics = {'mean': float(np.mean(_gray)), 'stddev': float(np.std(_gray)), 'min': int(np.min(_gray)), 'max': int(np.max(_gray))}")
        elif ntype == 'findContours':
            lines.append(f"    # Node {nid}: Find Contours")
            lines.append("    _gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY) if len(current.shape) == 3 else current")
            lines.append("    _contours, _ = cv2.findContours(_gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)")
            lines.append("    _vis = cv2.cvtColor(_gray, cv2.COLOR_GRAY2BGR)")
            lines.append("    cv2.drawContours(_vis, _contours, -1, (0, 255, 0), 2)")
            lines.append("    current = _vis")
            lines.append("")

    lines.append("    return current")
    lines.append("")
    lines.append("if __name__ == '__main__':")
    lines.append("    result = run_pipeline('sample.jpg')")
    lines.append("    cv2.imwrite('output.png', result)")
    lines.append("    print('Pipeline executed successfully. Result saved to output.png')")

    return "\n".join(lines)
