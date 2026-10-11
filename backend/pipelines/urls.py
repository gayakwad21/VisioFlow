from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PipelineViewSet, PipelineTemplateViewSet, generate_ai_pipeline

router = DefaultRouter()
router.register(r'pipelines', PipelineViewSet, basename='pipeline')
router.register(r'templates', PipelineTemplateViewSet, basename='template')

urlpatterns = [
    path('pipelines/generate-ai/', generate_ai_pipeline, name='generate_ai_pipeline'),
    path('', include(router.urls)),
]
