import mimetypes

from rest_framework import serializers

from .models import ProcessingJob, ProcessingResult, Experiment

class ProcessingResultSerializer(serializers.ModelSerializer):
    output_url = serializers.SerializerMethodField()
    output_content_type = serializers.SerializerMethodField()
    output_size_bytes = serializers.SerializerMethodField()
    output_filename = serializers.SerializerMethodField()

    class Meta:
        model = ProcessingResult
        fields = ('id', 'job', 'output_url', 'output_content_type', 'output_size_bytes',
                  'output_filename',
                  'metrics', 'detected_objects', 'logs', 'created_at')

    def get_output_url(self, obj):
        if obj.output_file:
            request = self.context.get('request')
            path = f'/api/jobs/{obj.job_id}/result/'
            if request:
                return request.build_absolute_uri(path)
            return path
        return None

    def get_output_content_type(self, obj):
        if not obj.output_file:
            return None
        if obj.output_file.name.lower().endswith('.mp4'):
            return 'video/mp4'
        return mimetypes.guess_type(obj.output_file.name)[0] or 'application/octet-stream'

    def get_output_size_bytes(self, obj):
        return obj.output_file.size if obj.output_file else None

    def get_output_filename(self, obj):
        return obj.output_file.name.rsplit('/', 1)[-1] if obj.output_file else None

class ProcessingJobSerializer(serializers.ModelSerializer):
    result = ProcessingResultSerializer(read_only=True)
    pipeline_name = serializers.CharField(source='pipeline.name', read_only=True)
    pipeline_version_number = serializers.IntegerField(
        source='pipeline_version.version_number', read_only=True, allow_null=True
    )
    project_name = serializers.CharField(source='project.name', read_only=True)
    input_file_url = serializers.SerializerMethodField()
    input_file_name = serializers.SerializerMethodField()
    input_file_type = serializers.SerializerMethodField()
    input_file_content_type = serializers.SerializerMethodField()
    input_file_size = serializers.IntegerField(source='input_file.file_size', read_only=True, allow_null=True)
    input_width = serializers.IntegerField(source='input_file.width', read_only=True, allow_null=True)
    input_height = serializers.IntegerField(source='input_file.height', read_only=True, allow_null=True)
    input_channels = serializers.IntegerField(source='input_file.channels', read_only=True, allow_null=True)
    input_metadata = serializers.JSONField(source='input_file.metadata', read_only=True, allow_null=True)

    class Meta:
        model = ProcessingJob
        fields = ('id', 'project', 'project_name', 'pipeline', 'pipeline_name',
                  'pipeline_version', 'pipeline_version_number', 'pipeline_graph', 'user',
                  'input_file', 'input_file_name', 'input_file_type', 'input_file_content_type',
                  'input_file_url', 'input_file_size', 'input_width', 'input_height',
                  'input_channels', 'input_metadata',
                  'status', 'progress', 'error_message',
                  'start_time', 'end_time', 'processing_time', 'result', 'created_at')
        read_only_fields = ('user', 'status', 'progress', 'error_message', 'start_time',
                            'end_time', 'processing_time', 'result', 'created_at',
                            'pipeline_version', 'pipeline_graph')

    def get_input_file_url(self, obj):
        if obj.input_file and obj.input_file.file:
            request = self.context.get('request')
            path = f'/api/files/{obj.input_file_id}/download/'
            if request:
                return request.build_absolute_uri(path)
            return path
        return None

    def get_input_file_name(self, obj):
        return obj.input_file.original_name if obj.input_file_id else None

    def get_input_file_type(self, obj):
        return obj.input_file.file_type if obj.input_file_id else None

    def get_input_file_content_type(self, obj):
        if not obj.input_file_id:
            return None
        return (
            (obj.input_file.metadata or {}).get('mime_type')
            or mimetypes.guess_type(obj.input_file.original_name)[0]
            or 'application/octet-stream'
        )

class ExperimentSerializer(serializers.ModelSerializer):
    job_a_detail = ProcessingJobSerializer(source='job_a', read_only=True)
    job_b_detail = ProcessingJobSerializer(source='job_b', read_only=True)

    class Meta:
        model = Experiment
        fields = ('id', 'user', 'project', 'name', 'description', 'job_a', 'job_b',
                  'job_a_detail', 'job_b_detail', 'comparison_metrics', 'created_at')
        read_only_fields = ('user', 'created_at')

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        project = attrs.get('project', getattr(self.instance, 'project', None))
        job_a = attrs.get('job_a', getattr(self.instance, 'job_a', None))
        job_b = attrs.get('job_b', getattr(self.instance, 'job_b', None))
        if not user or not project or project.owner_id != user.id:
            raise serializers.ValidationError({'project': 'Choose a project that belongs to your account.'})
        for field, job in (('job_a', job_a), ('job_b', job_b)):
            if not job or job.user_id != user.id or job.project_id != project.id:
                raise serializers.ValidationError({field: 'Choose a job from this project that belongs to your account.'})
        return attrs
