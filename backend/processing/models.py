from django.db import models
from django.contrib.auth.models import User
from backend.projects.models import Project, UploadedFile
from backend.pipelines.models import Pipeline, PipelineVersion

class ProcessingJob(models.Model):
    STATUS_CHOICES = (
        ('QUEUED', 'Queued'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='jobs')
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name='jobs')
    pipeline_version = models.ForeignKey(
        PipelineVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name='jobs'
    )
    pipeline_graph = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='jobs')
    input_file = models.ForeignKey(UploadedFile, on_delete=models.SET_NULL, null=True, blank=True, related_name='jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='QUEUED')
    progress = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default='')
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    processing_time = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Job #{self.id} [{self.status}] - {self.pipeline.name}"

def result_file_path(instance, filename):
    return f"results/job_{instance.job.id}/{filename}"

class ProcessingResult(models.Model):
    job = models.OneToOneField(ProcessingJob, on_delete=models.CASCADE, related_name='result')
    output_file = models.FileField(upload_to=result_file_path, null=True, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    detected_objects = models.JSONField(default=list, blank=True)
    logs = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result for Job #{self.job.id}"

class Experiment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='experiments')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='experiments')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    job_a = models.ForeignKey(ProcessingJob, on_delete=models.CASCADE, related_name='experiment_a')
    job_b = models.ForeignKey(ProcessingJob, on_delete=models.CASCADE, related_name='experiment_b')
    comparison_metrics = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Experiment: {self.name}"
