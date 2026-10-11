from rest_framework import serializers
from .models import Pipeline, PipelineNode, PipelineConnection, PipelineVersion, PipelineTemplate

class PipelineVersionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = PipelineVersion
        fields = ('id', 'pipeline', 'version_number', 'name', 'description', 'graph_data',
                  'created_at', 'created_by_username')
        read_only_fields = ('version_number', 'created_at')

class PipelineSerializer(serializers.ModelSerializer):
    versions = PipelineVersionSerializer(many=True, read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = Pipeline
        fields = ('id', 'project', 'project_name', 'owner', 'name', 'description',
                  'graph_data', 'is_template', 'versions', 'created_at', 'updated_at')
        read_only_fields = ('owner', 'created_at', 'updated_at')

    def validate_project(self, project):
        request = self.context.get('request')
        if not request or project.owner_id != request.user.id:
            raise serializers.ValidationError('Choose a project that belongs to your account.')
        return project

class PipelineTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PipelineTemplate
        fields = ('id', 'name', 'category', 'description', 'graph_data', 'is_official', 'created_by', 'created_at')
        read_only_fields = ('is_official', 'created_by', 'created_at')
