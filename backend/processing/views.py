import mimetypes

from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ProcessingJob, ProcessingResult, Experiment
from .serializers import ProcessingJobSerializer, ProcessingResultSerializer, ExperimentSerializer
from backend.analytics.models import ActivityLog
from backend.media_responses import protected_media_response
from backend.processing.tasks import submit_processing_job

class ProcessingJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProcessingJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProcessingJob.objects.filter(user=self.request.user)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj

    @action(detail=True, methods=['get'], url_path='result')
    def result_file(self, request, pk=None):
        job = self.get_object()
        try:
            result = job.result
        except ProcessingResult.DoesNotExist:
            result = None
        if not result or not result.output_file:
            return Response({'detail': 'This job has no output file.'}, status=status.HTTP_404_NOT_FOUND)
        content_type = (
            'video/mp4' if result.output_file.name.lower().endswith('.mp4')
            else mimetypes.guess_type(result.output_file.name)[0] or 'application/octet-stream'
        )
        response = protected_media_response(
            request,
            result.output_file,
            content_type=content_type,
            filename=f'job-{job.id}-{result.output_file.name.rsplit("/", 1)[-1]}',
            as_attachment=request.query_params.get('download') == '1',
        )
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    @action(detail=True, methods=['post'], url_path='retry')
    def retry_job(self, request, pk=None):
        old_job = self.get_object()
        new_job = ProcessingJob.objects.create(
            project=old_job.project,
            pipeline=old_job.pipeline,
            pipeline_version=old_job.pipeline_version,
            pipeline_graph=old_job.pipeline_graph,
            user=request.user,
            input_file=old_job.input_file,
            status='QUEUED'
        )
        ActivityLog.objects.create(
            user=request.user,
            action='JOB_RETRIED',
            details={'previous_job_id': old_job.id, 'job_id': new_job.id}
        )
        from django.db import transaction
        transaction.on_commit(lambda: submit_processing_job(new_job.pk))
        return Response(
            ProcessingJobSerializer(new_job, context={'request': request}).data,
            status=status.HTTP_202_ACCEPTED
        )

class ExperimentViewSet(viewsets.ModelViewSet):
    serializer_class = ExperimentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Experiment.objects.filter(user=self.request.user)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
