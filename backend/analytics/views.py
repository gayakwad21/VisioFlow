from django.db.models import Sum, Count
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import ActivityLog
from .serializers import ActivityLogSerializer
from backend.projects.models import Project, UploadedFile
from backend.pipelines.models import Pipeline
from backend.processing.models import ProcessingJob
from backend.projects.serializers import ProjectSerializer
from backend.processing.serializers import ProcessingJobSerializer

class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ActivityLog.objects.filter(user=self.request.user)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    user = request.user
    projects_count = Project.objects.filter(owner=user).count()
    pipelines_count = Pipeline.objects.filter(owner=user).count()
    images_count = UploadedFile.objects.filter(user=user, file_type='IMAGE').count()
    videos_count = UploadedFile.objects.filter(user=user, file_type='VIDEO').count()

    user_jobs = ProcessingJob.objects.filter(user=user)
    completed_jobs = user_jobs.filter(status='COMPLETED').count()
    failed_jobs = user_jobs.filter(status='FAILED').count()
    total_processing_time = user_jobs.aggregate(total=Sum('processing_time'))['total'] or 0.0
    recent_projects = ProjectSerializer(
        Project.objects.filter(owner=user)[:5], many=True, context={'request': request}
    ).data
    recent_jobs = ProcessingJobSerializer(
        user_jobs.select_related('project', 'pipeline', 'input_file')[:8],
        many=True,
        context={'request': request}
    ).data

    recent_activities = ActivityLogSerializer(
        ActivityLog.objects.filter(user=user)[:10],
        many=True
    ).data
    operation_counts = {}
    for graph in Pipeline.objects.filter(owner=user).values_list('graph_data', flat=True):
        for node in (graph or {}).get('nodes', []):
            node_type = node.get('type')
            if node_type:
                operation_counts[node_type] = operation_counts.get(node_type, 0) + 1
    most_used_pipelines = list(
        Pipeline.objects.filter(owner=user)
        .annotate(job_count=Count('jobs'))
        .order_by('-job_count', 'name')
        .values('id', 'name', 'job_count')[:5]
    )

    return Response({
        'projects_count': projects_count,
        'pipelines_count': pipelines_count,
        'jobs_count': user_jobs.count(),
        'images_count': images_count,
        'videos_count': videos_count,
        'completed_jobs': completed_jobs,
        'failed_jobs': failed_jobs,
        'total_processing_time': round(total_processing_time, 2),
        'recent_projects': recent_projects,
        'recent_jobs': recent_jobs,
        'recent_activities': recent_activities,
        'operation_counts': operation_counts,
        'most_used_pipelines': most_used_pipelines,
    })
