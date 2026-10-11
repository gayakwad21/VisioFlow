from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from backend.pipelines.models import Pipeline
from backend.processing.models import ProcessingJob, ProcessingResult
from backend.processing.views import ProcessingJobViewSet
from backend.projects.models import Project


class ProcessingJobAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='jobowner', password='password123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.project = Project.objects.create(owner=self.user, name='Job project')
        self.pipeline = Pipeline.objects.create(
            project=self.project, owner=self.user, name='Job pipeline', graph_data={'nodes': [], 'edges': []}
        )
        self.job = ProcessingJob.objects.create(
            project=self.project, pipeline=self.pipeline, user=self.user, status='FAILED'
        )

    @patch('backend.processing.views.submit_processing_job')
    def test_retry_queues_a_new_owned_job(self, submit_job):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/jobs/{self.job.id}/retry/', format='json')
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data['status'], 'QUEUED')
        self.assertEqual(ProcessingJob.objects.count(), 2)
        submit_job.assert_called_once_with(response.data['id'])

    def test_another_user_cannot_retry_job(self):
        other = User.objects.create_user(username='jobintruder', password='password123')
        client = APIClient()
        client.force_authenticate(user=other)
        response = client.post(f'/api/jobs/{self.job.id}/retry/', format='json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ProcessingJob.objects.count(), 1)

    def test_video_result_api_uses_mp4_content_type_and_protected_url(self):
        result = ProcessingResult.objects.create(job=self.job)
        result.output_file.save('processed.mp4', ContentFile(b'video result'), save=True)

        job_response = self.client.get(f'/api/jobs/{self.job.id}/')
        self.assertEqual(job_response.status_code, 200)
        serialized_result = job_response.data['result']
        self.assertEqual(serialized_result['output_url'], f'http://testserver/api/jobs/{self.job.id}/result/')
        self.assertEqual(serialized_result['output_content_type'], 'video/mp4')
        self.assertEqual(serialized_result['output_size_bytes'], len(b'video result'))

        other = User.objects.create_user(username='resultintruder', password='password123')
        other_client = APIClient()
        other_client.force_authenticate(user=other)
        self.assertEqual(other_client.get(f'/api/jobs/{self.job.id}/result/').status_code, 404)

        view = ProcessingJobViewSet.as_view({'get': 'result_file'})
        factory = APIRequestFactory()
        request = factory.get(f'/api/jobs/{self.job.id}/result/', HTTP_RANGE='bytes=0-4')
        force_authenticate(request, user=self.user)
        result_response = view(request, pk=self.job.id)
        try:
            self.assertEqual(result_response.status_code, 206)
            self.assertEqual(result_response['Content-Type'], 'video/mp4')
            self.assertEqual(result_response['Accept-Ranges'], 'bytes')
            self.assertEqual(result_response['Content-Range'], 'bytes 0-4/12')
            self.assertNotIn('attachment', result_response['Content-Disposition'])
            self.assertEqual(b''.join(result_response.streaming_content), b'video')
        finally:
            result_response.close()
            result.output_file.delete(save=False)

    def test_experiment_cannot_expose_another_users_jobs(self):
        from backend.processing.models import Experiment

        other_user = User.objects.create_user(username='experimentintruder', password='password123')
        foreign_project = Project.objects.create(owner=other_user, name='Private project')
        foreign_pipeline = Pipeline.objects.create(
            project=foreign_project, owner=other_user, name='Private pipeline',
            graph_data={'nodes': [], 'edges': []},
        )
        foreign_job = ProcessingJob.objects.create(
            project=foreign_project, pipeline=foreign_pipeline, user=other_user,
        )
        response = self.client.post('/api/experiments/', {
            'project': self.project.id,
            'name': 'Unauthorized comparison',
            'job_a': self.job.id,
            'job_b': foreign_job.id,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Experiment.objects.count(), 0)

    def test_experiment_jobs_must_match_owned_project(self):
        from backend.processing.models import Experiment

        second_pipeline = Pipeline.objects.create(
            project=self.project, owner=self.user, name='Second pipeline',
            graph_data={'nodes': [], 'edges': []},
        )
        second_job = ProcessingJob.objects.create(
            project=self.project, pipeline=second_pipeline, user=self.user,
        )
        response = self.client.post('/api/experiments/', {
            'project': self.project.id, 'name': 'Owned comparison',
            'job_a': self.job.id, 'job_b': second_job.id,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Experiment.objects.count(), 1)


class ProcessingTaskTests(TransactionTestCase):
    def test_worker_claims_queued_job_and_persists_terminal_status(self):
        from backend.processing.tasks import process_processing_job

        user = User.objects.create_user(username='workeruser', password='password123')
        project = Project.objects.create(owner=user, name='Worker project')
        pipeline = Pipeline.objects.create(
            project=project, owner=user, name='Worker pipeline',
            graph_data={'nodes': [], 'edges': []},
        )
        job = ProcessingJob.objects.create(
            project=project, pipeline=pipeline, user=user, status='QUEUED',
        )

        def finish(processing_job):
            self.assertEqual(processing_job.status, 'PROCESSING')
            processing_job.status = 'COMPLETED'
            processing_job.progress = 100
            processing_job.save(update_fields=('status', 'progress'))
            return True

        with patch('backend.processing.tasks.execute_processing_job', side_effect=finish):
            process_processing_job(job.id)

        job.refresh_from_db()
        self.assertEqual(job.status, 'COMPLETED')
        self.assertEqual(job.progress, 100)
