from django.db import migrations


def seed_default_templates(apps, schema_editor):
    PipelineTemplate = apps.get_model('pipelines', 'PipelineTemplate')
    templates = [
        {
            'name': 'Grayscale',
            'category': 'Preprocessing',
            'description': 'Convert the input image to a single grayscale channel.',
            'graph_data': {
                'nodes': [
                    {'id': 'input', 'type': 'imageSource', 'position': {'x': 80, 'y': 180}, 'data': {}},
                    {'id': 'grayscale', 'type': 'grayscale', 'position': {'x': 310, 'y': 180}, 'data': {}},
                    {'id': 'output', 'type': 'output', 'position': {'x': 540, 'y': 180}, 'data': {}},
                ],
                'edges': [
                    {'id': 'edge-1', 'source': 'input', 'target': 'grayscale'},
                    {'id': 'edge-2', 'source': 'grayscale', 'target': 'output'},
                ],
            },
        },
        {
            'name': 'Edge Detection',
            'category': 'Edges',
            'description': 'Convert to grayscale, then extract edges with Canny.',
            'graph_data': {
                'nodes': [
                    {'id': 'input', 'type': 'imageSource', 'position': {'x': 80, 'y': 180}, 'data': {}},
                    {'id': 'grayscale', 'type': 'grayscale', 'position': {'x': 300, 'y': 180}, 'data': {}},
                    {'id': 'canny', 'type': 'canny', 'position': {'x': 520, 'y': 180}, 'data': {'threshold1': 75, 'threshold2': 200}},
                    {'id': 'output', 'type': 'output', 'position': {'x': 740, 'y': 180}, 'data': {}},
                ],
                'edges': [
                    {'id': 'edge-1', 'source': 'input', 'target': 'grayscale'},
                    {'id': 'edge-2', 'source': 'grayscale', 'target': 'canny'},
                    {'id': 'edge-3', 'source': 'canny', 'target': 'output'},
                ],
            },
        },
        {
            'name': 'Noise Removal',
            'category': 'Preprocessing',
            'description': 'Apply a Gaussian blur to reduce image noise before grayscale conversion.',
            'graph_data': {
                'nodes': [
                    {'id': 'input', 'type': 'imageSource', 'position': {'x': 80, 'y': 180}, 'data': {}},
                    {'id': 'denoise', 'type': 'blur', 'position': {'x': 300, 'y': 180}, 'data': {'strength': 5, 'blurType': 'gaussian'}},
                    {'id': 'grayscale', 'type': 'grayscale', 'position': {'x': 520, 'y': 180}, 'data': {}},
                    {'id': 'output', 'type': 'output', 'position': {'x': 740, 'y': 180}, 'data': {}},
                ],
                'edges': [
                    {'id': 'edge-1', 'source': 'input', 'target': 'denoise'},
                    {'id': 'edge-2', 'source': 'denoise', 'target': 'grayscale'},
                    {'id': 'edge-3', 'source': 'grayscale', 'target': 'output'},
                ],
            },
        },
        {
            'name': 'Contour Detection',
            'category': 'Analysis',
            'description': 'Create an edge map and draw detected contours.',
            'graph_data': {
                'nodes': [
                    {'id': 'input', 'type': 'imageSource', 'position': {'x': 80, 'y': 180}, 'data': {}},
                    {'id': 'grayscale', 'type': 'grayscale', 'position': {'x': 290, 'y': 180}, 'data': {}},
                    {'id': 'canny', 'type': 'canny', 'position': {'x': 500, 'y': 180}, 'data': {'threshold1': 75, 'threshold2': 200}},
                    {'id': 'contours', 'type': 'findContours', 'position': {'x': 710, 'y': 180}, 'data': {'fill': False}},
                    {'id': 'output', 'type': 'output', 'position': {'x': 920, 'y': 180}, 'data': {}},
                ],
                'edges': [
                    {'id': 'edge-1', 'source': 'input', 'target': 'grayscale'},
                    {'id': 'edge-2', 'source': 'grayscale', 'target': 'canny'},
                    {'id': 'edge-3', 'source': 'canny', 'target': 'contours'},
                    {'id': 'edge-4', 'source': 'contours', 'target': 'output'},
                ],
            },
        },
    ]
    for template in templates:
        PipelineTemplate.objects.get_or_create(
            name=template['name'],
            defaults={
                **template,
                'is_official': True,
                'created_by_id': None,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('pipelines', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_default_templates, migrations.RunPython.noop),
    ]
