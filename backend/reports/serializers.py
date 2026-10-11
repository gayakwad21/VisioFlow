from rest_framework import serializers
from .models import Report

class ReportSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    author_name = serializers.CharField(source='user.username', read_only=True)
    pipeline_name = serializers.CharField(source='pipeline.name', read_only=True, allow_null=True)
    job_status = serializers.CharField(source='job.status', read_only=True, allow_null=True)
    pipeline_version_number = serializers.IntegerField(
        source='job.pipeline_version.version_number', read_only=True, allow_null=True
    )
    class Meta:
        model = Report
        fields = ('id', 'project', 'project_name', 'user', 'author_name', 'pipeline',
                  'pipeline_name', 'pipeline_version_number', 'job', 'job_status',
                  'title', 'summary', 'content_json', 'created_at')
        read_only_fields = ('user', 'created_at')

    def validate(self, attrs):
        request = self.context.get('request')
        if not request:
            return attrs
        project = attrs.get('project', getattr(self.instance, 'project', None))
        pipeline = attrs.get('pipeline', getattr(self.instance, 'pipeline', None))
        job = attrs.get('job', getattr(self.instance, 'job', None))
        if not project or project.owner_id != request.user.id:
            raise serializers.ValidationError({'project': 'Choose a project that belongs to your account.'})
        if pipeline and (pipeline.owner_id != request.user.id or pipeline.project_id != project.id):
            raise serializers.ValidationError({'pipeline': 'Choose a pipeline in this project that belongs to your account.'})
        if job and (job.user_id != request.user.id or job.project_id != project.id):
            raise serializers.ValidationError({'job': 'Choose a processing job in this project that belongs to your account.'})
        if job and pipeline and job.pipeline_id != pipeline.id:
            raise serializers.ValidationError({'pipeline': 'The selected pipeline does not match the processing job.'})
        return attrs
