from django.db import models
from django.contrib.auth.models import User
from backend.projects.models import Project
from backend.pipelines.models import Pipeline
from backend.processing.models import ProcessingJob

def report_pdf_path(instance, filename):
    return f"reports/project_{instance.project.id}/{filename}"

class Report(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='reports')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    pipeline = models.ForeignKey(Pipeline, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    job = models.ForeignKey(ProcessingJob, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True, default='')
    content_json = models.JSONField(default=dict, blank=True)
    pdf_file = models.FileField(upload_to=report_pdf_path, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Report: {self.title}"
