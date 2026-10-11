import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from pathlib import Path
from fastapi.testclient import TestClient
from cv_service.main import app
from cv_service.processors.image_processor import execute_cv_pipeline
from cv_service.routes.pipeline import MEDIA_ROOT

class FastAPIMicroserviceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def create_media_file(self, suffix):
        MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
        return tempfile.NamedTemporaryFile(suffix=suffix, dir=MEDIA_ROOT, delete=False)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")

    def test_pipeline_execution_endpoint(self):
        with self.create_media_file(suffix=".png") as image_file:
            input_path = image_file.name
        cv2.imwrite(input_path, np.full((80, 120, 3), 128, dtype=np.uint8))
        payload = {
            "job_id": 999,
            "pipeline_id": 888,
            "input_file_path": input_path,
            "pipeline": {
                "nodes": [
                    {"id": "n1", "type": "imageSource", "data": {}},
                    {"id": "n2", "type": "grayscale", "data": {}},
                    {"id": "n3", "type": "canny", "data": {"threshold1": 50, "threshold2": 150}},
                    {"id": "n4", "type": "output", "data": {}},
                ],
                "edges": [
                    {"source": "n1", "target": "n2"},
                    {"source": "n2", "target": "n3"},
                    {"source": "n3", "target": "n4"},
                ]
            }
        }
        try:
            response = self.client.post("/pipeline/execute", json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual(data["status"], "success")
            self.assertIn("result_file_path", data)
            self.assertIn("metrics", data)
            self.assertTrue(os.path.exists(data["result_file_path"]))
            os.unlink(data["result_file_path"])
        finally:
            os.unlink(input_path)

    def test_pipeline_uses_connection_order_and_image_operations(self):
        with self.create_media_file(suffix='.png') as image_file:
            input_path = image_file.name
        try:
            cv2.imwrite(input_path, np.full((80, 120, 3), 128, dtype=np.uint8))
            payload = {
                "job_id": 1000,
                "pipeline_id": 889,
                "input_file_path": input_path,
                "pipeline": {
                    "nodes": [
                        {"id": "stats", "type": "imageStatistics", "data": {}},
                        {"id": "resize", "type": "resize", "data": {"width": 64, "height": 32}},
                        {"id": "gray", "type": "grayscale", "data": {}},
                        {"id": "source", "type": "imageSource", "data": {}},
                        {"id": "output", "type": "output", "data": {}}
                    ],
                    "edges": [
                        {"source": "source", "target": "gray"},
                        {"source": "gray", "target": "resize"},
                        {"source": "resize", "target": "stats"},
                        {"source": "stats", "target": "output"}
                    ]
                }
            }
            response = self.client.post("/pipeline/execute", json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            self.assertEqual(data["metrics"]["width"], 64)
            self.assertEqual(data["metrics"]["height"], 32)
            self.assertEqual(data["objects_detected"][0]["type"], "image_statistics")
            log_text = "\n".join(data["logs"])
            self.assertLess(log_text.index("Node 'source'"), log_text.index("Node 'gray'"))
            self.assertLess(log_text.index("Node 'gray'"), log_text.index("Node 'resize'"))
            os.unlink(data["result_file_path"])
        finally:
            os.unlink(input_path)

    def test_video_is_processed_incrementally_and_keeps_dimensions_and_fps(self):
        if not shutil.which('ffmpeg'):
            self.skipTest('FFmpeg is required to encode browser-compatible H.264 MP4 output.')
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, 'source.mp4')
            output_path = os.path.join(temp_dir, 'processed.mp4')
            writer = cv2.VideoWriter(
                input_path, cv2.VideoWriter_fourcc(*'mp4v'), 12.0, (64, 48)
            )
            if not writer.isOpened():
                self.skipTest('The installed OpenCV build cannot encode the mp4v test fixture.')
            for index in range(8):
                writer.write(np.full((48, 64, 3), index * 20, dtype=np.uint8))
            writer.release()
            graph = {
                'nodes': [
                    {'id': 'source', 'type': 'imageSource', 'data': {}},
                    {'id': 'gray', 'type': 'grayscale', 'data': {}},
                    {'id': 'edges', 'type': 'canny', 'data': {'threshold1': 20, 'threshold2': 90}},
                    {'id': 'output', 'type': 'output', 'data': {}},
                ],
                'edges': [
                    {'source': 'source', 'target': 'gray'},
                    {'source': 'gray', 'target': 'edges'},
                    {'source': 'edges', 'target': 'output'},
                ],
            }
            result = execute_cv_pipeline(graph, input_path, temp_dir)
            os.replace(result['result_file_path'], output_path)
            self.assertEqual(result['metrics']['frame_count'], 8)
            self.assertEqual(result['metrics']['width'], 64)
            self.assertEqual(result['metrics']['height'], 48)
            self.assertAlmostEqual(result['metrics']['fps'], 12.0, delta=1.0)
            capture = cv2.VideoCapture(output_path)
            ok, frame = capture.read()
            self.assertTrue(ok)
            self.assertEqual(frame.shape[:2], (48, 64))
            capture.release()

    def test_video_without_ffmpeg_fails_with_install_instructions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, 'source.mp4')
            writer = cv2.VideoWriter(
                input_path, cv2.VideoWriter_fourcc(*'mp4v'), 12.0, (64, 48)
            )
            if not writer.isOpened():
                self.skipTest('The installed OpenCV build cannot encode the mp4v test fixture.')
            for index in range(2):
                writer.write(np.full((48, 64, 3), index * 20, dtype=np.uint8))
            writer.release()
            graph = {
                'nodes': [
                    {'id': 'source', 'type': 'imageSource', 'data': {}},
                    {'id': 'output', 'type': 'output', 'data': {}},
                ],
                'edges': [{'source': 'source', 'target': 'output'}],
            }
            with patch('cv_service.processors.image_processor.shutil.which', return_value=None):
                with self.assertRaisesRegex(ValueError, 'FFmpeg is required.*add ffmpeg.exe to PATH'):
                    execute_cv_pipeline(graph, input_path, temp_dir)

    def test_execution_rejects_missing_input_invalid_parameters_cycles_and_unknown_nodes(self):
        base_nodes = [
            {'id': 'source', 'type': 'imageSource', 'data': {}},
            {'id': 'output', 'type': 'output', 'data': {}},
        ]
        missing = self.client.post('/pipeline/execute', json={
            'job_id': 1, 'pipeline_id': 1,
            'pipeline': {'nodes': base_nodes, 'edges': [{'source': 'source', 'target': 'output'}]},
        })
        self.assertEqual(missing.status_code, 400)

        with self.create_media_file(suffix='.png') as image_file:
            path = image_file.name
        cv2.imwrite(path, np.zeros((32, 32, 3), dtype=np.uint8))
        try:
            bad_graphs = [
                {
                    'nodes': base_nodes + [{'id': 'bad', 'type': 'python', 'data': {}}],
                    'edges': [{'source': 'source', 'target': 'bad'}, {'source': 'bad', 'target': 'output'}],
                },
                {
                    'nodes': [
                        base_nodes[0],
                        {'id': 'edges', 'type': 'canny', 'data': {'threshold1': -1, 'threshold2': 20}},
                        base_nodes[1],
                    ],
                    'edges': [
                        {'source': 'source', 'target': 'edges'},
                        {'source': 'edges', 'target': 'output'},
                    ],
                },
                {
                    'nodes': base_nodes,
                    'edges': [{'source': 'source', 'target': 'output'}, {'source': 'output', 'target': 'source'}],
                },
            ]
            for graph in bad_graphs:
                response = self.client.post('/pipeline/execute', json={
                    'job_id': 1, 'pipeline_id': 1, 'input_file_path': path, 'pipeline': graph,
                })
                self.assertEqual(response.status_code, 400, response.text)
        finally:
            os.unlink(path)

    def test_cv_service_rejects_paths_outside_media_root(self):
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as image_file:
            outside_path = image_file.name
        response = self.client.post('/pipeline/execute', json={
            'job_id': 1,
            'pipeline_id': 1,
            'input_file_path': outside_path,
            'pipeline': {
                'nodes': [
                    {'id': 'source', 'type': 'imageSource', 'data': {}},
                    {'id': 'output', 'type': 'output', 'data': {}},
                ],
                'edges': [{'source': 'source', 'target': 'output'}],
            },
        })
        self.assertEqual(response.status_code, 400)
        os.unlink(outside_path)

    def test_other_image_routes_reject_paths_outside_media_root(self):
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as image_file:
            outside_path = image_file.name
        try:
            cv2.imwrite(outside_path, np.full((16, 16, 3), 32, dtype=np.uint8))
            self.assertEqual(self.client.post('/analyze/image', json={'image_path': outside_path}).status_code, 400)
            self.assertEqual(self.client.post('/compare/images', json={'image_a_path': outside_path, 'image_b_path': outside_path}).status_code, 400)
            self.assertEqual(self.client.post('/detect/objects', json={'image_path': outside_path}).status_code, 400)
        finally:
            os.unlink(outside_path)

    def test_corrupt_video_returns_a_meaningful_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, 'corrupt.mp4')
            Path(path).write_bytes(b'not a video')
            graph = {
                'nodes': [
                    {'id': 'source', 'type': 'imageSource', 'data': {}},
                    {'id': 'output', 'type': 'output', 'data': {}},
                ],
                'edges': [{'source': 'source', 'target': 'output'}],
            }
            with self.assertRaisesRegex(ValueError, 'corrupt|unsupported codec'):
                execute_cv_pipeline(graph, path, temp_dir)
