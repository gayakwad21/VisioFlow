import mimetypes

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from .models import Project, UploadedFile
from .serializers import ProjectSerializer, UploadedFileSerializer
from backend.media_responses import protected_media_response


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Project.objects.filter(owner=self.request.user)
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))
        return queryset

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        for uploaded_file in instance.files.all():
            uploaded_file.file.delete(save=False)
        super().perform_destroy(instance)

class UploadedFileViewSet(viewsets.ModelViewSet):
    serializer_class = UploadedFileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = UploadedFile.objects.filter(user=self.request.user, project__owner=self.request.user)
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        uploaded_file = self.get_object()
        content_type = mimetypes.guess_type(uploaded_file.original_name)[0] or 'application/octet-stream'
        response = protected_media_response(
            request,
            uploaded_file.file,
            content_type=content_type,
            filename=uploaded_file.original_name,
        )
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    def perform_destroy(self, instance):
        instance.file.delete(save=False)
        super().perform_destroy(instance)
