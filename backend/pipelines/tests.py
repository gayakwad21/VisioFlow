import os
import json
import shutil
import subprocess
import tempfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from PIL import Image
from fastapi.testclient import TestClient

from cv_service.main import app
from backend.projects.models import Project, UploadedFile
from backend.pipelines.models import Pipeline
from backend.processing.models import ProcessingJob
from backend.pipelines.services import execute_processing_job

class PipelineAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='pipeuser', password='password123')
        self.client.force_authenticate(user=self.user)
        self.project = Project.objects.create(owner=self.user, name='Pipeline Test Project')

    def test_create_and_ai_generate_pipeline(self):
        # Test pipeline creation with json format
        response = self.client.post('/api/pipelines/', {
            'project': self.project.id,
            'name': 'Edge Detection Pipeline',
            'graph_data': {'nodes': [], 'edges': []}
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Pipeline.objects.count(), 1)

        # Test AI synthesis endpoint
        ai_resp = self.client.post('/api/pipelines/generate-ai/', {
            'prompt': 'Detect edges and blur image'
        }, format='json')
        self.assertEqual(ai_resp.status_code, 200)
        self.assertIn('graph_data', ai_resp.data)
        self.assertIn('explanation', ai_resp.data)

        generated = self.client.post('/api/pipelines/generate-ai/', {
            'prompt': 'Detect edges, remove noise and find contours'
        }, format='json')
        self.assertEqual(generated.status_code, 200)
        types = [node['type'] for node in generated.data['graph_data']['nodes']]
        self.assertEqual(types, ['imageSource', 'blur', 'grayscale', 'canny', 'findContours', 'output'])
        self.assertEqual(len(generated.data['graph_data']['edges']), len(types) - 1)

    def test_other_user_cannot_access_owner_pipeline_or_jobs(self):
        pipeline = Pipeline.objects.create(
            project=self.project,
            owner=self.user,
            name='Private Pipeline',
            graph_data={'nodes': [], 'edges': []}
        )

        other_user = User.objects.create_user(username='otherpipeuser', password='password123')
        other_client = APIClient()
        other_client.force_authenticate(user=other_user)

        pipeline_list = other_client.get('/api/pipelines/')
        self.assertEqual(pipeline_list.status_code, 200)
        self.assertEqual(len(pipeline_list.data), 0)

        pipeline_detail = other_client.get(f'/api/pipelines/{pipeline.id}/')
        self.assertEqual(pipeline_detail.status_code, 404)

        job_list = other_client.get('/api/jobs/')
        self.assertEqual(job_list.status_code, 200)
        self.assertEqual(len(job_list.data), 0)

    def test_cannot_create_pipeline_in_another_users_project(self):
        other_user = User.objects.create_user(username='foreignprojectowner', password='password123')
        foreign_project = Project.objects.create(owner=other_user, name='Not yours')
        response = self.client.post('/api/pipelines/', {
            'project': foreign_project.id,
            'name': 'Unauthorized pipeline',
            'graph_data': {'nodes': [], 'edges': []}
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Pipeline.objects.exists())

    @patch('backend.pipelines.views.submit_processing_job')
    def test_pipeline_run_queues_job_for_owner(self, submit_job):
        from backend.projects.models import UploadedFile

        input_file = UploadedFile.objects.create(
            project=self.project, user=self.user, file='projects/test/uploads/input.png',
            original_name='input.png', file_size=10, file_type='IMAGE'
        )
        pipeline = Pipeline.objects.create(
            project=self.project, owner=self.user, name='Runnable',
            graph_data={
                'nodes': [
                    {'id': 'source', 'type': 'imageSource', 'data': {}},
                    {'id': 'gray', 'type': 'grayscale', 'data': {}},
                    {'id': 'output', 'type': 'output', 'data': {}},
                ],
                'edges': [{'source': 'source', 'target': 'gray'}, {'source': 'gray', 'target': 'output'}],
            }
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f'/api/pipelines/{pipeline.id}/run/',
                {'input_file_id': input_file.id},
                format='json',
            )
        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(response.data['job']['status'], 'QUEUED')
        self.assertEqual(response.data['job']['pipeline_graph'], pipeline.graph_data)
        self.assertIsNotNone(response.data['job']['pipeline_version'])
        submit_job.assert_called_once_with(response.data['job']['id'])

    def test_pipeline_run_rejects_missing_or_invalid_execution_inputs(self):
        pipeline = Pipeline.objects.create(
            project=self.project,
            owner=self.user,
            name='Invalid graph',
            graph_data={'nodes': [{'id': 'source', 'type': 'imageSource', 'data': {}}], 'edges': []},
        )
        missing_input = self.client.post(f'/api/pipelines/{pipeline.id}/run/', {}, format='json')
        self.assertEqual(missing_input.status_code, 400)

        pipeline.graph_data = {
            'nodes': [
                {'id': 'source', 'type': 'imageSource', 'data': {}},
                {'id': 'unknown', 'type': 'python', 'data': {}},
                {'id': 'output', 'type': 'output', 'data': {}},
            ],
            'edges': [{'source': 'source', 'target': 'unknown'}, {'source': 'unknown', 'target': 'output'}],
        }
        pipeline.save(update_fields=('graph_data',))
        from backend.projects.models import UploadedFile
        input_file = UploadedFile.objects.create(
            project=self.project, user=self.user, file='projects/test/uploads/input.png',
            original_name='input.png', file_size=10, file_type='IMAGE'
        )
        invalid_graph = self.client.post(
            f'/api/pipelines/{pipeline.id}/run/', {'input_file_id': input_file.id}, format='json'
        )
        self.assertEqual(invalid_graph.status_code, 400)
        self.assertIn('Unsupported pipeline operation', str(invalid_graph.data))

    def test_pipeline_versions_are_created_on_meaningful_saves_and_can_be_restored(self):
        graph_one = {
            'nodes': [
                {'id': 'source', 'type': 'imageSource', 'data': {}},
                {'id': 'output', 'type': 'output', 'data': {}},
            ],
            'edges': [{'source': 'source', 'target': 'output'}],
        }
        response = self.client.post('/api/pipelines/', {
            'project': self.project.id, 'name': 'Versioned', 'description': 'first',
            'graph_data': graph_one,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        pipeline_id = response.data['id']
        self.assertEqual(response.data['versions'][0]['version_number'], 1)

        graph_two = {
            'nodes': graph_one['nodes'] + [{'id': 'gray', 'type': 'grayscale', 'data': {}}],
            'edges': [{'source': 'source', 'target': 'gray'}, {'source': 'gray', 'target': 'output'}],
        }
        update = self.client.patch(f'/api/pipelines/{pipeline_id}/', {
            'graph_data': graph_two, 'description': 'second',
        }, format='json')
        self.assertEqual(update.status_code, 200, update.data)
        self.assertEqual([version['version_number'] for version in update.data['versions']], [2, 1])
        repeat = self.client.patch(f'/api/pipelines/{pipeline_id}/', {'description': 'second'}, format='json')
        self.assertEqual([version['version_number'] for version in repeat.data['versions']], [2, 1])

        versions = self.client.get(f'/api/pipelines/{pipeline_id}/versions/')
        self.assertEqual(versions.status_code, 200)
        restore = self.client.post(f'/api/pipelines/{pipeline_id}/restore-version/', {
            'version_id': versions.data[1]['id'],
        }, format='json')
        self.assertEqual(restore.status_code, 200, restore.data)
        self.assertEqual(restore.data['pipeline']['graph_data'], graph_one)
        self.assertEqual(restore.data['version']['version_number'], 3)

    def test_other_user_cannot_read_pipeline_versions(self):
        pipeline = Pipeline.objects.create(
            project=self.project, owner=self.user, name='Private versions',
            graph_data={'nodes': [], 'edges': []},
        )
        other = User.objects.create_user(username='versionintruder', password='password123')
        client = APIClient()
        client.force_authenticate(user=other)
        self.assertEqual(client.get(f'/api/pipelines/{pipeline.id}/versions/').status_code, 404)

    @patch('backend.pipelines.views.submit_processing_job')
    def test_job_uses_the_selected_immutable_pipeline_version(self, submit_job):
        from backend.projects.models import UploadedFile

        first_graph = {
            'nodes': [
                {'id': 'source', 'type': 'imageSource', 'data': {}},
                {'id': 'gray', 'type': 'grayscale', 'data': {}},
                {'id': 'output', 'type': 'output', 'data': {}},
            ],
            'edges': [{'source': 'source', 'target': 'gray'}, {'source': 'gray', 'target': 'output'}],
        }
        created = self.client.post('/api/pipelines/', {
            'project': self.project.id, 'name': 'Runnable versions', 'graph_data': first_graph,
        }, format='json')
        pipeline_id = created.data['id']
        first_version_id = created.data['versions'][0]['id']
        second_graph = {
            'nodes': [
                {'id': 'source', 'type': 'imageSource', 'data': {}},
                {'id': 'output', 'type': 'output', 'data': {}},
            ],
            'edges': [{'source': 'source', 'target': 'output'}],
        }
        self.client.patch(f'/api/pipelines/{pipeline_id}/', {
            'graph_data': second_graph,
        }, format='json')
        input_file = UploadedFile.objects.create(
            project=self.project, user=self.user, file='projects/test/uploads/input.png',
            original_name='input.png', file_size=10, file_type='IMAGE'
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/pipelines/{pipeline_id}/run/', {
                'input_file_id': input_file.id, 'version_id': first_version_id,
            }, format='json')
        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(response.data['job']['pipeline_graph'], first_graph)
        self.assertEqual(response.data['job']['pipeline_version'], created.data['versions'][0]['id'])

    def test_pipeline_rejects_an_input_from_another_project(self):
        from backend.projects.models import UploadedFile
        other_project = Project.objects.create(owner=self.user, name='Other input project')
        other_file = UploadedFile.objects.create(
            project=other_project,
            user=self.user,
            file='projects/other/uploads/input.png',
            original_name='input.png',
            file_size=10,
            file_type='IMAGE',
        )
        pipeline = Pipeline.objects.create(
            project=self.project, owner=self.user, name='Input check', graph_data={'nodes': [], 'edges': []}
        )
        response = self.client.post(
            f'/api/pipelines/{pipeline.id}/run/',
            {'input_file_id': other_file.id},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_python_export_is_valid_and_respects_graph_connections(self):
        pipeline = Pipeline.objects.create(
            project=self.project,
            owner=self.user,
            name='Generated workflow',
            graph_data={
                'nodes': [
                    {'id': 'output', 'type': 'output', 'data': {}},
                    {'id': 'edges', 'type': 'canny', 'data': {'threshold1': 20, 'threshold2': 100}},
                    {'id': 'input', 'type': 'imageSource', 'data': {}},
                    {'id': 'gray', 'type': 'grayscale', 'data': {}},
                ],
                'edges': [
                    {'source': 'input', 'target': 'gray'},
                    {'source': 'gray', 'target': 'edges'},
                    {'source': 'edges', 'target': 'output'},
                ],
            },
        )
        response = self.client.get(f'/api/pipelines/{pipeline.id}/export-python/')
        self.assertEqual(response.status_code, 200)
        code = response.data['python_code']
        compile(code, '<generated-pipeline>', 'exec')
        self.assertLess(code.index('COLOR_BGR2GRAY'), code.index('cv2.Canny'))

    def test_default_pipeline_templates_are_available(self):
        response = APIClient().get('/api/templates/')
        self.assertEqual(response.status_code, 200)
        names = {template['name'] for template in response.data}
        self.assertTrue({'Grayscale', 'Edge Detection', 'Noise Removal', 'Contour Detection'}.issubset(names))

    def test_pipeline_run_integrates_django_job_with_cv_service_result(self):
        image_bytes = BytesIO()
        Image.new('RGB', (32, 24), color=(10, 80, 180)).save(image_bytes, format='PNG')
        image_bytes.seek(0)
        upload_response = self.client.post(
            '/api/files/',
            {'project': self.project.id, 'file': SimpleUploadedFile('source.png', image_bytes.read(), content_type='image/png')},
            format='multipart',
        )
        self.assertEqual(upload_response.status_code, 201, upload_response.data)
        uploaded_file_id = upload_response.data['id']
        pipeline = Pipeline.objects.create(
            project=self.project,
            owner=self.user,
            name='Integrated grayscale',
            graph_data={
                'nodes': [
                    {'id': 'source', 'type': 'imageSource', 'data': {}},
                    {'id': 'gray', 'type': 'grayscale', 'data': {}},
                    {'id': 'edges', 'type': 'canny', 'data': {'threshold1': 25, 'threshold2': 80}},
                    {'id': 'output', 'type': 'output', 'data': {}},
                ],
                'edges': [
                    {'source': 'source', 'target': 'gray'},
                    {'source': 'gray', 'target': 'edges'},
                    {'source': 'edges', 'target': 'output'},
                ],
            },
        )

        service_output_paths = []
        with TestClient(app) as cv_client:
            def call_cv_service(url, json, timeout):
                service_response = cv_client.post('/pipeline/execute', json=json)
                if service_response.is_success:
                    service_output_paths.append(service_response.json()['result_file_path'])
                return SimpleNamespace(
                    ok=service_response.is_success,
                    status_code=service_response.status_code,
                    json=service_response.json,
                    text=service_response.text,
                )

            job = ProcessingJob.objects.create(
                project=self.project,
                pipeline=pipeline,
                pipeline_graph=pipeline.graph_data,
                user=self.user,
                input_file_id=uploaded_file_id,
                status='PROCESSING',
            )
            with patch('backend.pipelines.services.requests.post', side_effect=call_cv_service):
                self.assertTrue(execute_processing_job(job))

        job.refresh_from_db()
        self.assertEqual(job.status, 'COMPLETED')
        self.assertEqual(job.result.metrics['width'], 32)
        self.assertEqual(job.input_file.original_name, 'source.png')
        self.assertIsNotNone(job.result.output_file)
        result_response = self.client.get(f'/api/jobs/{job.id}/')
        self.assertEqual(result_response.status_code, 200)
        self.assertEqual(result_response.data['input_file_name'], 'source.png')
        self.assertNotIn('output_file', result_response.data['result'])
        self.assertEqual(result_response.data['result']['output_content_type'], 'image/png')
        self.assertEqual(result_response.data['result']['output_url'].split('/api/jobs/')[1].split('/')[0], str(job.id))

        job.input_file.file.delete(save=False)
        job.result.output_file.delete(save=False)
        for path in service_output_paths:
            if os.path.exists(path):
                os.remove(path)

    def test_grayscale_video_job_stores_playable_h264_mp4(self):
        graph = {
            'nodes': [
                {'id': 'source', 'type': 'imageSource', 'data': {}},
                {'id': 'gray', 'type': 'grayscale', 'data': {}},
                {'id': 'output', 'type': 'output', 'data': {}},
            ],
            'edges': [
                {'source': 'source', 'target': 'gray'},
                {'source': 'gray', 'target': 'output'},
            ],
        }
        self._assert_video_job_stores_playable_h264_mp4(graph)

    def test_grayscale_blur_canny_video_job_stores_playable_h264_mp4(self):
        graph = {
            'nodes': [
                {'id': 'source', 'type': 'imageSource', 'data': {}},
                {'id': 'gray', 'type': 'grayscale', 'data': {}},
                {'id': 'blur', 'type': 'gaussianBlur', 'data': {'kernelSize': 5}},
                {'id': 'canny', 'type': 'canny', 'data': {'threshold1': 20, 'threshold2': 90}},
                {'id': 'output', 'type': 'output', 'data': {}},
            ],
            'edges': [
                {'source': 'source', 'target': 'gray'},
                {'source': 'gray', 'target': 'blur'},
                {'source': 'blur', 'target': 'canny'},
                {'source': 'canny', 'target': 'output'},
            ],
        }
        self._assert_video_job_stores_playable_h264_mp4(graph)

    def _assert_video_job_stores_playable_h264_mp4(self, graph):
        ffmpeg = shutil.which('ffmpeg')
        ffprobe = shutil.which('ffprobe')
        if not ffmpeg or not ffprobe:
            self.skipTest('FFmpeg and ffprobe are required for the H.264 video integration test.')

        supplied_source = os.environ.get('VISIONFLOW_TEST_VIDEO')
        cleanup_source = not supplied_source
        if supplied_source:
            source_path = os.path.abspath(supplied_source)
        else:
            with tempfile.NamedTemporaryFile(suffix='.mp4', dir=settings.MEDIA_ROOT, delete=False) as source:
                source_path = source.name
            source_writer = cv2.VideoWriter(
                source_path, cv2.VideoWriter_fourcc(*'mp4v'), 12.0, (64, 48)
            )
            if not source_writer.isOpened():
                os.remove(source_path)
                self.skipTest('The installed OpenCV build cannot create the MP4 input fixture.')
            try:
                for index in range(8):
                    source_writer.write(np.full((48, 64, 3), index * 20, dtype=np.uint8))
            finally:
                source_writer.release()

        input_capture = cv2.VideoCapture(source_path)
        if not input_capture.isOpened():
            input_capture.release()
            if cleanup_source:
                os.remove(source_path)
            self.fail('The video processing test input could not be opened.')
        expected_width = int(input_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        expected_height = int(input_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        expected_frame_count = int(input_capture.get(cv2.CAP_PROP_FRAME_COUNT))
        input_capture.release()

        relative_path = os.path.relpath(source_path, settings.MEDIA_ROOT)
        uploaded_file = UploadedFile.objects.create(
            project=self.project,
            user=self.user,
            file=relative_path,
            file_type='VIDEO',
            original_name='video-integration.mp4',
            file_size=os.path.getsize(source_path),
            width=expected_width,
            height=expected_height,
            channels=3,
            metadata = {'mime_type': 'video/mp4'},
        )
        service_output_paths = []
        stored_output_paths = []
        try:
            with TestClient(app) as cv_client:
                def call_cv_service(url, json, timeout):
                    service_response = cv_client.post('/pipeline/execute', json=json)
                    if service_response.is_success:
                        service_output_paths.append(service_response.json()['result_file_path'])
                    return SimpleNamespace(
                        ok=service_response.is_success,
                        status_code=service_response.status_code,
                        json=service_response.json,
                        text=service_response.text,
                    )

                pipeline = Pipeline.objects.create(
                    project=self.project,
                    owner=self.user,
                    name='Video integration',
                    graph_data=graph,
                )
                job = ProcessingJob.objects.create(
                    project=self.project,
                    pipeline=pipeline,
                    pipeline_graph=graph,
                    user=self.user,
                    input_file=uploaded_file,
                    status='PROCESSING',
                )
                with patch('backend.pipelines.services.requests.post', side_effect=call_cv_service):
                    self.assertTrue(execute_processing_job(job))

                job.refresh_from_db()
                self.assertEqual(job.status, 'COMPLETED')
                self.assertGreater(job.result.metrics['frame_count'], 0)
                self.assertEqual(job.result.metrics['frame_count'], expected_frame_count)
                self.assertEqual(job.result.metrics['width'], expected_width)
                self.assertEqual(job.result.metrics['height'], expected_height)
                self.assertTrue(os.path.isfile(job.result.output_file.path))
                self.assertGreater(os.path.getsize(job.result.output_file.path), 0)
                stored_output_paths.append(job.result.output_file.path)
                self.assertEqual(job.result.metrics['output_format'], 'MP4 (H.264)')

                probe = subprocess.run(
                    [
                        ffprobe, '-v', 'error', '-select_streams', 'v:0',
                        '-show_entries', 'stream=codec_name,width,height,nb_frames',
                        '-show_entries', 'format=format_name',
                        '-of', 'json', job.result.output_file.path,
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                metadata = json.loads(probe.stdout)
                self.assertEqual(metadata['streams'][0]['codec_name'], 'h264')
                self.assertEqual(
                    (metadata['streams'][0]['width'], metadata['streams'][0]['height']),
                    (expected_width, expected_height),
                )
                self.assertEqual(metadata['streams'][0]['nb_frames'], str(expected_frame_count))
                self.assertIn('mp4', metadata['format']['format_name'].split(','))

                job_response = self.client.get(f'/api/jobs/{job.id}/')
                self.assertEqual(job_response.status_code, 200)
                result_data = job_response.data['result']
                self.assertEqual(result_data['output_content_type'], 'video/mp4')
                self.assertEqual(result_data['output_size_bytes'], os.path.getsize(job.result.output_file.path))
                self.assertEqual(result_data['output_url'], f'http://testserver/api/jobs/{job.id}/result/')
        finally:
            cleanup_paths = stored_output_paths + service_output_paths
            if cleanup_source:
                cleanup_paths.append(source_path)
            for output_path in cleanup_paths:
                if os.path.isfile(output_path):
                    os.remove(output_path)
