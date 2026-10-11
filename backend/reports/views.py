import copy
import mimetypes
import os

from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Report
from .serializers import ReportSerializer
from backend.processing.models import ProcessingJob, ProcessingResult


def _ordered_nodes(graph):
    nodes = graph.get('nodes', []) if isinstance(graph, dict) else []
    edges = graph.get('edges', []) if isinstance(graph, dict) else []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return []

    safe_nodes = [node for node in nodes if isinstance(node, dict)]
    node_ids = [node.get('id') for node in safe_nodes]
    if len(node_ids) != len(nodes) or any(not isinstance(node_id, str) or not node_id for node_id in node_ids):
        return safe_nodes
    order_index = {node_id: index for index, node_id in enumerate(node_ids)}
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source, target = edge.get('source'), edge.get('target')
        if isinstance(source, str) and isinstance(target, str) and source in outgoing and target in incoming:
            outgoing[source].append(target)
            incoming[target] += 1

    ready = sorted(
        (node_id for node_id, count in incoming.items() if count == 0),
        key=order_index.get,
    )
    ordered_ids = []
    while ready:
        node_id = ready.pop(0)
        ordered_ids.append(node_id)
        for target in outgoing[node_id]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort(key=order_index.get)

    if len(ordered_ids) != len(node_ids):
        return safe_nodes
    by_id = {node.get('id'): node for node in safe_nodes}
    return [by_id[node_id] for node_id in ordered_ids]


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Report.objects.filter(user=self.request.user).select_related(
            'project', 'pipeline', 'job__pipeline_version'
        )

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='generate')
    def generate_from_job(self, request):
        job_id = request.data.get('job_id')
        job = ProcessingJob.objects.filter(user=request.user).select_related(
            'project', 'pipeline', 'pipeline_version', 'input_file'
        ).filter(pk=job_id).first()
        if not job:
            return Response({'job_id': ['Processing job not found.']}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = job.result
        except ProcessingResult.DoesNotExist:
            result = None
        graph = copy.deepcopy(job.pipeline_graph or job.pipeline.graph_data or {})
        if not isinstance(graph, dict):
            graph = {}
        logs = result.logs if result and isinstance(result.logs, list) else []
        input_file = job.input_file
        output_file = result.output_file if result and result.output_file else None
        output_url = (
            request.build_absolute_uri(f'/api/jobs/{job.id}/result/')
            if output_file else None
        )
        input_url = (
            request.build_absolute_uri(f'/api/files/{input_file.id}/download/')
            if input_file and input_file.file else None
        )
        mime_type = None
        if input_file:
            mime_type = (
                (input_file.metadata or {}).get('mime_type')
                or mimetypes.guess_type(input_file.original_name)[0]
            )
        graph_nodes = graph.get('nodes', [])
        if not isinstance(graph_nodes, list):
            graph_nodes = []
        for node in graph_nodes:
            if not isinstance(node, dict) or node.get('type') != 'imageSource':
                continue
            data = node.get('data')
            if not isinstance(data, dict):
                data = {}
                node['data'] = data
            if input_file:
                data['imageName'] = input_file.original_name
            else:
                data.pop('imageName', None)
        steps = []
        for node in _ordered_nodes(graph):
            node_id = node.get('id')
            node_logs = [
                str(log) for log in logs
                if node_id and f"Node '{node_id}'" in str(log)
            ]
            execution_status = 'not_available'
            if any('completed.' in log.lower() or 'initialized.' in log.lower() for log in node_logs):
                execution_status = 'success'
            elif any('failed' in log.lower() or 'error' in log.lower() for log in node_logs):
                execution_status = 'failed'
            steps.append({
                'node_id': node_id,
                'type': node.get('type'),
                'name': (node.get('data') or {}).get('label') if isinstance(node.get('data'), dict) else None,
                'parameters': node.get('data', {}),
                'status': execution_status,
            })
        operation_labels = {
            'grayscale': 'grayscale conversion',
            'blur': 'blur',
            'gaussianBlur': 'Gaussian blur',
            'medianBlur': 'median blur',
            'canny': 'Canny edge detection',
            'threshold': 'thresholding',
            'adaptiveThreshold': 'adaptive thresholding',
            'morphological': 'morphological processing',
            'rotate': 'rotation',
            'resize': 'resize',
            'crop': 'crop',
            'brightness': 'brightness adjustment',
            'sharpen': 'sharpening',
            'findContours': 'contour detection',
            'histogram': 'histogram analysis',
            'imageStatistics': 'image statistics',
            'objectDetection': 'object detection',
        }
        operation_names = [
            operation_labels.get(step['type'], str(step['type']))
            for step in steps
            if step.get('type') and step.get('type') not in ('imageSource', 'output')
        ]
        summary_parts = [f"{job.status.title()}: {job.pipeline.name}"]
        summary_parts.append(
            f"Operations: {', '.join(operation_names)}" if operation_names
            else 'No processing operations were recorded'
        )
        if input_file:
            input_details = [input_file.original_name]
            if input_file.width is not None and input_file.height is not None:
                input_details.append(f'{input_file.width} × {input_file.height} px')
            if input_file.file_size:
                input_details.append(f'{input_file.file_size} bytes')
            summary_parts.append(f"Input: {', '.join(input_details)}")
        if output_file:
            output_dimensions = [
                str(result.metrics.get(key))
                for key in ('width', 'height')
                if isinstance(result.metrics, dict) and result.metrics.get(key) is not None
            ]
            output_details = [os.path.basename(output_file.name)]
            if len(output_dimensions) == 2:
                output_details.append(f'{output_dimensions[0]} × {output_dimensions[1]} px')
            output_details.append(f'{output_file.size} bytes')
            summary_parts.append(f"Output: {', '.join(output_details)}")
        elif job.error_message:
            summary_parts.append(f"Error: {job.error_message}")
        if job.end_time or job.processing_time > 0:
            summary_parts.append(f"Processing time: {job.processing_time} s")
        summary = '. '.join(summary_parts) + '.'
        content = {
            'project': {'id': job.project_id, 'name': job.project.name},
            'pipeline': {
                'id': job.pipeline_id,
                'name': job.pipeline.name,
                'version': job.pipeline_version.version_number if job.pipeline_version_id else None,
                'graph_data': graph,
                'steps': steps,
            },
            'input': {
                'id': input_file.id if input_file else None,
                'name': input_file.original_name if input_file else None,
                'file_type': input_file.file_type if input_file else None,
                'format': os.path.splitext(input_file.original_name)[1].lstrip('.').upper() or None
                if input_file else None,
                'content_type': mime_type,
                'size_bytes': input_file.file_size if input_file else None,
                'width': input_file.width if input_file else None,
                'height': input_file.height if input_file else None,
                'channels': input_file.channels if input_file else None,
                'metadata': input_file.metadata if input_file else {},
                'url': input_url,
            },
            'output': {
                'url': output_url,
                'filename': os.path.basename(output_file.name) if output_file else None,
                'format': os.path.splitext(output_file.name)[1].lstrip('.').upper()
                if output_file else None,
                'content_type': (
                    'video/mp4' if output_file.name.lower().endswith('.mp4')
                    else mimetypes.guess_type(output_file.name)[0] or 'application/octet-stream'
                ) if output_file else None,
                'size_bytes': output_file.size if output_file else None,
            } if output_file else None,
            'status': job.status,
            'error': job.error_message or None,
            'metrics': result.metrics if result and isinstance(result.metrics, dict) else {},
            'logs': logs,
            'execution_time': job.processing_time,
            'start_time': job.start_time.isoformat() if job.start_time else None,
            'end_time': job.end_time.isoformat() if job.end_time else None,
            'created_at': job.created_at.isoformat(),
        }
        report = Report.objects.create(
            project=job.project,
            user=request.user,
            pipeline=job.pipeline,
            job=job,
            title=f'{job.pipeline.name} — Job #{job.id}',
            summary=summary,
            content_json=content,
        )
        return Response(
            ReportSerializer(report, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
