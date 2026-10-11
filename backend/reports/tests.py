from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from backend.pipelines.models import Pipeline
from backend.processing.models import ProcessingJob, ProcessingResult
from backend.projects.models import Project
from backend.reports.models import Report


class ReportAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reportowner', password='password123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.project = Project.objects.create(owner=self.user, name='Report project')
        self.pipeline = Pipeline.objects.create(
            project=self.project,
            owner=self.user,
            name='Edge pipeline',
            graph_data={'nodes': [{'id': 'n1', 'type': 'canny', 'data': {'threshold1': 25}}], 'edges': []},
        )

    def test_report_pages_are_served(self):
        response = self.client.get('/reports.html')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="reports-list"')

        response = self.client.get('/report-detail.html?id=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="report-print-area"')

    def test_generate_report_from_owned_job(self):
        job = ProcessingJob.objects.create(
            project=self.project,
            pipeline=self.pipeline,
            user=self.user,
            status='COMPLETED',
            processing_time=0.42,
        )
        ProcessingResult.objects.create(
            job=job,
            metrics={'width': 64, 'height': 48},
            logs=['Pipeline complete'],
        )

        response = self.client.post('/api/reports/generate/', {'job_id': job.id}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['content_json']['pipeline']['steps'][0]['parameters']['threshold1'], 25)
        self.assertEqual(response.data['content_json']['pipeline']['steps'][0]['status'], 'not_available')
        self.assertEqual(response.data['content_json']['metrics']['width'], 64)
        self.assertIn('Edge pipeline', response.data['summary'])
        self.assertEqual(response.data['pipeline_name'], 'Edge pipeline')
        self.assertEqual(response.data['job_status'], 'COMPLETED')
        self.assertNotIn('pdf_file', response.data)
        self.assertNotIn('pdf_url', response.data)
        self.assertEqual(Report.objects.count(), 1)
        detail = self.client.get(f"/api/reports/{response.data['id']}/")
        self.assertEqual(detail.status_code, 200, detail.data)

    def test_report_generation_and_creation_enforce_ownership(self):
        other = User.objects.create_user(username='reportother', password='password123')
        other_project = Project.objects.create(owner=other, name='Private report project')
        other_pipeline = Pipeline.objects.create(
            project=other_project, owner=other, name='Private pipeline', graph_data={'nodes': [], 'edges': []}
        )
        other_job = ProcessingJob.objects.create(
            project=other_project, pipeline=other_pipeline, user=other, status='COMPLETED'
        )

        response = self.client.post('/api/reports/generate/', {'job_id': other_job.id}, format='json')
        self.assertEqual(response.status_code, 404)
        response = self.client.post('/api/reports/', {
            'project': other_project.id,
            'pipeline': other_pipeline.id,
            'job': other_job.id,
            'title': 'Unauthorized report',
            'summary': 'Should not be created',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Report.objects.exists())
        private_report = Report.objects.create(
            project=self.project,
            user=self.user,
            pipeline=self.pipeline,
            title='Owner-only report',
        )
        self.client.force_authenticate(user=other)
        self.assertEqual(self.client.get(f'/api/reports/{private_report.id}/').status_code, 404)
        self.assertEqual(self.client.get('/api/reports/').data, [])

    def test_report_captures_owned_media_metadata_and_execution_order(self):
        import tempfile

        from backend.projects.models import UploadedFile

        graph = {
            'nodes': [
                {'id': 'output', 'type': 'output', 'data': {}},
                {'id': 'blur', 'type': 'gaussianBlur', 'data': {'kernelSize': 5}},
                {'id': 'source', 'type': 'imageSource', 'data': {'imageName': 'stale-sample.jpg'}},
            ],
            'edges': [
                {'source': 'source', 'target': 'blur'},
                {'source': 'blur', 'target': 'output'},
            ],
        }
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            uploaded = UploadedFile.objects.create(
                project=self.project,
                user=self.user,
                file=SimpleUploadedFile('input-image.png', b'original-image-bytes'),
                original_name='input-image.png',
                file_type='IMAGE',
                file_size=20,
                width=640,
                height=480,
                channels=3,
                metadata={'mime_type': 'image/png'},
            )
            job = ProcessingJob.objects.create(
                project=self.project,
                pipeline=self.pipeline,
                pipeline_graph=graph,
                user=self.user,
                input_file=uploaded,
                status='COMPLETED',
                processing_time=0.25,
            )
            result = ProcessingResult.objects.create(
                job=job,
                metrics={'width': 640, 'height': 480},
                logs=[
                    "Node 'source' (ImageSource) initialized.",
                    "Node 'blur' (Gaussian Blur) completed.",
                    "Node 'output' (Output) completed.",
                ],
            )
            result.output_file.save('actual-output.png', ContentFile(b'processed-image-bytes'), save=True)

            response = self.client.post('/api/reports/generate/', {'job_id': job.id}, format='json')

            self.assertEqual(response.status_code, 201, response.data)
            content = response.data['content_json']
            self.assertEqual([step['node_id'] for step in content['pipeline']['steps']],
                             ['source', 'blur', 'output'])
            self.assertEqual([step['status'] for step in content['pipeline']['steps']],
                             ['success', 'success', 'success'])
            self.assertEqual(content['input']['name'], 'input-image.png')
            self.assertEqual(content['input']['size_bytes'], 20)
            self.assertEqual(content['input']['width'], 640)
            self.assertEqual(content['input']['height'], 480)
            self.assertEqual(content['input']['content_type'], 'image/png')
            self.assertTrue(content['input']['url'].endswith(f'/api/files/{uploaded.id}/download/'))
            self.assertEqual(content['pipeline']['graph_data']['nodes'][2]['data']['imageName'],
                             'input-image.png')
            self.assertEqual(content['pipeline']['steps'][0]['parameters']['imageName'],
                             'input-image.png')
            self.assertEqual(content['output']['filename'], 'actual-output.png')
            self.assertEqual(content['output']['size_bytes'], len(b'processed-image-bytes'))
            self.assertTrue(content['output']['url'].endswith(f'/api/jobs/{job.id}/result/'))
            input_response = self.client.get(f'/api/files/{uploaded.id}/download/')
            output_response = self.client.get(f'/api/jobs/{job.id}/result/')
            self.assertEqual(b''.join(input_response.streaming_content), b'original-image-bytes')
            self.assertEqual(b''.join(output_response.streaming_content), b'processed-image-bytes')

    def test_report_output_download_is_authenticated_and_owned(self):
        job = ProcessingJob.objects.create(
            project=self.project,
            pipeline=self.pipeline,
            user=self.user,
            status='COMPLETED',
        )
        result = ProcessingResult.objects.create(job=job)
        result.output_file.save('processed.png', ContentFile(b'image-bytes'), save=True)

        response = self.client.get(f'/api/jobs/{job.id}/result/?download=1')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content), b'image-bytes')

        ranged_download = self.client.get(
            f'/api/jobs/{job.id}/result/?download=1',
            HTTP_RANGE='bytes=0-4',
        )
        self.assertEqual(ranged_download.status_code, 206)
        self.assertIn('attachment', ranged_download['Content-Disposition'])
        self.assertEqual(b''.join(ranged_download.streaming_content), b'image')

        other = User.objects.create_user(username='reportother', password='password123')
        self.client.force_authenticate(user=other)
        response = self.client.get(f'/api/jobs/{job.id}/result/?download=1')
        self.assertEqual(response.status_code, 404)

        self.client.force_authenticate(user=None)
        response = self.client.get(f'/api/jobs/{job.id}/result/?download=1')
        self.assertEqual(response.status_code, 403)

        result.output_file.delete(save=False)
