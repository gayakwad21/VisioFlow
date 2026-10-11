import mimetypes
import os

from rest_framework import serializers
from .models import Project, UploadedFile


IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
MAX_UPLOAD_SIZE = 100 * 1024 * 1024
VIDEO_MIME_TYPES = {
    'video/mp4', 'video/x-msvideo', 'video/quicktime',
    'video/x-matroska', 'video/webm', 'application/octet-stream',
}


class UploadedFileSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = UploadedFile
        fields = ('id', 'project', 'user', 'file', 'file_url', 'file_type', 'original_name',
                  'file_size', 'width', 'height', 'channels', 'metadata', 'created_at')
        read_only_fields = ('user', 'file_type', 'original_name', 'file_size', 'width',
                            'height', 'channels', 'metadata', 'created_at')

    def validate_project(self, project):
        request = self.context.get('request')
        if not request or project.owner_id != request.user.id:
            raise serializers.ValidationError('Choose a project that belongs to your account.')
        return project

    def validate_file(self, uploaded_file):
        if uploaded_file.size <= 0:
            raise serializers.ValidationError('The uploaded file is empty.')
        if uploaded_file.size > MAX_UPLOAD_SIZE:
            raise serializers.ValidationError('File size must not exceed 100 MB.')

        original_name = os.path.basename(uploaded_file.name.replace('\\', '/')).strip()
        extension = os.path.splitext(original_name)[1].lower()
        if extension not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
            raise serializers.ValidationError('Upload a JPG, JPEG, PNG, BMP, WEBP, MP4, AVI, MOV, MKV, or WEBM file.')

        mime_type = (uploaded_file.content_type or mimetypes.guess_type(original_name)[0] or '').lower()
        if extension in IMAGE_EXTENSIONS:
            if mime_type and mime_type not in {'application/octet-stream', 'image/jpeg', 'image/png',
                                               'image/bmp', 'image/webp', 'image/x-ms-bmp'}:
                raise serializers.ValidationError('The image MIME type does not match the file extension.')
            try:
                from PIL import Image
                uploaded_file.seek(0)
                with Image.open(uploaded_file) as image:
                    expected_formats = {
                        '.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG',
                        '.bmp': 'BMP', '.webp': 'WEBP',
                    }
                    if image.format != expected_formats[extension]:
                        raise serializers.ValidationError('The image content does not match its filename extension.')
                    image.verify()
                uploaded_file.seek(0)
            except serializers.ValidationError:
                raise
            except (OSError, ValueError) as exc:
                raise serializers.ValidationError('The uploaded image is invalid or cannot be decoded.') from exc
        elif mime_type and mime_type not in VIDEO_MIME_TYPES and not mime_type.startswith('video/'):
            raise serializers.ValidationError('The video MIME type does not match the file extension.')

        uploaded_file.seek(0)
        uploaded_file._visionforge_original_name = original_name
        uploaded_file._visionforge_extension = extension
        return uploaded_file

    def create(self, validated_data):
        uploaded_file = validated_data['file']
        original_name = uploaded_file._visionforge_original_name
        safe_stem = os.path.splitext(original_name)[0]
        from django.utils.text import get_valid_filename
        stored_name = f'{get_valid_filename(safe_stem) or "upload"}{uploaded_file._visionforge_extension}'
        uploaded_file.name = stored_name
        extension = uploaded_file._visionforge_extension
        file_type = 'VIDEO' if extension in VIDEO_EXTENSIONS else 'IMAGE'
        validated_data['user'] = self.context['request'].user
        validated_data['original_name'] = original_name[:255]
        validated_data['file_size'] = uploaded_file.size
        validated_data['file_type'] = file_type
        validated_data['metadata'] = {'mime_type': uploaded_file.content_type or mimetypes.guess_type(original_name)[0] or ''}

        instance = super().create(validated_data)
        if file_type == 'IMAGE':
            from PIL import Image
            with Image.open(instance.file.path) as image:
                instance.width, instance.height = image.size
                instance.channels = len(image.getbands())
            instance.save(update_fields=('width', 'height', 'channels'))
        else:
            import cv2
            capture = cv2.VideoCapture(instance.file.path)
            try:
                if not capture.isOpened():
                    instance.file.delete(save=False)
                    instance.delete()
                    raise serializers.ValidationError({'file': 'The uploaded video could not be opened.'})
                has_frame, frame = capture.read()
                if not has_frame or frame is None:
                    instance.file.delete(save=False)
                    instance.delete()
                    raise serializers.ValidationError({'file': 'The uploaded video contains no readable frames.'})
                instance.width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                instance.height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                instance.channels = int(frame.shape[2]) if len(frame.shape) == 3 else 1
                fps = float(capture.get(cv2.CAP_PROP_FPS))
                frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
                instance.metadata.update({
                    'fps': fps if fps > 0 else None,
                    'frame_count': frame_count if frame_count > 0 else None,
                    'duration_seconds': round(frame_count / fps, 3) if fps > 0 and frame_count > 0 else None,
                })
                instance.save(update_fields=('width', 'height', 'channels', 'metadata'))
            finally:
                capture.release()
        return instance

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            path = f'/api/files/{obj.pk}/download/'
            return request.build_absolute_uri(path) if request else path
        return None

class ProjectSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    pipeline_count = serializers.SerializerMethodField()
    file_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ('id', 'owner', 'owner_username', 'name', 'description', 'pipeline_count',
                  'file_count', 'created_at', 'updated_at')
        read_only_fields = ('owner', 'created_at', 'updated_at')

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Project name cannot be blank.')
        return value

    def get_pipeline_count(self, obj):
        return obj.pipelines.count()

    def get_file_count(self, obj):
        return obj.files.count()
