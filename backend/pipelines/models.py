from django.db import models
from django.contrib.auth.models import User
from backend.projects.models import Project

class Pipeline(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='pipelines')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pipelines')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    graph_data = models.JSONField(default=dict)
    is_template = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} - {self.project.name}"

class PipelineNode(models.Model):
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='nodes')
    node_id = models.CharField(max_length=100)
    node_type = models.CharField(max_length=100)
    position_x = models.FloatField(default=0.0)
    position_y = models.FloatField(default=0.0)
    config = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.node_type} ({self.node_id})"

class PipelineConnection(models.Model):
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='connections')
    source_node = models.CharField(max_length=100)
    source_handle = models.CharField(max_length=100, default='output')
    target_node = models.CharField(max_length=100)
    target_handle = models.CharField(max_length=100, default='input')

    def __str__(self):
        return f"{self.source_node} -> {self.target_node}"

class PipelineVersion(models.Model):
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField(default=1)
    name = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField(blank=True, default='')
    graph_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-version_number']

    def __str__(self):
        return f"{self.pipeline.name} v{self.version_number}"

class PipelineTemplate(models.Model):
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, default='Computer Vision')
    description = models.TextField(blank=True, default='')
    graph_data = models.JSONField(default=dict)
    is_official = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Template: {self.name} ({self.category})"
