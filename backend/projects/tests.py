from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from backend.projects.models import Project, UploadedFile
from PIL import Image
from backend.pipelines.models import Pipeline
from backend.processing.models import ProcessingJob

class ProjectAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='projuser', password='password123')
        self.client.force_authenticate(user=self.user)

    def test_create_project(self):
        response = self.client.post('/api/projects/', {
            'name': 'CV Test Project',
            'description': 'Testing computer vision project creation'
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(Project.objects.first().owner, self.user)

    def test_other_user_cannot_access_owner_project_or_files(self):
        project = Project.objects.create(owner=self.user, name='Private Project')
        uploaded = UploadedFile.objects.create(
            project=project,
            user=self.user,
            file='projects/test/uploads/sample.jpg',
            original_name='sample.jpg',
            file_size=128,
            file_type='IMAGE',
        )

        other_user = User.objects.create_user(username='otheruser', password='password123')
        other_client = APIClient(raise_request_exception=False)
        other_client.force_authenticate(user=other_user)

        project_detail = other_client.get(f'/api/projects/{project.id}/')
        self.assertEqual(project_detail.status_code, 404)

        project_list = other_client.get('/api/projects/')
        self.assertEqual(project_list.status_code, 200)
        self.assertEqual(len(project_list.data), 0)

        file_detail = other_client.get(f'/api/files/{uploaded.id}/')
        self.assertEqual(file_detail.status_code, 404)
        self.assertEqual(other_client.delete(f'/api/files/{uploaded.id}/').status_code, 404)

        file_list = other_client.get('/api/files/')
        self.assertEqual(file_list.status_code, 200)
        self.assertEqual(len(file_list.data), 0)

    def test_project_crud_search_and_ownership(self):
        created = self.client.post('/api/projects/', {'name': 'Vision project', 'description': 'Object tests'})
        self.assertEqual(created.status_code, 201)
        project_id = created.data['id']

        updated = self.client.patch(f'/api/projects/{project_id}/', {'name': 'Renamed project'}, format='json')
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data['name'], 'Renamed project')
        self.assertEqual(self.client.get('/api/projects/?search=renamed').data[0]['id'], project_id)

        other = User.objects.create_user(username='projectintruder', password='password123')
        other_client = APIClient()
        other_client.force_authenticate(user=other)
        self.assertEqual(other_client.patch(
            f'/api/projects/{project_id}/', {'name': 'Hijacked'}, format='json'
        ).status_code, 404)
        self.assertEqual(other_client.delete(f'/api/projects/{project_id}/').status_code, 404)

        deleted = self.client.delete(f'/api/projects/{project_id}/')
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(Project.objects.filter(pk=project_id).exists())

    def test_dashboard_contains_only_authenticated_users_data(self):
        own_project = Project.objects.create(owner=self.user, name='My dashboard project')
        own_pipeline = Pipeline.objects.create(
            project=own_project,
            owner=self.user,
            name='My pipeline',
            graph_data={'nodes': [{'id': 'gray', 'type': 'grayscale', 'data': {}}], 'edges': []},
        )
        ProcessingJob.objects.create(
            project=own_project, pipeline=own_pipeline, user=self.user, status='COMPLETED'
        )
        other = User.objects.create_user(username='dashboardother', password='password123')
        other_project = Project.objects.create(owner=other, name='Not my project')
        other_pipeline = Pipeline.objects.create(
            project=other_project, owner=other, name='Other pipeline', graph_data={'nodes': [], 'edges': []}
        )
        ProcessingJob.objects.create(
            project=other_project, pipeline=other_pipeline, user=other, status='FAILED'
        )

        response = self.client.get('/api/analytics/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['projects_count'], 1)
        self.assertEqual(response.data['pipelines_count'], 1)
        self.assertEqual(response.data['jobs_count'], 1)
        self.assertEqual(response.data['completed_jobs'], 1)
        self.assertEqual(response.data['failed_jobs'], 0)
        self.assertEqual([item['name'] for item in response.data['recent_projects']], ['My dashboard project'])
        self.assertEqual([item['pipeline_name'] for item in response.data['recent_jobs']], ['My pipeline'])
        self.assertEqual(response.data['operation_counts'], {'grayscale': 1})
        self.assertEqual(response.data['most_used_pipelines'][0]['job_count'], 1)

    def test_upload_image_metadata_and_delete(self):
        project = Project.objects.create(owner=self.user, name='Uploads')
        image_bytes = BytesIO()
        Image.new('RGB', (12, 8), color=(20, 40, 60)).save(image_bytes, format='PNG')
        image_bytes.seek(0)
        upload = SimpleUploadedFile('sample.png', image_bytes.read(), content_type='image/png')

        response = self.client.post('/api/files/', {'project': project.id, 'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn('file', response.data)
        self.assertIn('/api/files/', response.data['file_url'])
        self.assertEqual(response.data['file_type'], 'IMAGE')
        self.assertEqual(response.data['width'], 12)
        self.assertEqual(response.data['height'], 8)
        self.assertEqual(response.data['channels'], 3)
        uploaded_id = response.data['id']

        other = User.objects.create_user(username='downloadintruder', password='password123')
        other_client = APIClient()
        other_client.force_authenticate(user=other)
        self.assertEqual(other_client.get(f'/api/files/{uploaded_id}/download/').status_code, 404)
        file_object = UploadedFile.objects.get(pk=uploaded_id)
        file_api_path = response.data['file_url'].replace('http://testserver', '')
        preview_response = self.client.get(file_api_path)
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(self.client.get(f'/media/{file_object.file.name}').status_code, 404)

        download = self.client.get(f'/api/files/{uploaded_id}/download/')
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download['Content-Type'], 'image/png')
        for file_response in (preview_response, download):
            stream = getattr(file_response, 'file_to_stream', None)
            if stream:
                stream.close()

    def test_owner_can_delete_uploaded_file(self):
        project = Project.objects.create(owner=self.user, name='Delete uploads')
        uploaded = UploadedFile.objects.create(
            project=project,
            user=self.user,
            file='projects/delete/uploads/sample.png',
            original_name='sample.png',
            file_size=20,
            file_type='IMAGE',
        )
        deleted = self.client.delete(f'/api/files/{uploaded.id}/')
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(UploadedFile.objects.filter(pk=uploaded.id).exists())

    def test_reject_invalid_upload_and_foreign_project_upload(self):
        project = Project.objects.create(owner=self.user, name='Uploads')
        invalid = SimpleUploadedFile('payload.exe', b'not an image', content_type='application/octet-stream')
        response = self.client.post('/api/files/', {'project': project.id, 'file': invalid}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(UploadedFile.objects.exists())

        image_bytes = BytesIO()
        Image.new('RGB', (2, 2)).save(image_bytes, format='PNG')
        mismatched_image = SimpleUploadedFile('wrong.jpg', image_bytes.getvalue(), content_type='image/jpeg')
        response = self.client.post(
            '/api/files/', {'project': project.id, 'file': mismatched_image}, format='multipart'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(UploadedFile.objects.exists())

        invalid_video = SimpleUploadedFile('clip.mp4', b'not a video', content_type='video/mp4')
        response = self.client.post(
            '/api/files/', {'project': project.id, 'file': invalid_video}, format='multipart'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(UploadedFile.objects.exists())

        other = User.objects.create_user(username='fileintruder', password='password123')
        other_client = APIClient()
        other_client.force_authenticate(user=other)
        image_bytes = BytesIO()
        Image.new('RGB', (2, 2)).save(image_bytes, format='PNG')
        foreign_upload = SimpleUploadedFile('foreign.png', image_bytes.getvalue(), content_type='image/png')
        response = other_client.post(
            '/api/files/', {'project': project.id, 'file': foreign_upload}, format='multipart'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(UploadedFile.objects.exists())

    def test_project_and_file_apis_require_authentication(self):
        anonymous = APIClient()
        self.assertEqual(anonymous.get('/api/projects/').status_code, 403)
        self.assertEqual(anonymous.get('/api/files/').status_code, 403)
