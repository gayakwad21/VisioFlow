import os
from django.db import models
from django.contrib.auth.models import User

class Project(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

def upload_file_path(instance, filename):
    return f"projects/{instance.project.id}/uploads/{filename}"

class UploadedFile(models.Model):
    FILE_TYPES = (
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='files')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_files')
    file = models.FileField(upload_to=upload_file_path)
    file_type = models.CharField(max_length=10, choices=FILE_TYPES, default='IMAGE')
    original_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(default=0)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    channels = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.original_name} - {self.project.name}"
